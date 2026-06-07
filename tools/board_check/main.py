#!/usr/bin/env python3
"""
main.py
=======
ESP32-S3 자동 진단 및 불량 검사 도구의 진입점(CLI).

여러 대의 ESP32-S3를 동시에(병렬) 검사하고, 항목별 PASS/FAIL/SKIP과 전체
결과를 컬러 터미널로 출력한 뒤 JSON/로그로 저장합니다.

사용 예:
    # 연결된 모든 보드 기본 검사
    python main.py

    # 특정 포트만 검사
    python main.py --port /dev/ttyACM0 --port /dev/ttyACM1

    # 권한이 없을 때 sudo로 실행
    sudo python main.py --sudo        # 또는 python main.py --sudo

    # WiFi/PSRAM 런타임 검사까지(진단 펌웨어 필요)
    python main.py --firmware

    # 스트레스 테스트 100회
    python main.py --stress 100

옵션은 --help 참고.
"""

from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

import config
import diagnostics
import esptool_wrapper
import report
import usb_detector

try:
    from colorama import Fore, Style
    from colorama import init as colorama_init

    colorama_init()
except Exception:  # pragma: no cover
    class _Dummy:
        def __getattr__(self, _):
            return ""

    Fore = Style = _Dummy()  # type: ignore


logger = logging.getLogger("board_check")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """CLI 인자 파싱."""
    parser = argparse.ArgumentParser(
        prog="board_check",
        description="ESP32-S3 자동 진단 및 불량 검사 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--port",
        action="append",
        dest="ports",
        metavar="DEV",
        help="검사할 시리얼 포트(여러 번 지정 가능). 미지정 시 자동 탐색.",
    )
    parser.add_argument(
        "--sudo",
        action="store_true",
        help="esptool/펌웨어 명령을 sudo로 실행(포트 권한 부족 시). 비밀번호는 터미널에서 입력.",
    )
    parser.add_argument(
        "--firmware",
        action="store_true",
        help="진단 펌웨어를 flash해 WiFi 스캔/PSRAM 런타임 검사 수행(firmware/ 빌드 필요).",
    )
    parser.add_argument(
        "--stress",
        type=int,
        default=0,
        metavar="N",
        help="스트레스 테스트: esptool 연결을 N회 반복하며 통신 오류 집계(기본 0=비활성).",
    )
    parser.add_argument(
        "--min-ap",
        type=int,
        default=1,
        metavar="N",
        help="WiFi 스캔 PASS 판정 최소 AP 개수(기본 1).",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=0,
        metavar="N",
        help="동시 검사할 보드 수(기본 0=보드 수만큼 자동).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="결과를 파일로 저장하지 않음.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="상세 로그 출력.",
    )
    return parser.parse_args(argv)


def setup_logging(verbose: bool, log_path) -> None:
    """콘솔 + 파일 로깅 설정."""
    level = logging.DEBUG if verbose else logging.INFO
    handlers: List[logging.Handler] = []
    # 파일 핸들러(상세 로그 항상 기록).
    if log_path is not None:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        handlers.append(fh)
    # 콘솔 핸들러(verbose일 때만 INFO 흐름 표시; 기본은 WARNING 이상).
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level if verbose else logging.WARNING)
    ch.setFormatter(logging.Formatter("%(message)s"))
    handlers.append(ch)

    root = logging.getLogger("board_check")
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)


def check_environment() -> bool:
    """필수 도구(esptool) 설치 여부를 확인하고 안내. 진행 가능 여부 반환."""
    ver = esptool_wrapper.esptool_version()
    if ver:
        print(f"{Fore.GREEN}✓{Style.RESET_ALL} esptool {ver} 감지")
        return True
    print(
        f"{Fore.RED}✗ esptool을 찾을 수 없습니다.{Style.RESET_ALL}\n"
        f"  설치: pip install -r requirements.txt   (venv 활성화 후)"
    )
    return False


