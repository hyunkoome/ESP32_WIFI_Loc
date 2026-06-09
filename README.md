# ESP32_WIFI_Loc

여러 대의 ESP32-S3 보드를 활용해 WiFi **CSI**(Channel State Information)를
수집하고, 이를 기반으로 다양한 **WiFi Sensing** 기술을 연구·개발하기 위한
플랫폼입니다.

## 목표

- WiFi CSI 수집
- 사람 존재 감지(Presence Detection)
- 움직임 감지(Motion Detection)
- 호흡 감지(Breathing Detection)
- 제스처 인식(Gesture Recognition)
- 실내 위치 추정(Localization)
- WiFi 기반 포즈 인식(Pose Estimation)

## 📚 문서

세부 내용은 [`docs/`](docs/) 에 항목별로 정리돼 있습니다.

| 문서 | 내용 |
|------|------|
| [설치 가이드](docs/install.md) | venv, 포트 권한, ESP-IDF 설치까지 처음부터 |
| [Python 환경 두 개](docs/python-environments.md) | 프로젝트 venv vs ESP-IDF venv — 왜 둘이고 언제 뭘 쓰나 |
| [USB-C 포트 가이드](docs/usb-ports.md) | 왼쪽(USB)/오른쪽(COM) 포트 차이와 사용법 |
| [펌웨어 가이드](docs/firmware-guide.md) | MicroPython bin 선택·플래시, 진단 펌웨어 |
| [Espressif 생태계](docs/espressif.md) | Espressif GitHub 저장소 317개 전체를 프로젝트 관련도(★5~★1)로 정리 |
| [보드 진단 도구](tools/board_check/README.md) | 보드 자동 진단 도구 사용법 (CLI + 웹) |
| [진단 펌웨어](tools/board_check/firmware/README.md) | PSRAM/WiFi/LED/버튼 검사 펌웨어 빌드 |
| [CSI 데이터 획득](csi/README.md) | CSI 송수신 펌웨어·수집·파싱·웹 모니터(tx/rx) |
| [보드 하드웨어](hw/YD-ESP32-S3/README.KR.md) | YD-ESP32-S3 데이터시트/핀맵/스펙 |

## 하드웨어

| 항목 | 사양 |
|------|------|
| 개발보드 | YD-ESP32-S3 Development Board |
| 칩 | ESP32-S3N16R8 (Xtensa LX7 듀얼코어, 최대 240MHz) |
| Flash | 16MB |
| PSRAM | 8MB (Octal) |
| 무선 | WiFi 802.11 b/g/n (2.4GHz), BLE 5 |
| 인터페이스 | USB-C UART(CH343) / USB-C 네이티브(USB-Serial-JTAG) |
| 보유 수량 | 3대 (동시 연결 예정) |

- **USB-C 포트가 2개**입니다 — 평소엔 오른쪽(`COM`) 하나만 쓰면 됩니다. 자세히:
  [USB-C 포트 가이드](docs/usb-ports.md)
- **펌웨어**: 이 보드는 N16R8 이므로 `...-N16R8-...` 펌웨어를 씁니다. 자세히:
  [펌웨어 가이드](docs/firmware-guide.md)

## 빠른 시작

```bash
# 1) 진단 도구 환경
python3 -m venv venv && source venv/bin/activate
pip install -r tools/board_check/requirements.txt

# 2) 시리얼 포트 권한 (최초 1회)
sudo usermod -aG dialout "$USER" && newgrp dialout

# 3) 보드 진단 (연결된 모든 보드)
python tools/board_check/main.py
```

PSRAM / WiFi 스캔·접속 / Bluetooth LE / RGB LED / BOOT 버튼 / 온도센서 / GPIO 까지
**런타임 검사**를 하려면 진단 펌웨어가 필요합니다. 아래 단계로 실행합니다 —
[설치 가이드](docs/install.md) 참고.

