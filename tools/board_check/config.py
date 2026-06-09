"""
config.py
=========
ESP32-S3 보드 진단 도구의 전역 상수 및 설정 모음.

이 파일은 다른 모듈들이 공유하는 값(USB 식별자, 시리얼 통신 파라미터,
타임아웃, 결과 저장 경로, 검사 항목 키 등)을 한 곳에서 관리합니다.
값을 바꾸고 싶다면 가급적 이 파일만 수정하면 되도록 구성했습니다.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# USB 식별 정보
# ---------------------------------------------------------------------------
# Espressif의 네이티브 USB-Serial-JTAG 컨트롤러 VID/PID.
# YD-ESP32-S3(ESP32-S3N16R8)는 USB-C UART 포트가 이 식별자로 잡힙니다.
#   예) Bus 001 Device 009: ID 303a:4001 Espressif Systems Espressif Device
ESPRESSIF_VID = "303a"

# Espressif가 사용하는 대표적인 PID 목록(소문자 4자리, '0x' 없음).
#   4001: USB-Serial-JTAG (S3/C3 등 네이티브 USB)
#   1001: CP210x 류 외장 브리지를 쓰는 일부 보드에서 관찰됨
#   0002: ESP32-S2/S3 USB-OTG/CDC 등
# 외장 USB-UART 브리지(CP2102, CH340 등)를 쓰는 보드도 있으므로
# VID/PID가 목록에 없어도 "미확인 보드"로 검사는 진행합니다.
ESPRESSIF_PIDS = {"4001", "1001", "0002", "0009"}

# 외장 USB-UART 브리지 칩 VID(참고용). 이 경우 시리얼 포트는 잡히지만
# VID는 Espressif가 아닙니다.
KNOWN_BRIDGE_VIDS = {
    "10c4": "Silicon Labs (CP210x)",
    "1a86": "QinHeng (CH340/CH9102)",
    "0403": "FTDI",
}

# ---------------------------------------------------------------------------
# 시리얼 포트
# ---------------------------------------------------------------------------
# 리눅스에서 ESP32-S3가 잡히는 시리얼 포트 glob 패턴.
#   /dev/ttyACM* : 네이티브 USB-Serial-JTAG (CDC-ACM)
#   /dev/ttyUSB* : 외장 USB-UART 브리지
SERIAL_PORT_GLOBS = ["/dev/ttyACM*", "/dev/ttyUSB*"]

# 기본 통신 속도. 네이티브 USB-Serial-JTAG는 보율을 무시하지만
# 외장 브리지 호환을 위해 표준값을 사용합니다.
DEFAULT_BAUD = 115200

# 진단 펌웨어가 시리얼로 결과를 출력할 때 사용하는 보율.
FIRMWARE_MONITOR_BAUD = 115200

# ---------------------------------------------------------------------------
# 타임아웃 (초)
# ---------------------------------------------------------------------------
SERIAL_OPEN_TIMEOUT = 2.0       # UART 포트 open 시도 타임아웃
ESPTOOL_TIMEOUT = 30.0          # esptool 단일 명령 타임아웃
FIRMWARE_FLASH_TIMEOUT = 120.0  # 진단 펌웨어 flash 타임아웃
# 진단 펌웨어 출력 대기 타임아웃. 부팅 후 검사를 1회 수행한 뒤 첫 사이클을
# 출력하는데, WiFi 접속 테스트(최대 ~12초)까지 끝나야 하므로 넉넉히 둔다.
FIRMWARE_MONITOR_TIMEOUT = 45.0

# ---------------------------------------------------------------------------
# 경로
# ---------------------------------------------------------------------------
# 이 파일이 위치한 디렉터리(tools/board_check).
BASE_DIR = Path(__file__).resolve().parent

# 검사 결과(JSON/로그) 저장 디렉터리.
RESULTS_DIR = BASE_DIR / "results"

# 진단 펌웨어 소스 및 빌드 산출물 경로.
FIRMWARE_DIR = BASE_DIR / "firmware"
# 빌드된 단일 병합 바이너리(esptool로 바로 flash 가능). 빌드 README 참고.
FIRMWARE_BIN = FIRMWARE_DIR / "build" / "diag_merged.bin"

# ---------------------------------------------------------------------------
# esptool
# ---------------------------------------------------------------------------
# 대상 칩 종류. 자동 감지도 가능하지만 명시하면 연결이 빨라집니다.
ESPTOOL_CHIP = "esp32s3"

# 검사 항목 식별자 -> 사람이 읽는 라벨.
# report.py가 이 순서대로 결과를 출력합니다.
CHECK_LABELS = {
    "usb_detection": "USB Detection",
    "uart_connection": "UART Connection",
    "bootloader_access": "Bootloader Access",
    "flash_access": "Flash Access",
    "flash_size": "Flash Size",
    "psram": "PSRAM",
    "rgb_led": "RGB LED",
    "boot_button": "BOOT Button",
    "wifi_scan": "WiFi Scan",
    "wifi_connect": "WiFi Connect",
    "ble": "Bluetooth LE",
    "temperature": "Temperature",
    "gpio": "GPIO",
}

# 전체 결과(Overall)에 영향을 주는 "필수" 검사 항목.
# WiFi/PSRAM은 진단 펌웨어가 있어야 판정 가능하므로, 펌웨어 미사용 시
# SKIP 처리되며 전체 결과를 FAIL로 만들지 않습니다.
REQUIRED_CHECKS = (
    "usb_detection",
    "uart_connection",
    "bootloader_access",
    "flash_access",
    "flash_size",
)

# 검사 결과 상태값.
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIP"

# ---------------------------------------------------------------------------
# Flash 제조사 ID(JEDEC) -> 제조사 이름.
# esptool의 'flash-id'가 보고하는 Manufacturer 코드(16진수)를 해석합니다.
# ---------------------------------------------------------------------------
FLASH_MANUFACTURERS = {
    "ef": "Winbond",
    "c8": "GigaDevice",
    "c2": "Macronix",
    "20": "XMC / Micron",
    "9d": "ISSI",
    "1c": "EON",
    "01": "Spansion / Cypress",
    "0b": "XTX",
    "68": "Boya",
    "5e": "Zbit",
    "85": "Puya",
    "a1": "Fudan",
}


def manufacturer_name(code: str | None) -> str:
    """Flash 제조사 16진수 코드를 사람이 읽는 이름으로 변환."""
    if not code:
        return "Unknown"
    code = code.lower().replace("0x", "").strip()
    return FLASH_MANUFACTURERS.get(code, f"Unknown (0x{code})")


def ensure_results_dir() -> Path:
    """결과 저장 디렉터리를 생성(이미 있으면 무시)하고 경로를 반환."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR


