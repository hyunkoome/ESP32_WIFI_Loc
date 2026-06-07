"""
psram_test.py
=============
PSRAM(외장 SPI RAM) 존재 및 사용 가능 여부 검사.

YD-ESP32-S3(N16R8)는 8MB octal PSRAM을 탑재합니다. 다만 PSRAM은 esptool의
flash-id/chip-id로는 신뢰성 있게 보고되지 않으므로(외장 RAM), 칩에서 실제로
초기화/할당이 되는지 진단 펌웨어로 확인합니다.

판정 기준:
  - present == True 이고 size > 0 이면 PASS.
  - present == False 이면 FAIL(PSRAM 미탑재/초기화 실패).
  - 펌웨어 결과가 없으면 SKIP.
"""

from __future__ import annotations

from typing import Dict, Optional

import config


def _human_size(num_bytes: Optional[int]) -> Optional[str]:
    """바이트 수를 'MB' 등 사람이 읽는 문자열로 변환."""
    if not num_bytes or num_bytes <= 0:
        return None
    mb = num_bytes / (1024 * 1024)
    if mb >= 1:
        # 8388608 -> '8MB', 4194304 -> '4MB'
        return f"{mb:.0f}MB" if mb == int(mb) else f"{mb:.1f}MB"
    return f"{num_bytes // 1024}KB"


def evaluate_psram(firmware_diag: Optional[Dict[str, object]]) -> Dict[str, object]:
    """
    펌웨어 진단 결과의 PSRAM 부분을 해석해 검사 결과로 변환.

    반환: {
      status  : "PASS"|"FAIL"|"SKIP",
      present : bool|None,
      size    : int|None (bytes),
      size_human : str|None,
      detail  : str,
    }
    """
    result: Dict[str, object] = {
        "status": config.STATUS_SKIP,
        "present": None,
        "size": None,
        "size_human": None,
        "detail": "",
    }

    if firmware_diag is None:
        result["detail"] = (
            "진단 펌웨어 미사용 — PSRAM 검사를 건너뜀 "
            "(--firmware 옵션 및 firmware/ 빌드 필요)"
        )
        return result

    psram = firmware_diag.get("psram")
    if not psram or "present" not in psram:
        err = firmware_diag.get("error") or "펌웨어 PSRAM 결과 없음"
        result["detail"] = f"PSRAM 결과를 받지 못함: {err}"
        return result

    present = bool(psram.get("present"))
    size = psram.get("size")
    result["present"] = present
    result["size"] = size
    result["size_human"] = _human_size(size)

    if present and size and size > 0:
        result["status"] = config.STATUS_PASS
        result["detail"] = f"PSRAM 사용 가능, 용량 {result['size_human']}"
    else:
        result["status"] = config.STATUS_FAIL
        result["detail"] = "PSRAM 미탑재 또는 초기화 실패"
    return result
