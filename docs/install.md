# 설치 가이드

ESP32_WIFI_Loc 개발 환경을 처음부터 구성하는 순서입니다. Ubuntu Linux 기준.

대략 두 부분으로 나뉩니다.

1. **Python 환경** — 보드 진단 도구(`tools/board_check`)를 돌리는 데 필요. esptool/pyserial.
2. **ESP-IDF (C SDK)** — 진단 펌웨어 / CSI 펌웨어를 **빌드**하는 데 필요. 펌웨어를
   빌드하지 않고 esptool 기반 검사만 할 거라면 건너뛰어도 됩니다.

---

## 0. 시스템 요구사항

- Ubuntu Linux (또는 호환 배포판)
- Python 3.10 이상
- USB-C 케이블(데이터 전송용 — 충전 전용 케이블 ❌)
- 디스크 여유 약 5 GB 이상 (ESP-IDF + toolchain 포함)

```bash
python3 --version          # 3.10+ 확인

# venv 생성 패키지가 없으면:
sudo apt update
sudo apt install -y python3-venv
```

---

## 1. 저장소와 Python 가상환경(venv)

이 프로젝트는 conda 가 아니라 표준 **venv** 를 씁니다(저장소 루트의 `venv/`).

```bash
cd ESP32_WIFI_Loc

python3 -m venv venv
source venv/bin/activate          # 활성화 (프롬프트에 (venv) 표시)

pip install --upgrade pip
pip install -r tools/board_check/requirements.txt   # esptool, pyserial 등
```

> 이후 모든 명령은 `source venv/bin/activate` 로 venv 를 활성화한 상태에서 실행한다고
> 가정합니다.

---

## 2. 시리얼 포트 권한 (dialout)

`/dev/ttyACM*` 는 보통 `root:dialout` 소유라, 일반 사용자는 그대로는 접근하지
못하고 `Permission denied` 가 납니다. 사용자 계정을 **dialout 그룹에 추가**하면
해결됩니다.

```bash
sudo usermod -aG dialout "$USER"

# 변경을 현재 셸에 즉시 반영 (로그아웃 없이):
newgrp dialout

# 확인 (dialout 이 보이면 OK):
groups | tr ' ' '\n' | grep dialout
```

> `newgrp dialout` 은 **그 셸에만** 적용됩니다. VS Code 통합 터미널이나 새 셸 전체에
> 반영하려면 한 번 **로그아웃→로그인**(혹은 재부팅)하는 것이 확실합니다.
>
> 권한 설정이 귀찮거나 일회성이라면, 진단 도구의 `--sudo` 옵션이나
> `sudo venv/bin/python -m esptool ...` 처럼 venv 의 python 을 **절대경로**로 호출하면
> 됩니다. (`sudo python ...` 는 시스템 python 을 쓰게 돼 esptool 을 못 찾으니 주의.)

---

## 3. 보드 진단 도구 실행

여기까지 하면 펌웨어 빌드 없이도 보드 하드웨어를 검사할 수 있습니다.

```bash
source venv/bin/activate
python tools/board_check/main.py            # 연결된 모든 보드 검사
```

- esptool 로 가능한 항목(부트로더/Flash/칩 ID 등)은 검사되고,
- **PSRAM 실동작 / WiFi 스캔·접속 / Bluetooth LE / RGB LED / BOOT 버튼 / 온도센서 /
  GPIO**는 진단 펌웨어가 있어야 하므로(아래 4~5단계) 펌웨어가 없으면 자동으로
  `SKIP` 됩니다.

자세한 사용법: [`tools/board_check/README.md`](../tools/board_check/README.md)

---

## 4. ESP-IDF 설치 (펌웨어 빌드용)

진단 펌웨어 / CSI 펌웨어를 빌드하려면 ESP-IDF 5.x 가 필요합니다. **설치 스크립트**를
제공하므로 한 줄이면 됩니다.

```bash
bash scripts/install_esp_idf.sh
```

