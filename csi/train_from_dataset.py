"""dataset/csi_logs 의 각 디바이스·상태별 '가장 최근' CSV 로 학습해 config/motion_detection.yaml
의 classifiers 를 갱신한다(GUI 의 Train 과 동일 로직, GUI 없이 일괄).

판정 기준: presence = std(진폭 변동), motion = doppler(도플러 피크).
  std_th     = (Empty 평균 + Presence 평균) / 2      (Empty↔Presence 경계)
  doppler_th = (Presence 평균 + Motion 평균) / 2      (Presence↔Motion 경계)
Presence 가 없으면 Empty/Motion 으로 추정.

사용: python3 csi/train_from_dataset.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "dataset" / "csi_logs"
YAML = ROOT / "config" / "motion_detection.yaml"
STD_COL, DOPPLER_COL, SRC_COL = 6, 7, 1   # CSV 컬럼 인덱스(t_sec,source,mac,rssi,rate,n_sub,std,doppler,...)


def load_recent(serial: str, mode: str) -> tuple[list, str | None]:
    files = sorted(LOGS.glob(f"log_{mode}_{serial}_*.csv"))   # 파일명 timestamp 순
    if not files:
        return [], None
    rows: list[tuple[float, float]] = []
    source = None
    with open(files[-1], newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)  # 헤더
        for row in rd:
            try:
                rows.append((float(row[STD_COL]), float(row[DOPPLER_COL])))
                if source is None and len(row) > SRC_COL:
                    source = row[SRC_COL]
            except (IndexError, ValueError):
                pass
    return rows, source


def stats(buf: list) -> dict | None:
    if not buf:
        return None
    ss = [s for s, _ in buf]; dd = [d for _, d in buf]
    return {"std_mean": sum(ss) / len(ss), "std_max": max(ss),
            "doppler_mean": sum(dd) / len(dd), "doppler_max": max(dd)}


def mean(xs):
    return sum(xs) / len(xs)


def main() -> None:
    serials = sorted({f.stem.split("_")[2] for f in LOGS.glob("log_*_*_*.csv")})
    classifiers: dict[str, dict] = {}
    for serial in serials:
        e, src = load_recent(serial, "empty")
        p, _ = load_recent(serial, "presence")
        m, src_m = load_recent(serial, "motion")
        src = src or src_m
        if not e or not m:
            print(f"  [{serial}] 건너뜀 — Empty/Motion CSV 부족 (e={len(e)}, m={len(m)})")
            continue
        es = [s for s, _ in e]; ed = [d for _, d in e]
        md = [d for _, d in m]
        if p:
            ps = [s for s, _ in p]; pd = [d for _, d in p]
            std_th = (mean(es) + mean(ps)) / 2.0
            doppler_th = (mean(pd) + mean(md)) / 2.0
        else:
            std_th = max(es) * 1.15
            doppler_th = (max(ed) + mean(md)) / 2.0
        classifiers[serial] = {
            "source": src or "tx",
            "std_th": float(std_th),
            "doppler_th": float(doppler_th),
            "empty": stats(e),
            "presence": stats(p),
            "motion": stats(m),
        }
        print(f"  [{serial}] source={src} std_th={std_th:.2f} doppler_th={doppler_th:.1f} "
              f"(e={len(e)}, p={len(p)}, m={len(m)})")

    full = yaml.safe_load(YAML.read_text()) or {}
    full.setdefault("motion_detection", {})["classifiers"] = classifiers
    YAML.write_text(yaml.safe_dump(full, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"\n→ {YAML} 갱신 완료 ({len(classifiers)} 디바이스)")


if __name__ == "__main__":
    main()
