"""CSI 통합 데스크톱 GUI (PyQt5 + pyqtgraph).

web(csi/web) 과 동일한 csi/common 백엔드(boards/role_detect/flasher/csi_stream/
port_lock)를 쓴다. 디바이스 I/O 는 백그라운드 스레드에서 돌고 pyqtSignal 로 UI 를 갱신.

UI 구성:
  - 상단: 연결 보드 패널(실시간 감지 · role 자동표시 · tx/rx flash)
  - rx 로 감지된 보드마다 **동적 탭**을 만든다. 각 탭에서 신호원(tx/wifi router/all)을
    고르고 진폭/위상/워터폴/도플러를 본다. 여러 rx 는 각자 독립 스트림으로 동시에 본다.

실행: scripts/csi_gui.sh  (또는 python csi/gui/main.py)
"""
from __future__ import annotations

import csv
import queue
import sys
import threading
import time
from pathlib import Path

import numpy as np
from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg

# csi/common 공용 백엔드 import.
_CSI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CSI / "common"))

import boards as boards_mod   # noqa: E402
import csi_stream             # noqa: E402
import flasher                # noqa: E402
import role_detect            # noqa: E402
from port_lock import port_lock  # noqa: E402

WF_HISTORY = 120  # 워터폴 시간축 길이(최근 N 패킷)
MOVE_WIN = 20     # 움직임지표(변동) 계산 윈도우(최근 N프레임 ~2초). 짧을수록 판단이 빠름


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


_MOTION_YAML = Path(__file__).resolve().parents[2] / "config" / "motion_detection.yaml"


def load_motion_config() -> dict:
    """config/motion_detection.yaml 로드 — 하이퍼파라미터 + rx 별 classifiers."""
    defaults = {"move_window": 20, "ema_alpha": 0.3, "outlier_n": 5,
                "hysteresis": 0.15, "classifiers": {}}
    try:
        import yaml
        cfg = (yaml.safe_load(_MOTION_YAML.read_text()) or {}).get("motion_detection") or {}
        for k in defaults:
            if k in cfg and cfg[k] is not None:
                defaults[k] = cfg[k]
    except Exception:
        pass
    return defaults


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


class Bridge(QtCore.QObject):
    """워커 스레드 → UI 시그널."""

    boards_ready = QtCore.pyqtSignal(list)
    role_ready = QtCore.pyqtSignal(str, object, str)
    flash_line = QtCore.pyqtSignal(str)
    flash_done = QtCore.pyqtSignal(str, bool)
    csi_packet = QtCore.pyqtSignal(str, dict)        # (port, packet)
    stream_stopped = QtCore.pyqtSignal(str, object)  # (port, err)
    log = QtCore.pyqtSignal(str)
    state_changed = QtCore.pyqtSignal(str, str, str, float)  # (port, serial, state, move)
    move_event = QtCore.pyqtSignal(str, float)               # (serial, move)


