# csi/web — CSI 웹 대시보드

브라우저에서 **보드 감지 → tx/rx 펌웨어 다운로드 → CSI 실시간 시각화 → 3상태
인지(로깅·학습·방 상태 voting)** 까지 하는 대시보드(FastAPI + WebSocket + 순수
canvas). 데스크톱 GUI([`../gui/`](../gui/))와 **동일한 공용 백엔드**
([`../common/`](../common/), 특히 `classifier.py`)를 공유해 **두 프런트의 숫자가
100% 일치**합니다 — 같은 CSI 패킷이면 web 과 GUI 가 똑같은 std/doppler/상태를 냅니다.

> 휴대폰 브라우저로 열어도 동일하게 동작합니다(아래 화면 예시는 모바일).

## 화면 예시

| 보드·WiFi·분류기 | 공간 모니터링(방 상태) | rx 라이브 차트 |
|---|---|---|
| ![web 보드/분류기](../../docs/figures/app01.jpg) | ![web 방 상태](../../docs/figures/app02.jpg) | ![web rx 차트](../../docs/figures/app03.jpg) |

## 기능

1. **보드 실시간 감지** — USB 연결만 하면 by-id 로 감지하고 펌웨어 `DEVICE_ROLE` 로
   **tx/rx 를 자동 표시**(`config_devices.yaml` 불필요). 보드 카드에서 **tx/rx 펌웨어를
   골라 다운로드**(flash).
2. **Wi-Fi 라우터 자동 접속** — `config/wifi_config.yaml` 의 SSID 를 자동 로드.
   rx 신호원을 `wifi router` 로 두면 **router CSI 가 실제로 들어올 때까지 `WIFI_CONNECT`
   를 주기 재전송**(부팅 직후 1회 전송이 씹히는 문제 해결).
3. **신호원 선택(rx 별)** — `tx`(ESP-NOW) / `wifi router`(AP) / `all`. 학습된 신호원이
   있으면 그 값으로 기본 선택(예: 8007=tx, 2284=router).
4. **CSI 라이브 차트** — rx 별 **진폭 / 위상 / 워터폴 / 도플러 스펙트럼**(canvas, ~5Hz
   throttle).
5. **3상태 인지** — `empty` / `presence` / `motion`. 두 메트릭으로 판정 —
   **presence = 진폭 std**, **motion = 도플러 피크**. 히스테리시스 + outlier 필터로
   경계 진동/순간 노이즈를 억제.
6. **로깅 → 학습** — `Log Empty/Presence/Motion` 으로 상태별 raw CSI 를 CSV 저장
   (`dataset/csi_logs/`), `Train Classifier` 로 std_th/doppler_th 임계를 계산해
   `config/motion_detection.yaml` 에 저장(모든 rx 동시).
7. **공간 모니터링** — rx 별 상태 + **다중 링크 voting** 으로 최종 방 상태 결정
   (활성 링크 ≥2 면 2표, 1개면 1표) + 움직임 이벤트 로그.

## 실행

```bash
bash scripts/csi_app.sh                              # 기본 0.0.0.0:8200 (LAN/휴대폰 접속 가능)
HOST=127.0.0.1 PORT=9200 bash scripts/csi_app.sh     # 로컬 전용/다른 포트
```

기본이 `0.0.0.0` 이라 **같은 LAN 의 휴대폰**에서도 열립니다 — 스크립트가 기동 시
`http://localhost:8200` 과 `http://<LAN_IP>:8200` 을 함께 출력합니다.

스크립트가 venv + 의존성(`requirements-web.txt`: fastapi/uvicorn/pyserial/pyyaml/numpy)
을 설치한 뒤 `csi/` 에서 `uvicorn web.app:app` 으로 기동합니다.

## 로깅·학습 흐름

1. tx/rx 펌웨어를 다운로드하고, rx 신호원을 고른다(router 면 자동 접속).
2. 빈 방에서 `Log Empty` → 잠시 후 다시 눌러 종료. 사람이 가만히 있을 때
   `Log Presence`, 움직일 때 `Log Motion` 도 같은 식으로.
3. `Train Classifier` — 상태별 **가장 최근** CSV 로 임계를 계산해 yaml 에 저장하고
   바로 실시간 인지로 전환된다.
   - GUI 없이 일괄 재학습하려면: `python csi/train_from_dataset.py`

## 구성

| 파일 | 역할 |
|------|------|
| `app.py` | FastAPI 백엔드. 보드 감지/flash, `/ws`(CSI·상태 스트림), 라우터 자동 접속 |
| `static/index.html` · `style.css` · `app.js` | 프론트(외부 차트 라이브러리 없음, 순수 canvas) |
| `requirements-web.txt` | 웹 대시보드 의존성 |
| [`../common/classifier.py`](../common/classifier.py) | **web/GUI 공용** 메트릭·3상태·로깅·학습·voting |

> 메트릭/3상태/로깅/학습/voting 로직은 전부 공용 `classifier.py` 에 있고 web/GUI 가
> 함께 씁니다. 시리얼은 한 포트당 하나의 수집만 열도록 동작합니다(수집기와 동시 사용 주의).
