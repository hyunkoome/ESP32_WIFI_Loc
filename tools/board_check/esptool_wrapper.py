"""
esptool_wrapper.py
==================
esptool을 서브프로세스로 호출해 칩/Flash/MAC 정보를 수집하는 래퍼.

설계 포인트:
  - 현재 파이썬 인터프리터(sys.executable)로 'python -m esptool'을 실행한다.
    => venv에 설치된 esptool을 PATH 설정과 무관하게 항상 사용.
  - esptool v4(언더스코어 명령: chip_id)와 v5(하이픈 명령: chip-id)를
    모두 지원하기 위해 버전을 감지해 명령 이름을 매핑한다.
  - 권한 부족 시 sudo로 재실행하는 옵션(use_sudo)을 제공한다.
  - esptool 출력(stdout/stderr)을 정규식으로 파싱해 구조화한다.

주의: 네이티브 USB-Serial-JTAG(ESP32-S3) 보드는 esptool이 자동 리셋으로
부트로더에 진입하므로 BOOT 버튼 조작이 필요 없습니다. 따라서 esptool 연결
성공은 곧 "부트로더 접근 + 칩 리셋 + UART 통신"이 모두 정상임을 의미합니다.
"""

from __future__ import annotations

import re
import subprocess
import sys
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import config


