"""role 펌웨어 빌드(csi_flash.sh --build-only) + flash(--port). web/GUI 공용.

빌드는 ESP-IDF 환경이 필요해 Python 안에서 직접 못 하므로 scripts/csi_flash.sh 를
subprocess 로 호출한다(스크립트가 venv 해제→export.sh→build→merge-bin 처리). flash 는
스크립트가 venv 의 esptool 로 수행한다. 진행 로그는 on_line 콜백으로 한 줄씩 전달한다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

_REPO = Path(__file__).resolve().parents[2]
_FLASH_SH = _REPO / "scripts" / "csi_flash.sh"
_FW = {"tx": "csi_send", "rx": "csi_recv"}

OnLine = Optional[Callable[[str], None]]


def merged_bin(role: str) -> Path:
    """role 의 병합 바이너리 경로(csi_flash.sh 산출물)."""
    return _REPO / "csi" / "firmware" / _FW[role] / "build" / f"{role}_merged.bin"


def is_built(role: str) -> bool:
    return merged_bin(role).exists()


def _run(args: list[str], on_line: OnLine) -> int:
    """csi_flash.sh 를 실행하며 출력을 on_line 으로 스트리밍. 반환 코드."""
    proc = subprocess.Popen(
        ["bash", str(_FLASH_SH), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        if on_line:
            on_line(line.rstrip("\n"))
    proc.wait()
    return proc.returncode


def build(role: str, clean: bool = False, on_line: OnLine = None) -> int:
    """role 펌웨어 빌드 + merge-bin (flash 안 함). 0=성공."""
    if role not in _FW:
        raise ValueError(f"role 은 tx 또는 rx: {role}")
    args = ["--role", role, "--build-only"]
    if clean:
        args.append("--clean")
    return _run(args, on_line)


def flash(role: str, port: str, on_line: OnLine = None) -> int:
    """빌드 산출물을 포트에 flash(빌드 생략). 산출물 없으면 build() 먼저."""
    if role not in _FW:
        raise ValueError(f"role 은 tx 또는 rx: {role}")
    return _run(["--role", role, "--port", port, "--no-build"], on_line)


def build_and_flash(role: str, port: str, clean: bool = False, on_line: OnLine = None) -> int:
    """빌드 + flash 를 한 번에(편의)."""
    if role not in _FW:
        raise ValueError(f"role 은 tx 또는 rx: {role}")
    args = ["--role", role, "--port", port]
    if clean:
        args.append("--clean")
    return _run(args, on_line)


if __name__ == "__main__":
    role = sys.argv[1] if len(sys.argv) > 1 else "rx"
    print(f"role={role}  merged_bin={merged_bin(role)}  built={is_built(role)}")