def select_boards(args: argparse.Namespace) -> List[Dict[str, object]]:
    """검사 대상 보드 목록을 구성(자동 탐색 또는 --port 지정)."""
    if args.ports:
        boards: List[Dict[str, object]] = []
        for i, port in enumerate(args.ports, start=1):
            info = usb_detector.get_usb_info(port)
            info.update(usb_detector.classify(info))
            info["board_index"] = i
            info["port"] = port
            import os

            info["accessible"] = os.access(port, os.R_OK | os.W_OK)
            boards.append(info)
        return boards
    return usb_detector.discover_boards()


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # 시각 문자열(파일명/타임스탬프). 진단 시작 시점 기준.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    config.ensure_results_dir()
    log_path = None if args.no_save else config.RESULTS_DIR / f"board_test_{timestamp}.log"
    setup_logging(args.verbose, log_path)

    print(f"{Style.BRIGHT}ESP32-S3 보드 진단 도구{Style.RESET_ALL}  ({timestamp})")
    print("=" * 56)

    if not check_environment():
        return 2

    boards = select_boards(args)
    if not boards:
        print(
            f"{Fore.YELLOW}연결된 보드를 찾지 못했습니다.{Style.RESET_ALL}\n"
            f"  - USB 케이블 연결 확인\n"
            f"  - 'lsusb | grep 303a' 로 인식 여부 확인\n"
            f"  - 포트 패턴: {', '.join(config.SERIAL_PORT_GLOBS)}"
        )
        return 1

    print(f"\n{len(boards)}대의 보드를 발견했습니다:")
    for b in boards:
        acc = "" if b.get("accessible") else f" {Fore.RED}[권한없음]{Style.RESET_ALL}"
        print(f"  Board #{b['board_index']}  {b['port']}  ({b.get('vid_pid')}){acc}")

    # 권한 없는 보드가 있고 --sudo 미지정이면 안내.
    if any(not b.get("accessible") for b in boards) and not args.sudo:
        print(
            f"\n{Fore.YELLOW}⚠ 일부 포트에 접근 권한이 없습니다.{Style.RESET_ALL}\n"
            f"  해결: sudo usermod -aG dialout $USER  (후 재로그인)\n"
            f"  또는: 이 명령에 --sudo 옵션 추가\n"
        )

    # 진행률 콜백(간단한 라인 출력).
    def progress(msg: str) -> None:
        if args.verbose:
            print(f"  · {msg}")

    print(f"\n진단을 시작합니다... (병렬 {args.jobs or len(boards)}개)\n")

    # 보드별 병렬 검사.
    workers = args.jobs if args.jobs > 0 else len(boards)
    results: List[Dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        future_map = {
            pool.submit(
                diagnostics.diagnose_board,
                board,
                use_sudo=args.sudo,
                use_firmware=args.firmware,
                stress=args.stress,
                min_ap=args.min_ap,
                progress=progress,
            ): board
            for board in boards
        }
        done = 0
        for future in as_completed(future_map):
            board = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:  # 개별 보드 실패가 전체를 막지 않도록.
                logger.exception("보드 진단 중 예외")
                results.append(
                    {
                        "board_index": board.get("board_index"),
                        "port": board.get("port"),
                        "usb": {},
                        "chip": {},
                        "checks": {},
                        "errors": [f"진단 예외: {exc}"],
                        "overall": config.STATUS_FAIL,
                    }
                )
            done += 1
            print(f"  진행률: {done}/{len(boards)} 완료")

    # 보드 번호 순으로 정렬 후 리포트.
    results.sort(key=lambda r: (r.get("board_index") or 0))
    print("\n" + "=" * 56)
    log_text = report.print_report(results)

    # 결과 저장.
    if not args.no_save:
        paths = report.save_results(results, timestamp, log_text=log_text)
        print(f"결과 저장:")
        print(f"  JSON : {paths['json']}")
        print(f"  LOG  : {paths['log']}")

    # 종료 코드: 모두 PASS면 0, 하나라도 FAIL이면 1.
    any_fail = any(r.get("overall") == config.STATUS_FAIL for r in results)
    return 1 if any_fail else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
        sys.exit(130)
