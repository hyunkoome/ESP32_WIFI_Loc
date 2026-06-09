# ESP32-S3 보드 자동 진단 도구 (board_check)

여러 대의 YD-ESP32-S3(ESP32-S3N16R8) 보드를 동시에 검사해 하드웨어 이상 여부를
자동으로 판정하고 PASS/FAIL 리포트를 생성하는 진단 도구입니다. WiFi CSI / WiFi
Pose 연구에 들어가기 전, 구매한 보드의 정상 동작을 검증하는 것이 목적입니다.

## 검사 항목

| 항목 | 방식 | 비고 |
|------|------|------|
| USB Detection | `/dev/ttyACM*` 탐색 + VID/PID | Espressif `303a` 식별 |
| UART Connection | pyserial 포트 open | 권한 검사 포함 |
| Bootloader Access | esptool 자동 리셋 연결 | 칩/리비전/크리스털 |
| Flash Access | esptool `flash-id` + 4KB 읽기 | 제조사/디바이스 ID |
| Flash Size | esptool 감지 크기 | 예: 16MB |
| PSRAM | 진단 펌웨어 런타임 | 펌웨어 없으면 SKIP |
| RGB LED | 진단 펌웨어 WS2812 점등 | 펌웨어 없으면 SKIP |
| BOOT Button | 진단 펌웨어 GPIO0 입력 | 대화형(`--no-button-test` 로 끔) |
| WiFi Scan | 진단 펌웨어 AP 스캔 | 펌웨어 없으면 SKIP |
| WiFi Connect | 진단 펌웨어 실제 AP 접속 | `cli_wifi_config.yaml` 자격증명 필요(미설정 SKIP) |
| Bluetooth LE | 진단 펌웨어 BLE 스캔 | 펌웨어 없으면 SKIP |
| Temperature | 진단 펌웨어 내장 온도센서 | 펌웨어 없으면 SKIP |
| GPIO | 진단 펌웨어 자유 GPIO 풀업/풀다운 | 펌웨어 없으면 SKIP |
| Stress Test | esptool 연결 N회 반복(옵션) | `--stress N` |

> **런타임 항목 안내**: PSRAM/RGB LED/BOOT 버튼/WiFi 스캔·접속/Bluetooth LE/온도/
> GPIO 는 esptool만으로는 검사할 수 없어(칩에서 코드 실행 필요) 진단 펌웨어가 있을
> 때만 PASS/FAIL을 판정합니다. 펌웨어가 없으면 `SKIP`으로 표시되며 전체 결과
> (Overall)를 FAIL로 만들지 않습니다. 펌웨어 빌드는
> [`firmware/README.md`](firmware/README.md) 참고.

## 설치

```bash
git clone git@github.com:hyunkoome/ESP32_WIFI_Loc.git
cd ESP32_WIFI_Loc
# 프로젝트 venv 활성화
source venv/bin/activate

# 의존성 설치
cd tools/board_check
pip install -r requirements.txt
```

핵심 의존성은 `esptool`(칩/Flash 조회)과 `pyserial`(UART)입니다.
`colorama`(컬러 출력), `pyudev`(USB 정보), `tqdm`(진행률)는 없으면 자동 폴백합니다.

