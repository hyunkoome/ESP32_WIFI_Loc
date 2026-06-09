"""두 rx 동시 측정(tx 신호원 + 라우터 신호원) + 진폭변동/도플러 — 움직임 감지 디버깅.

사용: python3 csi/debug_dualrx.py <duration> <label>
  - ttyACM1 = tx 신호원(ESP-NOW, 채널11), ttyACM2 = 라우터 신호원(STA, WIFI_CONNECT 됨).
  - 진폭변동 std(서브캐리어별 시간 표준편차 평균): 움직임이 클수록 커진다.
  - 도플러피크: 진폭 시간변화의 FFT 최대(0.3~8Hz). 움직임 주파수.
가만히 vs 움직임에서 두 지표를 비교하면 어느 신호원이 움직임을 잡는지 알 수 있다.
"""
from __future__ import annotations
import sys, time, math, threading
import numpy as np
import serial
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "analysis"))
from csi_parser import parse_line

PORTS = {"tx(ACM1)": ("/dev/ttyACM1", "tx"), "router(ACM2)": ("/dev/ttyACM2", "router")}
TX_MAC = "1a:00:00:00:00:00"


def stream(name, port, source, duration, out, wifi=None):
    try:
        ser = serial.Serial(port, 921600, timeout=1)
        ser.dtr = False; ser.rts = False
    except Exception as e:
        out[name] = ("err", str(e)); return
    time.sleep(0.5); ser.reset_input_buffer()
    # 라우터 신호원은 재open 시 연결이 풀릴 수 있어 매번 WIFI_CONNECT 후 연결 대기.
    if source == "router" and wifi and wifi[0]:
        ser.write(f"WIFI_CONNECT {wifi[0]}\t{wifi[1]}\n".encode())
        c0 = time.time()
        while time.time() - c0 < 10:
            raw = ser.readline()
            if raw and b'connected":true' in raw:
                break
        ser.reset_input_buffer()
    header = None; rows = []; t0 = time.time()
    while time.time() - t0 < duration:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode(errors="replace").strip()
        if line.startswith("type,"):
            header = line.split(","); continue
        if not line.startswith("CSI_DATA"):
            continue
        is_tx = TX_MAC in line
        if (source == "tx") != is_tx:
            continue
        pkt = parse_line(line, header)
        if pkt is None:
            continue
        amp = [math.hypot(pkt.raw_csi[k], pkt.raw_csi[k + 1])
               for k in range(0, len(pkt.raw_csi) - 1, 2)]
        rows.append((time.time() - t0, amp, pkt.rssi))
    ser.close()
    out[name] = ("ok", rows)


def analyze(name, status, data):
    if status == "err":
        print(f"  [{name}] 오류: {data}"); return
    rows = data
    if len(rows) < 10:
        print(f"  [{name}] CSI 부족({len(rows)}개) — 신호 없음/약함"); return
    amps = np.array([r[1] for r in rows], dtype=float)
    rssi = float(np.mean([r[2] for r in rows]))
    dur = rows[-1][0] or 1
    rate = len(rows) / dur
    a = amps - amps.mean(axis=0, keepdims=True)
    n = a.shape[0]
    spec = np.abs(np.fft.rfft(a * np.hanning(n)[:, None], axis=0)).mean(axis=1)
    freqs = np.fft.rfftfreq(n, 1.0 / max(rate, 1))
    m = (freqs > 0.3) & (freqs <= 8)
    peak = float(spec[m].max()) if m.any() else 0.0
    fpk = float(freqs[m][spec[m].argmax()]) if m.any() else 0.0
    print(f"  [{name}] pkt={len(rows)} rate={rate:.0f}Hz rssi={rssi:.0f} sub={amps.shape[1]} "
          f"진폭={amps.mean():.1f} 변동std={amps.std(axis=0).mean():.2f} "
          f"도플러피크={peak:.1f}@{fpk:.1f}Hz")


if __name__ == "__main__":
    import yaml
    DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 12
    LABEL = sys.argv[2] if len(sys.argv) > 2 else "측정"
    cfg = yaml.safe_load(open("config/wifi_config.yaml")) or {}
    w = cfg.get("wifi") or {}
    wifi = (str(w.get("ssid") or ""), str(w.get("password") or ""))
    out = {}
    ts = [threading.Thread(target=stream, args=(n, p, s, DUR, out),
                           kwargs={"wifi": wifi} if s == "router" else {})
          for n, (p, s) in PORTS.items()]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(f"=== {LABEL} ({DUR:.0f}초) ===")
    for name in PORTS:
        st, dt = out.get(name, ("err", "측정 안 됨"))
        analyze(name, st, dt)
