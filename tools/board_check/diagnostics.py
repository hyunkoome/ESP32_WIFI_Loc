"""
diagnostics.py
==============
보드 1대에 대한 전체 진단을 오케스트레이션하는 핵심 모듈.

각 검사 모듈(usb_detector, serial_check, esptool_wrapper, firmware/wifi/psram)을
순서대로 호출해 항목별 PASS/FAIL/SKIP을 산출하고, 하나의 구조화된 결과
딕셔너리로 합칩니다. main.py는 보드마다 이 함수를 (병렬로) 호출합니다.

검사 항목(키는 config.CHECK_LABELS 참고):
  usb_detection, uart_connection, bootloader_access,
  flash_access, flash_size, psram, wifi_scan
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

import config
import esptool_wrapper
import firmware as firmware_mod
import peripheral_test
import psram_test
import serial_check
import wifi_test

logger = logging.getLogger("board_check.diagnostics")


def _check(status: str, detail: str = "", **extra) -> Dict[str, object]:
    """검사 항목 결과 표준 형태를 만든다."""
    item = {"status": status, "detail": detail}
    item.update(extra)
    return item


def diagnose_board(
    board: Dict[str, object],
    use_sudo: bool = False,
    use_firmware: bool = False,
    stress: int = 0,
    min_ap: int = 1,
    progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, object]:
    """
    보드 1대를 진단하고 결과 딕셔너리를 반환.

    board       : usb_detector.discover_boards()가 만든 보드 정보 딕셔너리
    use_sudo    : esptool/펌웨어 명령을 sudo로 실행
    use_firmware: 진단 펌웨어를 flash해 WiFi/PSRAM 런타임 검사 수행
    stress      : 스트레스 테스트 반복 횟수(0이면 비활성)
    min_ap      : WiFi PASS 판정 최소 AP 개수
    progress    : 진행 상황 콜백(문자열 메시지)

    반환 구조:
      {
        board_index, port, usb: {...}, chip: {...},
        checks: { usb_detection: {...}, ... },
        stress: {...}|None,
        overall: "PASS"|"FAIL",
        errors: [..],
      }
    """
    port = str(board.get("port"))
    index = board.get("board_index")

    def emit(msg: str) -> None:
        if progress:
            progress(f"[Board #{index} {port}] {msg}")
        logger.info("Board #%s %s: %s", index, port, msg)

    result: Dict[str, object] = {
        "board_index": index,
        "port": port,
        "usb": {
            "vid_pid": board.get("vid_pid"),
            "vid": board.get("vid"),
            "pid": board.get("pid"),
            "serial": board.get("serial"),
            "vendor": board.get("vendor"),
            "model": board.get("model"),
            "is_espressif": board.get("is_espressif"),
            "bridge": board.get("bridge"),
            "accessible": board.get("accessible"),
        },
        "chip": {},
        "checks": {},
        "stress": None,
        "errors": [],
    }
    checks: Dict[str, Dict[str, object]] = result["checks"]
    errors: List[str] = result["errors"]

    # ---------------------------------------------------------------
    # 1) USB Detection — 포트가 발견됐고 Espressif/브리지로 식별되면 PASS.
    # ---------------------------------------------------------------
    emit("USB 감지 확인")
    if board.get("is_espressif"):
        checks["usb_detection"] = _check(
            config.STATUS_PASS, f"Espressif {board.get('vid_pid')}"
        )
    elif board.get("bridge"):
        checks["usb_detection"] = _check(
            config.STATUS_PASS, f"USB-UART 브리지: {board.get('bridge')}"
        )
    else:
        # 포트는 있으나 VID 미확인 — FAIL 대신 경고성 PASS로 두되 상세 기록.
        checks["usb_detection"] = _check(
            config.STATUS_PASS,
            f"VID/PID 미확인({board.get('vid_pid')}) — 포트는 존재",
        )

    # ---------------------------------------------------------------
    # 2) UART Connection — 포트 open + 권한.
    # ---------------------------------------------------------------
    emit("UART 연결 확인")
    uart = serial_check.test_uart_open(port)
    if uart.get("uart_open"):
        checks["uart_connection"] = _check(config.STATUS_PASS, "포트 open 성공")
    else:
        msg = str(uart.get("error") or "UART open 실패")
        checks["uart_connection"] = _check(config.STATUS_FAIL, msg)
        errors.append(f"UART: {msg}")

    # 권한이 없으면 esptool도 실패가 자명하므로, 안내 후 esptool 단계는
    # 진행하되 use_sudo가 아니면 빠르게 실패 처리됨.
    if not board.get("accessible") and not use_sudo:
        emit("포트 접근 권한 없음 — dialout 그룹 또는 --sudo 필요")

    # ---------------------------------------------------------------
    # 3) 칩 정보 (esptool) — Bootloader Access / Flash Access / Flash Size 판정 근거.
    # ---------------------------------------------------------------
    emit("esptool 칩 정보 조회")
    chip = esptool_wrapper.get_chip_info(port, use_sudo=use_sudo)
    result["chip"] = chip

    connected = bool(chip.get("connected"))
    if connected:
        # esptool 연결 성공 = 자동 리셋으로 부트로더 진입 성공.
        checks["bootloader_access"] = _check(
            config.STATUS_PASS,
            f"{chip.get('chip')} rev {chip.get('revision')} "
            f"(crystal {chip.get('crystal_freq')})",
        )
    else:
        msg = str(chip.get("error") or "칩 연결 실패")
        checks["bootloader_access"] = _check(config.STATUS_FAIL, msg)
        errors.append(f"Bootloader: {msg}")

    # ---------------------------------------------------------------
    # 4) Flash Access — flash-id로 제조사/디바이스 ID 확보 + 읽기 테스트.
    # ---------------------------------------------------------------
    emit("Flash 접근 확인")
    if connected and chip.get("flash_manufacturer_code"):
        detail = (
            f"{chip.get('flash_manufacturer')} "
            f"(mfr 0x{chip.get('flash_manufacturer_code')}, "
            f"dev 0x{chip.get('flash_device')})"
        )
        # 추가로 실제 읽기 가능 여부 검증(4KB 읽기).
        read = esptool_wrapper.read_flash_test(port, use_sudo=use_sudo)
        if read.get("flash_read_ok"):
            checks["flash_access"] = _check(
                config.STATUS_PASS, f"{detail}; 읽기 {read.get('bytes')}B OK"
            )
        else:
            # ID는 읽혔지만 데이터 읽기 실패 — 부분 통과(PASS)로 두되 경고.
            checks["flash_access"] = _check(
                config.STATUS_PASS,
                f"{detail}; 읽기 테스트 경고: {read.get('error')}",
            )
    elif connected:
        checks["flash_access"] = _check(
            config.STATUS_FAIL, "Flash ID를 읽지 못함"
        )
        errors.append("Flash: ID 읽기 실패")
    else:
        checks["flash_access"] = _check(config.STATUS_FAIL, "칩 미연결로 확인 불가")

    # ---------------------------------------------------------------
    # 5) Flash Size — esptool이 감지한 크기.
    # ---------------------------------------------------------------
    flash_size = chip.get("flash_size")
    if connected and flash_size:
        checks["flash_size"] = _check(config.STATUS_PASS, str(flash_size))
    elif connected:
        checks["flash_size"] = _check(config.STATUS_FAIL, "Flash 크기 미감지")
    else:
        checks["flash_size"] = _check(config.STATUS_FAIL, "칩 미연결로 확인 불가")

    # ---------------------------------------------------------------
    # 6) PSRAM / 7) WiFi — 진단 펌웨어 기반(옵션). 펌웨어 미사용 시 SKIP.
    # ---------------------------------------------------------------
    fw_diag: Optional[Dict[str, object]] = None
    if use_firmware and connected:
        if firmware_mod.available():
            emit("진단 펌웨어 flash 및 WiFi/PSRAM 검사")
            fw_diag = firmware_mod.run_firmware_diagnostics(port, use_sudo=use_sudo)
        else:
            emit("진단 펌웨어 바이너리 없음 — WiFi/PSRAM SKIP")
            errors.append("Firmware: 빌드된 진단 펌웨어가 없음 (firmware/README.md)")

    psram_res = psram_test.evaluate_psram(fw_diag if use_firmware else None)
    checks["psram"] = _check(
        psram_res["status"],
        psram_res["detail"],
        present=psram_res.get("present"),
        size=psram_res.get("size"),
        size_human=psram_res.get("size_human"),
    )

    # 6-2) RGB LED / BOOT 버튼 — 진단 펌웨어 기반(옵션).
    led_res = peripheral_test.evaluate_led(fw_diag if use_firmware else None)
    checks["rgb_led"] = _check(
        led_res["status"],
        led_res["detail"],
        ok=led_res.get("ok"),
        gpio=led_res.get("gpio"),
    )

    button_res = peripheral_test.evaluate_button(fw_diag if use_firmware else None)
    checks["boot_button"] = _check(
        button_res["status"],
        button_res["detail"],
        idle_level=button_res.get("idle_level"),
        pressed_now=button_res.get("pressed_now"),
        gpio=button_res.get("gpio"),
    )

    wifi_res = wifi_test.evaluate_wifi(fw_diag if use_firmware else None, min_ap=min_ap)
    checks["wifi_scan"] = _check(
        wifi_res["status"],
        wifi_res["detail"],
        ap_count=wifi_res.get("ap_count"),
        strongest_rssi=wifi_res.get("strongest_rssi"),
    )

    # ---------------------------------------------------------------
    # 8) 스트레스 테스트(옵션) — esptool 연결을 N회 반복하며 실패 카운트.
    # ---------------------------------------------------------------
    if stress and connected:
        emit(f"스트레스 테스트 {stress}회 시작")
        result["stress"] = _run_stress(port, stress, use_sudo, emit)

    # ---------------------------------------------------------------
    # 전체 판정 — 필수 항목(REQUIRED_CHECKS)이 모두 PASS여야 PASS.
    # SKIP은 전체 결과에 영향 없음.
    # ---------------------------------------------------------------
    overall = config.STATUS_PASS
    for key in config.REQUIRED_CHECKS:
        if checks.get(key, {}).get("status") == config.STATUS_FAIL:
            overall = config.STATUS_FAIL
            break
    # 펌웨어를 사용했는데 PSRAM/LED/버튼/WiFi가 FAIL이면 전체도 FAIL로 격상.
    if use_firmware:
        for key in ("psram", "rgb_led", "boot_button", "wifi_scan"):
            if checks.get(key, {}).get("status") == config.STATUS_FAIL:
                overall = config.STATUS_FAIL
                break
    result["overall"] = overall
    emit(f"결과: {overall}")
    return result


def _run_stress(
    port: str, count: int, use_sudo: bool, emit: Callable[[str], None]
) -> Dict[str, object]:
    """esptool 연결(chip-id)을 count회 반복하며 통신 오류를 집계."""
    failures = 0
    fail_details: List[str] = []
    for i in range(1, count + 1):
        rc, out = esptool_wrapper.run_esptool(port, "chip-id", use_sudo=use_sudo)
        ok = "Chip is" in out
        if not ok:
            failures += 1
            fail_details.append(f"#{i}: {esptool_wrapper._summarize_failure(out)}")
        if i % max(1, count // 10) == 0 or i == count:
            emit(f"스트레스 {i}/{count} (실패 {failures})")
    return {
        "iterations": count,
        "failures": failures,
        "success_rate": round((count - failures) / count * 100, 1) if count else 0.0,
        "fail_details": fail_details[:10],  # 너무 길어지지 않게 상위 10개만.
        "status": config.STATUS_PASS if failures == 0 else config.STATUS_FAIL,
    }
