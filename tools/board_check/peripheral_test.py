"""
peripheral_test.py
==================
보드 주변장치(RGB LED, BOOT 버튼) 검사 결과 해석.

RGB LED 점등과 BOOT 버튼 입력은 칩에서 코드가 실행돼야 하므로, 진단
펌웨어(firmware.py)가 출력한 DIAG_LED / DIAG_BUTTON 결과를 해석합니다.
펌웨어가 없거나 결과를 못 받으면 SKIP 처리합니다.

판정 기준:
  - LED   : 펌웨어가 led_strip 초기화/점등에 성공(ok=true)하면 PASS.
            (실제 발광은 육안 확인용 — 펌웨어 실행 중 R→G→B 로 점등)
  - Button: GPIO0 유휴 레벨이 1(내부 풀업 정상)이면 PASS.
            0이면 버튼이 눌린 채이거나 핀 단락 등 이상 가능 → FAIL.
"""

from __future__ import annotations

from typing import Dict, Optional

import config


def evaluate_led(firmware_diag: Optional[Dict[str, object]]) -> Dict[str, object]:
    """펌웨어 진단 결과의 RGB LED 부분을 해석."""
    result: Dict[str, object] = {
        "status": config.STATUS_SKIP,
        "ok": None,
        "gpio": None,
        "detail": "",
    }

    if firmware_diag is None:
        result["detail"] = (
            "진단 펌웨어 미사용 — RGB LED 검사를 건너뜀 "
            "(--firmware 옵션 및 firmware/ 빌드 필요)"
        )
        return result

    led = firmware_diag.get("led")
    if not led or "ok" not in led:
        err = firmware_diag.get("error") or "펌웨어 LED 결과 없음"
        result["detail"] = f"RGB LED 결과를 받지 못함: {err}"
        return result

    ok = bool(led.get("ok"))
    gpio = led.get("gpio")
    result["ok"] = ok
    result["gpio"] = gpio
    if ok:
        result["status"] = config.STATUS_PASS
        result["detail"] = f"WS2812 초기화/점등 성공 (GPIO{gpio}, R→G→B 육안 확인)"
    else:
        result["status"] = config.STATUS_FAIL
        result["detail"] = f"WS2812 초기화 실패 (GPIO{gpio})"
    return result


def evaluate_button(firmware_diag: Optional[Dict[str, object]]) -> Dict[str, object]:
    """펌웨어 진단 결과의 BOOT 버튼 부분을 해석."""
    result: Dict[str, object] = {
        "status": config.STATUS_SKIP,
        "idle_level": None,
        "pressed_now": None,
        "gpio": None,
        "detail": "",
    }

    if firmware_diag is None:
        result["detail"] = (
            "진단 펌웨어 미사용 — BOOT 버튼 검사를 건너뜀 "
            "(--firmware 옵션 및 firmware/ 빌드 필요)"
        )
        return result

    button = firmware_diag.get("button")
    if not button or "idle_level" not in button:
        err = firmware_diag.get("error") or "펌웨어 BOOT 버튼 결과 없음"
        result["detail"] = f"BOOT 버튼 결과를 받지 못함: {err}"
        return result

    idle = int(button.get("idle_level"))
    pressed = bool(button.get("pressed_now"))
    gpio = button.get("gpio")
    result["idle_level"] = idle
    result["pressed_now"] = pressed
    result["gpio"] = gpio

    if idle == 1:
        result["status"] = config.STATUS_PASS
        extra = " (검사 중 눌림 감지됨)" if pressed else ""
        result["detail"] = f"GPIO{gpio} 입력 정상 (유휴 HIGH, 내부 풀업){extra}"
    else:
        result["status"] = config.STATUS_FAIL
        result["detail"] = (
            f"GPIO{gpio} 유휴 레벨이 LOW — 버튼이 눌린 채이거나 핀 이상 가능"
        )
    return result