> 웹 대시보드(아래 [웹 대시보드](#웹-대시보드))를 쓰려면 웹 의존성도 설치합니다:
> `pip install -r requirements-web.txt` (FastAPI/uvicorn).

## 포트 접근 권한

Ubuntu에서 `/dev/ttyACM0`은 보통 `root:dialout` 소유라 일반 사용자는 권한이
없을 수 있습니다. 둘 중 하나로 해결하세요.

```bash
# (권장) 사용자를 dialout 그룹에 추가 — 이후 재로그인 필요
sudo usermod -aG dialout $USER
newgrp dialout      # 또는 로그아웃/로그인

# (대안) 도구를 sudo 권한으로 실행
python main.py --sudo
```

## 사용법

```bash
# 연결된 모든 보드 자동 검사
python main.py

# 특정 포트만
python main.py --port /dev/ttyACM0 --port /dev/ttyACM1

# 권한 없을 때 sudo로
python main.py --sudo

# PSRAM/WiFi(스캔·접속)/BLE/온도/GPIO/LED/버튼 런타임 검사까지(진단 펌웨어 필요)
python main.py --firmware

# 대화형 BOOT 버튼 검사 끄기
python main.py --firmware --no-button-test

# 스트레스 테스트 100회
python main.py --stress 100

# 상세 로그
python main.py -v
```

> 위 단계별 스크립트(`tools/board_check/scripts/step01~03`)로도 동일한 검사를 실행할 수 있습니다 —
> 빌드/실행/환경 준비가 자동화돼 있어 더 편합니다. 자세히는
> [`firmware/README.md`](firmware/README.md) 참고.

### 주요 옵션

| 옵션 | 설명 |
|------|------|
| `--port DEV` | 검사할 포트 지정(여러 번 가능). 미지정 시 자동 탐색 |
| `--sudo` | esptool/펌웨어 명령을 sudo로 실행 |
| `--firmware` | 진단 펌웨어 flash 후 PSRAM/WiFi/BLE/온도/GPIO/LED/버튼 검사 |
| `--no-button-test` | 대화형 BOOT 버튼 검사 생략(기본은 수행, `--firmware` 시) |
| `--stress N` | esptool 연결을 N회 반복하며 오류 집계 |
| `--min-ap N` | WiFi PASS 최소 AP 개수(기본 1) |
| `--jobs N` | 동시 검사 보드 수(기본 자동) |
| `--no-save` | 결과 파일 저장 안 함 |
| `-v` | 상세 로그 |

## 결과

콘솔에 보드별 컬러 리포트를 출력하고 다음 파일로 저장합니다.

```
results/
├── board_test_20260607_142530.json   # 구조화된 전체 결과
└── board_test_20260607_142530.log    # 사람이 읽는 로그
```

종료 코드: 전부 PASS면 `0`, 하나라도 FAIL이면 `1`(CI 연동 가능).

## 구조

```
tools/board_check/
├── main.py            # CLI 진입점, 다중 보드 병렬 검사, 진행률
├── config.py          # 상수(VID/PID, 타임아웃, 경로, 검사 항목)
├── usb_detector.py    # 포트 탐색 + USB VID/PID (pyudev/sysfs)
├── serial_check.py    # UART open + 권한 검사
├── esptool_wrapper.py # esptool 호출/파싱 (칩/Flash/MAC), sudo 지원
├── firmware.py        # 진단 펌웨어 flash + 시리얼 결과 파싱
├── wifi_test.py       # WiFi 스캔/접속 결과 해석
├── psram_test.py      # PSRAM 결과 해석
├── ble_test.py        # Bluetooth LE 스캔 결과 해석
├── peripheral_test.py # RGB LED / BOOT 버튼 / 온도 / GPIO 결과 해석
├── diagnostics.py     # 보드 1대 전체 검사 오케스트레이션 + PASS/FAIL
├── report.py          # 컬러 콘솔 출력 + JSON/로그 저장
├── web/               # 웹 대시보드(FastAPI) — app.py + static(index.html/app.js/style.css)
├── figures/           # 문서용 대시보드 스크린샷
├── requirements.txt       # 진단 도구 의존성(esptool, pyserial)
├── requirements-web.txt   # 웹 대시보드 의존성(FastAPI, uvicorn)
├── firmware/          # ESP-IDF 진단 펌웨어(PSRAM/WiFi/BLE/온도/GPIO/LED/버튼 런타임 검사)
└── results/           # 검사 결과 저장(자동 생성)
```

## 웹 대시보드

CLI 대신 브라우저에서 진단할 수 있는 웹 대시보드(FastAPI)를 제공합니다. 기존 CLI
진단 모듈을 그대로 재사용하며, 결과를 녹색/적색 동그라미로 보여주고 RGB LED 순환·
BOOT 버튼을 라이브로 갱신합니다. WiFi 접속·BLE 스캔도 대화형으로 테스트할 수
있습니다.

```bash
# (펌웨어 빌드는 최초 1회) bash tools/board_check/scripts/step01_build_diag_firmware.sh
bash tools/board_check/scripts/step03_run_web_based_diagnostics.sh
# → 브라우저에서 http://127.0.0.1:8000 열기 (종료: Ctrl+C)
# 다른 PC 에서 접속: HOST=0.0.0.0 PORT=9000 bash tools/board_check/scripts/step03_run_web_based_diagnostics.sh
```

진단/WiFi/BLE 탭 화면 예시는 [`firmware/README.md`](firmware/README.md#진단-결과-화면-웹-대시보드) 참고.

## 개별 모듈 단독 실행

각 모듈은 단독 실행으로 빠르게 점검할 수 있습니다.

```bash
python usb_detector.py            # 탐색된 보드 출력
python serial_check.py /dev/ttyACM0
python esptool_wrapper.py /dev/ttyACM0
```

## 관련 문서

- [진단 펌웨어](firmware/README.md) — PSRAM/WiFi/BLE/온도/GPIO 런타임 검사 펌웨어
- [설치 가이드](../../docs/install.md) — venv/ESP-IDF/esptool 설치
- [Espressif 생태계](../../docs/espressif.md) — ESP-IDF·esptool·esp-csi 등 Espressif GitHub 저장소 정리
