"""포트별 직렬화 락.

같은 시리얼 포트에 flash(esptool)·role 감지·CSI 스트림이 동시에 접근하면
'chip stopped responding' 등으로 깨진다. 포트당 하나의 작업만 돌도록 보장한다.
(tools/board_check/web/app.py 의 _PORT_LOCKS 패턴을 공용 모듈로 추출.)
"""
from __future__ import annotations

import threading

_LOCKS: dict[str, threading.Lock] = {}
_GUARD = threading.Lock()


def port_lock(port: str) -> threading.Lock:
    """포트 문자열에 대응하는 (프로세스 전역) Lock 을 반환."""
    with _GUARD:
        lk = _LOCKS.get(port)
        if lk is None:
            lk = threading.Lock()
            _LOCKS[port] = lk
        return lk
