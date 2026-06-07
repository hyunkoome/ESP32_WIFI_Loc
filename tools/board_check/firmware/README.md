# ESP32-S3 진단 펌웨어

PSRAM, RGB LED, BOOT 버튼, WiFi 스캔/접속, **Bluetooth LE 스캔**, 내장 온도센서,
GPIO 점검 같은 검사는 칩에서 코드가 실제로 실행돼야 하므로(esptool 만으로는 불가),
이 작은 ESP-IDF 펌웨어를 보드에 올린 뒤 시리얼 출력을 호스트(`firmware.py`)가
파싱합니다.

---

## 가장 쉬운 방법: 2단계 스크립트 (권장)

보드의 **오른쪽 USB-C 포트(`COM`/CH343, `1A86:55D3`)** 에 케이블을 연결한 뒤,
저장소 루트에서 두 단계를 실행합니다.

```bash
# [1단계] 펌웨어 빌드 (최초 1회 — ESP-IDF 없으면 자동 설치)
bash scripts/step01_build_diag_firmware.sh

# [2단계] 보드 진단 실행 (반복 실행 가능)
bash scripts/step02_run_cli_based_diagnostics.sh
```

> 오른쪽 COM 포트가 플래시·로그에 가장 안정적입니다. 좌/우 구분은
> [docs/usb-ports.md](../../../docs/usb-ports.md) 참고.

**왜 둘로 나누나:** 빌드(느림, ESP-IDF 환경, 보통 1회)와 진단 실행(빠름, venv
환경, 반복)은 성격과 Python 환경이 달라서 분리했습니다. 펌웨어 소스를 고쳤을
때만 [1단계]를 다시 실행하면 됩니다.

### [1단계] `step01_build_diag_firmware.sh`

| 동작 | 내용 |
|------|------|
| 0 | ESP-IDF 설치 확인(없으면 `scripts/install_esp_idf.sh` 로 자동 설치) |
| 1 | `idf.py build` 로 펌웨어 빌드 |
| 2 | `idf.py merge-bin` 으로 병합 → `firmware/build/diag_merged.bin` 생성 |

### [2단계] `step02_run_cli_based_diagnostics.sh`

| 동작 | 내용 |
|------|------|
| 1 | 진단용 Python venv 준비(없으면 생성 + `requirements.txt` 설치) |
| 2 | `main.py --firmware` 실행 — flash 전체 erase → 펌웨어 다운로드 → **PSRAM / WiFi 스캔·접속 / Bluetooth LE / RGB LED / BOOT 버튼 / 온도센서 / GPIO 검사** |
| 3 | (기본 ON) **대화형 BOOT 버튼 검사** — 보드별로 "버튼 누르세요" 안내 후 실제 눌림 감지 |

자주 쓰는 옵션(모두 `main.py` 로 전달됨):

```bash
bash scripts/step02_run_cli_based_diagnostics.sh --sudo            # 포트 권한 부족 시
bash scripts/step02_run_cli_based_diagnostics.sh --port /dev/ttyACM0
bash scripts/step02_run_cli_based_diagnostics.sh --no-button-test  # 대화형 버튼 검사 끄기
bash scripts/step02_run_cli_based_diagnostics.sh --stress 100      # 스트레스 테스트
```

> ⚠️ [2단계]는 보드의 flash 를 **전체 erase** 한 뒤 진단 펌웨어로 덮어씁니다.
> 보드에 보존할 펌웨어/데이터가 있으면 먼저 백업하세요.

---

## 수동으로 단계별 실행하기

스크립트 대신 직접 단계를 밟고 싶을 때.

### 1) ESP-IDF 5.x 설치

```bash
bash scripts/install_esp_idf.sh          # ~/esp/esp-idf 에 설치(toolchain 포함)
# 수동 설치 시:
#   git clone -b v5.4 --recursive https://github.com/espressif/esp-idf.git ~/esp/esp-idf
#   ~/esp/esp-idf/install.sh esp32s3
source ~/esp/esp-idf/export.sh           # 새 터미널마다 실행 (IDF_PATH 설정)
```

### 2) 빌드 + 병합 바이너리 생성

진단 도구는 `firmware/build/diag_merged.bin` 하나(부트로더+파티션+앱 병합)를
`0x0` 에 flash 합니다. `step01_build_diag_firmware.sh` 가 빌드와
병합(`idf.py merge-bin`)을 함께 처리합니다.

직접 `idf.py` 로 하려면:

```bash
cd tools/board_check/firmware
idf.py set-target esp32s3
idf.py build
idf.py merge-bin -o build/diag_merged.bin
```

### 3) 진단 실행

```bash
source venv/bin/activate
python tools/board_check/main.py --firmware
```

### (선택) 도구 없이 직접 확인

ESP-IDF 환경에서 flash + 모니터를 직접 띄워 `DIAG_*` 라인을 눈으로 볼 수도
있습니다:

```bash
cd tools/board_check/firmware
idf.py -p /dev/ttyACM0 flash monitor
```

---

## 출력 규약

펌웨어는 부팅 후 아래 라인을 출력합니다(`firmware.py` 가 파싱):

검사는 부팅 시 1회만 수행해 결과를 보관하고, 아래 한 사이클(`DIAG_START` ~
`DIAG_DONE`)을 약 2초마다 반복 출력합니다(호스트가 늦게 연결해도 완전한 사이클을
받도록). RGB LED 는 매 사이클 R→G→B 로 순환 점등합니다.

```
DIAG_START
DIAG_CHIP         {"cores":2,"model":"ESP32-S3","revision":2}
DIAG_PSRAM        {"present":true,"size":8388608}
DIAG_LED          {"ok":true,"gpio":48}
DIAG_BUTTON       {"idle_level":1,"pressed_now":false,"gpio":0}
DIAG_WIFI         {"ap_count":15,"strongest_rssi":-42,"aps":[{"ssid":"AP","rssi":-42,"ch":6}]}
DIAG_WIFI_CONNECT {"attempted":true,"connected":true,"ssid":"AP","ip":"192.168.0.10"}
DIAG_BLE          {"ok":true,"devices":3,"list":[{"addr":"..","rssi":-77,"name":"JBL"}]}
DIAG_TEMP         {"ok":true,"celsius":34.0}
DIAG_GPIO         {"ok":true,"tested":20,"passed":20,"failed":[]}
DIAG_DONE
```

> WiFi 접속(`DIAG_WIFI_CONNECT`)은 `config.yaml` 의 wifi.ssid/password 를 빌드 시
> 주입해 실제 AP 에 붙어 본다(미설정 시 `attempted:false` → 호스트가 SKIP).

---

## 펌웨어 빌드 없이 사용하려면

ESP-IDF 설치가 부담되면 `--firmware` 옵션을 빼고 실행하세요:

```bash
python tools/board_check/main.py
```

이 경우 PSRAM/WiFi/LED/버튼 항목은 `SKIP` 으로 표시되고, esptool 기반 하드웨어
검사(USB/UART/부트로더/Flash)는 모두 정상 수행됩니다.
