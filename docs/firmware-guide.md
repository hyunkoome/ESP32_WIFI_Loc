# 펌웨어 가이드

이 보드에서 쓰는 펌웨어는 크게 두 종류입니다.

1. **MicroPython 펌웨어** (벤더 제공 bin) — Python 인터프리터를 칩에 올려 REPL/스크립트
   실행. 빠른 테스트·학습용.
2. **ESP-IDF(C) 펌웨어** — 직접 빌드하는 C 펌웨어. 보드 진단 펌웨어와, 이후 단계의 CSI
   수집 펌웨어가 여기에 해당.

> 펌웨어(인터프리터/실행파일)와, 그 위에서 도는 사용자 스크립트(`.py`)는 다른
> 개념입니다. MicroPython bin 은 "Python을 실행할 수 있게 하는 런타임"이고,
> `*.py` 는 "그 위에서 무엇을 할지" 정의하는 앱입니다.

---

## 1. MicroPython 펌웨어 선택 (벤더 제공 bin)

[`hw/YD-ESP32-S3/1-MPY-firmware/`](../hw/YD-ESP32-S3/1-MPY-firmware/) 에 벤더가 제공한
**MicroPython v1.19.1** 펌웨어 bin 이 3개 있습니다. 파일명 규칙은 **N = Flash 크기(MB),
R = PSRAM 크기(MB)** 입니다. **메모리 구성이 맞는 것 하나만** 써야 합니다.

| 파일 | Flash | PSRAM | 이 보드(N16R8)에? |
|------|-------|-------|--------------------|
| `YD-ESP32-S3-N16R8-MPY-V1.1.bin` | 16MB | 8MB | ✅ **이것** |
| `YD-ESP32-S3-N8R2-MPY-V1.1.bin` | 8MB | 2MB | ❌ 다른 구성 |
| `YD-ESP32-S3-N8R8-MPY-V1.1.bin` | 8MB | 8MB | ❌ 다른 구성 |

본 프로젝트 보드는 **Flash 16MB + PSRAM 8MB(N16R8)** 이므로
**`YD-ESP32-S3-N16R8-MPY-V1.1.bin`** 를 사용합니다. 다른 bin 을 올리면 Flash 를 8MB 로만
인식하거나 PSRAM 설정이 맞지 않아(특히 N8R2 는 2MB) 오동작할 수 있습니다.

### MicroPython flash 방법

이 벤더 bin 은 `0x0` 에 굽는 **통합 이미지**(부트로더+파티션+앱 병합)입니다.

```bash
source venv/bin/activate

# 1) 전체 flash 지우기 (벤더 권장, 16MB라 1~2분)
venv/bin/esptool --chip esp32s3 --port /dev/ttyACM0 erase-flash

# 2) N16R8 MicroPython 굽기 (0x0 통합 이미지)
venv/bin/esptool --chip esp32s3 --port /dev/ttyACM0 -b 921600 \
  write-flash 0x0 "hw/YD-ESP32-S3/1-MPY-firmware/YD-ESP32-S3-N16R8-MPY-V1.1.bin"

# 3) 부팅 검증 — 접속 후 보드 RST 버튼 한 번 누르기
venv/bin/python -m serial.tools.miniterm /dev/ttyACM0 115200
```

부팅 성공 시 배너 `MicroPython v1.19.1 on ...; YD-ESP32S3-N16R8 with ESP32S3R8` 와 `>>>`
프롬프트가 뜹니다. REPL 에서 PSRAM 확인:

```python
import gc; gc.collect(); print(gc.mem_free())   # 8MB PSRAM 활성 시 7MB 이상
```

(miniterm 나가기: **Ctrl-]**)

> 참고: 이 MicroPython bin 은 벤더 제공 원본(백업) 용도입니다. CSI 연구 단계에서는
> ESP-IDF(C) 기반 펌웨어를 직접 빌드해 사용하게 됩니다.

---

## 2. 진단 펌웨어 (ESP-IDF, 직접 빌드)

보드 진단 도구(`tools/board_check`)는 esptool 만으로 칩/Flash 등을 검사하지만, **PSRAM
실동작·WiFi 스캔·WiFi 접속·Bluetooth LE 스캔·RGB LED·BOOT 버튼·내장 온도센서·GPIO**는
칩에서 코드가 실제로 돌아야 검증됩니다. 이를 위한 작은 ESP-IDF 펌웨어가
[`tools/board_check/firmware/`](../tools/board_check/firmware/) 에 있습니다.

빌드/플래시/검증 방법은 전용 문서를 참고하세요:

- [진단 펌웨어 README](../tools/board_check/firmware/README.md)
- [보드 진단 도구 README](../tools/board_check/README.md)

요약하면:

```bash
source ~/esp/esp-idf/export.sh        # ESP-IDF 환경
cd tools/board_check/firmware
idf.py set-target esp32s3
idf.py build
cd ../../..

source venv/bin/activate              # 진단 도구 환경
python tools/board_check/main.py --firmware   # PSRAM/WiFi/BLE/온도/GPIO/LED/버튼 포함 검사
```

CLI 대신 **웹 대시보드**로 진단하려면(진단/WiFi/BLE 탭, 라이브 LED 색):

```bash
bash scripts/step03_run_web_based_diagnostics.sh   # → http://127.0.0.1:8000
```

> ESP-IDF 환경과 프로젝트 venv 가 헷갈린다면 [Python 환경 두 개](python-environments.md)
> 문서를 보세요.

---

## 관련 문서

- [Python 환경 두 개](python-environments.md)
- [USB-C 포트 가이드](usb-ports.md)
- [설치 가이드](install.md)
- [Espressif 생태계](espressif.md) — ESP-IDF·esptool·esp-csi 등 Espressif GitHub 저장소 정리
