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

import queue
import sys
import threading
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
        v.addLayout(row)

        self.amp_plot = pg.PlotWidget(title="진폭 |H| — 서브캐리어별 채널 세기")
        self.amp_plot.setLabel("bottom", "서브캐리어 인덱스 (= 주파수)")
        self.amp_plot.setLabel("left", "진폭 |H|")
        self.amp_curve = self.amp_plot.plot(pen=pg.mkPen("#4aa3ff", width=1.5))

        self.phase_plot = pg.PlotWidget(title="위상 ∠H — 서브캐리어별 위상")
        self.phase_plot.setLabel("bottom", "서브캐리어 인덱스 (= 주파수)")
        self.phase_plot.setLabel("left", "위상 (rad)")
        self.phase_plot.setYRange(-3.2, 3.2)
        self.phase_curve = self.phase_plot.plot(pen=pg.mkPen("#f5a623", width=1.5))

        self.wf_plot = pg.PlotWidget(title="워터폴 — 시간에 따른 서브캐리어 진폭(색=진폭)")
        self.wf_plot.setLabel("bottom", "서브캐리어 인덱스 (= 주파수)")
        self.wf_plot.setLabel("left", "시간 (프레임, 위=최근)")
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

        self.tabs = QtWidgets.QTabWidget()
        v.addWidget(self.tabs, 1)
        self._tab_hint = QtWidgets.QLabel(
            "rx 로 감지된 보드가 있으면 여기에 탭이 생깁니다. 각 탭에서 신호원(tx/wifi router/all)을 고르세요.")
        self.tabs.addTab(self._tab_hint, "안내")

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
