"""CSI 메트릭/3상태 분류기 · 학습 · 방 상태 voting (web/GUI 공용).

csi/gui/main.py 의 RxTab(on_csi 메트릭 계산, _update_classifier 3상태, train,
_load_recent) 과 SpaceMonitor._vote 로직을 UI 와 무관하게 추출했다. GUI 와 web 이
이 모듈을 공유하면 **두 프런트의 숫자가 100% 일치**한다.

핵심 클래스/함수:
  - load_motion_config / save_motion_classifier : config/motion_detection.yaml I/O.
  - RxClassifier : rx 1개의 워터폴/EMA/도플러/3상태 상태머신. on_csi(packet) 마다
    update() 를 호출하면 메트릭(std/doppler), 차트 데이터(waterfall/doppler 스펙트럼),
    확정 3상태, 로깅 CSV 행을 만든다(GUI on_csi 와 동일 계산).
  - vote_room : 다중 링크 voting 으로 최종 방 상태 결정(SpaceMonitor._vote 복제).
  - train_classifier : dataset/csi_logs 의 상태별 최근 CSV 로 std_th/doppler_th 학습.

GUI 와의 차이: 여기엔 pyqtgraph 가 없다. 차트는 web 이 canvas 로 그릴 수 있도록
숫자 배열(amp/phase/waterfall/doppler freqs·mags)만 반환한다.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Optional

import numpy as np

WF_HISTORY = 120  # 워터폴 시간축 길이(최근 N 패킷) — GUI 와 동일.

# config/motion_detection.yaml 경로(csi/common → repo root/config).
_MOTION_YAML = Path(__file__).resolve().parents[2] / "config" / "motion_detection.yaml"
_DATASET_DIR = Path(__file__).resolve().parents[2] / "dataset" / "csi_logs"


# --------------------------------------------------------------------------- #
# config/motion_detection.yaml 로드/저장 (GUI load_motion_config 등과 동일)
# --------------------------------------------------------------------------- #
def load_motion_config() -> dict:
    """config/motion_detection.yaml 로드 — 하이퍼파라미터 + rx 별 classifiers."""
    defaults = {"move_window": 20, "ema_alpha": 0.3, "outlier_n": 5,
                "hysteresis": 0.15, "default_std_th": 0.9,
                "default_doppler_th": 75.0, "classifiers": {}}
    try:
        import yaml
        cfg = (yaml.safe_load(_MOTION_YAML.read_text()) or {}).get("motion_detection") or {}
        for k in defaults:
            if k in cfg and cfg[k] is not None:
                defaults[k] = cfg[k]
    except Exception:
        pass
    return defaults


def trained_source_for(serial: str) -> Optional[str]:
    """이 디바이스(serial)의 학습된 신호원(classifiers[serial].source). 없으면 None.

    rx 카드/탭 생성 시 기본 신호원을 '순서(첫=router)'가 아니라 **학습 데이터대로**
    붙이기 위함 — 예: 8007 은 학습 때 tx, 2284 는 router 였으면 그대로 자동 선택.
    """
    clf = (load_motion_config().get("classifiers") or {}).get(serial)
    if isinstance(clf, dict) and clf.get("source") in ("tx", "router"):
        return str(clf["source"])
    return None


def save_motion_classifier(serial: str, params: dict) -> None:
    """학습 결과를 motion_detection.yaml 의 classifiers[serial] 에 저장(나머지 값 보존)."""
    import yaml
    try:
        full = yaml.safe_load(_MOTION_YAML.read_text()) or {}
    except Exception:
        full = {}
    md = full.setdefault("motion_detection", {})
    clf = md.get("classifiers")
    if not isinstance(clf, dict):
        clf = {}
        md["classifiers"] = clf
    clf[serial] = params
    _MOTION_YAML.parent.mkdir(exist_ok=True)
    _MOTION_YAML.write_text(
        yaml.safe_dump(full, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_wifi_config() -> tuple[str, str]:
    """config/wifi_config.yaml 에서 (ssid, pw). 없으면 ('', '')."""
    try:
        import yaml
        p = Path(__file__).resolve().parents[2] / "config" / "wifi_config.yaml"
        cfg = yaml.safe_load(p.read_text()) or {}
        w = cfg.get("wifi") or {}
        return str(w.get("ssid") or ""), str(w.get("password") or "")
    except Exception:
        return "", ""


# --------------------------------------------------------------------------- #
# 방 상태 voting (SpaceMonitor._vote 복제)
# --------------------------------------------------------------------------- #
def vote_room(rx_states: dict[str, str]) -> str:
    """다중 링크 voting 으로 최종 방 상태 결정(empty|presence|motion).

    활성 링크 ≥2 면 같은 상태 2표 이상, 1개뿐이면 1표로 확정 → 단일 링크 노이즈 완화.
    (GUI SpaceMonitor._vote 와 동일.)
    """
    states = list(rx_states.values())
    active = len(states)
    if active == 0:
        return "empty"
    motion_n = sum(1 for s in states if s == "motion")
    presence_n = sum(1 for s in states if s in ("presence", "motion"))
    min_det = 2 if active >= 2 else 1
    if motion_n >= min_det:
        return "motion"
    if presence_n >= min_det:
        return "presence"
    return "empty"


# --------------------------------------------------------------------------- #
# rx 1개의 분류기 상태머신 (RxTab 의 메트릭/3상태/로깅 로직 추출)
# --------------------------------------------------------------------------- #
class RxClassifier:
    """rx 1개의 CSI 메트릭 계산 + 3상태 판정 + 로깅 버퍼.

    update(packet) 를 매 CSI 패킷마다 호출하면 dict 를 반환한다(없으면 None — 신호원
    불일치 등으로 스킵). 반환 dict 에 차트/메트릭/상태/로깅에 필요한 모든 값이 들어 있어
    web 이 그대로 브라우저로 push 하면 된다.
    """

    def __init__(self, serial: str, port: str = "") -> None:
        self.serial = serial
        self.port = port
        self._want_source = "tx"
        self._wf: Optional[np.ndarray] = None
        self._dop_smooth: Optional[np.ndarray] = None
        # 3상태 로깅 버퍼(각 항목은 (std, doppler) 쌍 리스트).
        self._log_bufs: dict[str, list] = {"empty": [], "presence": [], "motion": []}
        self._logging: Optional[str] = None
        self._log_start = 0.0
        self._csv_f = None
        self._csv_w = None
        self._csv_path: Optional[Path] = None
        self._move = 0.0
        self._std = 0.0          # presence 메트릭(진폭 std, EMA)
        self._doppler = 0.0      # motion 메트릭(도플러 피크, EMA)
        self._state = "empty"
        self._pending_state = "empty"
        self._pending_count = 0
        # 하이퍼파라미터 + 학습결과를 yaml 에서 로드(런타임). GUI RxTab.__init__ 과 동일.
        mc = load_motion_config()
        self._move_win = int(mc["move_window"])
        self._ema = float(mc["ema_alpha"])
        self._outlier_n = int(mc["outlier_n"])
        self._hyst = float(mc["hysteresis"])
        self._std_th = float(mc.get("default_std_th") or 0.9)
        self._doppler_th = float(mc.get("default_doppler_th") or 75.0)
        clf = (mc.get("classifiers") or {}).get(serial)
        if isinstance(clf, dict):
            if clf.get("std_th") is not None:
                self._std_th = float(clf["std_th"])
            if clf.get("doppler_th") is not None:
                self._doppler_th = float(clf["doppler_th"])

    # ---- 신호원 ----
    @property
    def want_source(self) -> str:
        return self._want_source

    def set_source(self, source: str) -> None:
        """신호원 변경(tx|router|all). 워터폴 리셋(서로 다른 신호원 섞임 방지)."""
        self._want_source = source
        self._wf = None

    @property
    def std_th(self) -> float:
        return self._std_th

    @property
    def doppler_th(self) -> float:
        return self._doppler_th

    @property
    def state(self) -> str:
        return self._state

    # ---- CSI 1패킷 처리(GUI on_csi 복제, 차트는 숫자만 반환) ----
    def update(self, p: dict) -> Optional[dict]:
        """CSI 패킷 1개 처리. 신호원 불일치면 None. 일치하면 메트릭/차트/상태 dict 반환.

        반환 dict 키:
          source, rate, rssi, n_sub, amplitude[], phase[],
          waterfall(2D list, 최근 N×n_sub), doppler_freqs[], doppler_mags[],
          std, doppler, std_th, doppler_th, state(확정 3상태),
          state_changed(bool), move_event(bool)
        """
        src = p.get("source", "tx")
        if self._want_source != "all" and src != self._want_source:
            return None
        amp = p["amplitude"]
        phase = p["phase"]
        n = len(amp)
        if n == 0:
            return None
        if self._wf is None or self._wf.shape[1] != n:
            self._wf = np.zeros((WF_HISTORY, n), dtype=np.float32)
        self._wf = np.roll(self._wf, -1, axis=0)
        self._wf[-1, :] = np.asarray(amp, dtype=np.float32)

        # 도플러: 워터폴(시간×서브캐리어)의 시간축 FFT → 움직임 주파수.
        wf = self._wf - self._wf.mean(axis=0, keepdims=True)
        win = np.hanning(wf.shape[0])[:, None]
        spec = np.abs(np.fft.rfft(wf * win, axis=0)).mean(axis=1)
        fs = float(p.get("rate") or 0.0)
        if fs < 1.0:    # rate 미집계(초기)·저조(source 전환 직후 신호 끊김) 시 도플러 mask 가
            fs = 50.0   # 비지 않도록 기본 50Hz. (fs<0.6 이면 freqs 가 전부 <0.3Hz → mask 빈 배열)
        freqs = np.fft.rfftfreq(self._wf.shape[0], 1.0 / fs)
        mask = (freqs >= 0.3) & (freqs <= 10.0)   # DC 근처 저주파(AGC/드리프트) 제외
        sp = spec[mask]
        if self._dop_smooth is None or self._dop_smooth.shape != sp.shape:
            self._dop_smooth = sp
        else:
            self._dop_smooth = 0.7 * self._dop_smooth + 0.3 * sp
        f = freqs[mask]

        # 움직임 지표(EMA): 최근 MOVE_WIN 프레임 진폭의 시간 변동.
        recent = self._wf[-self._move_win:]
        move_raw = float(recent.std(axis=0).mean())
        self._move = (1.0 - self._ema) * self._move + self._ema * move_raw

        # 두 메트릭(GUI 와 동일): motion=도플러 피크, presence=전체 진폭 std. EMA 스무딩.
        # 0.3~10Hz mask 가 빈 배열이면(rate 가 매우 낮거나 워터폴 시간축이 짧을 때)
        # .max() 가 zero-size 로 터져 stream 스레드가 죽는다 → 빈 배열은 도플러 0 으로 안전 처리.
        doppler_raw = (float(self._dop_smooth.max())
                       if self._dop_smooth is not None and self._dop_smooth.size > 0
                       else 0.0)
        std_raw = float(self._wf.std(axis=0).mean())
        self._doppler = (1.0 - self._ema) * self._doppler + self._ema * doppler_raw
        self._std = (1.0 - self._ema) * self._std + self._ema * std_raw

        # 로깅 중이면 raw 데이터(GUI 와 100% 동일 컬럼)를 CSV 에 기록.
        if self._logging and self._csv_w is not None:
            t = time.monotonic() - self._log_start
            row = [t, p.get("source", ""), p.get("mac", ""), p["rssi"],
                   p.get("rate", 0.0), len(amp), self._std, self._doppler]
            row += list(p.get("raw_csi", []))   # raw CSI i/q 원본(2*n_sub)
            row += amp                           # amplitude (n_sub)
            row += phase                         # phase (n_sub)
            self._csv_w.writerow(row)

        changed, move_event = self._update_state(self._std, self._doppler)

        return {
            "source": src,
            "rate": p.get("rate", 0.0),
            "rssi": p.get("rssi"),
            "n_sub": n,
            "amplitude": amp,
            "phase": phase,
            "waterfall": self._wf.tolist(),
            "doppler_freqs": f.tolist(),
            "doppler_mags": self._dop_smooth.tolist(),
            "std": self._std,
            "doppler": self._doppler,
            "std_th": self._std_th,
            "doppler_th": self._doppler_th,
            "state": self._state,
            "state_changed": changed,
            "move_event": move_event,
        }

    def _update_state(self, std: float, doppler: float) -> tuple[bool, bool]:
        """3상태 판정 + 히스테리시스 + outlier 필터(GUI _update_classifier 복제).

        반환: (state_changed, move_event). 로깅 중이면 판정하지 않고 (False, False).
        """
        if self._logging:
            self._log_bufs[self._logging].append((std, doppler))
            return False, False
        jth_hi = self._doppler_th * (1 + self._hyst)
        jth_lo = self._doppler_th * (1 - self._hyst)
        wth_hi = self._std_th * (1 + self._hyst)
        wth_lo = self._std_th * (1 - self._hyst)
        if doppler > (jth_lo if self._state == "motion" else jth_hi):
            raw = "motion"
        elif std > (wth_lo if self._state == "presence" else wth_hi):
            raw = "presence"
        else:
            raw = "empty"
        if raw == self._pending_state:
            self._pending_count += 1
        else:
            self._pending_state = raw
            self._pending_count = 1
        changed = False
        move_event = False
        if self._pending_count >= self._outlier_n and raw != self._state:
            self._state = raw
            changed = True
            if raw == "motion":
                move_event = True
        return changed, move_event

    # ---- 로깅(GUI start_logging/stop_logging 복제) ----
    def start_logging(self, mode: str) -> None:
        """정적/동적 상태 데이터 로깅 시작. raw 데이터를 CSV 로 저장(GUI 와 동일 컬럼)."""
        self._logging = mode
        self._log_bufs[mode] = []
        _DATASET_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        self._csv_path = _DATASET_DIR / f"log_{mode}_{self.serial}_{ts}.csv"
        self._csv_f = open(self._csv_path, "w", newline="", encoding="utf-8")
        self._csv_w = csv.writer(self._csv_f)
        self._csv_w.writerow(["t_sec", "source", "mac", "rssi", "rate", "n_sub",
                              "std", "doppler",
                              "raw_csi_iq...(2*n_sub) then amp...(n_sub) then phase...(n_sub)"])
        self._log_start = time.monotonic()

    def stop_logging(self) -> int:
        """로깅 종료(버퍼 확정 + CSV 닫기). 수집한 보드 수(1) 반환."""
        if self._logging is None:
            return 0
        self._logging = None
        if self._csv_f is not None:
            self._csv_f.close()
            self._csv_f = None
            self._csv_w = None
        return 1

    @property
    def logging_mode(self) -> Optional[str]:
        return self._logging

    @property
    def csv_name(self) -> str:
        return self._csv_path.name if self._csv_path else ""

    def log_count(self) -> int:
        return len(self._log_bufs[self._logging]) if self._logging else 0

    # ---- 학습(GUI RxTab.train + _load_recent 복제) ----
    def _load_recent(self, mode: str) -> list:
        """dataset/csi_logs 에서 (mode, serial)의 '가장 최근' CSV 를 로드해 [(std, doppler)]."""
        return load_recent_csv(self.serial, mode)

    def train(self) -> tuple[bool, str]:
        """학습: 상태별 '가장 최근' CSV 로드(없으면 세션 버퍼). yaml 갱신.

        반환: (성공?, 메시지). GUI RxTab.train 과 동일 로직.
        """
        e = self._load_recent("empty") or self._log_bufs["empty"]
        p = self._load_recent("presence") or self._log_bufs["presence"]
        m = self._load_recent("motion") or self._log_bufs["motion"]
        if not e or not m:
            return False, f"[{self.serial[-4:]}] Cannot train: need Empty + Motion (CSV or session log)"
        mean = lambda xs: sum(xs) / len(xs)
        ew = [w for w, _ in e]; ej = [j for _, j in e]
        mj = [j for _, j in m]
        if p:
            pw = [w for w, _ in p]; pj = [j for _, j in p]
            self._std_th = (mean(ew) + mean(pw)) / 2.0
            self._doppler_th = (mean(pj) + mean(mj)) / 2.0
        else:
            self._std_th = max(ew) * (1 + self._hyst)
            self._doppler_th = (max(ej) + mean(mj)) / 2.0

        def _stats(buf):
            if not buf:
                return None
            ws = [w for w, _ in buf]; js = [j for _, j in buf]
            return {"std_mean": sum(ws) / len(ws), "std_max": max(ws),
                    "doppler_mean": sum(js) / len(js), "doppler_max": max(js)}

        save_motion_classifier(self.serial, {
            "source": self._want_source,
            "std_th": float(self._std_th),
            "doppler_th": float(self._doppler_th),
            "empty": _stats(e),
            "presence": _stats(p),
            "motion": _stats(m),
        })
        # 판정 상태머신도 즉시 새 임계로 재시작.
        self._state = "empty"
        self._pending_state = "empty"
        self._pending_count = 0
        return True, (f"[{self.serial[-4:]}] Trained: std_th={self._std_th:.2f} "
                      f"doppler_th={self._doppler_th:.1f} → motion_detection.yaml")


def load_recent_csv(serial: str, mode: str) -> list:
    """dataset/csi_logs 에서 (mode, serial)의 '가장 최근' CSV 를 [(std, doppler)] 로 로드."""
    files = sorted(_DATASET_DIR.glob(f"log_{mode}_{serial}_*.csv"))
    if not files:
        return []
    rows: list = []
    try:
        with open(files[-1], newline="", encoding="utf-8") as f:
            rd = csv.reader(f)
            next(rd, None)  # 헤더
            for row in rd:
                try:
                    rows.append((float(row[6]), float(row[7])))  # std, doppler 컬럼
                except (IndexError, ValueError):
                    pass
    except Exception:
        return []
    return rows
