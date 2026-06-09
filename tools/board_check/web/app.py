"""
app.py
======
ESP32-S3 보드 진단 "웹 대시보드" 백엔드(FastAPI).

기존 CLI 진단 모듈(usb_detector / diagnostics / firmware)을 그대로 재사용해,
브라우저에서 진단을 돌리고 결과를 녹색/적색 동그라미로 보여준다. WiFi AP 목록·
BLE 기기 목록·온도·GPIO 도 함께 표시하고, RGB LED 순환과 BOOT 버튼은 라이브
모니터(WebSocket)로 갱신한다.

실행: tools/board_check/scripts/step03_run_web_based_diagnostics.sh (uvicorn 으로 기동)

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
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# tools/board_check 를 import 경로에 추가(기존 진단 모듈 재사용).
BASE_DIR = Path(__file__).resolve().parent
PKG_DIR = BASE_DIR.parent
sys.path.insert(0, str(PKG_DIR))

import diagnostics  # noqa: E402
import firmware as firmware_mod  # noqa: E402
import usb_detector  # noqa: E402

import config  # noqa: E402

app = FastAPI(title="ESP32-S3 보드 진단 대시보드")
STATIC_DIR = BASE_DIR / "static"

# 포트별 접근 직렬화 락(프로세스 전역). 같은 시리얼 포트에 진단(esptool flash)과
# 라이브 모니터가 동시에 접근하면 'chip stopped responding' 으로 실패하므로,
# 브라우저 탭/연결이 여러 개여도 포트당 하나의 작업만 돌도록 보장한다.
_PORT_LOCKS: Dict[str, threading.Lock] = {}
_PORT_LOCKS_GUARD = threading.Lock()

# 새로고침/재접속 시 화면 복원용: 마지막 진단 결과 1건을 메모리에 보관한다.
# 브라우저를 새로 열거나 WebSocket 이 끊겼다 다시 붙어도 직전 결과를 그대로
# 다시 그릴 수 있게 한다(서버 재시작 시에는 사라짐 — 영속 저장은 하지 않는다).
# dict 항목만 갱신하므로 global 선언 없이 클로저/엔드포인트에서 공유된다.
_LAST_RESULT: Dict[str, object] = {}


def _port_lock(port: str) -> threading.Lock:
    with _PORT_LOCKS_GUARD:
        lock = _PORT_LOCKS.get(port)
        if lock is None:
            lock = threading.Lock()
            _PORT_LOCKS[port] = lock
        return lock


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
    # 새로고침/재접속 복원: 마지막 진단 결과가 있으면 즉시 전송해 화면을 되살린다.
    snapshot = _LAST_RESULT.get("data")
    if snapshot is not None:
        await websocket.send_text(
            json.dumps({"type": "restore", "data": snapshot}, ensure_ascii=False, default=str)
        )
    loop = asyncio.get_running_loop()
    out_q: asyncio.Queue = asyncio.Queue()
    live_stop = threading.Event()
    live_cmd_q: "queue.Queue" = queue.Queue()  # 라이브 스트림으로 보낼 명령(WiFi 접속 등)
    # WiFi 접속 명령 재전송 상태. 첫 명령이 UART 타이밍으로 유실되면 결과가 안 와서
    # '접속 테스트'를 두 번 눌러야 했다. attempted 응답이 올 때까지 ~2초마다 재전송하고,
    # 응답이 오면 cmd 를 None 으로 비워 재전송을 멈춘다.
    live_wifi: Dict[str, object] = {
        "cmd": None, "ssid": None, "last": 0.0, "tries": 0, "armed": False,
    }

    def push(obj: Dict[str, object]) -> None:
        """스레드에서 안전하게 송신 큐에 적재."""
        loop.call_soon_threadsafe(out_q.put_nowait, obj)

    async def sender() -> None:
        while True:
            item = await out_q.get()
            await websocket.send_text(json.dumps(item, ensure_ascii=False, default=str))

    sender_task = asyncio.create_task(sender())

    def run_diagnose(port: str, use_sudo: bool) -> None:
        live_stop.set()  # 라이브 모니터가 돌고 있으면 먼저 정지시킨다.
        # 라이브가 포트를 완전히 놓을 때까지 락에서 대기한 뒤 flash 진행.
        with _port_lock(port):
            try:
                board = _build_board(port)
                res = diagnostics.diagnose_board(
                    board,
                    use_sudo=use_sudo,
                    use_firmware=True,
                    # 웹은 config/wifi_config.yaml 을 쓰지 않는다. WiFi 접속은 사용자가
                    # WiFi 탭에서 AP 선택 + 비번 입력으로 직접 테스트한다.
                    wifi_from_config=False,
                    progress=lambda m: push({"type": "progress", "msg": m}),
                )
                safe = _json_safe(res)
                _LAST_RESULT["data"] = safe  # 새로고침/재접속 복원용으로 보관
                push({"type": "result", "data": safe})
            except Exception as exc:  # 진단 실패가 서버를 죽이지 않도록.
                push({"type": "error", "msg": f"진단 예외: {exc}"})

    def run_live(port: str, stop_ev: threading.Event, cmd_q: "queue.Queue") -> None:
        def pop_command():
            # 1) 즉시 보낼 명령이 큐에 있으면 우선 전송.
            try:
                return cmd_q.get_nowait()
            except queue.Empty:
                pass
            # 2) 미응답 WiFi 접속 명령은 ~2초마다 재전송(첫 명령 유실 보완).
            cmd = live_wifi.get("cmd")
            if cmd is not None and int(live_wifi.get("tries") or 0) < 6:
                now = time.monotonic()
                if now - float(live_wifi.get("last") or 0.0) >= 2.0:
                    live_wifi["last"] = now
                    live_wifi["tries"] = int(live_wifi.get("tries") or 0) + 1
                    return cmd
            return None

        def on_live_cycle(cyc):
            # 펌웨어는 WIFI_CONNECT 를 받으면 직전 결과를 attempted:false 로 '무효화'하고,
            # 접속이 끝나면 진짜 결과(attempted:true)를 낸다. 그래서 무효화를 한 번 본
            # 뒤의 attempted:true 만 진짜로 인정한다(명령 직후 남아있던 직전 결과 오인 방지).
            wc = cyc.get("wifi_connect")
            if isinstance(wc, dict):
                if not wc.get("attempted"):
                    live_wifi["armed"] = True            # 무효화 확인(처리 시작)
                elif (live_wifi.get("armed") and live_wifi.get("ssid")
                        and wc.get("ssid") == live_wifi.get("ssid")):
                    live_wifi["cmd"] = None               # 무효화 후 진짜 결과 → 재전송 중단
            push({"type": "live", "data": _json_safe(cyc)})

        # 진단이 끝나 포트가 비면 락을 잡고 시리얼을 한 번 열어 사이클을 읽는다.
        with _port_lock(port):
            if stop_ev.is_set():
                push({"type": "live_stopped", "error": None})
                return
            err = firmware_mod.stream_cycles(
                port,
                should_stop=stop_ev.is_set,
                on_cycle=on_live_cycle,
                pop_command=pop_command,
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
                live_stop.set()  # 진행 중 라이브가 있으면 중지 신호
                threading.Thread(
                    target=run_diagnose, args=(port, use_sudo), daemon=True
                ).start()
            elif action == "start_live":
                live_stop.set()  # 이전 라이브 정지
                live_stop = threading.Event()
                live_cmd_q = queue.Queue()
                live_wifi["cmd"] = None   # 새 라이브 세션 — 이전 재전송 상태 제거
                live_wifi["ssid"] = None
                port = str(msg.get("port"))
                threading.Thread(
                    target=run_live, args=(port, live_stop, live_cmd_q), daemon=True
                ).start()
            elif action == "stop_live":
                live_stop.set()
            elif action == "wifi_connect":
                # 웹 WiFi 탭: AP 클릭 → 비번 입력 → 접속. 명령을 1회만 보내면 UART
                # 타이밍으로 첫 전송이 유실돼 '두 번 눌러야' 결과가 나오던 문제가 있어,
                # attempted 응답이 올 때까지 재전송하도록 live_wifi 에 등록한다
                # (pop_command 가 ~2초마다 재전송하고, 응답이 오면 멈춘다).
                ssid = str(msg.get("ssid", ""))
                pw = str(msg.get("password", ""))
                live_wifi["cmd"] = f"WIFI_CONNECT {ssid}\t{pw}\n".encode("utf-8")
                live_wifi["ssid"] = ssid
                live_wifi["last"] = 0.0  # 즉시 첫 전송되도록
                live_wifi["tries"] = 0
                live_wifi["armed"] = False  # 무효화(attempted:false)를 본 뒤의 결과만 인정
                push({"type": "wifi_connecting", "ssid": ssid})
    except WebSocketDisconnect:
        pass
    finally:
        live_stop.set()
        sender_task.cancel()


# 정적 파일(css/js) 서빙.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