class SpaceMonitor(QtWidgets.QWidget):
    """Space Monitoring 탭: rx 별 움직임 상태(1=움직임/0=정적) 시계열 그래프 + 이벤트 로그."""

    _COLORS = ["#4aa3ff", "#ff5555", "#2ecc71", "#f5a623", "#a36bff", "#36d7d7"]

    def __init__(self) -> None:
        super().__init__()
        v = QtWidgets.QVBoxLayout(self)
        v.addWidget(QtWidgets.QLabel(
            "<b>Space Monitoring</b> — per-rx motion state over time (x=time, y=motion 1 / static 0)"))
        # rx 별 현재 상태 라벨(가로 배치).
        self._state_labels: dict[str, QtWidgets.QLabel] = {}
        self.state_box = QtWidgets.QHBoxLayout()
        sw = QtWidgets.QWidget(); sw.setLayout(self.state_box)
        v.addWidget(sw)
        # 상태 시계열 그래프(rx 별 색상, step). y=0 정적 / 1 움직임.
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setLabel("left", "Motion (1) / Static (0)")
        self.plot.addLegend(offset=(-10, 10))
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setYRange(-0.2, 1.4, padding=0)
        self.plot.setMouseEnabled(x=False, y=False)
        v.addWidget(self.plot, 2)
        self._curves: dict[str, object] = {}
        self._series: dict[str, tuple[list, list]] = {}
        self._offset: dict[str, float] = {}
        self._t0 = time.monotonic()
        # 움직임 이벤트 로그(축소) + 분당 카운트.
        v.addWidget(QtWidgets.QLabel("Motion event log (time · rx · variation):"))
        self.event_log = QtWidgets.QPlainTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMaximumHeight(90)
        v.addWidget(self.event_log)
        self.lbl_count = QtWidgets.QLabel("Motion in last 1 min: 0")
        fnt = self.lbl_count.font(); fnt.setBold(True); self.lbl_count.setFont(fnt)
        v.addWidget(self.lbl_count)
        self._move_times: list[float] = []
        # 현재 시각까지 상태선을 연장하는 주기 갱신 타이머(정적 유지도 수평선으로).
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._redraw_all)
        self._timer.start(1000)

    def _ensure(self, serial: str) -> None:
        if serial in self._series:
            return
        idx = len(self._curves)
        self._series[serial] = ([0.0], [0])    # 시작은 정적(0)
        self._offset[serial] = idx * 0.06      # rx 별 살짝 띄워 겹침 방지(거의 0/1)
        color = self._COLORS[idx % len(self._COLORS)]
        self._curves[serial] = self.plot.plot(pen=pg.mkPen(color, width=2), name=serial[-4:])

    def on_state(self, port: str, serial: str, state: str, move: float) -> None:
        lbl = self._state_labels.get(serial)
        if lbl is None:
            lbl = QtWidgets.QLabel()
            fnt = lbl.font(); fnt.setPointSize(13); fnt.setBold(True); lbl.setFont(fnt)
            self._state_labels[serial] = lbl
            self.state_box.addWidget(lbl)
            self.state_box.addSpacing(12)
        moving = state == "move"
        lbl.setText(f"{serial[-4:]}: {'🔴Motion' if moving else '🟢Static'}")
        lbl.setStyleSheet("color:#ff5555;" if moving else "color:#2ecc71;")
        self._ensure(serial)
        ts, ss = self._series[serial]
        now = time.monotonic() - self._t0
        ts.append(now); ss.append(1 if moving else 0)
        while len(ts) > 2 and ts[0] < now - 120:   # 최근 120초만 보관
            ts.pop(0); ss.pop(0)
        self._redraw(serial)

    def _redraw(self, serial: str) -> None:
        ts, ss = self._series[serial]
        off = self._offset[serial]
        now = time.monotonic() - self._t0
        xs: list[float] = []
        ys: list[float] = []
        for i in range(len(ts)):
            if i > 0:
                xs.append(ts[i]); ys.append(ss[i - 1] + off)   # 이전 상태 유지(수평)
            xs.append(ts[i]); ys.append(ss[i] + off)           # 변화(수직)
        xs.append(now); ys.append(ss[-1] + off)                # 현재까지 연장
        self._curves[serial].setData(xs, ys)
        self.plot.setXRange(max(0.0, now - 60), now, padding=0)

    def _redraw_all(self) -> None:
        for serial in list(self._series):
            self._redraw(serial)

    def on_move(self, serial: str, move: float) -> None:
        ts = time.strftime("%H:%M:%S")
        self.event_log.appendPlainText(f"{ts}   [{serial[-4:]}]   Motion (variation {move:.2f})")
        now = time.monotonic()
        self._move_times.append(now)
        self._move_times = [t for t in self._move_times if now - t <= 60]
        self.lbl_count.setText(f"Motion in last 1 min: {len(self._move_times)}")


