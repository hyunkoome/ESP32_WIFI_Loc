#!/usr/bin/env python3
"""config_devices.yaml 의 CSI 디바이스 매핑을 읽어 by-id 로 실제 시리얼 포트를 찾는다.

여러 대의 ESP32-S3 를 tx(송신) / rx(수신) 역할로 나눠 쓴다. `/dev/ttyACM*` 번호는
부팅·연결 순서에 따라 바뀌므로 신뢰할 수 없다. 대신 USB-Serial 칩의 **고유 serial**
(`/dev/serial/by-id/...<serial>-if00`)로 보드를 고정 식별한다. 같은 보드는 어느 USB
포트에 꽂아도 serial 이 동일하다.

디바이스 매핑은 자격증명이 아닌 하드웨어 인벤토리이므로, WiFi 자격증명이 든
config.yaml 과 분리해 별도 파일 config_devices.yaml 로 관리한다.

config_devices.yaml 예시:
    devices:
      - role: rx          # rx → csi_recv 펌웨어
        serial: "5C4C092284"
        name: "rx1"       # 사람이 식별하기 위한 별칭(선택)
      - role: tx          # tx → csi_send 펌웨어
        serial: "5B5E076216"
        name: "tx1"

확장: tx/rx 를 여러 개 둘 수 있다(같은 role 을 반복). 개수 제한 없음.

CLI 사용:
    python device_map.py            # 사람이 읽는 표
    python device_map.py --shell    # 셸 파싱용: "role<TAB>port<TAB>name<TAB>serial"
    python device_map.py --role rx  # 특정 role 만
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

# 이 파일: <repo>/csi/collect/device_map.py
#   parents[1] == <repo>/csi,  parents[2] == <repo>
CSI_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# CSI 디바이스 매핑은 csi 전용 설정이므로 csi/ 안에 둔다.
DEVICE_YAML = CSI_DIR / "config_devices.yaml"
BY_ID_DIR = Path("/dev/serial/by-id")

# role → 펌웨어 프로젝트 디렉터리명(csi/firmware/ 하위).
ROLE_FIRMWARE = {
    "tx": "csi_send",
    "rx": "csi_recv",
}


@dataclass
class CsiDevice:
    """config_devices.yaml 의 디바이스 한 개 + 해석된 포트."""

    role: str
    serial: str
    name: str
    # by-id 로 해석된 실제 포트(/dev/ttyACMx). 찾지 못하면 None(미연결).
    port: str | None

    @property
    def firmware(self) -> str | None:
        """이 role 에 대응하는 펌웨어 디렉터리명."""
        return ROLE_FIRMWARE.get(self.role)

    @property
    def firmware_path(self) -> Path | None:
        fw = self.firmware
        return PROJECT_ROOT / "csi" / "firmware" / fw if fw else None


def resolve_port(serial: str) -> str | None:
    """USB serial 문자열로 /dev/serial/by-id 항목을 찾아 실제 포트로 해석한다."""
    if not BY_ID_DIR.is_dir():
        return None
    # serial 을 포함하는 by-id 심볼릭 링크를 찾는다(보통 ...-<serial>-if00).
    matches = sorted(p for p in BY_ID_DIR.iterdir() if serial in p.name)
    if not matches:
        return None
    # 여러 개(if00/if02 등) 매칭되면 첫 번째를 쓴다.
    return str(matches[0].resolve())


def load_devices() -> list[CsiDevice]:
    """config_devices.yaml 의 devices 를 읽어 포트까지 해석한 목록을 반환한다."""
    if yaml is None:
        sys.exit("PyYAML 이 필요합니다:  pip install -r requirements.txt")
    if not DEVICE_YAML.exists():
        sys.exit(
            f"config_devices.yaml 이 없습니다: {DEVICE_YAML}\n"
            f"  config_devices.yaml.example 을 복사해 만드세요:\n"
            f"    cp config_devices.yaml.example config_devices.yaml"
        )

    with DEVICE_YAML.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}

    raw_devices = cfg.get("devices") or []

    devices: list[CsiDevice] = []
    for idx, entry in enumerate(raw_devices):
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role", "")).strip().lower()
        serial = str(entry.get("serial", "")).strip()
        name = str(entry.get("name") or f"{role or 'dev'}{idx}")
        if not role or not serial:
            print(f"[device_map] 경고: role/serial 누락 항목 건너뜀: {entry}", file=sys.stderr)
            continue
        if role not in ROLE_FIRMWARE:
            print(
                f"[device_map] 경고: 알 수 없는 role '{role}' (지원: {list(ROLE_FIRMWARE)})",
                file=sys.stderr,
            )
        devices.append(
            CsiDevice(role=role, serial=serial, name=name, port=resolve_port(serial))
        )
    return devices


def _print_table(devices: list[CsiDevice]) -> None:
    if not devices:
        print("(config_devices.yaml 의 devices 가 비어 있습니다)")
        return
    print(f"{'name':<8} {'role':<5} {'serial':<14} {'port':<14} firmware")
    print("-" * 60)
    for d in devices:
        port = d.port or "(미연결)"
        fw = d.firmware or "(알수없음)"
        print(f"{d.name:<8} {d.role:<5} {d.serial:<14} {port:<14} {fw}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="CSI 디바이스(by-id) 매핑 조회")
    p.add_argument("--shell", action="store_true", help="셸 파싱용 TSV 출력")
    p.add_argument("--role", choices=sorted(ROLE_FIRMWARE), help="해당 role 만 출력")
    p.add_argument(
        "--connected-only",
        action="store_true",
        help="포트가 해석된(연결된) 디바이스만 출력",
    )
    args = p.parse_args(argv)

    devices = load_devices()
    if args.role:
        devices = [d for d in devices if d.role == args.role]
    if args.connected_only:
        devices = [d for d in devices if d.port]

    if args.shell:
        # role<TAB>port<TAB>name<TAB>serial  (포트 없으면 그 줄은 생략)
        for d in devices:
            if d.port:
                print(f"{d.role}\t{d.port}\t{d.name}\t{d.serial}")
    else:
        _print_table(devices)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
