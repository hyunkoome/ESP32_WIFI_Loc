# csi/firmware — CSI 송수신 펌웨어

ESP32-S3(N16R8)용 CSI 펌웨어. [espressif/esp-csi](https://github.com/espressif/esp-csi)
get-started 예제(Apache-2.0)를 기반으로, 본 프로젝트 보드/구조에 맞게 수정했습니다.

| 디렉터리 | 역할 | 설명 |
|----------|------|------|
| [`csi_recv/`](csi_recv/) | **rx** | ESP-NOW 로 CSI 패킷을 수신하고 CSV 로 시리얼 출력 |
| [`csi_send/`](csi_send/) | **tx** | ESP-NOW 패킷을 주기적으로 송신(CSI 유발) |

송수신은 **ESP-NOW 기반**이라 라우터/AP 가 필요 없습니다. tx 가 쏜 패킷을 rx 가 받아
그 채널의 CSI 를 추출합니다.

## 원본 대비 변경점

- `CMakeLists.txt`: esp-csi monorepo 가정(`EXTRA_COMPONENT_DIRS` / `git_describe` /
  디렉터리명에서 project 명 추출)을 제거해 **독립 빌드 + CI** 가능하도록 단순화.
  project 명을 `csi_recv` / `csi_send` 로 고정.
- `sdkconfig.defaults`: 대상 보드 **YD-ESP32-S3 N16R8**(16MB Flash / 8MB Octal PSRAM)
  설정 추가(`CONFIG_IDF_TARGET=esp32s3`, flash 16MB, octal PSRAM).
- 한국어 주석으로 출처/변경점 표기.

각 펌웨어의 CSI 동작·출력 포맷 등 원본 설명은 하위 `csi_recv/README.md`,
`csi_send/README.md`(esp-csi 원본)를 참고하세요.

## 빌드 / flash

보통은 [`scripts/csi_flash.sh`](../../scripts/csi_flash.sh) 가 role 에 맞춰 자동으로
빌드+flash 합니다(권장):

```bash
bash scripts/csi_flash.sh            # config_devices.yaml 의 tx/rx 모두
bash scripts/csi_flash.sh --role rx  # rx(csi_recv) 만
```

수동 빌드(개별 펌웨어):

```bash
source ~/esp/esp-idf/export.sh
cd csi/firmware/csi_recv
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/ttyACM0 flash
```

> 빌드 산출물(`build/`, `managed_components/`)과 `*.bin` 은 commit 되지 않습니다
> (`.gitignore`). 재현성을 위해 `sdkconfig.defaults` 는 commit 합니다.

## CI

`.github/workflows/firmware-build.yml` 이 `csi_recv` / `csi_send` 를 esp32s3 타겟으로
빌드합니다(ESP-IDF v5.4, 하드웨어 불필요).
