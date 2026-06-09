"""CSI 웹 모니터 백엔드(FastAPI).

두 가지를 브라우저로 보여준다:
  1) 디바이스 상태판 — config_devices.yaml 의 tx/rx 목록과 연결(포트 해석) 여부.
  2) CSI 라이브 모니터 — 선택한 rx 보드의 시리얼을 열어 CSI_DATA 라인을 파싱하고
     패킷 rate / RSSI / 서브캐리어 진폭을 WebSocket 으로 실시간 푸시.

실행: scripts/csi_web_monitor.sh (uvicorn 으로 기동)

WebSocket(/ws) 메시지 규약:
  클라 → 서버: {"action": "start", "device": "rx1"}  또는 {"action": "stop"}
  서버 → 클라:
    {"type": "status", "msg": "..."}
    {"type": "csi", "rssi": int, "n_sub": int, "rate": float, "amplitude": [float, ...]}
    {"type": "stopped", "error": str|None}
"""
from __future__ import annotations

import asyncio
import json
import math
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    import serial  # pyserial
except ImportError:  # pragma: no cover
    serial = None  # type: ignore[assignment]

# csi/collect, csi/analysis 를 import 경로에 추가(기존 모듈 재사용).
BASE_DIR = Path(__file__).resolve().parent          # csi/web
CSI_DIR = BASE_DIR.parent                            # csi
sys.path.insert(0, str(CSI_DIR / "collect"))
sys.path.insert(0, str(CSI_DIR / "analysis"))

from csi_parser import parse_line  # noqa: E402
from device_map import load_devices  # noqa: E402

app = FastAPI(title="ESP32 CSI 모니터")
STATIC_DIR = BASE_DIR / "static"

# csi_recv 펌웨어 콘솔 보드레이트(sdkconfig.defaults 와 일치).
CSI_BAUD = 921600


def _device_list() -> list[dict[str, object]]:
    """디바이스 상태판용 직렬화 목록."""
    out: list[dict[str, object]] = []
    for d in load_devices():
        out.append(
            {
                "name": d.name,
                "role": d.role,
                "serial": d.serial,
                "port": d.port,
                "connected": d.port is not None,
                "firmware": d.firmware,
            }
        )
    return out


def _resolve_port(device_name: str) -> str | None:
    for d in load_devices():
        if d.name == device_name and d.port:
            return d.port
    return None


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/devices")
async def api_devices() -> dict[str, object]:
    devices = await asyncio.to_thread(_device_list)
    return {"devices": devices}


def _stream_csi(
    port: str,
    stop_ev: threading.Event,
    push: Callable[[dict[str, object]], None],
) -> str | None:
    """시리얼에서 CSI_DATA 라인을 읽어 집계 후 push. 오류 메시지(또는 None) 반환."""
    if serial is None:
        return "pyserial 미설치"
    try:
        ser = serial.Serial(port, CSI_BAUD, timeout=1)
    except Exception as exc:  # 권한/포트 문제로 서버가 죽지 않게.
        return f"포트 열기 실패: {exc}"

    push({"type": "status", "msg": f"{port} @ {CSI_BAUD}bps 수신 시작"})

    header: list[str] | None = None
    window_start = time.monotonic()
    window_count = 0
    last_emit = 0.0
    rate = 0.0
    try:
        while not stop_ev.is_set():
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue
            if line.startswith("type,"):
                header = line.split(",")
                continue
            pkt = parse_line(line, header)
            if pkt is None:
                continue

            window_count += 1
            now = time.monotonic()
            elapsed = now - window_start
            if elapsed >= 1.0:
                rate = window_count / elapsed
                window_start = now
                window_count = 0

            # 진폭은 매 패킷 보내지 않고 ~10Hz 로만(과부하 방지).
            if now - last_emit >= 0.1:
                last_emit = now
                amp = _amplitudes(pkt.raw_csi)
                push(
                    {
                        "type": "csi",
                        "rssi": pkt.rssi,
                        "n_sub": len(amp),
                        "rate": round(rate, 1),
                        "amplitude": amp,
                    }
                )
    finally:
        ser.close()
    return None


def _amplitudes(raw_csi: list[int]) -> list[float]:
    """(i, q) 쌍 배열 → 서브캐리어별 진폭. numpy 없이 계산(서버 의존 최소화)."""
    amp: list[float] = []
    for k in range(0, len(raw_csi) - 1, 2):
        i = raw_csi[k]
        q = raw_csi[k + 1]
        amp.append(round(math.hypot(i, q), 2))
    return amp


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    loop = asyncio.get_running_loop()
    out_q: asyncio.Queue = asyncio.Queue()
    stop_ev = threading.Event()
    worker: threading.Thread | None = None

    def push(obj: dict[str, object]) -> None:
        loop.call_soon_threadsafe(out_q.put_nowait, obj)

    async def sender() -> None:
        while True:
            item = await out_q.get()
            await websocket.send_text(json.dumps(item, ensure_ascii=False, default=str))

    sender_task = asyncio.create_task(sender())

    def start_stream(device_name: str) -> None:
        port = _resolve_port(device_name)
        if port is None:
            push({"type": "status", "msg": f"'{device_name}' 미연결 — 포트를 찾지 못함"})
            return

        def run() -> None:
            err = _stream_csi(port, stop_ev, push)
            push({"type": "stopped", "error": err})

        nonlocal worker
        worker = threading.Thread(target=run, daemon=True)
        worker.start()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            action = msg.get("action")
            if action == "start":
                if worker and worker.is_alive():
                    stop_ev.set()
                    worker.join(timeout=2)
                stop_ev = threading.Event()
                start_stream(str(msg.get("device")))
            elif action == "stop":
                stop_ev.set()
    except WebSocketDisconnect:
        pass
    finally:
        stop_ev.set()
        sender_task.cancel()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
