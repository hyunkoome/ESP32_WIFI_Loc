"""
wifi_test.py
============
WiFi 모듈 정상 여부 검사. CSI 개발 전 WiFi 라디오/스택 이상을 조기에 발견하는
것이 목적입니다.

WiFi AP 스캔은 칩에서 코드가 실행돼야 하므로 진단 펌웨어(firmware.py)에서 얻은
결과를 해석합니다. 펌웨어가 없거나 결과를 못 받으면 SKIP 처리합니다.

판정 기준:
  - ap_count >= 1 이면 PASS(주변 AP를 1개 이상 검색 = 라디오/스택 정상).
  - ap_count == 0 이면 WARN성 FAIL(주변에 AP가 없거나 라디오 이상).
    (전파 환경 영향이 있으므로 min_ap 인자로 임계값 조정 가능)
"""

from __future__ import annotations

from typing import Dict, Optional

import config


def evaluate_wifi(
    firmware_diag: Optional[Dict[str, object]], min_ap: int = 1
) -> Dict[str, object]:
    """
    펌웨어 진단 결과의 WiFi 부분을 해석해 검사 결과로 변환.

    firmware_diag : firmware.run_firmware_diagnostics() 반환값 또는 None
    min_ap        : PASS로 판정할 최소 AP 개수

    반환: {
      status      : "PASS"|"FAIL"|"SKIP",
      ap_count    : int|None,
      strongest_rssi : int|None,
      detail      : str,
    }
    """
    result: Dict[str, object] = {
        "status": config.STATUS_SKIP,
        "ap_count": None,
        "strongest_rssi": None,
        "detail": "",
    }

    # 펌웨어 자체가 없을 때.
    if firmware_diag is None:
        result["detail"] = (
            "진단 펌웨어 미사용 — WiFi 스캔 검사를 건너뜀 "
            "(--firmware 옵션 및 firmware/ 빌드 필요)"
        )
        return result

    wifi = firmware_diag.get("wifi")
    if not wifi or "ap_count" not in wifi:
        # flash는 됐지만 결과를 못 받은 경우.
        err = firmware_diag.get("error") or "펌웨어 WiFi 결과 없음"
        result["detail"] = f"WiFi 결과를 받지 못함: {err}"
        return result

    ap_count = int(wifi.get("ap_count", 0))
    rssi = wifi.get("strongest_rssi")
    result["ap_count"] = ap_count
    result["strongest_rssi"] = rssi
    if ap_count >= min_ap:
        result["status"] = config.STATUS_PASS
        rssi_txt = f", 최강 RSSI {rssi} dBm" if rssi is not None else ""
        result["detail"] = f"검색된 AP {ap_count}개{rssi_txt}"
    else:
        result["status"] = config.STATUS_FAIL
        result["detail"] = (
            f"검색된 AP {ap_count}개 (임계값 {min_ap}). "
            f"주변에 AP가 없거나 WiFi 라디오 이상 가능."
        )
    return result
