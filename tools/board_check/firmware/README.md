# ESP32-S3 진단 펌웨어

WiFi AP 스캔과 PSRAM 런타임 검사는 칩에서 코드가 실행돼야 하므로, 이 작은
ESP-IDF 펌웨어를 보드에 올린 뒤 시리얼 출력을 호스트가 파싱합니다.
진단 도구(`main.py --firmware`)는 빌드된 바이너리를 자동으로 flash하고 결과를
읽습니다.

## 사전 준비: ESP-IDF 5.x

```bash
# ESP-IDF 설치(이미 설치돼 있으면 export만)
git clone -b v5.3.1 --recursive https://github.com/espressif/esp-idf.git ~/esp/esp-idf
~/esp/esp-idf/install.sh esp32s3
source ~/esp/esp-idf/export.sh   # 새 터미널마다 실행 (IDF_PATH 설정)
```

## 빌드

```bash
cd tools/board_check/firmware
idf.py set-target esp32s3
idf.py build
```

## 진단 도구가 사용하는 병합 바이너리 만들기

진단 도구는 `firmware/build/diag_merged.bin` 하나를 `0x0`에 flash합니다.
(esptool만 있으면 되도록 부트로더+파티션+앱을 하나로 병합)

```bash
cd tools/board_check/firmware
esptool.py --chip esp32s3 merge_bin -o build/diag_merged.bin \
  @build/flash_args
```

> 참고: esptool v5에서는 `merge-bin`, `@build/flash_args` 인자 파일을 사용합니다.
> 또는 ESP-IDF가 생성하는 `idf.py build` 산출물을 그대로 flash해도 됩니다:
> ```bash
> idf.py -p /dev/ttyACM0 flash monitor
> ```
> 이 경우 도구 없이도 시리얼에서 `DIAG_*` 라인을 직접 확인할 수 있습니다.

## 출력 규약

펌웨어는 부팅 후 다음 라인을 출력합니다(`firmware.py`가 파싱):

```
DIAG_START
DIAG_CHIP  {"cores":2,"model":"ESP32-S3","revision":2}
DIAG_PSRAM {"present":true,"size":8388608}
DIAG_WIFI  {"ap_count":15,"strongest_rssi":-42}
DIAG_DONE
```

## 빌드 없이 사용하려면

ESP-IDF 설치가 부담되면 `--firmware` 옵션을 빼고 실행하세요. 이 경우
WiFi/PSRAM 항목은 `SKIP`으로 표시되고, 나머지 esptool 기반 하드웨어 검사는
모두 정상 수행됩니다.
