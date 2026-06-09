# csi/web — CSI 웹 모니터

브라우저에서 보드 상태와 CSI 실시간 수신을 확인하는 대시보드(FastAPI).
board_check 웹 대시보드와 같은 스택(FastAPI + uvicorn + WebSocket + 정적 파일)입니다.

## 기능

1. **디바이스 상태판** — `config_devices.yaml` 의 tx/rx 목록과 연결(포트 해석) 여부를
   카드로 표시(3초마다 갱신).
2. **CSI 라이브** — rx 카드의 "모니터 시작" → 해당 보드 시리얼을 열어 CSI 를 파싱하고
   **패킷 rate / RSSI / 서브캐리어 진폭**을 WebSocket 으로 실시간 푸시(진폭은 ~10Hz,
   canvas 막대그래프).

## 실행

```bash
bash scripts/csi_web_monitor.sh                 # http://127.0.0.1:8100
HOST=0.0.0.0 PORT=9100 bash scripts/csi_web_monitor.sh   # 외부 접속 허용
```

스크립트가 venv + 의존성(`requirements-web.txt`: fastapi/uvicorn/pyserial/pyyaml)을
설치한 뒤 `csi/` 에서 `uvicorn web.app:app` 으로 기동합니다.

## 구성

| 파일 | 역할 |
|------|------|
| `app.py` | FastAPI 백엔드. `/api/devices`(상태), `/ws`(CSI 스트림) |
| `static/index.html` · `style.css` · `app.js` | 프론트(외부 차트 라이브러리 없음, 순수 canvas) |
| `requirements-web.txt` | 웹 모니터 의존성 |

> 진폭 계산은 서버에서 numpy 없이(`math.hypot`) 처리해 의존성을 줄였습니다.
> 시리얼은 한 포트당 하나의 수집만 열도록 동작합니다(수집기와 동시 사용 주의).