```bash
# [1단계] 펌웨어 빌드 (최초 1회 — ESP-IDF 없으면 자동 설치)
bash tools/board_check/scripts/step01_build_diag_firmware.sh

# [2단계] 보드 진단 (CLI) — 반복 실행 가능
bash tools/board_check/scripts/step02_run_cli_based_diagnostics.sh

# [3단계] (선택) 웹 대시보드로 진단 — 브라우저에서 http://127.0.0.1:8000
bash tools/board_check/scripts/step03_run_web_based_diagnostics.sh
```

> WiFi **접속** 테스트는 `config/wifi_config.yaml` 의 `wifi.ssid`/`wifi.password` 로
> 실제 AP 에 붙어 봅니다(실행 시 런타임에 읽어 시리얼로 주입 — 펌웨어 재빌드 불필요).
> 미설정/빈 값이면 해당 항목만 SKIP.

> [2단계]는 기본으로 **대화형 BOOT 버튼 검사**를 포함합니다 — 검사 끝에 보드별로
> "BOOT 버튼을 누르세요" 안내가 나오면 누르면 됩니다. 끄려면 `--no-button-test`:
> `bash tools/board_check/scripts/step02_run_cli_based_diagnostics.sh --no-button-test`

> [3단계] 웹 대시보드는 진단/WiFi/BLE 탭에서 결과를 보여주고 WiFi 접속·BLE 스캔을
> 대화형으로 테스트합니다. 화면 예시는
> [진단 펌웨어 README](tools/board_check/firmware/README.md#진단-결과-화면-웹-대시보드) 참고.

## CSI 수집 (송수신 tx/rx)

보드 진단이 끝났다면, ESP32-S3 들을 tx(송신)/rx(수신)로 나눠 CSI 를 수집합니다.
rx 의 `csi_recv` 는 **통합 수신 펌웨어**로, tx 의 ESP-NOW broadcast CSI 와 라우터(AP)
CSI 를 **둘 다** 수집합니다. 호스트(GUI/web)가 신호원(tx / wifi router / all)을 골라
분석하므로 신호원을 바꿔도 **재flash 가 필요 없습니다**. 자세히: [`csi/README.md`](csi/README.md).

보드는 부팅 시 `DEVICE_ROLE` 을 출력해 **tx/rx 가 자동 표시**됩니다(매핑 파일 불필요).
**연결만 하면** 대시보드가 감지하고, 보드별로 tx/rx 펌웨어를 골라 다운로드합니다.

라우터 CSI 를 쓸 때 라우터 자격증명은 **펌웨어에 박지 않고 런타임 시리얼 주입**합니다 —
호스트가 `config/wifi_config.yaml`(없으면 사용자 입력)을 읽어 `WIFI_CONNECT <ssid>\t<pw>`
명령을 보내면 rx 가 라우터에 STA 접속 + 게이트웨이 ping 으로 라우터 CSI 를 수집하고,
`WIFI_DISCONNECT` 로 tx(ESP-NOW 채널)로 복귀합니다.

```bash
# 웹 대시보드 — 보드 실시간 감지 + tx/rx 펌웨어 다운로드 + CSI 진폭/위상 라이브
bash scripts/csi_app.sh                        # http://127.0.0.1:8200
#   또는 데스크톱 GUI(동일 기능): bash scripts/csi_gui.sh

# (CLI) CSI 수집 → CSV : --role 은 연결 보드를 실시간 감지해 선택
python csi/collect/serial_collector.py --role rx --out results/csi_run01.csv
```

> CSI 센싱은 **tx–rx 를 2~5m 띄워** 그 사이로 사람이 지나가게 배치합니다(붙여 두면
> 감지 영역이 없음). 위치/다중 인원 정확도를 높이려면 **rx(앵커)를 여러 곳에 분산**하세요.

## 개발 환경

- Ubuntu Linux / Python 3.10+ (**venv**) / ESP-IDF 5.x
- Python 환경이 **두 개**(진단 도구용 / 펌웨어 빌드용)입니다 — 헷갈리면
  [Python 환경 두 개](docs/python-environments.md) 참고.

### 버전 이야기: ESP-IDF 5.4 와 esptool 5.3.0 은 서로 다른 것 (초보자용)

진단을 돌리면 `✓ esptool 5.3.0 감지` 가 뜨는데, ESP-IDF 는 5.4 인데 왜 5.3 이냐고
헷갈릴 수 있습니다. **둘은 완전히 다른 도구라 버전이 달라도 정상입니다.**

| 이름 | 무엇 | 어디에 설치되나 | 누가 쓰나 |
|------|------|----------------|-----------|
| **ESP-IDF** (예: 5.4) | C 언어 SDK + 컴파일러 툴체인. 펌웨어를 **빌드**하는 데 쓰는 `idf.py` 가 들어 있음 | `~/esp/esp-idf` (스크립트가 설치) | **[1단계]** `step01_build_diag_firmware.sh` |
| **esptool** (예: 5.3.0) | 보드에 펌웨어를 **굽고(flash)** 칩 정보를 읽는 작은 Python 프로그램 | 프로젝트 `venv/` (pip 로 설치) | **[2단계]** `step02_run_cli_based_diagnostics.sh` |

- 두 버전 번호(5.4 vs 5.3.0)는 **서로 다른 버전 체계**라, 숫자가 비슷해도 아무 관계가
  없습니다. 충돌이나 오류가 아닙니다.
- ESP-IDF 안에도 자체 esptool 이 들어 있지만, 진단 도구([2단계])는 ESP-IDF 가 아니라
  `venv` 에서 돌기 때문에 **`venv` 에 pip 로 깔린 esptool**(`requirements.txt` 의
  `esptool>=4.7,<6` → 현재 5.3.0)을 사용합니다.
- 비유하면 — ESP-IDF 는 "공장(프로그램을 만드는 곳)", esptool 은 "USB 라이터(만든 걸
  보드에 굽는 도구)" 입니다. 둘은 따로 업데이트됩니다.

