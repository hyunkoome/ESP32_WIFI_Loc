"""연결된 ESP32 보드 실시간 감지 (board_check usb_detector 재사용) + by-id + role.

config_devices.yaml 을 쓰지 않고, 매번 실시간으로 연결 보드를 감지한다. 보드 고정
식별은 USB serial / by-id 로 한다. role(tx/rx)은 role_detect.detect_role 로 별도
채운다(포트를 열어야 하므로 느림 — 호스트가 백그라운드로 호출).
"""
from __future__ import annotations

import glob
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# tools/board_check 의 usb_detector 를 재사용(csi/web/app.py 의 sys.path 패턴과 동일).
_BC = Path(__file__).resolve().parents[2] / "tools" / "board_check"
if str(_BC) not in sys.path:
    sys.path.insert(0, str(_BC))
import usb_detector  # noqa: E402


@dataclass
class BoardInfo:
    """감지된 보드 한 개."""

    port: str
    serial: str | None          # USB 시리얼(고정 식별자)
    by_id: str | None           # /dev/serial/by-id/... 경로
    vid_pid: str
    is_espressif: bool
    accessible: bool
    detected_role: str | None = None   # "tx" | "rx" | None
    role_source: str = "unknown"       # "firmware" | "csi_stream" | "unknown"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def by_id_for_serial(serial: str | None) -> str | None:
    """USB serial 이 포함된 /dev/serial/by-id 심볼릭 링크를 찾아 반환."""
    if not serial:
        return None
    for link in glob.glob("/dev/serial/by-id/*"):
        if serial in os.path.basename(link):
            return link
    return None


def discover() -> list[BoardInfo]:
    """연결된 보드 목록(USB 정보만, 빠름). role 은 호출자가 role_detect 로 채운다."""
    out: list[BoardInfo] = []
    for b in usb_detector.discover_boards():
        serial = b.get("serial")
        out.append(
            BoardInfo(
                port=str(b.get("port")),
                serial=str(serial) if serial else None,
                by_id=by_id_for_serial(str(serial) if serial else None),
                vid_pid=str(b.get("vid_pid")),
                is_espressif=bool(b.get("is_espressif")),
                accessible=bool(b.get("accessible")),
            )
        )
    return out


if __name__ == "__main__":
    found = discover()
    if not found:
        print("연결된 보드 없음 (/dev/ttyACM*, /dev/ttyUSB*).")
    for b in found:
        print(
            f"{b.port}  serial={b.serial}  {b.vid_pid}  "
            f"espressif={b.is_espressif}  accessible={b.accessible}"
        )
        if b.by_id:
            print(f"    by-id: {b.by_id}")
