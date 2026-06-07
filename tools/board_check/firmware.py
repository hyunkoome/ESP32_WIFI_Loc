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
from typing import Callable, Dict, Optional

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
        "wifi_connect": None,
        "ble": None,
        "chip": None,
        "led": None,
        "button": None,
        "temp": None,
        "gpio": None,
        "done": False,
        "error": None,
        "raw": "",
    }
    if serial is None:
        result["error"] = "pyserial 미설치"
        return result

    buffer = []
    ser = None
    # 펌웨어는 결과 사이클(DIAG_START ... DIAG_DONE)을 약 2초마다 반복 출력한다.
    # 호스트가 flash 직후 시리얼을 늦게 열어 앞쪽 라인(특히 DIAG_PSRAM)을 놓치는
    # race 를 피하려고, "DIAG_START 를 본 뒤의 DIAG_DONE" 한 사이클만 완전한 결과로
    # 인정한다. 중간부터 받은 부분 사이클은 버리고 다음 DIAG_START 를 기다린다.
    # 태그 → 결과 필드 매핑. 라인의 첫 토큰(공백 전)과 "정확히" 비교하므로
    # DIAG_WIFI 와 DIAG_WIFI_CONNECT 처럼 접두사가 겹쳐도 안전하다.
    tag_map = {
        "DIAG_PSRAM": "psram",
        "DIAG_WIFI": "wifi",
        "DIAG_WIFI_CONNECT": "wifi_connect",
        "DIAG_BLE": "ble",
        "DIAG_CHIP": "chip",
        "DIAG_LED": "led",
        "DIAG_BUTTON": "button",
        "DIAG_TEMP": "temp",
        "DIAG_GPIO": "gpio",
    }
    data_fields = tuple(tag_map.values())

    saw_start = False
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=1.0)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            buffer.append(line)
            tag, _, payload = line.partition(" ")
            # 새 사이클 시작: 이전(부분) 사이클 결과를 초기화하고 수집을 다시 시작.
            if tag == "DIAG_START":
                saw_start = True
                for field in data_fields:
                    result[field] = None
                continue
            field = tag_map.get(tag)
            if field:
                try:
                    result[field] = json.loads(payload)
                except Exception:
                    result[field] = {"parse_error": payload}
            # DIAG_START 를 본 뒤의 DONE 만 완전한 사이클로 인정.
            if tag == "DIAG_DONE" and saw_start:
                result["done"] = True
                break
        if not result["done"] and not any(
            result[k] for k in data_fields
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
            "wifi_connect": None,
            "ble": None,
            "chip": None,
            "led": None,
            "button": None,
            "temp": None,
            "gpio": None,
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


# DIAG 태그 → 필드 매핑(스트리밍/단발 파싱 공용).
_TAG_MAP = {
    "DIAG_PSRAM": "psram",
    "DIAG_WIFI": "wifi",
    "DIAG_WIFI_CONNECT": "wifi_connect",
    "DIAG_BLE": "ble",
    "DIAG_CHIP": "chip",
    "DIAG_LED": "led",
    "DIAG_BUTTON": "button",
    "DIAG_TEMP": "temp",
    "DIAG_GPIO": "gpio",
}


def stream_cycles(
    port: str,
    should_stop: Callable[[], bool],
    on_cycle: Callable[[Dict[str, object]], None],
    baud: int = config.FIRMWARE_MONITOR_BAUD,
) -> Optional[str]:
    """
    이미 진단 펌웨어가 도는 보드에서 시리얼을 한 번 열고, 반복 출력되는
    DIAG_START..DIAG_DONE 사이클을 계속 읽어 완전한 사이클마다 on_cycle(dict)를
    호출한다(웹 라이브 모니터용).

    should_stop() 가 True 가 되면 종료한다. 시리얼을 한 번만 열어 보드 리셋을
    최소화한다. 반환: 오류 메시지(있으면) 또는 None.
    """
    if serial is None:
        return "pyserial 미설치"
    ser = None
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=1.0)
        cur: Dict[str, object] = {}
        saw_start = False
        while not should_stop():
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            tag, _, payload = line.partition(" ")
            if tag == "DIAG_START":
                saw_start = True
                cur = {}
                continue
            field = _TAG_MAP.get(tag)
            if field:
                try:
                    cur[field] = json.loads(payload)
                except Exception:
                    cur[field] = {"parse_error": payload}
            elif tag == "DIAG_DONE" and saw_start:
                on_cycle(dict(cur))
                saw_start = False
        return None
    except Exception as exc:
        return str(exc)
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass


def watch_button_press(
    port: str,
    timeout: float = 15.0,
    baud: int = config.FIRMWARE_MONITOR_BAUD,
) -> Dict[str, object]:
    """
    이미 진단 펌웨어가 도는 보드에서 BOOT 버튼 눌림을 대화형으로 감시한다.

    펌웨어는 DIAG_BUTTON 에 ever_pressed(부팅 후 한 번이라도 눌림)와 pressed_now
    를 실시간으로 싣는다. 이 함수는 시리얼을 열어 그 값을 timeout 까지 지켜본다.

    반환: {
      "detected": bool,   # 눌림 감지(또는 이미 눌린 기록 있음)
      "already":  bool,   # 감시 시작 시점에 이미 눌림 기록이 있었음
      "error":    str|None,
    }
    """
    result: Dict[str, object] = {"detected": False, "already": False, "error": None}
    if serial is None:
        result["error"] = "pyserial 미설치"
        return result

    ser = None
    baseline_checked = False
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=1.0)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            tag, _, payload = line.partition(" ")
            if tag != "DIAG_BUTTON":
                continue
            try:
                data = json.loads(payload)
            except Exception:
                continue
            ever = bool(data.get("ever_pressed"))
            now = bool(data.get("pressed_now"))
            # 첫 DIAG_BUTTON 으로 기준선(이미 눌린 기록 여부) 판단.
            if not baseline_checked:
                baseline_checked = True
                if ever:
                    result["already"] = True
                    result["detected"] = True
                    return result
            if ever or now:
                result["detected"] = True
                return result
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