class RxTab(QtWidgets.QWidget):
    """rx 보드 1개: 신호원 선택 + 진폭/위상/워터폴/도플러 + 독립 스트림."""

    def __init__(self, port: str, serial: str, bridge: Bridge) -> None:
        super().__init__()
        self.port = port
        self.serial = serial
        self.bridge = bridge
        self._want_source = "tx"
        self._wf: np.ndarray | None = None
        self._dop_smooth: np.ndarray | None = None
        self._dop_ymax = 60.0  # 도플러 세로 상한(피크를 천천히 따라가 출렁임 최소)
        # 정적/움직임 분류기(간단 임계). 학습으로 기준을 잡고 변동지표로 실시간 판단.
        self._static_ref: float | None = None
        self._motion_ref: float | None = None
        self._thresh: float | None = None
        self._static_buf: list[float] = []     # 정적 상태 로깅 데이터(변동지표)
        self._motion_buf: list[float] = []     # 동적 상태 로깅 데이터
        self._logging: str | None = None       # "static" | "motion" | None (로깅 중)
        self._log_start = 0.0                  # 로깅 시작 시각(경과초 표시용)
        self._csv_f = None                     # raw 로깅 CSV 파일 핸들
        self._csv_w = None
        self._csv_path: Path | None = None
        self._move = 0.0                       # EMA 스무딩된 움직임지표(변동)
        self._wander = 0.0                     # presence 메트릭(느린 변동, 호흡/미세)
        self._jitter = 0.0                     # motion 메트릭(빠른 변화, 움직임)
        self._state = "static"                 # 확정 상태: static | move
        self._pending_state = "static"
        self._pending_count = 0
        # 모션 인지 하이퍼파라미터 + 학습결과를 config/motion_detection.yaml 에서 로드(런타임).
        mc = load_motion_config()
        self._move_win = int(mc["move_window"])
        self._ema = float(mc["ema_alpha"])
        self._outlier_n = int(mc["outlier_n"])
        self._hyst = float(mc["hysteresis"])
        clf = (mc.get("classifiers") or {}).get(serial)
        if isinstance(clf, dict) and clf.get("thresh") is not None:
            self._static_ref = clf.get("static_ref")
            self._motion_ref = clf.get("motion_ref")
            self._thresh = clf.get("thresh")
        self._send_q: "queue.Queue[str]" = queue.Queue()
        self._stop = threading.Event()
        self._build()
        self._start_stream()

    # ---- UI ----
    def _build(self) -> None:
        v = QtWidgets.QVBoxLayout(self)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Source:"))
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItems(["tx", "wifi router", "all (fusion)"])
        self.src_combo.setMinimumWidth(160)
        self.src_combo.currentTextChanged.connect(self._on_src)
        row.addWidget(self.src_combo)
        self.lbl_stats = QtWidgets.QLabel("rate: -")
        row.addWidget(self.lbl_stats)
        row.addStretch(1)
        # 이 rx 의 실시간 상태 라벨(로깅/학습은 상단 공용 패널에서 모든 rx 동시 수행).
        self.lbl_state = QtWidgets.QLabel("State: not trained")
        fnt = self.lbl_state.font(); fnt.setPointSize(12); fnt.setBold(True)
        self.lbl_state.setFont(fnt)
        row.addWidget(self.lbl_state)
        v.addLayout(row)

        self.amp_plot = pg.PlotWidget(title="Amplitude |H| — per-subcarrier channel gain")
        self.amp_plot.setLabel("bottom", "Subcarrier index (= frequency)")
        self.amp_plot.setLabel("left", "Amplitude |H|")
        self.amp_plot.setMouseEnabled(x=False, y=False)  # 마우스로 축 못 바꾸게(자동 범위 유지)
        self.amp_plot.enableAutoRange()                  # 어떤 라우터/tx 든 데이터에 맞춰 자동
        self.amp_curve = self.amp_plot.plot(pen=pg.mkPen("#4aa3ff", width=1.5))

        self.phase_plot = pg.PlotWidget(title="Phase ∠H — per-subcarrier phase")
        self.phase_plot.setLabel("bottom", "Subcarrier index (= frequency)")
        self.phase_plot.setLabel("left", "Phase (rad)")
        self.phase_plot.setMouseEnabled(x=False, y=False)
        self.phase_plot.setYRange(-3.2, 3.2)
        self.phase_curve = self.phase_plot.plot(pen=pg.mkPen("#f5a623", width=1.5))

        self.wf_plot = pg.PlotWidget(title="Waterfall — subcarrier amplitude over time (color=amplitude)")
        self.wf_plot.setLabel("bottom", "Subcarrier index (= frequency)")
        self.wf_plot.setLabel("left", "Time (frames, top=recent)")
        self.wf_plot.setMouseEnabled(x=False, y=False)
        self.wf_img = pg.ImageItem()
        self.wf_plot.addItem(self.wf_img)
        try:
            self.wf_img.setColorMap(pg.colormap.get("viridis"))
        except Exception:
            pass

        self.dop_plot = pg.PlotWidget(title="Doppler spectrum — FFT of amplitude over time (motion frequency)")
        self.dop_plot.setLabel("bottom", "Motion frequency (Hz)")
        self.dop_plot.setLabel("left", "Magnitude (FFT)")
        # 축 고정: autoRange 로 매 프레임 범위가 출렁이지 않게 가로 0~10Hz, 세로 0~60 고정.
        self.dop_plot.setXRange(0, 10, padding=0)
        self.dop_plot.setYRange(0, 60, padding=0)
        self.dop_plot.disableAutoRange()
        self.dop_plot.setMouseEnabled(x=False, y=False)
        # stem 그래프: FFT 는 이산 주파수 빈이라 각 빈에 수직선(stem)+끝점으로 또렷이 구분.
        self.dop_curve = self.dop_plot.plot(pen=pg.mkPen("#2ecc71", width=1.5))
        self.dop_pts = self.dop_plot.plot(pen=None, symbol="o", symbolSize=5,
                                          symbolBrush="#2ecc71", symbolPen=None)

        v.addWidget(self.amp_plot)
        v.addWidget(self.phase_plot)
        v.addWidget(self.wf_plot)
        v.addWidget(self.dop_plot)

    # ---- 스트림 ----
    def _start_stream(self) -> None:
        def work() -> None:
            with port_lock(self.port):
                err = csi_stream.stream_csi(
                    self.port, self._stop,
                    lambda d: self.bridge.csi_packet.emit(self.port, d),
                    send_q=self._send_q)
            self.bridge.stream_stopped.emit(self.port, err)
        threading.Thread(target=work, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    # ---- 신호원 ----
    def _on_src(self, text: str) -> None:
        tag = self.serial[-4:] if self.serial else self.port
        if "router" in text:
            self._want_source = "router"
            self._send_wifi_connect()
        elif "all" in text:
            self._want_source = "all"
        else:
            self._want_source = "tx"
            # tx 복귀: 라우터 연결을 끊어 ESP-NOW 채널(11)로 돌아간다.
            self._send_q.put("WIFI_DISCONNECT")
            self.bridge.log.emit(f"[{tag}] WIFI_DISCONNECT → back to tx (ESP-NOW) channel")
        self._wf = None
        self.bridge.log.emit(f"[{tag}] source → {self._want_source}")

    def _send_wifi_connect(self) -> None:
        tag = self.serial[-4:] if self.serial else self.port
        ssid, pw = read_wifi_config()
        if not ssid:
            ssid, ok = QtWidgets.QInputDialog.getText(self, "Router SSID", "Router SSID:")
            if not ok or not ssid:
                return
            pw, ok = QtWidgets.QInputDialog.getText(self, "Router password", f"Password for '{ssid}':")
            if not ok:
                return
        self._send_q.put(csi_stream.wifi_connect_cmd(ssid, pw))
        self.bridge.log.emit(f"[{tag}] WIFI_CONNECT → \"{ssid}\" (rx attempting to connect to router)")

    # ---- 정적/동적 로깅 + 학습(분류기) — 상단 공용 패널이 모든 rx 에 동시 호출 ----
    def start_logging(self, mode: str) -> None:
        """정적/동적 상태 데이터 로깅 시작(stop_logging 까지). raw 데이터를 CSV 로도 저장."""
        self._logging = mode
        if mode == "static":
            self._static_buf = []
        else:
            self._motion_buf = []
        out = Path(__file__).resolve().parents[2] / "dataset" / "csi_logs"
        out.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        self._csv_path = out / f"log_{mode}_{self.serial}_{ts}.csv"
        self._csv_f = open(self._csv_path, "w", newline="", encoding="utf-8")
        self._csv_w = csv.writer(self._csv_f)
        # 딥러닝 학습용 raw: 저장 가능한 값 모두 + 전체 float(반올림 없음).
        # 라벨은 파일명의 mode(static/motion). 가변 길이 꼬리: raw_csi(i/q) → amp → phase.
        self._csv_w.writerow(["t_sec", "source", "mac", "rssi", "rate", "n_sub",
                              "wander", "jitter", "raw_csi_iq...(2*n_sub) then amp...(n_sub) then phase...(n_sub)"])
        self._log_start = time.monotonic()
        self.lbl_state.setText(f"Logging ({'static' if mode == 'static' else 'motion'})…")
        self.lbl_state.setStyleSheet("color:#f5a623;")

    def stop_logging(self) -> int:
        """로깅 종료(버퍼 확정 + CSV 닫기). 수집한 보드 수(1) 반환."""
        if self._logging is None:
            return 0
        buf = self._static_buf if self._logging == "static" else self._motion_buf
        done = self._logging
        elapsed = time.monotonic() - self._log_start
        self._logging = None
        if self._csv_f is not None:
            self._csv_f.close()
            self.bridge.log.emit(f"[{self.serial[-4:]}] raw saved → dataset/csi_logs/{self._csv_path.name}")
            self._csv_f = None
            self._csv_w = None
        self.lbl_state.setText(
            f"{'Static' if done == 'static' else 'Motion'} done ({elapsed:.1f}s, {len(buf)} samples)")
        self.lbl_state.setStyleSheet("color:#888;")
        return 1

    def train(self) -> bool:
        """로깅한 정적/동적 데이터로 임계를 학습 + config/motion_detection.yaml 갱신."""
        if not self._static_buf or not self._motion_buf:
            self.bridge.log.emit(f"[{self.serial[-4:]}] Cannot train: need both static and motion logging")
            return False
        self._static_ref = sum(self._static_buf) / len(self._static_buf)
        self._motion_ref = sum(self._motion_buf) / len(self._motion_buf)
        self._thresh = (self._static_ref + self._motion_ref) / 2.0
        save_motion_classifier(self.serial, {
            "source": self._want_source,
            "static_ref": round(self._static_ref, 4),
            "motion_ref": round(self._motion_ref, 4),
            "thresh": round(self._thresh, 4),
        })
        self.bridge.log.emit(
            f"[{self.serial[-4:]}] Trained: static={self._static_ref:.2f} "
            f"motion={self._motion_ref:.2f} thresh={self._thresh:.2f} → motion_detection.yaml")
        return True

    def _update_classifier(self, move: float) -> None:
        # 로깅 중이면 버퍼에 변동지표를 수집(분류 안 함) + 경과시간/샘플수 표시.
        if self._logging:
            buf = self._static_buf if self._logging == "static" else self._motion_buf
            buf.append(move)
            elapsed = time.monotonic() - self._log_start
            kind = "static" if self._logging == "static" else "motion"
            self.lbl_state.setText(f"Logging {kind} ({elapsed:.1f}s, {len(buf)} samples)")
            return
        if self._thresh is None:
            return
        # 히스테리시스(yaml hysteresis): 정적→동적은 높은 임계, 동적→정적은 낮은 임계로
        # 경계에서 0/1 진동(튐)을 막는다. 마진 = (동적평균-정적평균) × hysteresis.
        rng = (self._motion_ref or 0.0) - (self._static_ref or 0.0)
        margin = self._hyst * rng
        if self._state == "static":
            raw = "move" if move > self._thresh + margin else "static"
        else:
            raw = "static" if move < self._thresh - margin else "move"
        if raw == self._pending_state:
            self._pending_count += 1
        else:
            self._pending_state = raw
            self._pending_count = 1
        if self._pending_count >= self._outlier_n and raw != self._state:
            self._state = raw
            self.bridge.state_changed.emit(self.port, self.serial, raw, move)
            if raw == "move":
                self.bridge.move_event.emit(self.serial, move)
        moving = self._state == "move"
        self.lbl_state.setText(
            f"{'🔴 Motion' if moving else '🟢 Static'}   (variation {move:.2f} / thresh {self._thresh:.2f})")
        self.lbl_state.setStyleSheet("color:#ff5555;" if moving else "color:#2ecc71;")

    # ---- CSI 갱신 ----
    def on_csi(self, p: dict) -> None:
        src = p.get("source", "tx")
        if self._want_source != "all" and src != self._want_source:
            return
        amp = p["amplitude"]
        phase = p["phase"]
        self.lbl_stats.setText(f"[{src}] rate {p['rate']}  RSSI {p['rssi']}  sub {p['n_sub']}")
        self.amp_curve.setData(amp)
        self.phase_curve.setData(phase)
        n = len(amp)
        if n == 0:
            return
        if self._wf is None or self._wf.shape[1] != n:
            self._wf = np.zeros((WF_HISTORY, n), dtype=np.float32)
        self._wf = np.roll(self._wf, -1, axis=0)
        self._wf[-1, :] = np.asarray(amp, dtype=np.float32)
        self.wf_img.setImage(self._wf, autoLevels=True)

        # 도플러: 워터폴(시간×서브캐리어)의 시간축 FFT → 움직임 주파수.
        wf = self._wf - self._wf.mean(axis=0, keepdims=True)
        win = np.hanning(wf.shape[0])[:, None]
        spec = np.abs(np.fft.rfft(wf * win, axis=0)).mean(axis=1)
        fs = float(p.get("rate") or 0.0) or 50.0
        freqs = np.fft.rfftfreq(self._wf.shape[0], 1.0 / fs)
        mask = freqs <= 10.0
        sp = spec[mask]
        if self._dop_smooth is None or self._dop_smooth.shape != sp.shape:
            self._dop_smooth = sp
        else:
            self._dop_smooth = 0.7 * self._dop_smooth + 0.3 * sp
        # stem: 각 주파수 빈에 0→세기 수직선(connect='pairs') + 끝점.
        f = freqs[mask]
        xs = np.repeat(f, 2)
        ys = np.zeros(xs.shape[0])
        ys[1::2] = self._dop_smooth
        self.dop_curve.setData(xs, ys, connect="pairs")
        self.dop_pts.setData(f, self._dop_smooth)
        # 세로 상한: 피크에 여유(×1.3)를 두되 천천히(×0.97) 줄여 출렁임 없이 안 잘리게.
        peak = float(self._dop_smooth.max()) * 1.3
        self._dop_ymax = max(peak, self._dop_ymax * 0.97, 30.0)
        self.dop_plot.setYRange(0, self._dop_ymax, padding=0)

        # 움직임 지표: 워터폴 진폭의 시간 변동(서브캐리어별 std 평균). 가만히 ~1, 움직이면
        # 2~2.5 로 또렷이 오른다 — 느린 움직임/노이즈에 약한 도플러보다 직관적인 지표.
        # 움직임지표는 워터폴 전체(12초)가 아니라 최근 짧은 구간(MOVE_WIN)으로 — 전체면
        # 움직임이 윈도우에 반영될 때까지 판단이 느리다(체감 3초+ 지연의 원인).
        recent = self._wf[-self._move_win:]
        move_raw = float(recent.std(axis=0).mean())
        # EMA 스무딩(yaml ema_alpha): 짧은 윈도우의 순간 노이즈로 상태가 튀지 않게.
        self._move = (1.0 - self._ema) * self._move + self._ema * move_raw
        move = self._move
        # reference 차용 + 실측 검증으로 재정의한 두 메트릭:
        #  - motion = 도플러 피크(움직임 주파수 세기). 프레임차분(jitter)은 움직임 구분에
        #    실패했고, 도플러 피크가 빈방<정지<움직임으로 잘 갈렸다(검증 완료).
        #  - presence = wander(전체 진폭 std). 사람 유무(호흡/멀티패스 변화)에 반응.
        jitter_raw = float(self._dop_smooth.max()) if self._dop_smooth is not None else 0.0
        wander_raw = float(self._wf.std(axis=0).mean())
        self._jitter = (1.0 - self._ema) * self._jitter + self._ema * jitter_raw
        self._wander = (1.0 - self._ema) * self._wander + self._ema * wander_raw
        self.lbl_stats.setText(
            f"[{src}] rate {p['rate']} RSSI {p['rssi']}  |  "
            f"wander(presence) {self._wander:.2f}   jitter(motion) {self._jitter:.2f}")
        # 로깅 중이면 raw 데이터(타임스탬프+wander+jitter+진폭)를 CSV 에 기록.
        if self._logging and self._csv_w is not None:
            t = time.monotonic() - self._log_start
            # 저장 가능한 값 모두 + 전체 float(csv.writer 가 str(value) 로 반올림 없이 기록).
            row = [t, p.get("source", ""), p.get("mac", ""), p["rssi"],
                   p.get("rate", 0.0), len(amp), self._wander, self._jitter]
            row += list(p.get("raw_csi", []))   # raw CSI i/q 원본(2*n_sub)
            row += amp                           # amplitude (n_sub)
            row += phase                         # phase (n_sub)
            self._csv_w.writerow(row)
        self._update_classifier(move)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ESP32 CSI Dashboard (GUI)")
        self.resize(1080, 880)

        self.bridge = Bridge()
        self.bridge.boards_ready.connect(self._on_boards)
        self.bridge.role_ready.connect(self._on_role)
        self.bridge.flash_line.connect(self._append_log)
        self.bridge.flash_done.connect(self._on_flash_done)
        self.bridge.csi_packet.connect(self._on_csi)
        self.bridge.stream_stopped.connect(self._on_stream_stopped)
        self.bridge.log.connect(self._append_log)

        self._badges: dict[str, QtWidgets.QLabel] = {}
        self._roles: dict[str, object] = {}
        self._serials: dict[str, str] = {}    # port -> serial
        self._rx_tabs: dict[str, RxTab] = {}  # port -> RxTab
        self._logging_mode: str | None = None  # 공용 로깅 토글 상태(None | static | motion)

        self._build_ui()
        self.refresh()

    # ---- UI ----
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("<b>Connected boards</b> · live detection · auto role · tab per rx"))
        top.addStretch(1)
        btn_refresh = QtWidgets.QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.refresh)
        top.addWidget(btn_refresh)
        v.addLayout(top)

        self.board_box = QtWidgets.QVBoxLayout()
        bw = QtWidgets.QWidget()
        bw.setLayout(self.board_box)
        v.addWidget(bw)

        # 분류기 공용 패널(탭 위): 어느 탭에서든 누르면 모든 rx 가 동시에 로깅/학습한다.
        # 로깅 버튼은 토글 — 1번 누르면 시작, 다시 누르면 저장(정적/동적 로깅 시간이 달라도 OK).
        crow = QtWidgets.QHBoxLayout()
        crow.addWidget(QtWidgets.QLabel("Classifier:"))
        self.btn_log_static = QtWidgets.QPushButton("Log Static Data")
        self.btn_log_static.clicked.connect(lambda: self._do_logging("static"))
        self.btn_log_motion = QtWidgets.QPushButton("Log Motion Data")
        self.btn_log_motion.clicked.connect(lambda: self._do_logging("motion"))
        self.btn_train = QtWidgets.QPushButton("Train Classifier")
        self.btn_train.clicked.connect(self._do_train)
        crow.addWidget(self.btn_log_static)
        crow.addWidget(self.btn_log_motion)
        crow.addWidget(self.btn_train)
        crow.addSpacing(20)
        # 현재 모드 표시(대기 / 로깅중 / 학습중 / 실시간 감지중).
        self.lbl_mode = QtWidgets.QLabel("⏸ Idle")
        fnt = self.lbl_mode.font(); fnt.setPointSize(13); fnt.setBold(True)
        self.lbl_mode.setFont(fnt)
        crow.addWidget(self.lbl_mode)
        crow.addStretch(1)
        v.addLayout(crow)

        self.tabs = QtWidgets.QTabWidget()
        v.addWidget(self.tabs, 1)
        # Space Monitoring(종합 상태/이벤트)을 첫 탭으로 고정. rx 탭은 감지될 때 추가된다.
        self.space = SpaceMonitor()
        self.tabs.addTab(self.space, "Space Monitoring")
        self.bridge.state_changed.connect(self.space.on_state)
        self.bridge.move_event.connect(self.space.on_move)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        v.addWidget(self.log)

    # ---- 보드 감지 ----
    def refresh(self) -> None:
        def work() -> None:
            found = boards_mod.discover()
            self.bridge.boards_ready.emit([b.to_dict() for b in found])
            for b in found:
                # 스트림 중(rx 탭)인 포트는 role 재감지를 건너뛴다 — 같은 포트락을 스트림이
                # 잡고 있어 role_detect 가 무한 대기에 빠지는 것을 막는다.
                if b.port in self._rx_tabs:
                    self.bridge.role_ready.emit(b.port, self._roles.get(b.port, "rx"), "stream")
                    continue
                def det(port: str = b.port) -> None:
                    with port_lock(port):
                        role, src = role_detect.detect_role(port, timeout=4.0)
                    self.bridge.role_ready.emit(port, role, src)
                threading.Thread(target=det, daemon=True).start()
        threading.Thread(target=work, daemon=True).start()

    def _on_boards(self, boards: list) -> None:
        while self.board_box.count():
            item = self.board_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._badges.clear()
        present = set()
        for b in boards:
            present.add(b["port"])
            self._serials[b["port"]] = b["serial"]
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(
                f"{b['port']}  serial={b['serial']}  [{b['vid_pid']}]"
                + ("" if b["accessible"] else "  ⚠no permission")))
            badge = QtWidgets.QLabel("Detecting…")
            row.addWidget(badge)
            self._badges[b["port"]] = badge
            row.addStretch(1)
            btn_tx = QtWidgets.QPushButton("tx flash")
            btn_tx.clicked.connect(lambda _=False, p=b["port"]: self._flash("tx", p))
            btn_rx = QtWidgets.QPushButton("rx flash")
            btn_rx.clicked.connect(lambda _=False, p=b["port"]: self._flash("rx", p))
            row.addWidget(btn_tx)
            row.addWidget(btn_rx)
            rw = QtWidgets.QWidget()
            rw.setLayout(row)
            self.board_box.addWidget(rw)
        # 더 이상 안 보이는 보드의 rx 탭 제거.
        for port in list(self._rx_tabs):
            if port not in present:
                self._remove_rx_tab(port)

    def _on_role(self, port: str, role: object, src: str) -> None:
        self._roles[port] = role
        badge = self._badges.get(port)
        if badge:
            badge.setText(str(role).upper() if role else "role?")
        # rx 면 탭 생성(없을 때만). rx 가 아니게 되면 탭 제거.
        if role == "rx" and port not in self._rx_tabs:
            serial = self._serials.get(port, port)
            tab = RxTab(port, serial, self.bridge)
            self._rx_tabs[port] = tab
            self.tabs.addTab(tab, f"rx: {serial[-4:] if serial else port}")
            self.tabs.setCurrentWidget(tab)
            self._append_log(f"rx tab added: {port} ({serial})")
        elif role != "rx" and port in self._rx_tabs:
            self._remove_rx_tab(port)

    def _remove_rx_tab(self, port: str) -> None:
        tab = self._rx_tabs.pop(port, None)
        if tab is None:
            return
        tab.stop()
        idx = self.tabs.indexOf(tab)
        if idx >= 0:
            self.tabs.removeTab(idx)
        tab.deleteLater()
        self._append_log(f"rx tab removed: {port}")

    def _on_csi(self, port: str, p: dict) -> None:
        tab = self._rx_tabs.get(port)
        if tab:
            tab.on_csi(p)

    # ---- 분류기 공용 제어 (모든 rx 동시) ----
    def _do_logging(self, mode: str) -> None:
        if not self._rx_tabs:
            self._append_log("No rx to log (connect/detect an rx board first).")
            return
        btn = self.btn_log_static if mode == "static" else self.btn_log_motion
        other = self.btn_log_motion if mode == "static" else self.btn_log_static
        label = "Static" if mode == "static" else "Motion"
        if self._logging_mode is None:
            # 1번째 클릭: 모든 rx 로깅 시작. 다른 버튼은 비활성(클릭한 버튼만 '저장'으로).
            for tab in self._rx_tabs.values():
                tab.start_logging(mode)
            self._logging_mode = mode
            btn.setText(f"⏺ {label} logging (click to finish)")
            other.setEnabled(False)
            self.btn_train.setEnabled(False)
            self.lbl_mode.setText(f"⏺ Logging {label} data…")
            self.lbl_mode.setStyleSheet("color:#f5a623;")
            self._append_log(f"All rx ({len(self._rx_tabs)}) started {label} logging — click again to finish")
        elif self._logging_mode == mode:
            # 2번째 클릭: 로깅 완료(저장). 버튼은 다시 '시작'으로 돌아간다.
            n = sum(tab.stop_logging() for tab in self._rx_tabs.values())
            self._logging_mode = None
            btn.setText(f"Log {label} Data")
            other.setEnabled(True)
            self.btn_train.setEnabled(True)
            self._refresh_mode()
            self._append_log(f"{label} logging saved ({n} rx)")

    def _do_train(self) -> None:
        if not self._rx_tabs:
            self._append_log("No rx to train.")
            return
        self.lbl_mode.setText("⚙ Training…")
        self.lbl_mode.setStyleSheet("color:#4aa3ff;")
        n = sum(1 for tab in self._rx_tabs.values() if tab.train())
        self._append_log(f"Training done: {n}/{len(self._rx_tabs)} rx — live detection started.")
        self._refresh_mode()

    def _refresh_mode(self) -> None:
        trained = any(t._thresh is not None for t in self._rx_tabs.values())
        if trained:
            self.lbl_mode.setText("🟢 Detecting (live)")
            self.lbl_mode.setStyleSheet("color:#2ecc71;")
        else:
            self.lbl_mode.setText("⏸ Idle")
            self.lbl_mode.setStyleSheet("color:#888;")

    # ---- flash ----
    def _flash(self, role: str, port: str) -> None:
        if QtWidgets.QMessageBox.question(
            self, "Confirm flash",
            f"Flash {role} firmware to {port}?\n(This overwrites the board's existing firmware)",
        ) != QtWidgets.QMessageBox.Yes:
            return
        # 그 포트의 rx 탭(스트림)이 있으면 멈추고 flash(포트 점유 해제).
        if port in self._rx_tabs:
            self._remove_rx_tab(port)
        self._append_log(f"--- flash {role} → {port} ---")

        def work() -> None:
            try:
                with port_lock(port):
                    if not flasher.is_built(role):
                        self.bridge.flash_line.emit("[build] Building firmware (first time, may take a few minutes)...")
                        rc = flasher.build(role, on_line=lambda l: self.bridge.flash_line.emit(l))
                        if rc != 0:
                            self.bridge.flash_done.emit(port, False)
                            return
                    rc = flasher.flash(role, port, on_line=lambda l: self.bridge.flash_line.emit(l))
                    self.bridge.flash_done.emit(port, rc == 0)
            except Exception as exc:  # 스레드 예외가 조용히 사라지지 않게 로그로 표면화.
                self.bridge.flash_line.emit(f"[error] flash exception: {exc}")
                self.bridge.flash_done.emit(port, False)
        threading.Thread(target=work, daemon=True).start()

    def _on_flash_done(self, port: str, ok: bool) -> None:
        self._append_log(("✓ flash done " if ok else "✗ flash failed ") + port)
        if ok:
            QtCore.QTimer.singleShot(3000, self.refresh)

    def _on_stream_stopped(self, port: str, err: object) -> None:
        if err:
            self._append_log(f"[{port}] stream: {err}")

    def _append_log(self, line: str) -> None:
        self.log.appendPlainText(line)


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    pg.setConfigOptions(antialias=True, background="#0f1115", foreground="#c9d1d9")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