## 개발 진행 상황

CSI 연구에 들어가기 전, 먼저 구매한 ESP32-S3 보드들의 하드웨어 이상 여부를 자동
검사하는 진단 도구를 만들었습니다. 자세한 사용법은
[`tools/board_check/README.md`](tools/board_check/README.md) 참고.

### ✅ 완료 (보드 자동 진단)

- **CLI 진단 도구** — 다중 보드 병렬 검사, PASS/FAIL 리포트(JSON/로그) 저장
- **검사 항목** — USB·UART·부트로더·Flash·Flash 크기(esptool) + PSRAM·RGB LED·
  BOOT 버튼·WiFi 스캔/접속·Bluetooth LE·내장 온도센서·GPIO(진단 펌웨어)
- **진단 펌웨어** — ESP-IDF(C) 펌웨어로 런타임 항목 검사([`firmware/`](tools/board_check/firmware/README.md))
- **웹 대시보드** — 브라우저 진단(진단/WiFi/BLE 탭, 라이브 LED 색, WiFi 접속·BLE 대화형 테스트)
- **2/3단계 스크립트** — 빌드(step01)·CLI 진단(step02)·웹 대시보드(step03) 자동화
- **문서** — 설치/펌웨어/Python 환경/USB 포트/Espressif 생태계 가이드

### ✅ 완료 (CSI 데이터 획득)

- **CSI 통합 수신 펌웨어** — [esp-csi](docs/espressif.md) 기반 `csi_recv` 가 tx 의
  ESP-NOW broadcast CSI 와 라우터(AP) CSI 를 **둘 다** 수집(호스트가 신호원 선택,
  재flash 불필요) + 송신 `csi_send`. 부팅 시 `DEVICE_ROLE` 출력으로 **tx/rx 자동 감지** ([`csi/firmware/`](csi/firmware/README.md))
