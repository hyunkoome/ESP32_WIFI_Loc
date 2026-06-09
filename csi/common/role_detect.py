"""시리얼을 열어 펌웨어의 DEVICE_ROLE 식별자를 읽어 보드 role(tx/rx)을 감지.

펌웨어(csi_send/csi_recv)는 부팅 시 + 주기적으로 한 줄을 출력한다:
    DEVICE_ROLE {"role":"tx","fw":"csi_send","ver":1}
    DEVICE_ROLE {"role":"rx","fw":"csi_recv","ver":1}

보드레이트가 달라서(tx=115200 기본, rx=921600) 둘 다 시도한다. rx 는 DEVICE_ROLE 을
놓쳐도 CSI_DATA 스트림으로 추정 가능. 포트를 열 때 dtr/rts=False 로 두어 이미 도는
펌웨어를 리셋하지 않는다(board_check firmware.py 패턴).
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
BAUDS = (115200, 921600)  # tx(기본) / rx(콘솔)


def detect_role(port: str, timeout: float = 4.0) -> tuple[str | None, str]:
    """포트의 보드 role 을 감지.

    반환: (role, source)
      role   = "tx" | "rx" | None
      source = "firmware" | "csi_stream" | "unknown"
    """
    if serial is None:
        return None, "unknown"

    per = max(1.0, timeout / len(BAUDS))
    for baud in BAUDS:
        ser = None
        try:
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = baud
            ser.timeout = 0.5
            try:
                ser.dtr = False
                ser.rts = False
            except Exception:
                pass
            ser.open()
            deadline = time.monotonic() + per
            while time.monotonic() < deadline:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line.startswith(ROLE_PREFIX):
                    payload = line.partition(" ")[2]
                    try:
                        role = str(json.loads(payload).get("role"))
                        if role in ("tx", "rx"):
                            return role, "firmware"
                    except Exception:
                        continue
                # CSI 스트림(헤더/데이터)이 보이면 rx 로 추정.
                if line.startswith(CSI_PREFIX) or line.startswith("type,"):
                    return "rx", "csi_stream"
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
    role, src = detect_role(port)
    print(f"{port}: role={role} (source={src})")
