"""
usb_detector.py
===============
연결된 ESP32-S3 보드를 자동으로 탐색하고 USB 식별 정보를 수집하는 모듈.

동작 순서:
  1) /dev/ttyACM*, /dev/ttyUSB* 패턴으로 시리얼 포트를 찾는다.
  2) 각 포트의 USB VID/PID/시리얼번호/제조사 정보를 조회한다.
     - pyudev가 있으면 우선 사용.
     - 없으면 /sys 파일시스템(sysfs)을 직접 읽어 폴백한다.
  3) Espressif VID(303a) 여부를 판정해 ESP32 보드인지 추정한다.

pyudev가 설치돼 있지 않아도 sysfs 폴백 덕분에 동작합니다.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Dict, List, Optional

import config

try:
    import pyudev  # type: ignore
except Exception:  # pragma: no cover - pyudev 미설치 환경 폴백
    pyudev = None


def detect_serial_ports() -> List[str]:
    """설정된 glob 패턴으로 시리얼 포트 목록을 찾아 정렬 반환."""
    ports: List[str] = []
    for pattern in config.SERIAL_PORT_GLOBS:
        ports.extend(glob.glob(pattern))
    # 중복 제거 후 정렬(예: ttyACM0, ttyACM1, ...)
    return sorted(set(ports))


def _usb_info_via_pyudev(port: str) -> Optional[Dict[str, Optional[str]]]:
    """pyudev로 포트의 USB 정보를 조회. 실패 시 None."""
    if not pyudev:
        return None
    try:
        context = pyudev.Context()
        device = pyudev.Devices.from_device_file(context, port)
        return {
            "vid": (device.get("ID_VENDOR_ID") or "").lower() or None,
            "pid": (device.get("ID_MODEL_ID") or device.get("ID_PRODUCT_ID") or "").lower()
            or None,
            "serial": device.get("ID_SERIAL_SHORT") or device.get("ID_SERIAL"),
            "vendor": device.get("ID_VENDOR") or device.get("ID_VENDOR_FROM_DATABASE"),
            "model": device.get("ID_MODEL") or device.get("ID_MODEL_FROM_DATABASE"),
        }
    except Exception:
        return None


def _read_sysfs(path: Path) -> Optional[str]:
    """sysfs 속성 파일을 안전하게 읽어 문자열로 반환(없으면 None)."""
    try:
        return path.read_text().strip()
    except Exception:
        return None


def _usb_info_via_sysfs(port: str) -> Dict[str, Optional[str]]:
    """
    pyudev 없이 /sys를 직접 읽어 USB 정보를 조회하는 폴백.

    /sys/class/tty/ttyACM0/device 에서 USB 디바이스 디렉터리를 거슬러 올라가며
    idVendor / idProduct / serial / manufacturer / product 파일을 찾는다.
    """
    info: Dict[str, Optional[str]] = {
        "vid": None,
        "pid": None,
        "serial": None,
        "vendor": None,
        "model": None,
    }
    name = os.path.basename(port)
    dev_link = Path("/sys/class/tty") / name / "device"
    try:
        # 심볼릭 링크를 실제 경로로 변환.
        node = dev_link.resolve()
    except Exception:
        return info

    # idVendor 파일이 나올 때까지 부모 디렉터리로 최대 8단계 거슬러 올라간다.
    for _ in range(8):
        if (node / "idVendor").exists():
            info["vid"] = (_read_sysfs(node / "idVendor") or "").lower() or None
            info["pid"] = (_read_sysfs(node / "idProduct") or "").lower() or None
            info["serial"] = _read_sysfs(node / "serial")
            info["vendor"] = _read_sysfs(node / "manufacturer")
            info["model"] = _read_sysfs(node / "product")
            break
        if node.parent == node:  # 루트 도달
            break
        node = node.parent
    return info


def get_usb_info(port: str) -> Dict[str, Optional[str]]:
    """포트 하나의 USB 정보를 조회(pyudev 우선, 실패 시 sysfs)."""
    info = _usb_info_via_pyudev(port)
    if not info or not info.get("vid"):
        # pyudev 실패 또는 정보 부족 시 sysfs로 보강.
        sysfs = _usb_info_via_sysfs(port)
        info = info or {}
        for key, value in sysfs.items():
            info.setdefault(key, None)
            if not info.get(key):
                info[key] = value
    return info  # type: ignore[return-value]


def classify(info: Dict[str, Optional[str]]) -> Dict[str, object]:
    """
    USB 정보로 보드 종류를 추정.

    반환 키:
      is_espressif : VID가 Espressif(303a)인지 여부
      bridge       : 외장 USB-UART 브리지 칩 이름(있을 경우) 또는 None
      vid_pid      : "303A:4001" 형태 문자열
    """
    vid = (info.get("vid") or "").lower()
    pid = (info.get("pid") or "").lower()
    is_espressif = vid == config.ESPRESSIF_VID
    bridge = config.KNOWN_BRIDGE_VIDS.get(vid)
    vid_pid = f"{vid.upper()}:{pid.upper()}" if vid and pid else "UNKNOWN"
    return {"is_espressif": is_espressif, "bridge": bridge, "vid_pid": vid_pid}


def discover_boards() -> List[Dict[str, object]]:
    """
    연결된 모든 후보 보드를 탐색해 보드별 정보 딕셔너리 리스트로 반환.

    각 항목:
      board_index, port, vid, pid, serial, vendor, model,
      is_espressif, bridge, vid_pid
    """
    boards: List[Dict[str, object]] = []
    for index, port in enumerate(detect_serial_ports(), start=1):
        info = get_usb_info(port)
        info.update(classify(info))
        info["board_index"] = index
        info["port"] = port
        # 포트 접근 권한(읽기/쓰기) 여부도 함께 기록 -> 권한 안내에 사용.
        info["accessible"] = os.access(port, os.R_OK | os.W_OK)
        boards.append(info)
    return boards


if __name__ == "__main__":
    # 단독 실행 시: 탐색된 보드 정보를 보기 좋게 출력.
    found = discover_boards()
    if not found:
        print("연결된 시리얼 포트를 찾지 못했습니다 (/dev/ttyACM*, /dev/ttyUSB*).")
    for board in found:
        print(
            f"Board #{board['board_index']}\n"
            f"  VID:PID = {board['vid_pid']}\n"
            f"  Port    = {board['port']}\n"
            f"  Serial  = {board.get('serial')}\n"
            f"  Espressif = {board['is_espressif']}  Accessible = {board['accessible']}"
        )
