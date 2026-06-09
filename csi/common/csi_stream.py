"""rx 보드 시리얼에서 CSI_DATA 를 읽어 진폭+위상 dict 로 스트림(web/GUI 공용).

csi/web/app.py 의 _stream_csi 를 공용으로 추출하고 '위상'을 추가했다. numpy 없이
math 로 계산(서버 의존 최소화). on_packet 콜백으로 ~10Hz throttle 해 전달한다.

통합 csi_recv 펌웨어는 tx(ESP-NOW)와 라우터(AP) CSI 를 둘 다 출력하므로, mac 으로
신호원(source: "tx" / "router")을 구분해 emit 한다. 또한 send_q 로 호스트→보드 명령
('WIFI_CONNECT <ssid>\\t<pw>')을 같은 시리얼로 보낸다(라우터 자격증명 런타임 주입).
"""
from __future__ import annotations

import math
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

try:
    import serial  # pyserial
except ImportError:  # pragma: no cover
    serial = None  # type: ignore[assignment]

# csi/analysis 의 파서 재사용.
_ANALYSIS = Path(__file__).resolve().parents[1] / "analysis"
if str(_ANALYSIS) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS))
from csi_parser import parse_line  # noqa: E402

CSI_BAUD = 921600  # csi_recv 콘솔 보드레이트
TX_MAC = "1a:00:00:00:00:00"  # csi_send(tx) 고정 MAC — 이 mac 이면 신호원=tx


def amp_phase(raw_csi: list[int]) -> tuple[list[float], list[float]]:
    """(i, q) 쌍 배열 → (진폭, 위상). numpy 없이 계산."""
    amp: list[float] = []
    ph: list[float] = []
    for k in range(0, len(raw_csi) - 1, 2):
        i = raw_csi[k]
        q = raw_csi[k + 1]
        amp.append(math.hypot(i, q))      # 반올림 없이 전체 float
        ph.append(math.atan2(q, i))
    return amp, ph


def wifi_connect_cmd(ssid: str, pw: str) -> str:
    """'WIFI_CONNECT <ssid>\\t<pw>' 한 줄을 만든다(펌웨어 handle_command 규약)."""
    return f"WIFI_CONNECT {ssid}\t{pw}"


def stream_csi(
    port: str,
    stop_ev: threading.Event,
    on_packet: Callable[[dict[str, object]], None],
    baud: int = CSI_BAUD,
    send_q: Optional["queue.Queue[str]"] = None,
) -> str | None:
    """시리얼에서 CSI_DATA 를 읽어 신호원별 ~10Hz 로 on_packet(dict) 호출.

    dict: {"type":"csi","source":"tx"|"router","mac":str,"rssi":int,"n_sub":int,
           "rate":float,"amplitude":[...],"phase":[...]}
    send_q 에 문자열이 들어오면 그 줄을 보드로 write 한다(WIFI_CONNECT 등).
    반환: 오류 메시지(또는 None).
    """
    if serial is None:
        return "pyserial 미설치"
    try:
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = baud
        ser.timeout = 1.0
        try:
            ser.dtr = False
            ser.rts = False
        except Exception:
            pass
        ser.open()
    except Exception as exc:  # 권한/포트 문제로 서버가 죽지 않게.
        return f"포트 열기 실패: {exc}"

    header: list[str] | None = None
    win_start = time.monotonic()
    win_count = 0
    # 신호원별 throttle(tx 와 router 가 섞여 들어와도 각각 ~10Hz 유지).
    last_emit = {"tx": 0.0, "router": 0.0}
    rate = 0.0
    try:
        while not stop_ev.is_set():
            # 호스트 → 보드 명령 전송(WIFI_CONNECT 등)을 같은 시리얼로.
            if send_q is not None:
                try:
                    while True:
                        cmd = send_q.get_nowait()
                        ser.write((cmd + "\n").encode("utf-8"))
                except queue.Empty:
                    pass

            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue
            if line.startswith("type,"):
                header = line.split(",")
                continue
            pkt = parse_line(line, header)
            if pkt is None:
                continue

            win_count += 1
            now = time.monotonic()
            elapsed = now - win_start
            if elapsed >= 1.0:
                rate = win_count / elapsed
                win_start = now
                win_count = 0

            src = "tx" if pkt.mac.lower() == TX_MAC else "router"
            if now - last_emit[src] >= 0.1:  # 신호원별 ~10Hz throttle
                last_emit[src] = now
                amp, ph = amp_phase(pkt.raw_csi)
                on_packet(
                    {
                        "type": "csi",
                        "source": src,
                        "mac": pkt.mac,
                        "rssi": pkt.rssi,
                        "n_sub": len(amp),
                        "rate": rate,
                        "amplitude": amp,
                        "phase": ph,
                        "raw_csi": pkt.raw_csi,   # i/q 원본(딥러닝 raw)
                    }
                )
    finally:
        try:
            ser.close()
        except Exception:
            pass
    return None


if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
    ev = threading.Event()

    def _show(p: dict[str, object]) -> None:
        amp = p["amplitude"]  # type: ignore[index]
        print(f"[{p['source']}] rate={p['rate']} rssi={p['rssi']} n_sub={p['n_sub']} amp[:3]={amp[:3]}")

    print("CSI 스트림 시작 (Ctrl+C 중지)...")
    try:
        err = stream_csi(port, ev, _show)
        if err:
            print("오류:", err)
    except KeyboardInterrupt:
        ev.set()
