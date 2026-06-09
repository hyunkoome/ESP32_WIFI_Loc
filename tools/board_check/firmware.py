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
    wifi_inject: Optional[tuple] = None,
) -> Dict[str, object]:
    """
    펌웨어가 출력하는 DIAG_* 라인을 시리얼에서 읽어 파싱.

    wifi_inject=(ssid, password) 를 주면(CLI 경로), 첫 완전 사이클을 받은 뒤 '같은
    시리얼 연결'로 'WIFI_CONNECT ssid\\tpw' 명령을 보내고 DIAG_WIFI_CONNECT 의
    attempted=true 결과가 올 때까지 더 읽는다. 포트를 닫았다 다시 열지 않으므로
    보드 리셋/명령 유실 없이 런타임 접속 테스트가 안정적으로 동작한다(끊었다 다시
    열면 보드가 리셋돼 serial_cmd_task 가 명령을 못 받는 문제가 있었다).

    반환: {
      "psram": {...}|None, "wifi": {...}|None, "wifi_connect": {...}|None,
      "chip": {...}|None, "done": bool, "error": str|None, "raw": str, ...
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

    # WiFi 런타임 주입 명령(있으면). 첫 완전 사이클 뒤부터 ~2초마다 재전송한다.
    wifi_cmd = None
    if wifi_inject and wifi_inject[0]:
        _ssid, _pw = wifi_inject[0], (wifi_inject[1] or "")
        wifi_cmd = f"WIFI_CONNECT {_ssid}\t{_pw}\n".encode("utf-8")
    wifi_phase = False   # 첫 사이클이 끝나 WIFI_CONNECT 명령을 보내는 단계인지
    wifi_done = False    # attempted=true 결과를 받았는지
    next_wifi_send = 0.0

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
            # WiFi 명령 단계: 명령이 유실될 수 있어 ~2초마다 재전송한다.
            if wifi_phase and not wifi_done:
                now = time.monotonic()
                if now >= next_wifi_send:
                    try:
                        ser.write(wifi_cmd)
                    except Exception:
                        pass
                    next_wifi_send = now + 2.0
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
                # WiFi 주입 단계에서 attempted=true 가 오면 접속 테스트 완료.
                if tag == "DIAG_WIFI_CONNECT" and wifi_phase:
                    v = result[field]
                    if isinstance(v, dict) and v.get("attempted"):
                        wifi_done = True
            # DIAG_START 를 본 뒤의 DONE 만 완전한 사이클로 인정.
            if tag == "DIAG_DONE" and saw_start:
                result["done"] = True
                if wifi_cmd is None:
                    break          # 일반 진단: 한 사이클이면 충분
                if wifi_done:
                    break          # WiFi 주입까지 끝남
                wifi_phase = True  # 첫 사이클 완료 → WIFI_CONNECT 명령 단계 진입
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


def run_firmware_diagnostics(
    port: str, use_sudo: bool = False, wifi_from_config: bool = True
) -> Dict[str, object]:
    """
    펌웨어 flash -> 부팅 대기 -> DIAG 출력 읽기를 한 번에 수행.

    WiFi '접속' 테스트는 펌웨어에 자격증명을 박지 않는다. wifi_from_config 가 True
    (CLI)면 cli_wifi_config.yaml 에 자격증명이 있을 때 read_diagnostics 가 '같은
    시리얼 연결'로 런타임 주입해 결과를 채운다. False(웹)면 yaml 을 쓰지 않고, 사용자가
    WiFi 탭에서 입력한 값으로 별도 접속 명령을 보낸다(여기서는 SKIP 상태로 둠).

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
    # CLI(wifi_from_config=True)만 cli_wifi_config.yaml 자격증명을 '같은 시리얼 연결'로
    # 런타임 주입한다(read_diagnostics 가 한 사이클을 읽은 뒤 WIFI_CONNECT 를 보내고
    # attempted=true 결과를 받음 — 포트를 끊었다 다시 열지 않아 명령이 안전히 닿는다).
    # 웹은 False 라 yaml 을 쓰지 않고, 사용자가 WiFi 탭 입력으로 별도 명령을 보낸다.
    wifi_inject = config.wifi_credentials() if wifi_from_config else None
    diag = read_diagnostics(port, wifi_inject=wifi_inject)
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
    pop_command: Optional[Callable[[], Optional[bytes]]] = None,
) -> Optional[str]:
    """
    이미 진단 펌웨어가 도는 보드에서 시리얼을 한 번 열고, 반복 출력되는
    DIAG_START..DIAG_DONE 사이클을 계속 읽어 완전한 사이클마다 on_cycle(dict)를
    호출한다(웹 라이브 모니터용).

    pop_command(): 펌웨어로 보낼 명령 바이트를 반환(없으면 None). 매 반복마다
    호출해 대기 중인 명령(예: b"WIFI_CONNECT ssid\\tpw\\n")을 시리얼로 써보낸다.
    같은 연결로 읽기/쓰기를 함께 처리해 웹의 AP 접속 명령을 지원한다.

    should_stop() 가 True 가 되면 종료한다. 시리얼을 한 번만 열어 보드 리셋을
    최소화한다. 반환: 오류 메시지(있으면) 또는 None.
    """
    if serial is None:
        return "pyserial 미설치"
    ser = None
    try:
        # DTR/RTS 를 미리 내려(False) 포트 open 시 보드가 리셋되지 않게 한다.
        # (CH343 의 자동 리셋 회로가 DTR/RTS 로 동작하므로. 리셋되면 보드가 모든
        #  검사를 다시 도느라 라이브 갱신이 ~20초 지연된다.) 이미 돌고 있는
        #  펌웨어의 반복 사이클을 그대로 받기 위함.
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = baud
        ser.timeout = 1.0
        try:
            ser.dtr = False
            ser.rts = False
        except Exception:
            pass
        ser.open()
        cur: Dict[str, object] = {}
        saw_start = False
        while not should_stop():
            # 대기 중인 명령이 있으면 펌웨어로 써보낸다(WiFi 접속 등).
            if pop_command is not None:
                cmd = pop_command()
                if cmd:
                    try:
                        ser.write(cmd)
                    except Exception:
                        pass
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
