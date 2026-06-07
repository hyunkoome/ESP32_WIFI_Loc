# Python 환경 두 개 (프로젝트 venv vs ESP-IDF venv)

이 프로젝트에는 **서로 다른 Python 가상환경이 두 개** 있습니다. 처음 보면 헷갈리기
쉬운데, 역할이 완전히 다릅니다. 이 문서는 "왜 둘인지, 언제 무엇을 쓰는지"를
설명합니다.

---

## 한눈에 보기

| | ① 프로젝트 venv | ② ESP-IDF 전용 venv |
|---|---|---|
| **위치** | `ESP32_WIFI_Loc/venv/` | `~/.espressif/python_env/idf5.4_py3.10_env/` |
| **만든 주체** | 우리 (`python3 -m venv venv`) | ESP-IDF의 `install.sh`가 **자동** 생성 |
| **용도** | 보드 진단 도구 실행 (esptool, pyserial) | 펌웨어 **빌드** (`idf.py`, kconfig, cmake 래퍼 등) |
| **활성화** | `source venv/bin/activate` | `source ~/esp/esp-idf/export.sh` |
| **무엇이 깔려있나** | `tools/board_check/requirements.txt` (esptool, pyserial, colorama) — 웹 대시보드 사용 시 `requirements-web.txt`(FastAPI/uvicorn)도 같은 venv 에 | ESP-IDF 빌드 시스템이 요구하는 고정 버전 패키지들 |

두 환경 모두 **시스템 python3(`/usr/bin/python3`)을 베이스로** 각각 따로 만든 독립
공간입니다. 시스템(루트) python 을 직접 더럽히지 않고, 서로 의존성이 섞이지 않게
격리한 것입니다.

```
/usr/bin/python3  (시스템 — 직접 건드리지 않음)
   ├── ESP32_WIFI_Loc/venv/                         ← ① 진단 도구용 (우리가 만듦)
   └── ~/.espressif/python_env/idf5.4_py3.10_env/   ← ② 펌웨어 빌드용 (ESP-IDF가 만듦)
```

---

## 왜 두 개인가

ESP-IDF 빌드 시스템은 **자기가 요구하는 정확한 Python 패키지 버전들**이 필요합니다
(kconfiglib, cmake 래퍼, esptool 특정 버전 등). 이게 우리 진단 도구가 쓰는 패키지와
충돌할 수 있어서, Espressif 는 아예 **전용 환경을 따로** 만들어 거기에 고정 설치합니다.

그래서 ESP-IDF 의 `install.sh` 는 "내가 venv 를 새로 만들겠다"는 식으로 동작합니다.
문제는, **우리 프로젝트 venv 가 활성화된 채로** `install.sh` 를 실행하면 다음 에러가
납니다:

```
ERROR: This script was called from a virtual environment,
       can not create a virtual environment again
```

venv 안에서 또 venv 를 만들 수 없기 때문입니다(중첩 불가). 그래서 설치
스크립트([`scripts/install_esp_idf.sh`](../scripts/install_esp_idf.sh))는 ESP-IDF 환경을
만들기 전에 **활성 venv 의 흔적(`VIRTUAL_ENV` 변수와 `PATH` 의 `venv/bin`)을 잠깐
제거**하도록 되어 있습니다.

---

## 실제 사용법 (섞지 않는다)

두 환경을 **동시에 활성화하지 않습니다.** 그때그때 목적에 맞는 것만 켭니다.

### 펌웨어를 빌드/플래시할 때 → ESP-IDF 환경

```bash
source ~/esp/esp-idf/export.sh     # → ESP-IDF 환경 (idf.py 사용 가능)
idf.py build
```

### 보드 진단 도구를 돌릴 때 → 프로젝트 환경

```bash
source venv/bin/activate           # → 프로젝트 환경
python tools/board_check/main.py
```

> 비유하면 **작업실이 둘**입니다 — 하나는 "펌웨어 컴파일 전용 작업실"(ESP-IDF가
> 차려줌), 하나는 "보드 점검 스크립트 작업실"(우리가 차림). 연장이 안 섞이게 분리해
> 두고, 그때그때 맞는 작업실에 들어가는 것입니다.

### 한 셸에서 둘 다 필요하면?

진단 도구가 펌웨어를 빌드까지 하는 경우(파이프라인)에는, **두 환경을 한 셸에서 번갈아**
쓰기보다 다음처럼 분리하는 것이 깔끔합니다.

- 펌웨어 빌드는 ESP-IDF 환경에서 별도로 수행하거나,
- 빌드 파이프라인 스크립트가 내부에서 `export.sh` 를 격리해 호출하도록 합니다.

(이미 활성화한 프로젝트 venv 위에 `export.sh` 를 덮어써도 대체로 동작하지만, 충돌을
피하려면 가급적 새 셸/서브셸에서 ESP-IDF 환경을 켜세요.)

---

## 자주 겪는 문제

### 1. `install.sh` 에서 "can not create a virtual environment again"

프로젝트 venv 가 활성화된 채 ESP-IDF 를 설치하려 해서입니다. 위 "왜 두 개인가" 참고.
→ [`scripts/install_esp_idf.sh`](../scripts/install_esp_idf.sh) 를 쓰면 자동으로
처리됩니다. 수동이라면 먼저 `deactivate` 후 설치하세요.

### 2. `sudo python ...` 했더니 `No module named esptool`

`sudo` 는 `PATH` 를 시스템 기본값(secure_path)으로 덮어써서, venv 의 python 이 아니라
**시스템 python**(`/usr/bin/python`)을 쓰게 됩니다. 거기엔 esptool 이 없으니 모듈을
못 찾습니다.

→ venv 의 python 을 **절대경로**로 호출하세요:
```bash
sudo venv/bin/python -m esptool --port /dev/ttyACM0 chip-id
```
(애초에 [dialout 그룹 설정](install.md#2-시리얼-포트-권한-dialout)을 해두면 `sudo`
자체가 필요 없습니다.)

### 3. `idf.py: command not found`

ESP-IDF 환경을 활성화하지 않은 것입니다. 새 터미널마다 한 번:
```bash
source ~/esp/esp-idf/export.sh
```
자주 쓴다면 별칭 등록:
```bash
echo "alias get_idf='source ~/esp/esp-idf/export.sh'" >> ~/.bashrc
```

---

## 관련 문서

- [설치 가이드](install.md) — 전체 설치 순서
- [보드 진단 도구](../tools/board_check/README.md) — 진단 도구 사용법
- [진단 펌웨어](../tools/board_check/firmware/README.md) — 펌웨어 빌드/플래시
