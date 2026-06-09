"""CSI 통합 웹 대시보드 백엔드(FastAPI) — csi/gui 데스크톱 GUI 와 기능 동등 포팅.

핸드폰/PC 브라우저에서 http://<PC-IP>:8000 으로 접속해 데스크톱 GUI(csi/gui/main.py)
와 동일한 일을 한다:
  1) 연결된 보드 실시간 감지 + role(tx/rx) 자동 표시(펌웨어 DEVICE_ROLE)
  2) 보드별 tx/rx 펌웨어 빌드·다운로드(flash)
  3) rx 보드마다 신호원(tx / wifi router / all) 선택 + CSI 진폭/위상/워터폴/도플러 차트
  4) 메트릭(std=진폭 std, doppler=도플러 피크) + 3상태 판정(Empty/Presence/Motion)
  5) 공용 로깅 토글(Log Empty/Presence/Motion) — 모든 rx 동시, dataset/csi_logs CSV
  6) Train Classifier — 상태별 최근 CSV 로 std_th/doppler_th 학습(yaml 갱신)
  7) Space Monitoring — rx 별 3상태 + 다중 링크 voting 최종 방 상태(ROOM) + 이벤트 로그

계산 로직(메트릭/3상태/train/voting)은 csi/common/classifier.py 로 GUI 와 공유 →
**브라우저에 표시되는 숫자가 데스크톱 GUI 와 일치**한다. 디바이스 I/O 는 csi/common
(boards/role_detect/flasher/csi_stream/port_lock)을 그대로 재사용(중복 구현 없음).

서버는 0.0.0.0 으로 바인딩(scripts/csi_app.sh 의 HOST) 하면 같은 LAN 의 핸드폰에서
접속할 수 있다.

실행: scripts/csi_app.sh

WebSocket(/ws) 규약:
  클라 → 서버:
    {"action":"refresh"}                                보드 재감지(+role 비동기)
    {"action":"flash","role":"rx","port":"..."}         해당 포트에 펌웨어 빌드/flash
    {"action":"set_source","port":"..","source":"tx|router|all"}  그 rx 신호원 변경
    {"action":"set_wifi","ssid":"..","password":".."}   라우터 자격증명(브라우저 입력)
    {"action":"log_start","mode":"empty|presence|motion"} 모든 rx 로깅 시작
    {"action":"log_stop"}                                모든 rx 로깅 종료(저장)
    {"action":"train"}                                  모든 rx 학습
  서버 → 클라:
    {"type":"boards","boards":[...]}
    {"type":"role","port":..,"role":"tx|rx|null","source":..}
    {"type":"flash_progress","port":..,"line":..}
    {"type":"flash_done","port":..,"ok":bool,"role":..}
    {"type":"rx_added","port":..,"serial":..,"source":..}   rx 감지 → 카드/차트 생성
    {"type":"rx_removed","port":..}
    {"type":"csi","port":..,...metrics/charts...}          rx 별 차트·메트릭·상태
    {"type":"room","room":"empty|presence|motion","rx_states":{serial:state}}
    {"type":"move_event","serial":..,"doppler":..,"ts":..}
    {"type":"mode","mode":"idle|logging|detecting","detail":..}
    {"type":"log","line":..}
    {"type":"stream_status","msg":..} / {"type":"stream_stopped","port":..,"error":..}
"""
from __future__ import annotations

import asyncio
import json
import queue
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# csi/common 공용 백엔드 import (csi/web → csi/common).
BASE_DIR = Path(__file__).resolve().parent        # csi/web
CSI_DIR = BASE_DIR.parent                          # csi
sys.path.insert(0, str(CSI_DIR / "common"))

import boards as boards_mod   # noqa: E402
import csi_stream             # noqa: E402
import flasher                # noqa: E402
import role_detect            # noqa: E402
from port_lock import port_lock  # noqa: E402
from classifier import (        # noqa: E402
    RxClassifier, vote_room, read_wifi_config,
)

app = FastAPI(title="ESP32 CSI 대시보드")
STATIC_DIR = BASE_DIR / "static"

# 차트(진폭/위상/워터폴/도플러)는 패킷마다 보내면 무거우므로 rx 별 ~5Hz 로 throttle.
CHART_PUSH_HZ = 5.0


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/boards")
async def api_boards() -> dict[str, object]:
    found = await asyncio.to_thread(boards_mod.discover)
    return {"boards": [b.to_dict() for b in found]}


class RxStream:
    """rx 1개의 스트림 스레드 + 분류기 상태(서버 측). 신호원/로깅/명령전송을 담는다."""

    def __init__(self, port: str, serial: str) -> None:
        self.port = port
        self.serial = serial
        self.clf = RxClassifier(serial, port)
        self.send_q: "queue.Queue[str]" = queue.Queue()
        self.stop_ev = threading.Event()
        self.last_push = 0.0   # 차트 throttle 용