스크립트가 하는 일:

1. `~/esp/esp-idf` 에 ESP-IDF `v5.3.1` 을 클론 (얕은 클론으로 용량 절약)
2. `install.sh esp32s3` 로 Xtensa toolchain + ESP-IDF 전용 Python 환경을
   `~/.espressif` 에 설치 (cmake/ninja 도 여기서 받으므로 시스템에 없어도 됨)

환경변수로 버전/경로를 바꿀 수 있습니다:

```bash
IDF_VERSION=v5.4 IDF_DIR=~/esp/esp-idf-5.4 bash scripts/install_esp_idf.sh
```

> 빌드에 필요한 시스템 패키지가 없다는 에러가 나면:
> ```bash
> sudo apt update && sudo apt install -y git wget flex bison gperf \
>   python3 python3-pip python3-venv cmake ninja-build ccache \
>   libffi-dev libssl-dev dfu-util libusb-1.0-0
> ```

### 환경 활성화 (매 터미널)

ESP-IDF 명령(`idf.py`)을 쓰려면 **새 터미널마다** 환경을 활성화해야 합니다:

```bash
source ~/esp/esp-idf/export.sh

idf.py --version          # 설치 확인 (예: ESP-IDF v5.3.1)
```

> 자주 쓴다면 셸 별칭을 등록해두면 편합니다:
> ```bash
> echo "alias get_idf='source ~/esp/esp-idf/export.sh'" >> ~/.bashrc
> ```
> 이후 `get_idf` 만 입력하면 활성화됩니다. (단, ESP-IDF 의 Python 환경과
> 이 프로젝트의 `venv` 는 별개입니다 — 펌웨어 빌드는 ESP-IDF 환경에서,
> 진단 도구 실행은 프로젝트 `venv` 에서 합니다.)

---

## 5. 진단 펌웨어 빌드 & 전체 검사

ESP-IDF 환경을 활성화한 뒤, 진단 펌웨어를 빌드하면 PSRAM/WiFi 까지 검사할 수
있습니다.

```bash
source ~/esp/esp-idf/export.sh      # ESP-IDF 환경
cd tools/board_check/firmware
idf.py set-target esp32s3
idf.py build
cd ../../..

# 빌드된 펌웨어로 PSRAM/WiFi/BLE/온도/GPIO/LED/버튼 포함 전체 검사
source venv/bin/activate
python tools/board_check/main.py --firmware
```

또는 위 [1~5단계]를 자동화한 스크립트로 실행할 수도 있습니다(CLI / 웹 대시보드):

```bash
bash scripts/step01_build_diag_firmware.sh        # 펌웨어 빌드(최초 1회)
bash scripts/step02_run_cli_based_diagnostics.sh  # CLI 진단
bash scripts/step03_run_web_based_diagnostics.sh  # 웹 대시보드(선택) → http://127.0.0.1:8000
```

> 웹 대시보드는 추가 의존성이 필요합니다:
> `pip install -r tools/board_check/requirements-web.txt` (step03 스크립트가 자동 설치).

자세한 펌웨어 빌드/플래시 방법: [`tools/board_check/firmware/README.md`](../tools/board_check/firmware/README.md)

---

## 요약 치트시트

```bash
# (최초 1회)
python3 -m venv venv && source venv/bin/activate
pip install -r tools/board_check/requirements.txt
sudo usermod -aG dialout "$USER" && newgrp dialout
bash scripts/install_esp_idf.sh

# (매 작업 시작 시)
source venv/bin/activate            # 진단 도구용
source ~/esp/esp-idf/export.sh      # 펌웨어 빌드용(필요 시)

# (실행)
python tools/board_check/main.py              # 기본 검사
python tools/board_check/main.py --firmware   # PSRAM/WiFi/BLE/온도/GPIO/LED/버튼 포함 검사
bash scripts/step03_run_web_based_diagnostics.sh   # 웹 대시보드(선택)
```
