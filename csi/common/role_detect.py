"""시리얼을 열어 펌웨어의 DEVICE_ROLE 식별자를 읽어 보드 role(tx/rx)을 감지.

펌웨어(csi_send/csi_recv)는 부팅 시 + 주기적으로 한 줄을 출력한다:
    DEVICE_ROLE {"role":"tx","fw":"csi_send","ver":1}
    DEVICE_ROLE {"role":"rx","fw":"csi_recv","ver":1}

rx 는 921600 에서 CSI_DATA 가 초당 수십 줄 쏟아지므로, readline() 으로 한 줄씩
처리하면 폭주에 밀려 감지 윈도우 안에 못 끝나는(hang 처럼 보이는) 문제가 있다.
그래서 **read(블록) + 직접 라인 분리 + 버퍼 상한 + 엄격한 deadline** 으로 처리한다.
보드레이트가 달라(rx=921600, tx=115200) 둘 다 시도하되, 데이터가 많은 921600 을
먼저 본다(rx 가 빨리 잡힘). dtr/rts=False 로 이미 도는 펌웨어를 리셋하지 않는다.
"""
from __future__ import annotations

import json
import time

try:
    import serial  # pyserial
except ImportError:  # pragma: no cover
    serial = None  # type: ignore[assignment]

ROLE_PREFIX = "DEVICE_ROLE"
CSI_PREFIX = "CSI_DATA"
BAUDS = (921600, 115200)  # rx(데이터 많음) 먼저, 그 다음 tx
_MAX_BUF = 16384          # 라인 버퍼 상한(폭주 시 잘라 메모리/CPU 폭주 방지)


def _scan_line(s: str) -> tuple[str | None, str] | None:
    """한 줄에서 role 을 판별. (role, source) 또는 None."""
    if s.startswith(ROLE_PREFIX):
        payload = s.partition(" ")[2]
        try:
            role = str(json.loads(payload).get("role"))
            if role in ("tx", "rx"):
                return role, "firmware"
        except Exception:
            return None
    if s.startswith(CSI_PREFIX) or s.startswith("type,"):
        return "rx", "csi_stream"
    return None


def detect_role(port: str, timeout: float = 4.0) -> tuple[str | None, str]:
    """포트의 보드 role 을 감지.

    반환: (role, source)
      role   = "tx" | "rx" | None
      source = "firmware" | "csi_stream" | "unknown"
    """
    if serial is None:
        return None, "unknown"

    per = max(1.2, timeout / len(BAUDS))
    for baud in BAUDS:
        ser = None
        try:
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = baud
            ser.timeout = 0.2
            try:
                ser.dtr = False
                ser.rts = False
            except Exception:
                pass
            ser.open()
            try:
                ser.reset_input_buffer()  # 이미 쌓인 폭주 데이터 버리고 시작
            except Exception:
                pass

            deadline = time.monotonic() + per
            buf = b""
            while time.monotonic() < deadline:
                chunk = ser.read(1024)  # 0.2s timeout, 최대 1KB
                if not chunk:
                    continue
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode("utf-8", errors="replace").strip()
                    hit = _scan_line(line)
                    if hit is not None:
                        return hit
                if len(buf) > _MAX_BUF:  # 폭주/깨진 스트림 방지
                    buf = buf[-2048:]
        except Exception:
            pass
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass
    return None, "unknown"


if __name__ == "__main__":
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
    t0 = time.monotonic()
    role, src = detect_role(port)
    print(f"{port}: role={role} (source={src})  [{time.monotonic() - t0:.2f}s]")
