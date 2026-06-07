"""
report.py
=========
진단 결과를 (1) 컬러 터미널로 출력하고 (2) JSON/로그 파일로 저장하는 모듈.

콘솔 출력은 colorama로 PASS=초록/FAIL=빨강/SKIP=노랑을 표시합니다.
colorama가 없으면 색 없이 일반 텍스트로 폴백합니다.

저장 형식:
  results/board_test_YYYYMMDD_HHMMSS.json   # 구조화된 전체 결과
  results/board_test_YYYYMMDD_HHMMSS.log    # 사람이 읽는 로그(콘솔과 동일)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import config

try:
    from colorama import Fore, Style
    from colorama import init as colorama_init

    colorama_init()
    _COLOR = True
except Exception:  # pragma: no cover - colorama 미설치 폴백
    _COLOR = False

    class _Dummy:
        def __getattr__(self, _):
            return ""

    Fore = Style = _Dummy()  # type: ignore


# 상태값 -> 색.
_STATUS_COLOR = {
    config.STATUS_PASS: Fore.GREEN,
    config.STATUS_FAIL: Fore.RED,
    config.STATUS_SKIP: Fore.YELLOW,
}


def _c(text: str, color: str) -> str:
    """색이 가능하면 색을 입혀 반환."""
    if not _COLOR:
        return text
    return f"{color}{text}{Style.RESET_ALL}"


def _status_tag(status: str) -> str:
    """상태값을 색 입힌 라벨로."""
    return _c(status, _STATUS_COLOR.get(status, ""))


def format_board(result: Dict[str, object]) -> str:
    """보드 1대 결과를 사람이 읽는 멀티라인 문자열로 변환."""
    lines: List[str] = []
    index = result.get("board_index")
    port = result.get("port")
    usb = result.get("usb", {})
    chip = result.get("chip", {})

    lines.append("")
    lines.append(_c(f"## Board #{index}", Fore.CYAN + Style.BRIGHT))
    lines.append(f"  Port        : {port}")
    lines.append(f"  VID:PID     : {usb.get('vid_pid')}")
    if usb.get("serial"):
        lines.append(f"  USB Serial  : {usb.get('serial')}")
    if chip.get("chip"):
        lines.append(
            f"  Chip        : {chip.get('chip')} "
            f"(rev {chip.get('revision')}, {chip.get('crystal_freq')})"
        )
    if chip.get("mac"):
        lines.append(f"  MAC Address : {chip.get('mac')}")
    if chip.get("features"):
        lines.append(f"  Features    : {chip.get('features')}")
    lines.append("")

    # 검사 항목 표 — config.CHECK_LABELS 순서대로.
    checks: Dict[str, Dict] = result.get("checks", {})
    label_width = max(len(v) for v in config.CHECK_LABELS.values())
    for key, label in config.CHECK_LABELS.items():
        item = checks.get(key)
        if not item:
            continue
        status = item.get("status", "")
        detail = item.get("detail", "")
        line = f"  {label.ljust(label_width)} : {_status_tag(status)}"
        if detail:
            line += f"   {Style.DIM if _COLOR else ''}{detail}{Style.RESET_ALL if _COLOR else ''}"
        lines.append(line)

    # 스트레스 테스트 결과(있을 때).
    stress = result.get("stress")
    if stress:
        lines.append("")
        st = stress.get("status", "")
        lines.append(
            f"  Stress Test : {_status_tag(st)}   "
            f"{stress.get('iterations')}회 중 실패 {stress.get('failures')} "
            f"(성공률 {stress.get('success_rate')}%)"
        )
        for d in stress.get("fail_details", []):
            lines.append(f"      - {d}")

    # 오류 모음(있을 때).
    errors = result.get("errors") or []
    if errors:
        lines.append("")
        lines.append(_c("  Errors:", Fore.RED))
        for e in errors:
            lines.append(f"    - {e}")

    # 전체 결과.
    lines.append("")
    overall = result.get("overall", "")
    lines.append(f"  Overall Result : {_status_tag(overall)}")
    lines.append("  " + "-" * 50)
    return "\n".join(lines)


def print_report(results: List[Dict[str, object]]) -> str:
    """모든 보드 결과를 콘솔에 출력하고, 출력에 쓴 평문 텍스트를 반환(로그 저장용)."""
    blocks = [format_board(r) for r in results]
    body = "\n".join(blocks)
    print(body)

    # 요약.
    total = len(results)
    passed = sum(1 for r in results if r.get("overall") == config.STATUS_PASS)
    failed = total - passed
    summary = (
        f"\n총 {total}대 검사 — "
        f"{_c(f'PASS {passed}', Fore.GREEN)} / {_c(f'FAIL {failed}', Fore.RED)}\n"
    )
    print(summary)
    # 로그 파일에는 색 코드 없이 저장하기 위해 평문 버전을 따로 구성.
    return _strip_for_log(results)


def _strip_for_log(results: List[Dict[str, object]]) -> str:
    """색 코드 없는 평문 리포트(로그 파일용)를 생성."""
    global _COLOR
    saved = _COLOR
    _COLOR = False
    try:
        blocks = [format_board(r) for r in results]
        total = len(results)
        passed = sum(1 for r in results if r.get("overall") == config.STATUS_PASS)
        text = "\n".join(blocks)
        text += f"\n\n총 {total}대 검사 — PASS {passed} / FAIL {total - passed}\n"
        return text
    finally:
        _COLOR = saved


def save_results(
    results: List[Dict[str, object]], timestamp: str, log_text: Optional[str] = None
) -> Dict[str, Path]:
    """
    결과를 JSON과 로그 파일로 저장하고 저장 경로를 반환.

    timestamp : 파일명에 쓸 시각 문자열(예: '20260607_142530'). 호출자가 생성.
                (스크립트 환경에서 시각 생성이 제한될 수 있어 인자로 받음)
    """
    out_dir = config.ensure_results_dir()
    json_path = out_dir / f"board_test_{timestamp}.json"
    log_path = out_dir / f"board_test_{timestamp}.log"

    payload = {
        "timestamp": timestamp,
        "board_count": len(results),
        "pass_count": sum(
            1 for r in results if r.get("overall") == config.STATUS_PASS
        ),
        "boards": results,
    }
    # raw_output(대용량) 은 JSON 가독성을 위해 제외하고 저장.
    cleaned = json.loads(json.dumps(payload, default=str))
    for b in cleaned.get("boards", []):
        if isinstance(b.get("chip"), dict):
            b["chip"].pop("raw_output", None)

    json_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2))
    if log_text is None:
        log_text = _strip_for_log(results)
    log_path.write_text(log_text)

    return {"json": json_path, "log": log_path}
