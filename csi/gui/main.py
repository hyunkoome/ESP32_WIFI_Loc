"""CSI 통합 데스크톱 GUI (PyQt5 + pyqtgraph).

web(csi/web) 과 동일한 csi/common 백엔드(boards/role_detect/flasher/csi_stream/
port_lock)를 쓴다. 디바이스 I/O 는 백그라운드 스레드에서 돌고 pyqtSignal 로 UI 를
갱신한다.

UI 구성:
  - 상단: 연결 보드 패널(실시간 감지 · role 자동표시 · tx/rx flash)
  - 탭:
    · "tx 링크 (rx↔tx)" : rx 가 받은 tx 신호의 CSI — 진폭/위상/워터폴 실시간
    · "rx (신호원 선택)" : tx | wifi router | all. router 선택 시 WIFI_CONNECT 로 라우터 접속.
  - rx role 이 감지되면 스트림을 **자동 시작**한다(버튼 없이).

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


class Bridge(QtCore.QObject):
    """워커 스레드 → UI 시그널."""

    boards_ready = QtCore.pyqtSignal(list)
    role_ready = QtCore.pyqtSignal(str, object, str)
    flash_line = QtCore.pyqtSignal(str)
    flash_done = QtCore.pyqtSignal(str, bool)
    csi_packet = QtCore.pyqtSignal(dict)
    stream_stopped = QtCore.pyqtSignal(object)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ESP32 CSI 대시보드 (GUI)")
        self.resize(1080, 860)

        self.bridge = Bridge()
        self.bridge.boards_ready.connect(self._on_boards)
        self.bridge.role_ready.connect(self._on_role)
        self.bridge.flash_line.connect(self._append_log)
        self.bridge.flash_done.connect(self._on_flash_done)
        self.bridge.csi_packet.connect(self._on_csi)
        self.bridge.stream_stopped.connect(self._on_stream_stopped)

        self._badges: dict[str, QtWidgets.QLabel] = {}
        self._roles: dict[str, object] = {}
        self._stream_stop = threading.Event()
        self._stream_port: str | None = None     # 현재 스트림 중인 포트
        self._send_q: "queue.Queue[str] | None" = None  # 보드로 보낼 명령(WIFI_CONNECT)
        self._want_source = "tx"                 # 신호원 필터: tx | router | all
        self._wf: np.ndarray | None = None          # 워터폴 버퍼
        self._dop_smooth: np.ndarray | None = None  # 도플러 스무딩(EMA) 상태

        self._build_ui()
        self.refresh()

    # ---- UI ----
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("<b>연결된 보드</b> · 실시간 감지 · role 자동표시"))
        top.addStretch(1)
        self.lbl_stream = QtWidgets.QLabel("스트림: 정지")
        top.addWidget(self.lbl_stream)
        btn_refresh = QtWidgets.QPushButton("🔄 새로고침")
        btn_refresh.clicked.connect(self.refresh)
        top.addWidget(btn_refresh)
        v.addLayout(top)

        self.board_box = QtWidgets.QVBoxLayout()
        bw = QtWidgets.QWidget()
        bw.setLayout(self.board_box)
        v.addWidget(bw)

        self.lbl_stats = QtWidgets.QLabel("rate: -  RSSI: -  sub: -")
        v.addWidget(self.lbl_stats)

        self.tabs = QtWidgets.QTabWidget()
        v.addWidget(self.tabs, 1)

        # --- tx 링크 탭: 진폭/위상/워터폴 ---
        tx_w = QtWidgets.QWidget()
        tx_v = QtWidgets.QVBoxLayout(tx_w)
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
        self.dop_curve = self.dop_plot.plot(pen=pg.mkPen("#2ecc71", width=1.5))
        tx_v.addWidget(self.amp_plot)
        tx_v.addWidget(self.phase_plot)
        tx_v.addWidget(self.wf_plot)
        tx_v.addWidget(self.dop_plot)
        self.tabs.addTab(tx_w, "tx 링크 (rx↔tx)")

        # --- rx 신호원 선택 탭 ---
        rx_w = QtWidgets.QWidget()
        rx_v = QtWidgets.QVBoxLayout(rx_w)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("신호원:"))
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItems(["tx", "wifi router", "all (융합)"])
        self.src_combo.setMinimumWidth(180)
        self.src_combo.currentTextChanged.connect(self._on_src_change)
        row.addWidget(self.src_combo)
        row.addStretch(1)
        rx_v.addLayout(row)
        rx_v.addWidget(QtWidgets.QLabel(
            "<b>tx</b> = ESP-NOW 송신기 CSI, <b>wifi router</b> = 라우터(AP) CSI.\n"
            "wifi router 선택 시 config/wifi_config.yaml(없으면 직접 입력)을 읽어 rx 에\n"
            "WIFI_CONNECT 를 보냅니다(rx 가 STA 접속+ping → 라우터 CSI). all = 둘 다 표시.\n"
            "⚠ 라우터 접속 시 그 채널로 고정 — tx 가 다른 채널이면 tx 신호는 끊깁니다."
        ))
        rx_v.addStretch(1)
        self.tabs.addTab(rx_w, "rx (신호원 선택)")

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
                # 스트림 중인 포트는 role 재감지를 건너뛴다 — 같은 포트락을 스트림이
                # 잡고 있어 role_detect 가 무한 대기(감지중 멈춤)에 빠지는 것을 막는다.
                if b.port == self._stream_port:
                    self.bridge.role_ready.emit(b.port, self._roles.get(b.port), "stream")
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
        self._roles.clear()
        for b in boards:
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

    def _on_role(self, port: str, role: object, src: str) -> None:
        self._roles[port] = role
        badge = self._badges.get(port)
        if badge:
            badge.setText(str(role).upper() if role else "role?")
        # rx 가 감지되면 스트림을 자동 시작(아직 아무것도 스트림 중이 아니면).
        if role == "rx" and self._stream_port is None:
            self._start_stream(port)

    # ---- 신호원 선택 ----
    def _on_src_change(self, text: str) -> None:
        if "router" in text:
            self._want_source = "router"
            self._send_wifi_connect()
        elif "all" in text:
            self._want_source = "all"
        else:
            self._want_source = "tx"
            # tx 로 복귀: 라우터 연결을 끊어 ESP-NOW 채널(11)로 돌아간다(tx CSI 재수신).
            if self._send_q is not None:
                self._send_q.put("WIFI_DISCONNECT")
                self._append_log("WIFI_DISCONNECT 전송 → tx(ESP-NOW) 채널 복귀")
        self._wf = None  # 신호원이 바뀌면 워터폴/도플러 누적을 초기화
        self._append_log(f"신호원 → {self._want_source}")

    def _read_wifi_config(self) -> tuple[str, str]:
        """config/wifi_config.yaml 에서 (ssid, pw). 없으면 ('', '')."""
        try:
            import yaml
            p = Path(__file__).resolve().parents[2] / "config" / "wifi_config.yaml"
            cfg = yaml.safe_load(p.read_text()) or {}
            w = cfg.get("wifi") or {}
            return str(w.get("ssid") or ""), str(w.get("password") or "")
        except Exception:
            return "", ""

    def _send_wifi_connect(self) -> None:
        """라우터 자격증명을 config/wifi_config.yaml(없으면 입력)에서 얻어 rx 로 WIFI_CONNECT 전송."""
        if self._send_q is None:
            self._append_log("라우터 접속: rx 스트림이 먼저 시작돼야 합니다(rx 보드 연결 확인).")
            return
        ssid, pw = self._read_wifi_config()
        if not ssid:
            ssid, ok = QtWidgets.QInputDialog.getText(self, "라우터 SSID", "라우터 SSID:")
            if not ok or not ssid:
                return
            pw, ok = QtWidgets.QInputDialog.getText(self, "라우터 비번", f"'{ssid}' 비밀번호:")
            if not ok:
                return
        self._send_q.put(csi_stream.wifi_connect_cmd(ssid, pw))
        self._append_log(f"WIFI_CONNECT 전송 → \"{ssid}\" (rx 가 라우터 접속 시도)")

    # ---- flash ----
    def _flash(self, role: str, port: str) -> None:
        if QtWidgets.QMessageBox.question(
            self, "flash 확인",
            f"{port} 에 {role} 펌웨어를 flash할까요?\n(보드의 기존 펌웨어를 덮어씁니다)",
        ) != QtWidgets.QMessageBox.Yes:
            return
        # 같은 포트를 스트림 중이면 멈추고 flash.
        if self._stream_port == port:
            self._stream_stop.set()
            self._stream_port = None
            self.lbl_stream.setText("스트림: 정지")
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

    # ---- CSI 스트림 (자동) ----
    def _start_stream(self, port: str) -> None:
        self._stream_stop.set()  # 이전 것 정지
        self._stream_stop = threading.Event()
        ev = self._stream_stop
        self._stream_port = port
        self._wf = None
        self.lbl_stream.setText(f"스트림: {port} (자동)")

        self._send_q = queue.Queue()
        def work() -> None:
            with port_lock(port):
                err = csi_stream.stream_csi(
                    port, ev, lambda d: self.bridge.csi_packet.emit(d), send_q=self._send_q)
            self.bridge.stream_stopped.emit(err)
        threading.Thread(target=work, daemon=True).start()

    def _on_csi(self, p: dict) -> None:
        # 신호원 필터: 선택한 신호원(tx/router)만 표시. all 이면 모두 받는다.
        src = p.get("source", "tx")
        if self._want_source != "all" and src != self._want_source:
            return
        amp = p["amplitude"]
        phase = p["phase"]
        self.lbl_stats.setText(f"[{src}] rate: {p['rate']}  RSSI: {p['rssi']}  sub: {p['n_sub']}")
        self.amp_curve.setData(amp)
        self.phase_curve.setData(phase)
        # 워터폴: 시간축으로 진폭을 누적(roll).
        n = len(amp)
        if n == 0:
            return
        if self._wf is None or self._wf.shape[1] != n:
            self._wf = np.zeros((WF_HISTORY, n), dtype=np.float32)
        self._wf = np.roll(self._wf, -1, axis=0)
        self._wf[-1, :] = np.asarray(amp, dtype=np.float32)
        # ImageItem 은 (x=행, y=열) 이므로 그대로: 행=시간, 열=서브캐리어.
        self.wf_img.setImage(self._wf, autoLevels=True)

        # 도플러 스펙트럼: 워터폴(시간×서브캐리어)의 '시간축'을 FFT 해 움직임 주파수를
        # 본다. 정적 성분(DC, 평균)을 빼 움직임만 남기고, 서브캐리어 평균으로 합친다.
        # 샘플레이트(fs)는 패킷 rate(Hz). 0Hz 근처=느린 움직임(호흡), 높을수록 빠른 움직임.
        wf = self._wf - self._wf.mean(axis=0, keepdims=True)
        win = np.hanning(wf.shape[0])[:, None]  # Hann 윈도우(FFT 누설 감소)
        spec = np.abs(np.fft.rfft(wf * win, axis=0)).mean(axis=1)
        fs = float(p.get("rate") or 0.0) or 50.0
        freqs = np.fft.rfftfreq(self._wf.shape[0], 1.0 / fs)
        # 움직임은 저주파(호흡~0.3, 걷기~1-2Hz)이므로 0~10Hz 만 본다.
        mask = freqs <= 10.0
        sp = spec[mask]
        # 시간 스무딩(EMA)으로 도플러를 안정화(노이즈 완화).
        if self._dop_smooth is None or self._dop_smooth.shape != sp.shape:
            self._dop_smooth = sp
        else:
            self._dop_smooth = 0.7 * self._dop_smooth + 0.3 * sp
        self.dop_curve.setData(freqs[mask], self._dop_smooth)

    def _on_stream_stopped(self, err: object) -> None:
        self._stream_port = None
        self.lbl_stream.setText("스트림: 정지")
        if err:
            self._append_log("스트림: " + str(err))

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
