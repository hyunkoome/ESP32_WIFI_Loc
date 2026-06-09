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

import json
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
    """Space Monitoring 탭: rx 별 정적/움직임 상태 종합 + 움직임 이벤트 로그 + 분당 카운트."""

    def __init__(self) -> None:
        super().__init__()
        v = QtWidgets.QVBoxLayout(self)
        v.addWidget(QtWidgets.QLabel(
            "<b>Space Monitoring</b> — rx 별 정적/움직임 상태와 움직임 이벤트를 종합 표시"))
        self._state_labels: dict[str, QtWidgets.QLabel] = {}
        self.state_box = QtWidgets.QVBoxLayout()
        sw = QtWidgets.QWidget(); sw.setLayout(self.state_box)
        v.addWidget(sw)
        v.addWidget(QtWidgets.QLabel("움직임 이벤트 로그 (시각 · rx · 변동):"))
        self.event_log = QtWidgets.QPlainTextEdit()
        self.event_log.setReadOnly(True)
        v.addWidget(self.event_log, 1)
        self.lbl_count = QtWidgets.QLabel("최근 1분 움직임: 0회")
        fnt = self.lbl_count.font(); fnt.setBold(True); self.lbl_count.setFont(fnt)
        v.addWidget(self.lbl_count)
        self._move_times: list[float] = []

    def on_state(self, port: str, serial: str, state: str, move: float) -> None:
        lbl = self._state_labels.get(serial)
        if lbl is None:
            lbl = QtWidgets.QLabel()
            fnt = lbl.font(); fnt.setPointSize(13); fnt.setBold(True); lbl.setFont(fnt)
            self._state_labels[serial] = lbl
            self.state_box.addWidget(lbl)
        moving = state == "move"
        lbl.setText(f"{serial[-4:]} :  {'🔴 움직임' if moving else '🟢 정적'}   (변동 {move:.2f})")
        lbl.setStyleSheet("color:#ff5555;" if moving else "color:#2ecc71;")

    def on_move(self, serial: str, move: float) -> None:
        ts = time.strftime("%H:%M:%S")
        self.event_log.appendPlainText(f"{ts}   [{serial[-4:]}]   움직임 시작 (변동 {move:.2f})")
        now = time.monotonic()
        self._move_times.append(now)
        self._move_times = [t for t in self._move_times if now - t <= 60]
        self.lbl_count.setText(f"최근 1분 움직임: {len(self._move_times)}회")


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
        self._move = 0.0                       # 최근 움직임지표(변동)
        self._state = "static"                 # 확정 상태: static | move
        self._pending_state = "static"
        self._pending_count = 0
        self._outlier_n = 3                    # 연속 N회 같아야 확정(outlier 필터)
        self._send_q: "queue.Queue[str]" = queue.Queue()
        self._stop = threading.Event()
        self._build()
        self._start_stream()

    # ---- UI ----
    def _build(self) -> None:
        v = QtWidgets.QVBoxLayout(self)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("신호원:"))
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItems(["tx", "wifi router", "all (융합)"])
        self.src_combo.setMinimumWidth(160)
        self.src_combo.currentTextChanged.connect(self._on_src)
        row.addWidget(self.src_combo)
        self.lbl_stats = QtWidgets.QLabel("rate: -")
        row.addWidget(self.lbl_stats)
        row.addStretch(1)
        # 이 rx 의 실시간 상태 라벨(로깅/학습은 상단 공용 패널에서 모든 rx 동시 수행).
        self.lbl_state = QtWidgets.QLabel("상태: 학습 전")
        fnt = self.lbl_state.font(); fnt.setPointSize(12); fnt.setBold(True)
        self.lbl_state.setFont(fnt)
        row.addWidget(self.lbl_state)
        v.addLayout(row)

        self.amp_plot = pg.PlotWidget(title="진폭 |H| — 서브캐리어별 채널 세기")
        self.amp_plot.setLabel("bottom", "서브캐리어 인덱스 (= 주파수)")
        self.amp_plot.setLabel("left", "진폭 |H|")
        self.amp_plot.setMouseEnabled(x=False, y=False)  # 마우스로 축 못 바꾸게(자동 범위 유지)
        self.amp_plot.enableAutoRange()                  # 어떤 라우터/tx 든 데이터에 맞춰 자동
        self.amp_curve = self.amp_plot.plot(pen=pg.mkPen("#4aa3ff", width=1.5))

        self.phase_plot = pg.PlotWidget(title="위상 ∠H — 서브캐리어별 위상")
        self.phase_plot.setLabel("bottom", "서브캐리어 인덱스 (= 주파수)")
        self.phase_plot.setLabel("left", "위상 (rad)")
        self.phase_plot.setMouseEnabled(x=False, y=False)
        self.phase_plot.setYRange(-3.2, 3.2)
        self.phase_curve = self.phase_plot.plot(pen=pg.mkPen("#f5a623", width=1.5))

        self.wf_plot = pg.PlotWidget(title="워터폴 — 시간에 따른 서브캐리어 진폭(색=진폭)")
        self.wf_plot.setLabel("bottom", "서브캐리어 인덱스 (= 주파수)")
        self.wf_plot.setLabel("left", "시간 (프레임, 위=최근)")
        self.wf_plot.setMouseEnabled(x=False, y=False)
        self.wf_img = pg.ImageItem()
        self.wf_plot.addItem(self.wf_img)
        try:
            self.wf_img.setColorMap(pg.colormap.get("viridis"))
        except Exception:
            pass

        self.dop_plot = pg.PlotWidget(title="도플러 스펙트럼 — 진폭 시간변화의 FFT(움직임 주파수)")
        self.dop_plot.setLabel("bottom", "움직임 주파수 (Hz)")
        self.dop_plot.setLabel("left", "세기 (FFT 크기)")
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
            self.bridge.log.emit(f"[{tag}] WIFI_DISCONNECT → tx(ESP-NOW) 채널 복귀")
        self._wf = None
        self.bridge.log.emit(f"[{tag}] 신호원 → {self._want_source}")

    def _send_wifi_connect(self) -> None:
        tag = self.serial[-4:] if self.serial else self.port
        ssid, pw = read_wifi_config()
        if not ssid:
            ssid, ok = QtWidgets.QInputDialog.getText(self, "라우터 SSID", "라우터 SSID:")
            if not ok or not ssid:
                return
            pw, ok = QtWidgets.QInputDialog.getText(self, "라우터 비번", f"'{ssid}' 비밀번호:")
            if not ok:
                return
        self._send_q.put(csi_stream.wifi_connect_cmd(ssid, pw))
        self.bridge.log.emit(f"[{tag}] WIFI_CONNECT → \"{ssid}\" (rx 가 라우터 접속 시도)")

    # ---- 정적/동적 로깅 + 학습(분류기) — 상단 공용 패널이 모든 rx 에 동시 호출 ----
    def start_logging(self, mode: str) -> None:
        """정적/동적 상태 데이터(변동지표) 로깅 시작(stop_logging 까지 계속 수집)."""
        self._logging = mode
        if mode == "static":
            self._static_buf = []
        else:
            self._motion_buf = []
        self.lbl_state.setText(f"로깅 중({'정적' if mode == 'static' else '동적'})…")
        self.lbl_state.setStyleSheet("color:#f5a623;")

    def stop_logging(self) -> int:
        """로깅 종료(저장). 수집한 보드 수(1) 반환."""
        if self._logging is None:
            return 0
        buf = self._static_buf if self._logging == "static" else self._motion_buf
        done = self._logging
        self._logging = None
        self.lbl_state.setText(f"{'정적' if done == 'static' else '동적'} 로깅 완료 ({len(buf)}샘플)")
        self.lbl_state.setStyleSheet("color:#888;")
        return 1

    def train(self) -> bool:
        """로깅한 정적/동적 데이터로 임계를 학습(분류기 생성) + 파라미터 저장."""
        if not self._static_buf or not self._motion_buf:
            self.bridge.log.emit(f"[{self.serial[-4:]}] 학습 불가: 정적·동적 둘 다 로깅 필요")
            return False
        self._static_ref = sum(self._static_buf) / len(self._static_buf)
        self._motion_ref = sum(self._motion_buf) / len(self._motion_buf)
        self._thresh = (self._static_ref + self._motion_ref) / 2.0
        out = Path(__file__).resolve().parents[2] / "results"
        out.mkdir(exist_ok=True)
        (out / f"classifier_{self.serial}.json").write_text(json.dumps({
            "serial": self.serial, "source": self._want_source,
            "static_ref": self._static_ref, "motion_ref": self._motion_ref,
            "thresh": self._thresh, "outlier_n": self._outlier_n,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        self.bridge.log.emit(
            f"[{self.serial[-4:]}] 학습완료 정적={self._static_ref:.2f} "
            f"동적={self._motion_ref:.2f} 임계={self._thresh:.2f}")
        return True

    def _update_classifier(self, move: float) -> None:
        # 로깅 중이면 해당 버퍼에 변동지표를 수집(분류 안 함).
        if self._logging:
            buf = self._static_buf if self._logging == "static" else self._motion_buf
            buf.append(move)
            return
        if self._thresh is None:
            return
        # outlier 필터: 연속 N회 같은 결과여야 상태를 확정(순간 노이즈로 안 튀게).
        raw = "move" if move > self._thresh else "static"
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
            f"{'🔴 움직임' if moving else '🟢 정적'}   (변동 {move:.2f} / 임계 {self._thresh:.2f})")
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
        move = float(self._wf.std(axis=0).mean())
        self._move = move
        self.lbl_stats.setText(
            f"[{src}]  rate {p['rate']}  RSSI {p['rssi']}  sub {p['n_sub']}"
            f"   |   움직임지표(변동) {move:.2f}")
        self._update_classifier(move)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ESP32 CSI 대시보드 (GUI)")
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
        top.addWidget(QtWidgets.QLabel("<b>연결된 보드</b> · 실시간 감지 · role 자동표시 · rx 마다 탭"))
        top.addStretch(1)
        btn_refresh = QtWidgets.QPushButton("🔄 새로고침")
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
        crow.addWidget(QtWidgets.QLabel("분류기:"))
        self.btn_log_static = QtWidgets.QPushButton("정적 데이터 로깅 시작")
        self.btn_log_static.clicked.connect(lambda: self._do_logging("static"))
        self.btn_log_motion = QtWidgets.QPushButton("동적 데이터 로깅 시작")
        self.btn_log_motion.clicked.connect(lambda: self._do_logging("motion"))
        self.btn_train = QtWidgets.QPushButton("파라미터 학습(분류기)")
        self.btn_train.clicked.connect(self._do_train)
        crow.addWidget(self.btn_log_static)
        crow.addWidget(self.btn_log_motion)
        crow.addWidget(self.btn_train)
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
                + ("" if b["accessible"] else "  ⚠권한없음")))
            badge = QtWidgets.QLabel("감지중…")
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
            self._append_log(f"rx 탭 생성: {port} ({serial})")
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
        self._append_log(f"rx 탭 제거: {port}")

    def _on_csi(self, port: str, p: dict) -> None:
        tab = self._rx_tabs.get(port)
        if tab:
            tab.on_csi(p)

    # ---- 분류기 공용 제어 (모든 rx 동시) ----
    def _do_logging(self, mode: str) -> None:
        if not self._rx_tabs:
            self._append_log("로깅할 rx 가 없습니다(rx 보드 연결/감지 필요).")
            return
        btn = self.btn_log_static if mode == "static" else self.btn_log_motion
        other = self.btn_log_motion if mode == "static" else self.btn_log_static
        label = "정적" if mode == "static" else "동적"
        if self._logging_mode is None:
            # 1번째 클릭: 모든 rx 로깅 시작. 다른 버튼은 비활성(클릭한 버튼만 '저장'으로).
            for tab in self._rx_tabs.values():
                tab.start_logging(mode)
            self._logging_mode = mode
            btn.setText(f"⏺ {label} 로깅중 (클릭→완료)")
            other.setEnabled(False)
            self.btn_train.setEnabled(False)
            self._append_log(f"모든 rx({len(self._rx_tabs)}개) {label} 로깅 시작 — 다시 누르면 완료")
        elif self._logging_mode == mode:
            # 2번째 클릭: 로깅 완료(저장). 버튼은 다시 '시작'으로 돌아간다.
            n = sum(tab.stop_logging() for tab in self._rx_tabs.values())
            self._logging_mode = None
            btn.setText(f"{label} 데이터 로깅 시작")
            other.setEnabled(True)
            self.btn_train.setEnabled(True)
            self._append_log(f"{label} 로깅 저장 완료 ({n}개 rx)")

    def _do_train(self) -> None:
        if not self._rx_tabs:
            self._append_log("학습할 rx 가 없습니다.")
            return
        n = sum(1 for tab in self._rx_tabs.values() if tab.train())
        self._append_log(f"파라미터 학습 완료: {n}/{len(self._rx_tabs)} rx — 이제 실시간 판단을 시작합니다.")

    # ---- flash ----
    def _flash(self, role: str, port: str) -> None:
        if QtWidgets.QMessageBox.question(
            self, "flash 확인",
            f"{port} 에 {role} 펌웨어를 flash할까요?\n(보드의 기존 펌웨어를 덮어씁니다)",
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
                        self.bridge.flash_line.emit("[build] 펌웨어 빌드(최초, 수 분 소요)...")
                        rc = flasher.build(role, on_line=lambda l: self.bridge.flash_line.emit(l))
                        if rc != 0:
                            self.bridge.flash_done.emit(port, False)
                            return
                    rc = flasher.flash(role, port, on_line=lambda l: self.bridge.flash_line.emit(l))
                    self.bridge.flash_done.emit(port, rc == 0)
            except Exception as exc:  # 스레드 예외가 조용히 사라지지 않게 로그로 표면화.
                self.bridge.flash_line.emit(f"[에러] flash 예외: {exc}")
                self.bridge.flash_done.emit(port, False)
        threading.Thread(target=work, daemon=True).start()

    def _on_flash_done(self, port: str, ok: bool) -> None:
        self._append_log(("✓ flash 완료 " if ok else "✗ flash 실패 ") + port)
        if ok:
            QtCore.QTimer.singleShot(3000, self.refresh)

    def _on_stream_stopped(self, port: str, err: object) -> None:
        if err:
            self._append_log(f"[{port}] 스트림: {err}")

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
