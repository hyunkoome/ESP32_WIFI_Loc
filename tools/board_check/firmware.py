"""
firmware.py
===========
진단 펌웨어를 flash하고 시리얼로 출력되는 결과(JSON 라인)를 읽어 파싱하는 모듈.

WiFi 스캔과 PSRAM 런타임 검사는 esptool만으로는 불가능합니다(칩에서 코드가
실행돼야 함). 그래서 작은 진단 펌웨어(firmware/ 디렉터리, ESP-IDF 프로젝트)를
빌드해 두면, 이 모듈이 해당 .bin을 esptool로 flash하고 부팅 후 출력되는
구조화된 라인을 읽어 WiFi/PSRAM 결과를 판정합니다.

펌웨어 출력 규약 (firmware/main/diag_main.c 가 출력):
    DIAG_PSRAM {"present": true, "size": 8388608}
    DIAG_WIFI  {"ap_count": 15, "strongest_rssi": -42}
    DIAG_CHIP  {"cores": 2, "model": "ESP32-S3"}
    DIAG_DONE

빌드된 펌웨어(config.FIRMWARE_BIN)가 없으면 available()=False 이며,
상위 모듈(wifi_test/psram_test)은 해당 검사를 SKIP 처리합니다.
"""

from __future__ import annotations

import json
import time
from typing import Dict, Optional

import config
from esptool_wrapper import run_esptool

try:
    import serial  # pyserial
except Exception:  # pragma: no cover
    serial = None


def available() -> bool:
    """빌드된 진단 펌웨어 바이너리가 존재하는지 여부."""
    return config.FIRMWARE_BIN.exists()


def flash_firmware(
    port: str, use_sudo: bool = False, erase: bool = True
) -> Dict[str, object]:
    """
    진단 펌웨어 병합 바이너리를 0x0에 flash.

    erase=True 면 write 전에 전체 flash 를 지운다(기존 펌웨어를 깨끗이 제거).

    반환: {"flashed": bool, "erased": bool, "error": str|None}
    """
    result: Dict[str, object] = {"flashed": False, "erased": False, "error": None}
    if not available():
        result["error"] = (
            f"진단 펌웨어가 없습니다: {config.FIRMWARE_BIN}\n"
            f"      firmware/README.md 를 참고해 빌드하세요."
        )
        return result

    # 1) (옵션) 전체 erase — 기존 펌웨어/데이터를 깨끗이 지우고 다운로드.
    if erase:
        rc_e, out_e = run_esptool(
            port,
            "erase-flash",
            use_sudo=use_sudo,
            timeout=config.FIRMWARE_FLASH_TIMEOUT,
        )
        if rc_e != 0:
            result["error"] = "erase 실패: " + out_e.strip()[-300:]
            return result
        result["erased"] = True

    # 2) 병합 바이너리를 0x0 에 write.
    rc, out = run_esptool(
        port,
        "write-flash" if _supports_hyphen_writeflash() else "write_flash",
        extra_args=["0x0", str(config.FIRMWARE_BIN)],
        use_sudo=use_sudo,
        timeout=config.FIRMWARE_FLASH_TIMEOUT,
    )
    result["flashed"] = rc == 0
    if rc != 0:
        result["error"] = out.strip()[-300:]
    return result


def _supports_hyphen_writeflash() -> bool:
    """esptool v5는 'write-flash', v4는 'write_flash'. 버전에 맞게 선택."""
    from esptool_wrapper import _major_version

    return _major_version() >= 5


def read_diagnostics(
    port: str,
    baud: int = config.FIRMWARE_MONITOR_BAUD,
    timeout: float = config.FIRMWARE_MONITOR_TIMEOUT,
) -> Dict[str, object]:
    """
    펌웨어가 출력하는 DIAG_* 라인을 시리얼에서 읽어 파싱.

    반환: {
      "psram": {...}|None,
      "wifi": {...}|None,
      "chip": {...}|None,
      "done": bool,
      "error": str|None,
      "raw": str,
    }
    """
    result: Dict[str, object] = {
        "psram": None,
        "wifi": None,
        "chip": None,
        "led": None,
        "button": None,
        "done": False,
        "error": None,
        "raw": "",
    }
    if serial is None:
        result["error"] = "pyserial 미설치"
        return result

    buffer = []
    ser = None
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=1.0)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            buffer.append(line)
            # "DIAG_KEY {json}" 형태만 처리.
            for key, field in (
                ("DIAG_PSRAM", "psram"),
                ("DIAG_WIFI", "wifi"),
                ("DIAG_CHIP", "chip"),
                ("DIAG_LED", "led"),
                ("DIAG_BUTTON", "button"),
            ):
                if line.startswith(key):
                    payload = line[len(key):].strip()
                    try:
                        result[field] = json.loads(payload)
                    except Exception:
                        result[field] = {"parse_error": payload}
            if line.startswith("DIAG_DONE"):
                result["done"] = True
                break
        if not result["done"] and not any(
            result[k] for k in ("psram", "wifi", "chip", "led", "button")
        ):
            result["error"] = (
                "펌웨어 출력(DIAG_*)을 받지 못했습니다. "
                "펌웨어가 정상 flash/부팅됐는지 확인하세요."
            )
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    result["raw"] = "\n".join(buffer)
    return result


def run_firmware_diagnostics(port: str, use_sudo: bool = False) -> Dict[str, object]:
    """
    펌웨어 flash -> 부팅 대기 -> DIAG 출력 읽기를 한 번에 수행.

    반환: read_diagnostics() 결과에 flash 정보를 합친 딕셔너리.
    """
    flash_res = flash_firmware(port, use_sudo=use_sudo, erase=True)
    if not flash_res["flashed"]:
        return {
            "psram": None,
            "wifi": None,
            "chip": None,
            "led": None,
            "button": None,
            "done": False,
            "error": flash_res["error"],
            "raw": "",
            "flashed": False,
        }
    # flash 직후 보드가 재부팅되며 진단을 출력하기까지 잠시 대기.
    time.sleep(1.5)
    diag = read_diagnostics(port)
    diag["flashed"] = True
    return diag
