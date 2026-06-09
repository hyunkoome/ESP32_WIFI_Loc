"""rx 보드 시리얼에서 CSI_DATA 를 읽어 진폭+위상 dict 로 스트림(web/GUI 공용).

csi/web/app.py 의 _stream_csi 를 공용으로 추출하고 '위상'을 추가했다. numpy 없이
math 로 계산(서버 의존 최소화). on_packet 콜백으로 ~10Hz throttle 해 전달한다.
"""
from __future__ import annotations

import math
import sys
import threading
import time
from pathlib import Path
from typing import Callable

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


def amp_phase(raw_csi: list[int]) -> tuple[list[float], list[float]]:
    """(i, q) 쌍 배열 → (진폭, 위상). numpy 없이 계산."""
    amp: list[float] = []
    ph: list[float] = []
    for k in range(0, len(raw_csi) - 1, 2):
        i = raw_csi[k]
        q = raw_csi[k + 1]
        amp.append(round(math.hypot(i, q), 2))
        ph.append(round(math.atan2(q, i), 3))
    return amp, ph


def stream_csi(
    port: str,
    stop_ev: threading.Event,
    on_packet: Callable[[dict[str, object]], None],
    baud: int = CSI_BAUD,
) -> str | None:
    """시리얼에서 CSI_DATA 를 읽어 ~10Hz 로 on_packet(dict) 호출.

    dict: {"type":"csi","rssi":int,"n_sub":int,"rate":float,
           "amplitude":[...],"phase":[...]}
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
    last_emit = 0.0
    rate = 0.0
    try:
        while not stop_ev.is_set():
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

            if now - last_emit >= 0.1:  # ~10Hz throttle
                last_emit = now
                amp, ph = amp_phase(pkt.raw_csi)
                on_packet(
                    {
                        "type": "csi",
                        "rssi": pkt.rssi,
                        "n_sub": len(amp),
                        "rate": round(rate, 1),
                        "amplitude": amp,
                        "phase": ph,
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
        print(f"rate={p['rate']} rssi={p['rssi']} n_sub={p['n_sub']} amp[:3]={amp[:3]}")

    print("CSI 스트림 시작 (Ctrl+C 중지)...")
    try:
        err = stream_csi(port, ev, _show)
        if err:
            print("오류:", err)
    except KeyboardInterrupt:
        ev.set()
