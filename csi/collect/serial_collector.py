#!/usr/bin/env python3
"""ESP32-S3 CSI 수신 펌웨어(csi_recv)의 시리얼 출력을 파일로 수집한다.

csi_recv 펌웨어는 USB-Serial 로 아래 형식의 CSV 라인을 내보낸다(자세한 포맷은
`csi/firmware/csi_recv/main/app_main.c` 의 ets_printf 참조):

    type,seq,mac,rssi,...,data           <- 헤더(1회)
    CSI_DATA,<seq>,<mac>,...,"[v1,v2,...]"  <- 데이터(매 패킷)

이 스크립트는 포트에서 라인을 읽어 그대로 .csv 로 저장하는 **얇은 수집기**다.
파싱/전처리는 `csi/analysis/` 단계에서 한다(수집 단계는 손실 없이 raw 보존이 목표).

포트 지정:
  1) --port 로 직접:   --port /dev/ttyACM0
  2) --role 로 자동:   --role rx
        (연결 보드를 실시간 감지해 펌웨어 DEVICE_ROLE 로 role 을 판별 — config_devices.yaml 불필요)

사용 예:
    python serial_collector.py --role rx --out ../../results/csi_run01.csv
    python serial_collector.py --port /dev/ttyACM0 --duration 30   # 30초만 수집
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import TextIO

try:
    import serial  # pyserial
except ImportError:  # pragma: no cover - 의존성 미설치 폴백
    serial = None  # type: ignore[assignment]

# role 로 포트를 찾을 때 csi/common 의 보드/role 감지를 쓴다(config_devices.yaml
# 의존 제거 — 연결 보드를 실시간 감지해 펌웨어 DEVICE_ROLE 로 role 을 판별).
_COMMON = Path(__file__).resolve().parent.parent / "common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))
try:
    import boards as _boards  # type: ignore
    import role_detect as _role_detect  # type: ignore
except ImportError:  # pragma: no cover
    _boards = None  # type: ignore[assignment]
    _role_detect = None  # type: ignore[assignment]

# csi_recv/sdkconfig.defaults 의 CONFIG_ESP_CONSOLE_UART_BAUDRATE 와 일치해야 한다.
DEFAULT_BAUDRATE = 921600
# 데이터 라인 접두사. 이 값으로 시작하는 라인만 CSI 패킷으로 간주한다.
CSI_LINE_PREFIX = "CSI_DATA"


def open_serial(port: str, baudrate: int) -> "serial.Serial":
    """시리얼 포트를 연다. 권한 부족(/dev/ttyACM*)은 친절히 안내하고 종료한다."""
    if serial is None:
        sys.exit("pyserial 이 필요합니다:  pip install -r requirements.txt")
    try:
        return serial.Serial(port, baudrate, timeout=1)
    except serial.SerialException as exc:  # type: ignore[union-attr]
        # CLAUDE.md 규칙: 권한 부족 시 크래시하지 말고 안내한다.
        msg = str(exc)
        if "Permission denied" in msg or "could not open port" in msg:
            sys.exit(
                f"포트 열기 실패: {port}\n"
                f"  - 권한 문제일 수 있습니다. 'sudo usermod -aG dialout $USER' 후 재로그인,\n"
                f"  - 또는 포트가 맞는지 'ls /dev/ttyACM*' 로 확인하세요.\n"
                f"  원본 오류: {msg}"
            )
        sys.exit(f"포트 열기 실패: {msg}")


def collect(
    port: str,
    baudrate: int,
    out_path: Path,
    duration: float | None,
    only_csi: bool,
) -> int:
    """시리얼 라인을 out_path 로 기록한다. 기록한 CSI 데이터 라인 수를 반환한다."""
    ser = open_serial(port, baudrate)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stop = {"flag": False}

    def _handle_sigint(_signum: int, _frame: object) -> None:
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handle_sigint)

    start = time.monotonic()
    csi_count = 0
    print(f"[collect] {port} @ {baudrate}bps → {out_path}  (Ctrl+C 로 중단)")

    fh: TextIO
    with out_path.open("w", encoding="utf-8") as fh:
        while not stop["flag"]:
            if duration is not None and (time.monotonic() - start) >= duration:
                break
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue
            is_csi = line.startswith(CSI_LINE_PREFIX)
            # only_csi=True 면 CSI 데이터 라인만, 아니면 헤더/로그도 함께 저장.
            if only_csi and not is_csi:
                continue
            fh.write(line + "\n")
            if is_csi:
                csi_count += 1
                if csi_count % 100 == 0:
                    print(f"\r[collect] CSI 패킷 {csi_count}개 수집...", end="", flush=True)

    ser.close()
    print(f"\n[collect] 완료. CSI 패킷 {csi_count}개 저장 → {out_path}")
    return csi_count


def resolve_port(args: argparse.Namespace) -> str:
    """--port 직접 지정, 또는 --role 로 연결 보드를 실시간 감지해 포트를 정한다."""
    if args.port:
        return args.port
    if args.role:
        if _boards is None or _role_detect is None:
            sys.exit("csi/common 을 불러올 수 없습니다. --port 로 직접 지정하세요.")
        cands: list[str] = []
        for b in _boards.discover():
            role, _src = _role_detect.detect_role(b.port)
            if role == args.role:
                cands.append(b.port)
        if not cands:
            sys.exit(
                f"role='{args.role}' 인 연결된 보드를 찾지 못했습니다"
                f"(펌웨어 DEVICE_ROLE 출력을 확인하세요)."
            )
        if len(cands) > 1:
            sys.exit(
                f"role='{args.role}' 보드가 여러 개입니다({', '.join(cands)}). "
                f"--port 로 직접 지정하세요."
            )
        return cands[0]
    sys.exit("--port 또는 --role 중 하나는 지정해야 합니다.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ESP32-S3 CSI 시리얼 수집기")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--port", help="시리얼 포트 직접 지정 (예: /dev/ttyACM0)")
    src.add_argument("--role", choices=["tx", "rx"],
                     help="연결 보드를 실시간 감지해 role(tx/rx) 로 선택")
    p.add_argument("--baud", type=int, default=DEFAULT_BAUDRATE, help="보드레이트")
    p.add_argument(
        "--out",
        type=Path,
        default=Path("csi_capture.csv"),
        help="출력 CSV 경로",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=None,
        help="수집 시간(초). 미지정 시 Ctrl+C 까지 계속.",
    )
    p.add_argument(
        "--all-lines",
        action="store_true",
        help="CSI 데이터 외 헤더/로그 라인도 함께 저장.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    port = resolve_port(args)
    collect(
        port=port,
        baudrate=args.baud,
        out_path=args.out,
        duration=args.duration,
        only_csi=not args.all_lines,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