# ---------------------------------------------------------------------------
# esptool 실행
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def esptool_version() -> Optional[str]:
    """설치된 esptool 버전 문자열(예: '5.3.0')을 반환. 없으면 None."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "esptool", "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
        )
    except Exception:
        return None
    # 출력 어딘가의 'x.y.z' 패턴을 찾는다.
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", proc.stdout or "")
    return match.group(1) if match else None


@lru_cache(maxsize=1)
def _major_version() -> int:
    """esptool 메이저 버전 정수. 알 수 없으면 5로 가정(하이픈 명령)."""
    ver = esptool_version()
    if not ver:
        return 5
    try:
        return int(ver.split(".")[0])
    except Exception:
        return 5


def _cmd(name: str) -> str:
    """
    논리적 명령 이름을 esptool 버전에 맞는 실제 서브커맨드로 변환.
    name은 항상 하이픈 형식('chip-id', 'flash-id', 'read-mac', 'read-flash')으로 전달.
    v4 이하에서는 언더스코어로 변환한다.
    """
    if _major_version() >= 5:
        return name
    return name.replace("-", "_")


def run_esptool(
    port: str,
    command: str,
    extra_args: Optional[List[str]] = None,
    use_sudo: bool = False,
    timeout: float = config.ESPTOOL_TIMEOUT,
    chip: str = config.ESPTOOL_CHIP,
) -> Tuple[int, str]:
    """
    esptool 단일 명령을 실행하고 (returncode, 결합된 출력)을 반환.

    command : 하이픈 형식 논리 명령('chip-id' 등). 내부에서 버전에 맞게 변환.
    use_sudo: True면 sudo로 실행(비밀번호 입력은 호출한 터미널에서 처리됨).
    """
    cmd: List[str] = [sys.executable, "-m", "esptool", "--chip", chip, "--port", port]
    cmd.append(_cmd(command))
    if extra_args:
        cmd.extend(extra_args)
    if use_sudo:
        # sudo로 동일 인터프리터/모듈을 실행. -E 로 환경변수 유지.
        cmd = ["sudo", "-E"] + cmd

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 파싱 편의를 위해 stderr를 stdout에 합침
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or ""
    except subprocess.TimeoutExpired:
        return 1, f"[timeout] esptool '{command}' 가 {timeout}s 내 응답하지 않음"
    except FileNotFoundError as exc:
        return 1, f"[not-found] {exc}"
    except Exception as exc:  # 예기치 못한 오류도 결과로 반환(크래시 방지)
        return 1, f"[error] {exc}"


# ---------------------------------------------------------------------------
# 출력 파싱
# ---------------------------------------------------------------------------
# esptool 연결 배너는 버전에 따라 라벨이 다르므로 v4/v5 양쪽을 모두 매칭한다.
#   esptool v4 예:
#     Chip is ESP32-S3 (QFN56) (revision v0.2)
#     Crystal is 40MHz
#   esptool v5 예:
#     Connected to ESP32-S3 on /dev/ttyACM0:
#     Chip type:          ESP32-S3 (QFN56) (revision v0.2)
#     Features:           Wi-Fi, BT 5 (LE), Dual Core + LP Core, 240MHz, Embedded PSRAM 8MB
#     Crystal frequency:  40MHz
#     MAC:                1c:db:d4:45:7b:30
# => 'Chip is'(v4) 와 'Chip type:'(v5), 'Crystal is'(v4) 와 'Crystal frequency:'(v5) 둘 다 처리.
_RE_CHIP = re.compile(r"Chip (?:is|type:)\s+([A-Za-z0-9\-]+)", re.IGNORECASE)
# 연결 성공 판정: 'Chip is/type:' 또는 v5 의 'Connected to <chip> on' 중 하나만 있으면 OK.
_RE_CONNECTED = re.compile(
    r"(?:Chip (?:is|type:)|Connected to)\s+[A-Za-z0-9\-]+", re.IGNORECASE
)
_RE_REVISION = re.compile(r"revision\s+v?([0-9.]+)", re.IGNORECASE)
_RE_FEATURES = re.compile(r"Features:\s*(.+)")
_RE_CRYSTAL = re.compile(r"Crystal (?:is|frequency:)\s+([0-9]+\s*MHz)", re.IGNORECASE)
_RE_MAC = re.compile(r"MAC:\s*([0-9A-Fa-f:]{17})")
# flash-id 출력(라벨이 'Flash ' 접두어가 붙는 v5 변형도 함께 처리):
#   Manufacturer: ef        / Flash Manufacturer: ef
#   Device: 4018            / Flash Device: 4018
#   Detected flash size: 16MB / Flash size: 16MB
_RE_FLASH_MFR = re.compile(r"(?:Flash\s+)?Manufacturer:\s*([0-9A-Fa-f]+)", re.IGNORECASE)
_RE_FLASH_DEV = re.compile(r"(?:Flash\s+)?Device:\s*([0-9A-Fa-f]+)", re.IGNORECASE)
_RE_FLASH_SIZE = re.compile(
    r"(?:Detected flash size|Flash size):\s*([0-9]+\s*[KMG]B)", re.IGNORECASE
)


def _search(pattern: re.Pattern, text: str) -> Optional[str]:
    """정규식 첫 매치의 그룹1을 strip해 반환(없으면 None)."""
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _connected(text: str) -> bool:
    """출력에 칩 식별 배너('Chip is/type:' 또는 'Connected to ...')가 있으면 연결 성공."""
    return _RE_CONNECTED.search(text) is not None


def get_chip_info(port: str, use_sudo: bool = False) -> Dict[str, object]:
    """
    esptool로 칩/Flash/MAC 정보를 수집해 구조화된 딕셔너리로 반환.

    최소한의 연결 횟수(기본 2회: flash-id, 필요 시 read-mac)로 다음을 수집:
      connected, chip, revision, features, crystal_freq, mac,
      flash_manufacturer_code, flash_manufacturer, flash_device,
      flash_size, raw_output, error

    'flash-id' 명령은 연결 배너(칩/리비전/크리스털/MAC)와 Flash 정보를 함께
    출력하므로 한 번의 연결로 대부분의 정보를 얻습니다.
    """
    info: Dict[str, object] = {
        "port": port,
        "connected": False,
        "chip": None,
        "revision": None,
        "features": None,
        "crystal_freq": None,
        "mac": None,
        "flash_manufacturer_code": None,
        "flash_manufacturer": None,
        "flash_device": None,
        "flash_size": None,
        "error": None,
    }

    # 1) flash-id: 칩 배너 + Flash 정보를 한 번에.
    rc, out = run_esptool(port, "flash-id", use_sudo=use_sudo)
    info["raw_output"] = out
    info["connected"] = _connected(out)

    if info["connected"]:
        info["chip"] = _search(_RE_CHIP, out)
        info["revision"] = _search(_RE_REVISION, out)
        info["features"] = _search(_RE_FEATURES, out)
        info["crystal_freq"] = _search(_RE_CRYSTAL, out)
        info["mac"] = _search(_RE_MAC, out)
        mfr_code = _search(_RE_FLASH_MFR, out)
        info["flash_manufacturer_code"] = mfr_code
        info["flash_manufacturer"] = config.manufacturer_name(mfr_code)
        info["flash_device"] = _search(_RE_FLASH_DEV, out)
        info["flash_size"] = _search(_RE_FLASH_SIZE, out)
    else:
        # 연결 실패 사유를 간결히 기록(권한/포트 사용중/하드웨어 등).
        info["error"] = _summarize_failure(out)
        return info

    # 2) MAC이 비어 있으면 read-mac으로 보강.
    if not info["mac"]:
        rc2, out2 = run_esptool(port, "read-mac", use_sudo=use_sudo)
        info["mac"] = _search(_RE_MAC, out2)

    return info


def _summarize_failure(text: str) -> str:
    """esptool 실패 출력에서 핵심 원인을 한 줄로 추려 반환."""
    lowered = text.lower()
    if "permission denied" in lowered:
        return "권한 거부 (dialout 그룹 추가 또는 --sudo 필요)"
    if "could not open" in lowered or "device or resource busy" in lowered:
        return "포트를 열 수 없음 (다른 프로그램이 사용 중이거나 포트 오류)"
    if "no serial data" in lowered or "failed to connect" in lowered:
        return "칩 연결 실패 (USB 케이블/보드 확인, BOOT 모드 필요 가능)"
    if "[timeout]" in lowered:
        return "esptool 응답 타임아웃"
    if "no module named esptool" in lowered:
        return "esptool 미설치 — 'pip install -r requirements.txt' 필요"
    # 마지막 비어있지 않은 줄을 원인으로.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1][:200] if lines else "알 수 없는 오류"


def read_flash_test(
    port: str, length: int = 0x1000, use_sudo: bool = False
) -> Dict[str, object]:
    """
    Flash 읽기 가능 여부를 검증. 0x0부터 length 바이트를 임시로 읽어 본다.

    실제 데이터를 디스크에 저장하지 않기 위해 esptool의 read-flash를 쓰되,
    임시 파일에 저장 후 크기를 확인하고 삭제한다.
    """
    import os
    import tempfile

    result: Dict[str, object] = {"flash_read_ok": False, "bytes": 0, "error": None}
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="esp_flash_", suffix=".bin")
        os.close(fd)
        rc, out = run_esptool(
            port,
            "read-flash",
            extra_args=["0x0", hex(length), tmp_path],
            use_sudo=use_sudo,
            timeout=config.ESPTOOL_TIMEOUT,
        )
        size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
        result["bytes"] = size
        # 요청한 길이만큼(혹은 그 이상) 읽혔고 esptool도 성공이면 PASS.
        result["flash_read_ok"] = rc == 0 and size >= length
        if not result["flash_read_ok"]:
            result["error"] = _summarize_failure(out)
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(f"esptool version: {esptool_version()}")
        from pprint import pprint

        pprint(get_chip_info(sys.argv[1]))
    else:
        print("사용법: esptool_wrapper.py /dev/ttyACM0")