# ---------------------------------------------------------------------------
# 사용자 설정 파일 (config/wifi_config.yaml)
# ---------------------------------------------------------------------------
# 프로젝트 공통 WiFi 자격증명을 루트 config/wifi_config.yaml 에서 읽는다(board_check 와
# CSI GUI/web 이 공유). 자격증명을 포함하지만 사용자 요청으로 commit 에 포함한다.
# 값은 실행 시 런타임에 읽혀 시리얼로 펌웨어에 주입된다(빌드 시 주입 아님).
# PyYAML 미설치/파일 부재 시 빈 설정으로 폴백.
USER_CONFIG_YAML = BASE_DIR.parent.parent / "config" / "wifi_config.yaml"

try:
    import yaml  # PyYAML
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


def load_user_config() -> dict:
    """config/wifi_config.yaml 을 읽어 딕셔너리로 반환. 없거나 PyYAML 미설치면 빈 dict."""
    if yaml is None or not USER_CONFIG_YAML.exists():
        return {}
    try:
        with open(USER_CONFIG_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def wifi_credentials() -> tuple[str | None, str | None]:
    """config/wifi_config.yaml 의 wifi.ssid / wifi.password 를 (ssid, password) 로 반환."""
    cfg = load_user_config()
    wifi = cfg.get("wifi") or {}
    if not isinstance(wifi, dict):
        return None, None
    return wifi.get("ssid"), wifi.get("password")
