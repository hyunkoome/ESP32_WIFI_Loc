"""
serial_check.py
===============
시리얼(UART) 포트가 정상적으로 열리는지 검사하는 모듈.

검사 내용:
  - 포트 접근 권한(읽기/쓰기) 확인 -> 권한 부족 시 명확한 안내 메시지.
  - pyserial로 포트 open 시도.
  - DTR/RTS 토글로 리셋 신호 라인이 동작하는지 확인(네이티브 USB-Serial-JTAG
    에서는 무해하며, 외장 브리지에서는 보드 리셋을 유발할 수 있음).

이 검사가 PASS면 "UART Connection" 항목이 PASS가 됩니다.
"""

from __future__ import annotations

import os
import time
from typing import Dict

import config

try:
    import serial  # pyserial
except Exception:  # pragma: no cover
    serial = None


def access_hint(port: str) -> str:
    """포트 권한 문제에 대한 해결 안내 문자열을 생성."""
    return (
        f"'{port}' 접근 권한이 없습니다. 아래 중 하나로 해결하세요:\n"
        f"      1) (권장) 현재 사용자를 dialout 그룹에 추가 후 재로그인:\n"
        f"           sudo usermod -aG dialout $USER\n"
        f"         (적용하려면 로그아웃/로그인 또는 'newgrp dialout' 필요)\n"
        f"      2) 진단 도구를 sudo 권한으로 실행: main.py 에 --sudo 옵션 사용\n"
        f"      3) 일시적 권한 부여: sudo chmod a+rw {port}"
    )


def test_uart_open(
    port: str, baud: int = config.DEFAULT_BAUD, timeout: float = config.SERIAL_OPEN_TIMEOUT
) -> Dict[str, object]:
    """
    UART 포트 open 검사를 수행하고 결과 딕셔너리를 반환.

    반환 키:
      uart_open  : bool       open 성공 여부
      accessible : bool       파일 권한(R/W) 보유 여부
      toggled    : bool       DTR/RTS 토글 성공 여부
      error      : str|None   실패 사유
    """
    result: Dict[str, object] = {
        "port": port,
        "uart_open": False,
        "accessible": os.access(port, os.R_OK | os.W_OK),
        "toggled": False,
        "error": None,
    }

    # pyserial 미설치 시 즉시 실패 처리(설치 안내).
    if serial is None:
        result["error"] = "pyserial 미설치 — 'pip install -r requirements.txt' 필요"
        return result

    # 파일 권한이 아예 없으면 open 시도조차 의미 없음 -> 친절한 안내.
    if not result["accessible"]:
        result["error"] = access_hint(port)
        return result

    ser = None
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=timeout)
        result["uart_open"] = True
        # DTR/RTS 토글(리셋 라인 점검). 실패해도 open 자체는 성공으로 둔다.
        try:
            ser.dtr = False
            ser.rts = False
            time.sleep(0.05)
            ser.dtr = True
            ser.rts = True
            result["toggled"] = True
        except Exception as exc:  # 일부 드라이버는 라인 제어 미지원
            result["toggled"] = False
            result["error"] = f"DTR/RTS 토글 경고: {exc}"
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        print(test_uart_open(sys.argv[1]))
    else:
        print("사용법: serial_check.py /dev/ttyACM0")
