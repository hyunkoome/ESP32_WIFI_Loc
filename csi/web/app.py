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

== 전역 Hub 구조(중요) ==
보드는 하나뿐인데 시리얼 포트는 동시에 여러 번 못 연다. 그래서 stream/classifier
상태를 **전역 Hub 1개**로 두고, **포트당 stream 스레드는 1개만** 돌린다. 각 브라우저
(WebSocket)는 Hub 의 '구독자'일 뿐이며, Hub 가 모든 구독자에게 동일 데이터를
**broadcast** 한다 → 로컬 PC·핸드폰 등 여러 곳에서 접속해도 모두 같은 실시간 화면.
신규 접속자에게는 현재 상태 snapshot(보드/rx/최근 CSI/방상태/모드)을 즉시 보낸다.

== router 신호원 주의 ==
시리얼 포트를 여는 순간 보드가 리셋(재부팅)된다. 부팅(~1초) 중에 WIFI_CONNECT 를
보내면 씹혀서 라우터에 영영 못 붙는다(→ router CSI 0). 그래서 stream open 후 부팅을
기다렸다가, **router CSI 가 실제로 들어올 때까지 WIFI_CONNECT 를 주기 재전송**한다
(_router_connect_loop). tx(ESP-NOW)는 명령이 필요 없어 자동으로 들어온다.

실행: scripts/csi_app.sh

WebSocket(/ws) 규약:
  클라 → 서버:
    {"action":"ping"}                                    keepalive(무시)
    {"action":"refresh"}                                보드 재감지(+role 비동기)
    {"action":"flash","role":"rx","port":"..."}         해당 포트에 펌웨어 빌드/flash
    {"action":"set_source","port":"..","source":"tx|router|all"}  그 rx 신호원 변경
    {"action":"log_start","mode":"empty|presence|motion"} 모든 rx 로깅 시작
    {"action":"log_stop"}                                모든 rx 로깅 종료(저장)
    {"action":"train"}                                  모든 rx 학습
  서버 → 클라:
    {"type":"boards","boards":[...]}
    {"type":"wifi","ssid":..}
    {"type":"role","port":..,"role":"tx|rx|null","source":..}
    {"type":"flash_progress|flash_done", ...}
    {"type":"rx_added","port":..,"serial":..,"source":..} / {"type":"rx_removed","port":..}
    {"type":"csi","port":..,...metrics/charts...}
    {"type":"room",...} / {"type":"move_event",...} / {"type":"mode",...}
    {"type":"log","line":..} / {"type":"stream_status|stream_stopped", ...}