- **라우터 자격증명 런타임 시리얼 주입** — 펌웨어에 박지 않고 호스트가
  `config/wifi_config.yaml`(없으면 입력)을 읽어 `WIFI_CONNECT` 으로 rx 에 주입 → STA
  접속 + 게이트웨이 ping 으로 라우터 CSI 수집, `WIFI_DISCONNECT` 로 tx 복귀
- **보드 실시간 감지 + role 자동표시** — `config_devices.yaml` 없이 연결만 하면 by-id
  로 감지하고 펌웨어 `DEVICE_ROLE` 로 tx/rx 를 자동 판별 ([`csi/common`](csi/README.md))
- **멀티보드 펌웨어 다운로드** — web/GUI 대시보드에서 보드별 tx/rx 펌웨어 선택 flash
  (`scripts/csi_flash.sh` role+port 인자, merge-bin)
- **CSI 실시간 시각화** — **web**(`scripts/csi_app.sh`) 과 **데스크톱 GUI**
  (PyQt5+pyqtgraph, `scripts/csi_gui.sh`) 둘 다 진폭/위상/워터폴/도플러 스펙트럼을
  실시간 표시 + 신호원 콤보(tx / wifi router / all), 공용 백엔드(`csi/common`) 공유
- **CSI 수집·파싱** — 시리얼 → CSV 수집기(`--role` 실시간 감지) + 진폭/위상 파서 ([`csi/collect`](csi/collect/README.md) · [`csi/analysis`](csi/analysis/README.md))
- **GitHub CI** — 펌웨어 빌드(esp32s3) + Python lint 워크플로 ([`.github/workflows`](.github/workflows/))

### ⬜ 추가 예정 (To do · 다중 수집·센싱)

- **다중 보드 동시 CSI 수집** — 여러 ESP32-S3 동기 수집(다중 링크)
- **데이터셋 구축** — 수집 CSI 라벨링·윈도우 분할
- **학습/추론 코드** ([`sensing/`](sensing/README.md)) — 카메라 없이 CSI 만으로 실내
  **다중 인원 감지 + 각 사람 pose 추정**(+ presence / motion / breathing / localization)

## 저장소 구조

```
ESP32_WIFI_Loc/
├── csi/                  # CSI 데이터 획득 계층
│   ├── firmware/         #   csi_recv / csi_send 펌웨어(부팅 시 DEVICE_ROLE 출력)
│   ├── common/           #   web/GUI 공용 백엔드(보드 감지·role·flash·CSI 스트림)
│   ├── collect/          #   시리얼 수집(--role 실시간 감지)
│   ├── analysis/         #   CSI 파싱·전처리
│   ├── web/              #   웹 대시보드(FastAPI): 감지·flash·진폭/위상 라이브
│   └── gui/              #   데스크톱 GUI(PyQt5+pyqtgraph): web 과 동일 백엔드
├── sensing/              # 응용 계층(예정): 다중 인원 감지 + pose/위치 추정
├── hw/
│   └── YD-ESP32-S3/      # 보드 하드웨어 자료(데이터시트/핀맵/벤더 펌웨어)
├── tools/
│   └── board_check/      # 보드 자동 진단 도구 (+ firmware/)
├── config/               # 프로젝트 공통 설정 (wifi_config.yaml: 진단+CSI 라우터 공유)
├── docs/                 # 설치/환경/하드웨어 세부 문서
├── scripts/              # 보조 스크립트 (csi_flash, csi_app, csi_gui, install_esp_idf 등)
├── .github/workflows/    # CI (펌웨어 빌드 + Python lint)
├── CLAUDE.md             # Claude Code 작업 가이드라인
├── LICENSE               # AGPL v3
└── README.md
```

## 라이선스

이 프로젝트는 [GNU Affero General Public License v3.0](LICENSE) 하에 공개됩니다.
