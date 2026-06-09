#!/usr/bin/env python3
"""csi_recv 가 출력한 CSV 라인을 파싱해 진폭/위상 배열로 변환한다.

csi_recv 펌웨어는 마지막 컬럼 `data` 에 CSI raw 값을 `"[i0,q0,i1,q1,...]"` 형태로
싣는다. 각 (i, q) 쌍이 한 서브캐리어의 복소수(허수부 q, 실수부 i)다.
이 모듈은 그 배열을 numpy 복소 배열 → 진폭/위상으로 풀어준다.

수집(raw 보존)은 `csi/collect/serial_collector.py`, 학습/추론은 `sensing/` 에서 한다.
이 파일은 그 사이의 **파싱·전처리 유틸**이다.

전체 GUI 뷰어가 필요하면 같은 디렉터리의 `csi_data_read_parse_ref.py`(esp-csi
원본, PyQt5 기반)를 참고하라. 이 모듈은 헤드리스/배치 처리에 맞춘 경량 버전이다.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]

CSI_LINE_PREFIX = "CSI_DATA"
# data 컬럼은 "[1,2,3,...]" 형태의 따옴표 묶인 정수 배열.
_DATA_ARRAY_RE = re.compile(r"\[(.*?)\]")


@dataclass
class CsiPacket:
    """파싱된 CSI 패킷 한 개."""

    seq: int
    mac: str
    rssi: int
    raw_fields: dict[str, str] = field(default_factory=dict)
    # (i0, q0, i1, q1, ...) 정수 배열 그대로.
    raw_csi: list[int] = field(default_factory=list)

    def to_complex(self) -> "np.ndarray":
        """raw_csi 의 (i, q) 쌍을 복소수 배열로 변환한다."""
        if np is None:
            raise ImportError("numpy 가 필요합니다:  pip install -r requirements.txt")
        arr = np.asarray(self.raw_csi, dtype=np.float32)
        # 짝수개여야 (i, q) 쌍이 맞는다. 홀수면 마지막 값 버림.
        if arr.size % 2 != 0:
            arr = arr[:-1]
        i = arr[0::2]
        q = arr[1::2]
        return i + 1j * q

    def amplitude(self) -> "np.ndarray":
        """서브캐리어별 진폭(|H|)."""
        return np.abs(self.to_complex())

    def phase(self) -> "np.ndarray":
        """서브캐리어별 위상(rad)."""
        return np.angle(self.to_complex())


def _parse_data_array(data_field: str) -> list[int]:
    """`"[1,2,3]"` 또는 `[1,2,3]` 문자열에서 정수 리스트를 뽑는다."""
    m = _DATA_ARRAY_RE.search(data_field)
    if not m:
        return []
    body = m.group(1).strip()
    if not body:
        return []
    out: list[int] = []
    for tok in body.split(","):
        tok = tok.strip()
        if tok:
            try:
                out.append(int(tok))
            except ValueError:
                # 손상된 토큰은 건너뛴다(시리얼 노이즈 대비).
                continue
    return out


def parse_line(line: str, header: list[str] | None = None) -> CsiPacket | None:
    """CSI_DATA 라인 하나를 CsiPacket 으로 파싱한다. 아니면 None."""
    line = line.strip()
    if not line.startswith(CSI_LINE_PREFIX):
        return None
    # data 컬럼에 콤마가 들어있어 단순 split 으로는 안 된다.
    # 마지막 '"[ ... ]"' 부분을 먼저 떼어내고 앞부분만 콤마 분리한다.
    bracket_idx = line.find("[")
    if bracket_idx == -1:
        return None
    meta_part = line[:bracket_idx].rstrip(',').rstrip('"').rstrip(",")
    data_part = line[bracket_idx:]
    fields = meta_part.split(",")

    raw_csi = _parse_data_array(data_part)
    raw_fields: dict[str, str] = {}
    if header is not None:
        for key, val in zip(header, fields):
            raw_fields[key] = val

    # 위치 기반 핵심 필드(헤더 유무와 무관하게 항상 같은 순서).
    # 0:type 1:seq 2:mac 3:rssi ...
    try:
        seq = int(fields[1])
        mac = fields[2]
        rssi = int(fields[3])
    except (IndexError, ValueError):
        return None

    return CsiPacket(seq=seq, mac=mac, rssi=rssi, raw_fields=raw_fields, raw_csi=raw_csi)


def iter_packets(csv_path: Path) -> Iterator[CsiPacket]:
    """수집된 CSV 파일을 순회하며 CsiPacket 을 yield 한다.

    헤더 라인(type,seq,...)이 있으면 raw_fields 키로 활용한다.
    """
    header: list[str] | None = None
    with Path(csv_path).open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line:
                continue
            if line.startswith("type,"):
                header = next(csv.reader([line]))
                continue
            pkt = parse_line(line, header)
            if pkt is not None:
                yield pkt


def _main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="수집된 CSI CSV 파싱 요약")
    p.add_argument("csv", type=Path, help="serial_collector.py 가 만든 CSV")
    p.add_argument("-n", "--limit", type=int, default=5, help="미리볼 패킷 수")
    args = p.parse_args(argv)

    count = 0
    for pkt in iter_packets(args.csv):
        if count < args.limit:
            n_sub = len(pkt.raw_csi) // 2
            print(f"seq={pkt.seq} mac={pkt.mac} rssi={pkt.rssi} subcarriers={n_sub}")
        count += 1
    print(f"총 {count}개 CSI 패킷.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