"""
from __future__ import annotations

import asyncio
import json
import queue
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
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
    RxClassifier, vote_room, read_wifi_config, trained_source_for,
)

app = FastAPI(title="ESP32 CSI 대시보드")
STATIC_DIR = BASE_DIR / "static"

# 차트(진폭/위상/워터폴/도플러)는 패킷마다 보내면 무거우므로 rx 별 ~5Hz 로 throttle.
CHART_PUSH_HZ = 5.0
# router CSI 가 안 들어올 때 WIFI_CONNECT 재전송 간격/최대 횟수.
ROUTER_RETRY_SEC = 2.0
ROUTER_RETRY_MAX = 25


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)   # 브라우저 자동 요청 — 빈 응답(404 로그 제거)


@app.get("/api/boards")
async def api_boards() -> dict[str, object]:
    found = await asyncio.to_thread(boards_mod.discover)
    return {"boards": [b.to_dict() for b in found]}


class RxStream:
    """rx 1개의 stream 스레드 + 분류기 상태(전역, 포트당 1개)."""

    def __init__(self, port: str, serial: str) -> None:
        self.port = port
        self.serial = serial
        self.clf = RxClassifier(serial, port)
        self.send_q: "queue.Queue[str]" = queue.Queue()
        self.stop_ev = threading.Event()
        self.last_push = 0.0                 # 차트 throttle 용
        self.router_seen = threading.Event()  # router CSI 수신됨 → WIFI_CONNECT 재전송 중지
        self.last_csi: dict | None = None    # 최근 csi 메시지(신규 구독자 snapshot 용)


class Hub:
    """전역 상태 + WebSocket 구독자 broadcast.

    보드/stream/classifier 는 전역 1벌이고, 접속한 모든 브라우저(구독자)에게 동일
    데이터를 흘린다. 포트 동시점유 충돌·중복 stream 을 원천 차단한다.
    """

    def __init__(self) -> None:
        self.rx: dict[str, RxStream] = {}      # port -> RxStream (전역)
        self.serials: dict[str, str] = {}      # port -> serial
        self.rx_states: dict[str, str] = {}    # serial -> empty|presence|motion
        self.role_cache: dict[str, tuple[str | None, str | None]] = {}  # port -> (role, src)
        self.boards: list[dict] = []           # 최근 보드 목록(snapshot 용)
        self.logging_mode: str | None = None
        self.wifi: tuple[str, str] = read_wifi_config()
        self.subscribers: set[asyncio.Queue] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.lock = threading.RLock()
        self.started = False                   # 첫 접속에서 보드 감지 1회 트리거
        self.refreshing = False

    def broadcast(self, obj: dict) -> None:
        """모든 구독자에게 메시지 전송(stream 백그라운드 스레드에서 호출)."""
        loop = self.loop
        if loop is None:
            return

        def _put() -> None:
            for q in list(self.subscribers):
                try:
                    q.put_nowait(obj)
                except Exception:
                    pass

        loop.call_soon_threadsafe(_put)


hub = Hub()


# ---- 보드 감지 / role ------------------------------------------------------
def detect_role_bg(port: str) -> None:
    # 스트림 중인 포트는 role 재감지 스킵(포트락 충돌 방지).
    if port in hub.rx:
        hub.broadcast({"type": "role", "port": port, "role": "rx", "source": "stream"})
        return
    cached = hub.role_cache.get(port)
    if cached and cached[0] is not None:
        role, src = cached          # 캐시 적중 — 재감지 생략(즉시 표시)
    else:
        with port_lock(port):
            role, src = role_detect.detect_role(port, timeout=4.0)
        if role is not None:        # 감지 실패(None)는 캐시하지 않음 → 다음에 재시도
            hub.role_cache[port] = (role, src)
    hub.broadcast({"type": "role", "port": port, "role": role, "source": src})
    if role == "rx":
        ensure_rx(port)


def do_refresh() -> None:
    with hub.lock:
        if hub.refreshing:
            return
        hub.refreshing = True
    try:
        found = boards_mod.discover()
        present = set()
        for b in found:
            present.add(b.port)
            hub.serials[b.port] = b.serial or b.port
        hub.boards = [b.to_dict() for b in found]
        hub.broadcast({"type": "boards", "boards": hub.boards})
        hub.broadcast({"type": "wifi", "ssid": hub.wifi[0]})
        # 더 이상 안 보이는 보드의 rx 스트림 제거.
        for port in list(hub.rx):
            if port not in present:
                remove_rx(port)
        for b in found:
            threading.Thread(target=detect_role_bg, args=(b.port,), daemon=True).start()
    finally:
        hub.refreshing = False


# ---- rx 스트림 생성/제거 ---------------------------------------------------
def ensure_rx(port: str) -> None:
    with hub.lock:
        if port in hub.rx:
            return
        serial = hub.serials.get(port, port)
        rs = RxStream(port, serial)
        hub.rx[port] = rs
        # 신호원 기본값: 이 디바이스가 학습된 source(yaml classifiers[serial])가 있으면
        # 그대로(예: 8007=tx, 2284=router), 없으면 순서(첫 rx=router, 2번째부터 tx).
        source = trained_source_for(serial) or ("router" if len(hub.rx) == 1 else "tx")
        rs.clf.set_source(source)
    hub.broadcast({"type": "rx_added", "port": port, "serial": serial, "source": source})
    hub.broadcast({"type": "log", "line": f"rx tab added: {port} ({serial})"})
    start_stream(rs)
    if source == "router":
        _ensure_router_connected(rs)
    refresh_mode()


def remove_rx(port: str) -> None:
    with hub.lock:
        rs = hub.rx.pop(port, None)
        if rs is None:
            return
        hub.rx_states.pop(rs.serial, None)
    rs.stop_ev.set()
    hub.broadcast({"type": "rx_removed", "port": port})
    hub.broadcast({"type": "log", "line": f"rx tab removed: {port}"})
    push_room()
    refresh_mode()


def start_stream(rs: RxStream) -> None:
    def run() -> None:
        with port_lock(rs.port):
            hub.broadcast({"type": "stream_status", "msg": f"{rs.port} CSI 수신 시작"})
            err = csi_stream.stream_csi(
                rs.port, rs.stop_ev,
                lambda d: on_csi(rs, d),
                send_q=rs.send_q)
        hub.broadcast({"type": "stream_stopped", "port": rs.port, "error": err})

    threading.Thread(target=run, daemon=True).start()


# ---- router 자동 접속(부팅 대기 + CSI 올 때까지 WIFI_CONNECT 재전송) --------
def _ensure_router_connected(rs: RxStream) -> None:
    """stream open(=보드 리셋) 후 부팅을 기다렸다가 WIFI_CONNECT 를 보내고, router CSI 가
    실제로 들어올 때까지 주기 재전송한다. 포트 open 직후(부팅 중) 1회 전송이 씹히는
    문제를 근본 해결한다(직접 디버깅으로 확인: 부팅 후 보내면 ~2.3초만에 접속)."""
    rs.router_seen.clear()

    def loop() -> None:
        for i in range(ROUTER_RETRY_MAX):
            # 첫 대기(ROUTER_RETRY_SEC)로 보드 부팅(~1초) 완료를 보장한 뒤 전송.
            if rs.stop_ev.wait(ROUTER_RETRY_SEC):
                return                       # stream 종료됨
            if rs.router_seen.is_set():
                return                       # router CSI 들어옴 → 접속 성공
            _send_wifi_connect(rs, retry=(i > 0))

    threading.Thread(target=loop, daemon=True).start()


def _send_wifi_connect(rs: RxStream, retry: bool = False) -> None:
    ssid, pw = hub.wifi
    tag = rs.serial[-4:] if rs.serial else rs.port
    if not ssid:
        hub.broadcast({"type": "log", "line": f"[{tag}] No router SSID in config/wifi_config.yaml"})
        hub.broadcast({"type": "need_wifi", "port": rs.port})
        return
    rs.send_q.put(csi_stream.wifi_connect_cmd(ssid, pw))
    note = " (retry)" if retry else ""
    hub.broadcast({"type": "log",
                   "line": f"[{tag}] WIFI_CONNECT → \"{ssid}\"{note}"})


# ---- CSI 패킷 → 분류기 → broadcast(throttle) ------------------------------
def on_csi(rs: RxStream, p: dict) -> None:
    if p.get("source") == "router":
        rs.router_seen.set()               # router CSI 수신 → 재전송 루프 중지 신호
    res = rs.clf.update(p)
    if res is None:
        return
    # 상태 변화/움직임 이벤트는 즉시 처리(throttle 무관) — 방 상태 voting 반영.
    if res["state_changed"]:
        hub.rx_states[rs.serial] = res["state"]
        push_room()
    if res["move_event"]:
        hub.broadcast({"type": "move_event", "serial": rs.serial,
                       "doppler": res["doppler"], "ts": time.strftime("%H:%M:%S")})
    if rs.clf.logging_mode:
        res["log_count"] = rs.clf.log_count()
    # 차트는 rx 별 ~CHART_PUSH_HZ 로 제한(모바일/대역폭 보호).
    now = time.monotonic()
    if now - rs.last_push < (1.0 / CHART_PUSH_HZ):
        return
    rs.last_push = now
    out = {"type": "csi", "port": rs.port, "serial": rs.serial}
    out.update(res)
    rs.last_csi = out                      # 신규 구독자 snapshot 용
    hub.broadcast(out)


# ---- 방 상태 voting / 모드 ------------------------------------------------
def push_room() -> None:
    room = vote_room(hub.rx_states)
    hub.broadcast({"type": "room", "room": room, "rx_states": dict(hub.rx_states)})


def refresh_mode() -> None:
    if hub.logging_mode:
        hub.broadcast({"type": "mode", "mode": "logging", "detail": hub.logging_mode})
    elif hub.rx:
        hub.broadcast({"type": "mode", "mode": "detecting", "detail": str(len(hub.rx))})
    else:
        hub.broadcast({"type": "mode", "mode": "idle", "detail": ""})


# ---- 신호원 변경 -----------------------------------------------------------
def set_source(port: str, source: str) -> None:
    rs = hub.rx.get(port)
    if rs is None:
        return
    tag = rs.serial[-4:] if rs.serial else port
    rs.clf.set_source(source)
    if source == "router":
        _ensure_router_connected(rs)       # 부팅 대기 + 재전송 루프
    elif source == "tx":
        rs.router_seen.set()               # 재전송 루프가 돌고 있으면 중지
        rs.send_q.put("WIFI_DISCONNECT")
        hub.broadcast({"type": "log", "line": f"[{tag}] WIFI_DISCONNECT → back to tx (ESP-NOW)"})
    hub.broadcast({"type": "log", "line": f"[{tag}] source → {source}"})


# ---- flash -----------------------------------------------------------------
def do_flash(role: str, port: str) -> None:
    if port in hub.rx:
        remove_rx(port)
    hub.role_cache.pop(port, None)         # 펌웨어가 바뀌므로 role 캐시 무효화

    def run() -> None:
        ok = False
        with port_lock(port):
            hub.broadcast({"type": "flash_progress", "port": port, "line": f"[flash] role={role} 시작"})
            if not flasher.is_built(role):
                hub.broadcast({"type": "flash_progress", "port": port,
                               "line": "[build] 펌웨어 빌드(최초, 수 분 소요)..."})
                rc = flasher.build(
                    role,
                    on_line=lambda l: hub.broadcast({"type": "flash_progress", "port": port, "line": l}),
                )
                if rc != 0:
                    hub.broadcast({"type": "flash_done", "port": port, "ok": False, "msg": "빌드 실패"})
                    return
            rc = flasher.flash(
                role, port,
                on_line=lambda l: hub.broadcast({"type": "flash_progress", "port": port, "line": l}),
            )
            ok = rc == 0
            hub.broadcast({"type": "flash_done", "port": port, "ok": ok, "role": role})
        if ok:
            time.sleep(3)
            detect_role_bg(port)

    threading.Thread(target=run, daemon=True).start()


# ---- 공용 로깅(모든 rx 동시) / 학습 ---------------------------------------
def do_log_start(mode: str) -> None:
    if not hub.rx:
        hub.broadcast({"type": "log", "line": "No rx to log (connect/detect an rx board first)."})
        return
    if hub.logging_mode is not None:
        return
    for rs in hub.rx.values():
        rs.clf.start_logging(mode)
    hub.logging_mode = mode
    hub.broadcast({"type": "log",
                   "line": f"All rx ({len(hub.rx)}) started {mode} logging — click again to finish"})
    refresh_mode()


def do_log_stop() -> None:
    if hub.logging_mode is None:
        return
    mode = hub.logging_mode
    n = 0
    for rs in hub.rx.values():
        if rs.clf.stop_logging():
            n += 1
            hub.broadcast({"type": "log",
                           "line": f"[{rs.serial[-4:]}] raw saved → dataset/csi_logs/{rs.clf.csv_name}"})
    hub.logging_mode = None
    hub.broadcast({"type": "log", "line": f"{mode} logging saved ({n} rx)"})
    refresh_mode()


def do_train() -> None:
    if not hub.rx:
        hub.broadcast({"type": "log", "line": "No rx to train."})
        return
    ok = 0
    for rs in hub.rx.values():
        success, msg = rs.clf.train()
        hub.broadcast({"type": "log", "line": msg})
        if success:
            ok += 1
    hub.broadcast({"type": "log",
                   "line": f"Training done: {ok}/{len(hub.rx)} rx — live detection started."})
    refresh_mode()


# ---- WebSocket: 구독자 등록 + snapshot + 액션 루프 -------------------------
def _send_snapshot(q: asyncio.Queue) -> None:
    """신규 구독자에게 현재 상태를 기존 메시지 타입으로 재생(JS 핸들러 그대로 재사용)."""
    def put(o: dict) -> None:
        try:
            q.put_nowait(o)
        except Exception:
            pass

    put({"type": "boards", "boards": hub.boards})
    put({"type": "wifi", "ssid": hub.wifi[0]})
    # 비-rx 보드 role(tx 등) 뱃지.
    for port, (role, src) in hub.role_cache.items():
        if port not in hub.rx:
            put({"type": "role", "port": port, "role": role, "source": src})
    # 현재 rx: role 뱃지 + 카드 + 최근 CSI(차트 즉시 표시).
    for port, rs in hub.rx.items():
        put({"type": "role", "port": port, "role": "rx", "source": "stream"})
        put({"type": "rx_added", "port": port, "serial": rs.serial, "source": rs.clf.want_source})
        if rs.last_csi is not None:
            put(rs.last_csi)
    put({"type": "room", "room": vote_room(hub.rx_states), "rx_states": dict(hub.rx_states)})
    if hub.logging_mode:
        put({"type": "mode", "mode": "logging", "detail": hub.logging_mode})
    elif hub.rx:
        put({"type": "mode", "mode": "detecting", "detail": str(len(hub.rx))})
    else:
        put({"type": "mode", "mode": "idle", "detail": ""})


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    hub.loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()
    hub.subscribers.add(q)

    async def sender() -> None:
        while True:
            item = await q.get()
            await websocket.send_text(json.dumps(item, ensure_ascii=False, default=str))

    sender_task = asyncio.create_task(sender())

    # 신규 접속자에게 현재 상태 즉시 표시.
    _send_snapshot(q)
    # 서버 생애 첫 접속이면 보드 감지/스트림 1회 시작(이후엔 전역 stream 이 계속 돈다).
    if not hub.started:
        hub.started = True
        threading.Thread(target=do_refresh, daemon=True).start()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            action = msg.get("action")
            if action == "ping":
                continue                     # keepalive — 무시
            elif action == "refresh":
                threading.Thread(target=do_refresh, daemon=True).start()
            elif action == "flash":
                do_flash(str(msg.get("role")), str(msg.get("port")))
            elif action == "set_source":
                set_source(str(msg.get("port")), str(msg.get("source")))
            elif action == "log_start":
                do_log_start(str(msg.get("mode")))
            elif action == "log_stop":
                do_log_stop()
            elif action == "train":
                do_train()
    except WebSocketDisconnect:
        pass
    finally:
        # 구독자만 제거. 전역 stream 은 다른 구독자/다음 접속을 위해 계속 유지한다.
        hub.subscribers.discard(q)
        sender_task.cancel()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
