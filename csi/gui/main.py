"""CSI 통합 데스크톱 GUI (PyQt5 + pyqtgraph).

web(csi/web) 과 동일한 csi/common 백엔드(boards/role_detect/flasher/csi_stream/
port_lock)를 쓴다. 보드 실시간 감지·role 자동표시·tx/rx 펌웨어 다운로드·CSI 진폭/
위상 실시간 플롯을 한 창에서 제공한다. 디바이스 I/O 는 QThread(백그라운드 스레드)에서
돌고 pyqtSignal 로 UI 를 갱신한다(web 의 loop.call_soon_threadsafe 와 대칭).

실행: scripts/csi_gui.sh  (또는 python csi/gui/main.py)
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg

# csi/common 공용 백엔드 import (csi/gui → csi/common).
_CSI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CSI / "common"))

import boards as boards_mod   # noqa: E402
import csi_stream             # noqa: E402
import flasher                # noqa: E402
import role_detect            # noqa: E402
from port_lock import port_lock  # noqa: E402


class Bridge(QtCore.QObject):
    """워커 스레드 → UI 시그널(스레드 안전 갱신)."""

    boards_ready = QtCore.pyqtSignal(list)
    role_ready = QtCore.pyqtSignal(str, object, str)   # port, role|None, source
    flash_line = QtCore.pyqtSignal(str)
    flash_done = QtCore.pyqtSignal(str, bool)
    csi_packet = QtCore.pyqtSignal(dict)
    stream_stopped = QtCore.pyqtSignal(object)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ESP32 CSI 대시보드 (GUI)")
        self.resize(1000, 780)

        self.bridge = Bridge()
        self.bridge.boards_ready.connect(self._on_boards)
        self.bridge.role_ready.connect(self._on_role)
        self.bridge.flash_line.connect(self._append_log)
        self.bridge.flash_done.connect(self._on_flash_done)
        self.bridge.csi_packet.connect(self._on_csi)
        self.bridge.stream_stopped.connect(self._on_stream_stopped)

        self._badges: dict[str, QtWidgets.QLabel] = {}
        self._stream_stop = threading.Event()
        self._streaming = False

        self._build_ui()
        self.refresh()

    # ---- UI 구성 ----
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("<b>연결된 보드</b> · 실시간 감지 · role 자동표시"))
        top.addStretch(1)
        btn_refresh = QtWidgets.QPushButton("🔄 새로고침")
        btn_refresh.clicked.connect(self.refresh)
        top.addWidget(btn_refresh)
        v.addLayout(top)

        self.board_box = QtWidgets.QVBoxLayout()
        board_w = QtWidgets.QWidget()
        board_w.setLayout(self.board_box)
        v.addWidget(board_w)

        ctl = QtWidgets.QHBoxLayout()
        ctl.addWidget(QtWidgets.QLabel("CSI rx:"))
        self.rx_combo = QtWidgets.QComboBox()
        ctl.addWidget(self.rx_combo)
        self.btn_stream = QtWidgets.QPushButton("▶ 스트림 시작")
        self.btn_stream.clicked.connect(self._toggle_stream)
        ctl.addWidget(self.btn_stream)
        self.lbl_stats = QtWidgets.QLabel("rate: -  RSSI: -  sub: -")
        ctl.addWidget(self.lbl_stats)
        ctl.addStretch(1)
        v.addLayout(ctl)

        self.amp_plot = pg.PlotWidget(title="진폭 |H|")
        self.amp_curve = self.amp_plot.plot(pen=pg.mkPen("#4aa3ff", width=1.5))
        self.phase_plot = pg.PlotWidget(title="위상 ∠H (rad)")
        self.phase_plot.setYRange(-3.2, 3.2)
        self.phase_curve = self.phase_plot.plot(pen=pg.mkPen("#f5a623", width=1.5))
        v.addWidget(self.amp_plot)
        v.addWidget(self.phase_plot)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        v.addWidget(self.log)

    # ---- 보드 감지 ----
    def refresh(self) -> None:
        def work() -> None:
            found = boards_mod.discover()
            self.bridge.boards_ready.emit([b.to_dict() for b in found])
            for b in found:
                def det(port: str = b.port) -> None:
                    with port_lock(port):
                        role, src = role_detect.detect_role(port, timeout=4.0)
                    self.bridge.role_ready.emit(port, role, src)
                threading.Thread(target=det, daemon=True).start()
        threading.Thread(target=work, daemon=True).start()

    def _on_boards(self, boards: list) -> None:
        # 기존 카드 제거.
        while self.board_box.count():
            item = self.board_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._badges.clear()
        self.rx_combo.clear()

        for b in boards:
            self.rx_combo.addItem(b["port"], b["port"])
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(
                f"{b['port']}  serial={b['serial']}  [{b['vid_pid']}]"
                + ("" if b["accessible"] else "  ⚠권한없음")
            ))
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
        badge = self._badges.get(port)
        if badge:
            badge.setText(str(role).upper() if role else "role?")
        for i in range(self.rx_combo.count()):
            if self.rx_combo.itemData(i) == port:
                self.rx_combo.setItemText(i, f"{port}" + (f" ({role})" if role else ""))

    # ---- flash ----
    def _flash(self, role: str, port: str) -> None:
        if QtWidgets.QMessageBox.question(
            self, "flash 확인",
            f"{port} 에 {role} 펌웨어를 flash할까요?\n(보드의 기존 펌웨어를 덮어씁니다)",
        ) != QtWidgets.QMessageBox.Yes:
            return
        self._append_log(f"--- flash {role} → {port} ---")

        def work() -> None:
            with port_lock(port):
                if not flasher.is_built(role):
                    self.bridge.flash_line.emit("[build] 펌웨어 빌드(최초, 수 분 소요)...")
                    rc = flasher.build(role, on_line=lambda l: self.bridge.flash_line.emit(l))
                    if rc != 0:
                        self.bridge.flash_done.emit(port, False)
                        return
                rc = flasher.flash(role, port, on_line=lambda l: self.bridge.flash_line.emit(l))
                self.bridge.flash_done.emit(port, rc == 0)
        threading.Thread(target=work, daemon=True).start()

    def _on_flash_done(self, port: str, ok: bool) -> None:
        self._append_log(("✓ flash 완료 " if ok else "✗ flash 실패 ") + port)
        if ok:
            QtCore.QTimer.singleShot(3000, self.refresh)

    # ---- CSI 스트림 ----
    def _toggle_stream(self) -> None:
        if self._streaming:
            self._stream_stop.set()
            self._streaming = False
            self.btn_stream.setText("▶ 스트림 시작")
            return
        port = self.rx_combo.currentData()
        if not port:
            return
        self._stream_stop = threading.Event()
        ev = self._stream_stop
        self._streaming = True
        self.btn_stream.setText("⏸ 중지")

        def work() -> None:
            with port_lock(port):
                err = csi_stream.stream_csi(port, ev, lambda d: self.bridge.csi_packet.emit(d))
            self.bridge.stream_stopped.emit(err)
        threading.Thread(target=work, daemon=True).start()

    def _on_csi(self, p: dict) -> None:
        self.lbl_stats.setText(f"rate: {p['rate']}  RSSI: {p['rssi']}  sub: {p['n_sub']}")
        self.amp_curve.setData(p["amplitude"])
        self.phase_curve.setData(p["phase"])

    def _on_stream_stopped(self, err: object) -> None:
        self._streaming = False
        self.btn_stream.setText("▶ 스트림 시작")
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