class Session:
    """WebSocket 연결 1개 = 대시보드 세션. rx 스트림/로깅/방상태를 보관."""

    def __init__(self) -> None:
        self.rx: dict[str, RxStream] = {}       # port -> RxStream
        self.serials: dict[str, str] = {}       # port -> serial
        self.rx_states: dict[str, str] = {}     # serial -> empty|presence|motion
        self.logging_mode: str | None = None    # 공용 로깅 토글
        self.wifi: tuple[str, str] = read_wifi_config()  # 라우터 자격증명(브라우저로 갱신 가능)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    loop = asyncio.get_running_loop()
    out_q: asyncio.Queue = asyncio.Queue()
    sess = Session()

    def push(obj: dict[str, object]) -> None:
        loop.call_soon_threadsafe(out_q.put_nowait, obj)

    async def sender() -> None:
        while True:
            item = await out_q.get()
            await websocket.send_text(json.dumps(item, ensure_ascii=False, default=str))

    sender_task = asyncio.create_task(sender())

    # ---- 보드 감지/role ----------------------------------------------------
    def detect_role_bg(port: str) -> None:
        # 스트림 중인 포트는 role 재감지 스킵(포트락 충돌 방지) — GUI refresh 와 동일.
        if port in sess.rx:
            push({"type": "role", "port": port, "role": "rx", "source": "stream"})
            return
        with port_lock(port):
            role, src = role_detect.detect_role(port, timeout=4.0)
        push({"type": "role", "port": port, "role": role, "source": src})
        if role == "rx":
            ensure_rx(port)

    def do_refresh() -> None:
        found = boards_mod.discover()
        present = set()
        for b in found:
            present.add(b.port)
            sess.serials[b.port] = b.serial or b.port
        push({"type": "boards", "boards": [b.to_dict() for b in found]})
        # 더 이상 안 보이는 보드의 rx 스트림 제거.
        for port in list(sess.rx):
            if port not in present:
                remove_rx(port)
        for b in found:
            threading.Thread(target=detect_role_bg, args=(b.port,), daemon=True).start()

    # ---- rx 스트림 생성/제거 ----------------------------------------------
    def ensure_rx(port: str) -> None:
        if port in sess.rx:
            return
        serial = sess.serials.get(port, port)
        rs = RxStream(port, serial)
        sess.rx[port] = rs
        # 첫 rx 는 'wifi router'(WIFI_CONNECT), 2번째부터 'tx' — GUI 자동설정과 동일.
        first = len(sess.rx) == 1
        source = "router" if first else "tx"
        rs.clf.set_source(source)
        push({"type": "rx_added", "port": port, "serial": serial, "source": source})
        push({"type": "log", "line": f"rx tab added: {port} ({serial})"})
        if source == "router":
            _send_wifi_connect(rs)
        start_stream(rs)
        refresh_mode()

    def remove_rx(port: str) -> None:
        rs = sess.rx.pop(port, None)
        if rs is None:
            return
        rs.stop_ev.set()
        sess.rx_states.pop(rs.serial, None)
        push({"type": "rx_removed", "port": port})
        push({"type": "log", "line": f"rx tab removed: {port}"})
        push_room()
        refresh_mode()

    def start_stream(rs: RxStream) -> None:
        def run() -> None:
            with port_lock(rs.port):
                push({"type": "stream_status", "msg": f"{rs.port} CSI 수신 시작"})
                err = csi_stream.stream_csi(
                    rs.port, rs.stop_ev,
                    lambda d: on_csi(rs, d),
                    send_q=rs.send_q)
            push({"type": "stream_stopped", "port": rs.port, "error": err})
        threading.Thread(target=run, daemon=True).start()

    # ---- CSI 패킷 → 분류기 → push(throttle) -------------------------------
    def on_csi(rs: RxStream, p: dict) -> None:
        res = rs.clf.update(p)
        if res is None:
            return
        # 상태 변화/움직임 이벤트는 즉시 처리(throttle 무관) — 방 상태 voting 반영.
        if res["state_changed"]:
            sess.rx_states[rs.serial] = res["state"]
            push_room()
        if res["move_event"]:
            push({"type": "move_event", "serial": rs.serial,
                  "doppler": res["doppler"], "ts": time.strftime("%H:%M:%S")})
        # 로깅 중 진행상황(샘플 수/경과초) 표시.
        if rs.clf.logging_mode:
            res["log_count"] = rs.clf.log_count()
        # 차트는 rx 별 ~CHART_PUSH_HZ 로 제한(모바일/대역폭 보호). 메트릭/상태는 차트에
        # 실어 같이 보낸다(별도 고빈도 push 안 함).
        now = time.monotonic()
        if now - rs.last_push < (1.0 / CHART_PUSH_HZ):
            return
        rs.last_push = now
        out = {"type": "csi", "port": rs.port, "serial": rs.serial}
        out.update(res)
        push(out)

    # ---- 방 상태 voting push ----------------------------------------------
    def push_room() -> None:
        room = vote_room(sess.rx_states)
        push({"type": "room", "room": room, "rx_states": dict(sess.rx_states)})

    # ---- 모드 표시(Idle/Logging/Detecting) --------------------------------
    def refresh_mode() -> None:
        if sess.logging_mode:
            push({"type": "mode", "mode": "logging", "detail": sess.logging_mode})
        elif sess.rx:
            push({"type": "mode", "mode": "detecting", "detail": str(len(sess.rx))})
        else:
            push({"type": "mode", "mode": "idle", "detail": ""})

    # ---- 신호원 변경 -------------------------------------------------------
    def _send_wifi_connect(rs: RxStream) -> None:
        ssid, pw = sess.wifi
        tag = rs.serial[-4:] if rs.serial else rs.port
        if not ssid:
            push({"type": "log", "line": f"[{tag}] No router SSID — set it in the Wi-Fi panel"})
            push({"type": "need_wifi", "port": rs.port})
            return
        rs.send_q.put(csi_stream.wifi_connect_cmd(ssid, pw))
        push({"type": "log",
              "line": f"[{tag}] WIFI_CONNECT → \"{ssid}\" (rx attempting to connect to router)"})

    def set_source(port: str, source: str) -> None:
        rs = sess.rx.get(port)
        if rs is None:
            return
        tag = rs.serial[-4:] if rs.serial else port
        rs.clf.set_source(source)
        if source == "router":
            _send_wifi_connect(rs)
        elif source == "tx":
            rs.send_q.put("WIFI_DISCONNECT")
            push({"type": "log", "line": f"[{tag}] WIFI_DISCONNECT → back to tx (ESP-NOW) channel"})
        push({"type": "log", "line": f"[{tag}] source → {source}"})

    # ---- flash -------------------------------------------------------------
    def do_flash(role: str, port: str) -> None:
        # 그 포트의 rx 스트림이 있으면 멈추고 flash(포트 점유 해제) — GUI 와 동일.
        if port in sess.rx:
            remove_rx(port)

        def run() -> None:
            ok = False
            with port_lock(port):
                push({"type": "flash_progress", "port": port, "line": f"[flash] role={role} 시작"})
                if not flasher.is_built(role):
                    push({"type": "flash_progress", "port": port,
                          "line": "[build] 펌웨어 빌드(최초, 수 분 소요)..."})
                    rc = flasher.build(
                        role,
                        on_line=lambda l: push({"type": "flash_progress", "port": port, "line": l}),
                    )
                    if rc != 0:
                        push({"type": "flash_done", "port": port, "ok": False, "msg": "빌드 실패"})
                        return
                rc = flasher.flash(
                    role, port,
                    on_line=lambda l: push({"type": "flash_progress", "port": port, "line": l}),
                )
                ok = rc == 0
                push({"type": "flash_done", "port": port, "ok": ok, "role": role})
            if ok:
                time.sleep(3)
                detect_role_bg(port)
        threading.Thread(target=run, daemon=True).start()

    # ---- 공용 로깅(모든 rx 동시) ------------------------------------------
    def do_log_start(mode: str) -> None:
        if not sess.rx:
            push({"type": "log", "line": "No rx to log (connect/detect an rx board first)."})
            return
        if sess.logging_mode is not None:
            return
        for rs in sess.rx.values():
            rs.clf.start_logging(mode)
        sess.logging_mode = mode
        push({"type": "log",
              "line": f"All rx ({len(sess.rx)}) started {mode} logging — click again to finish"})
        refresh_mode()

    def do_log_stop() -> None:
        if sess.logging_mode is None:
            return
        mode = sess.logging_mode
        n = 0
        for rs in sess.rx.values():
            if rs.clf.stop_logging():
                n += 1
                push({"type": "log",
                      "line": f"[{rs.serial[-4:]}] raw saved → dataset/csi_logs/{rs.clf.csv_name}"})
        sess.logging_mode = None
        push({"type": "log", "line": f"{mode} logging saved ({n} rx)"})
        refresh_mode()

    def do_train() -> None:
        if not sess.rx:
            push({"type": "log", "line": "No rx to train."})
            return
        ok = 0
        for rs in sess.rx.values():
            success, msg = rs.clf.train()
            push({"type": "log", "line": msg})
            if success:
                ok += 1
        push({"type": "log",
              "line": f"Training done: {ok}/{len(sess.rx)} rx — live detection started."})
        refresh_mode()

    # ---- 메시지 루프 -------------------------------------------------------
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            action = msg.get("action")
            if action == "refresh":
                threading.Thread(target=do_refresh, daemon=True).start()
            elif action == "flash":
                do_flash(str(msg.get("role")), str(msg.get("port")))
            elif action == "set_source":
                set_source(str(msg.get("port")), str(msg.get("source")))
            elif action == "set_wifi":
                sess.wifi = (str(msg.get("ssid") or ""), str(msg.get("password") or ""))
                push({"type": "log", "line": f"Wi-Fi credentials set: \"{sess.wifi[0]}\""})
                # router 신호원인 rx 들에 즉시 재연결 명령.
                for rs in sess.rx.values():
                    if rs.clf.want_source == "router":
                        _send_wifi_connect(rs)
            elif action == "log_start":
                do_log_start(str(msg.get("mode")))
            elif action == "log_stop":
                do_log_stop()
            elif action == "train":
                do_train()
    except WebSocketDisconnect:
        pass
    finally:
        for rs in sess.rx.values():
            rs.stop_ev.set()
        sender_task.cancel()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
