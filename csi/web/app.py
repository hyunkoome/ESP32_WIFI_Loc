"""CSI 통합 웹 대시보드 백엔드(FastAPI).

하나의 화면에서:
  1) 연결된 보드 실시간 감지 + role(tx/rx) 자동 표시(펌웨어 DEVICE_ROLE)
  2) 보드별 tx/rx 펌웨어 빌드·다운로드(flash)
  3) rx 보드의 CSI 진폭/위상 실시간 시각화

config_devices.yaml 의존 없음 — csi/common 의 공용 백엔드(boards/role_detect/
flasher/csi_stream/port_lock)를 그대로 쓴다. GUI(csi/gui)도 같은 백엔드를 호출한다.

실행: scripts/csi_app.sh

WebSocket(/ws) 규약:
  클라 → 서버:
    {"action":"refresh"}                       연결 보드 재감지(+role 비동기)
    {"action":"flash","role":"rx","port":"..."} 해당 포트에 펌웨어 빌드/flash
    {"action":"stream_start","port":"..."}      그 rx 포트의 CSI 스트림 시작
    {"action":"stream_stop"}
  서버 → 클라:
    {"type":"boards","boards":[...]}            보드 목록(USB 정보)
    {"type":"role","port":..,"role":"tx|rx|null","source":..}
    {"type":"flash_progress","port":..,"line":..}
    {"type":"flash_done","port":..,"ok":bool,"role":..}
    {"type":"csi","rssi":..,"n_sub":..,"rate":..,"amplitude":[..],"phase":[..]}
    {"type":"stream_status","msg":..} / {"type":"stream_stopped","error":..}
"""
from __future__ import annotations

import asyncio
import json
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

app = FastAPI(title="ESP32 CSI 대시보드")
STATIC_DIR = BASE_DIR / "static"


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/boards")
async def api_boards() -> dict[str, object]:
    found = await asyncio.to_thread(boards_mod.discover)
    return {"boards": [b.to_dict() for b in found]}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    loop = asyncio.get_running_loop()
    out_q: asyncio.Queue = asyncio.Queue()
    stream_stop = threading.Event()

    def push(obj: dict[str, object]) -> None:
        loop.call_soon_threadsafe(out_q.put_nowait, obj)

    async def sender() -> None:
        while True:
            item = await out_q.get()
            await websocket.send_text(json.dumps(item, ensure_ascii=False, default=str))

    sender_task = asyncio.create_task(sender())

    def detect_role_bg(port: str) -> None:
        """포트 role 을 백그라운드로 감지해 push(포트 점유 직렬화)."""
        with port_lock(port):
            role, src = role_detect.detect_role(port, timeout=4.0)
        push({"type": "role", "port": port, "role": role, "source": src})

    def do_refresh() -> None:
        found = boards_mod.discover()
        push({"type": "boards", "boards": [b.to_dict() for b in found]})
        for b in found:
            threading.Thread(target=detect_role_bg, args=(b.port,), daemon=True).start()

    def do_flash(role: str, port: str) -> None:
        def run() -> None:
            ok = False
            with port_lock(port):
                push({"type": "flash_progress", "port": port, "line": f"[flash] role={role} 시작"})
                # 빌드 산출물이 없으면 빌드부터(최초 1회, 수 분).
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
            # flash 성공 시 부팅 후 role 재감지.
            if ok:
                time.sleep(3)
                detect_role_bg(port)
        threading.Thread(target=run, daemon=True).start()

    def do_stream_start(port: str) -> None:
        nonlocal stream_stop
        stream_stop.set()  # 이전 스트림 정지
        stream_stop = threading.Event()
        ev = stream_stop

        def run() -> None:
            with port_lock(port):
                if ev.is_set():
                    push({"type": "stream_stopped", "error": None})
                    return
                push({"type": "stream_status", "msg": f"{port} CSI 수신 시작"})
                err = csi_stream.stream_csi(port, ev, lambda d: push(d))
            push({"type": "stream_stopped", "error": err})

        threading.Thread(target=run, daemon=True).start()

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
            elif action == "stream_start":
                do_stream_start(str(msg.get("port")))
            elif action == "stream_stop":
                stream_stop.set()
    except WebSocketDisconnect:
        pass
    finally:
        stream_stop.set()
        sender_task.cancel()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
