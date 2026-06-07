"""
ble_test.py
===========
Bluetooth LE 동작 검사. ESP32-S3 의 BLE 라디오/스택(NimBLE)이 정상인지
조기에 확인하는 것이 목적입니다.

BLE 스캔은 칩에서 코드가 실행돼야 하므로 진단 펌웨어(firmware.py)가 출력한
DIAG_BLE 결과를 해석합니다. 펌웨어가 없거나 결과를 못 받으면 SKIP 처리합니다.

판정 기준:
  - ok=true 면 PASS(컨트롤러/스택 초기화 + 스캔 완료 = BLE 정상).
    주변 기기가 0개여도 PASS(전파 환경 영향이므로 동작 자체가 핵심).
  - ok=false 면 FAIL(BT 컨트롤러/NimBLE 초기화 실패 등).
"""

from __future__ import annotations

from typing import Dict, Optional

import config
from wifi_test import _rssi_bar  # RSSI 신호막대 시각화 재사용


def evaluate_ble(firmware_diag: Optional[Dict[str, object]]) -> Dict[str, object]:
    """펌웨어의 BLE 스캔 결과를 해석해 검사 결과로 변환."""
    result: Dict[str, object] = {
        "status": config.STATUS_SKIP,
        "devices": None,
        "list": [],
        "sublist": [],
        "detail": "",
    }

    if firmware_diag is None:
        result["detail"] = (
            "진단 펌웨어 미사용 — BLE 검사를 건너뜀 "
            "(--firmware 옵션 및 firmware/ 빌드 필요)"
        )
        return result

    ble = firmware_diag.get("ble")
    if not ble or "ok" not in ble:
        err = firmware_diag.get("error") or "펌웨어 BLE 결과 없음"
        result["detail"] = f"BLE 결과를 받지 못함: {err}"
        return result

    if not ble.get("ok"):
        err = ble.get("error") or "원인 미상"
        result["status"] = config.STATUS_FAIL
        result["detail"] = f"BLE 초기화/스캔 실패: {err}"
        return result

    devices = int(ble.get("devices", 0))
    result["devices"] = devices
    result["status"] = config.STATUS_PASS
    result["detail"] = f"BLE 스캔 동작 — 주변 기기 {devices}개 발견"

    # 기기 목록(addr/rssi/name)을 RSSI 강한 순으로 정렬해 표시용 리스트 구성.
    devs = ble.get("list") or []
    if isinstance(devs, list) and devs:
        devs_sorted = sorted(devs, key=lambda d: d.get("rssi", -999), reverse=True)
        result["list"] = devs_sorted
        sublist = []
        for d in devs_sorted:
            name = d.get("name") or "<이름없음>"
            rssi = d.get("rssi")
            addr = d.get("addr") or "??"
            bar = _rssi_bar(rssi)
            sublist.append(f"{bar} {str(name)[:24]:<24} {addr}  {rssi:>4} dBm")
        result["sublist"] = sublist

    return result
