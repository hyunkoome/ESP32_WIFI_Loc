"""
app.py
======
ESP32-S3 보드 진단 "웹 대시보드" 백엔드(FastAPI).

기존 CLI 진단 모듈(usb_detector / diagnostics / firmware)을 그대로 재사용해,
브라우저에서 진단을 돌리고 결과를 녹색/적색 동그라미로 보여준다. WiFi AP 목록·
BLE 기기 목록·온도·GPIO 도 함께 표시하고, RGB LED 순환과 BOOT 버튼은 라이브
모니터(WebSocket)로 갱신한다.

실행: scripts/step03_run_web_based_diagnostics.sh (uvicorn 으로 기동)

WebSocket(/ws) 메시지 규약:
  client -> server:
    {"action":"diagnose","port":"/dev/ttyACM0","sudo":false}
    {"action":"start_live","port":"/dev/ttyACM0"}
    {"action":"stop_live"}
  server -> client:
    {"type":"progress","msg":"..."}            진행 상황
    {"type":"result","data":{...}}              최종 진단 결과(보드 1대)
    {"type":"live","data":{...}}                라이브 사이클(button/temp/led 등)
    {"type":"live_stopped","error":null}        라이브 종료
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# tools/board_check 를 import 경로에 추가(기존 진단 모듈 재사용).
BASE_DIR = Path(__file__).resolve().parent
PKG_DIR = BASE_DIR.parent
sys.path.insert(0, str(PKG_DIR))

import config  # noqa: E402
import diagnostics  # noqa: E402
import firmware as firmware_mod  # noqa: E402
import usb_detector  # noqa: E402

app = FastAPI(title="ESP32-S3 보드 진단 대시보드")
STATIC_DIR = BASE_DIR / "static"


def _json_safe(obj) -> object:
    """진단 결과에 비-직렬화 값이 섞여도 안전하게 JSON 화."""
    return json.loads(json.dumps(obj, default=str))


def _build_board(port: str) -> Dict[str, object]:
    """포트 하나로 diagnose_board 가 받는 보드 정보 딕셔너리를 구성."""
    info = usb_detector.get_usb_info(port)
    info.update(usb_detector.classify(info))
    info["port"] = port
    info["board_index"] = 1
    info["accessible"] = os.access(port, os.R_OK | os.W_OK)
    return info


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/boards")
async def api_boards() -> Dict[str, object]:
    """연결된 보드 자동 탐색."""
    boards = await asyncio.to_thread(usb_detector.discover_boards)
    return {"boards": _json_safe(boards)}


@app.get("/api/status")
async def api_status() -> Dict[str, object]:
    """진단 펌웨어 빌드 여부 등 환경 상태."""
    return {
        "firmware_available": firmware_mod.available(),
        "firmware_path": str(config.FIRMWARE_BIN),
        "check_labels": config.CHECK_LABELS,
    }


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    loop = asyncio.get_running_loop()
    out_q: asyncio.Queue = asyncio.Queue()
    live_stop = threading.Event()

    def push(obj: Dict[str, object]) -> None:
        """스레드에서 안전하게 송신 큐에 적재."""
        loop.call_soon_threadsafe(out_q.put_nowait, obj)

    async def sender() -> None:
        while True:
            item = await out_q.get()
            await websocket.send_text(json.dumps(item, ensure_ascii=False, default=str))

    sender_task = asyncio.create_task(sender())

    def run_diagnose(port: str, use_sudo: bool) -> None:
        try:
            board = _build_board(port)
            res = diagnostics.diagnose_board(
                board,
                use_sudo=use_sudo,
                use_firmware=True,
                progress=lambda m: push({"type": "progress", "msg": m}),
            )
            push({"type": "result", "data": _json_safe(res)})
        except Exception as exc:  # 진단 실패가 서버를 죽이지 않도록.
            push({"type": "error", "msg": f"진단 예외: {exc}"})

    def run_live(port: str) -> None:
        err = firmware_mod.stream_cycles(
            port,
            should_stop=live_stop.is_set,
            on_cycle=lambda cyc: push({"type": "live", "data": _json_safe(cyc)}),
        )
        push({"type": "live_stopped", "error": err})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            action = msg.get("action")
            if action == "diagnose":
                port = str(msg.get("port"))
                use_sudo = bool(msg.get("sudo"))
                threading.Thread(
                    target=run_diagnose, args=(port, use_sudo), daemon=True
                ).start()
            elif action == "start_live":
                live_stop.set()  # 이전 라이브가 있으면 정지
                live_stop = threading.Event()
                port = str(msg.get("port"))
                threading.Thread(target=run_live, args=(port,), daemon=True).start()
            elif action == "stop_live":
                live_stop.set()
    except WebSocketDisconnect:
        pass
    finally:
        live_stop.set()
        sender_task.cancel()


# 정적 파일(css/js) 서빙.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
