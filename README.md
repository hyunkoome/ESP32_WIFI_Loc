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

## 하드웨어

| 항목 | 사양 |
|------|------|
| 개발보드 | YD-ESP32-S3 Development Board |
| 칩 | ESP32-S3N16R8 (Xtensa LX7 듀얼코어, 최대 240MHz) |
| Flash | 16MB |
| PSRAM | 8MB (Octal) |
| 무선 | WiFi 802.11 b/g/n (2.4GHz), BLE 5 |
| 인터페이스 | USB-C UART / USB-C OTG, USB Serial/JTAG |
| 보유 수량 | 3대 (동시 연결 예정) |

## USB-C 포트 (왼쪽 vs 오른쪽)

YD-ESP32-S3 에는 USB-C 포트가 **2개** 있습니다. **양쪽 모두 펌웨어 다운로드와
시리얼 로그가 둘 다 됩니다.** 차이는 "무엇만 되냐"가 아니라 "얼마나 안정적이냐 +
특수 기능"입니다. (좌/우는 보드 방향에 따라 뒤집힐 수 있으니, 커넥터 옆
**실크스크린 라벨 `USB` / `COM`** 을 기준으로 보세요.)

| 항목 | 왼쪽 (`USB`, 네이티브) | 오른쪽 (`COM`, CH343) |
|------|------------------------|------------------------|
| 펌웨어 다운로드 | ✅ 됨 | ✅ 됨 |
| 시리얼 로그 | ✅ 됨 | ✅ 됨 |
| 자동 리셋(버튼 없이 플래시) | 됨 | ✅ 가장 안정적 |
| JTAG 디버깅 | ✅ 이쪽만 가능 | ❌ |
| 앱이 GPIO19/20 사용 시 | 연결 끊길 수 있음 | 영향 없음 |
| Linux 인식 | `/dev/ttyACM*` (`303a:1001`) | `/dev/ttyACM*` (`1A86:55D3`) |

**기억할 것:**

- 평소엔 **오른쪽(`COM`) 하나만** 쓰면 됩니다. 플래시도 로그도 다 되고 제일 안정적.
- **왼쪽(`USB`)** 은 JTAG 디버깅이나 USB 디바이스 기능 개발이 필요할 때만.

## MicroPython 펌웨어 선택 (벤더 제공 bin)

[`hw/YD-ESP32-S3/1-MPY-firmware/`](hw/YD-ESP32-S3/1-MPY-firmware/) 에 벤더가 제공한
MicroPython v1.19.1 펌웨어 bin 이 3개 있습니다. 파일명 규칙은 **N = Flash 크기(MB),
R = PSRAM 크기(MB)** 입니다. **메모리 구성이 맞는 것 하나만** 써야 합니다.

| 파일 | Flash | PSRAM | 이 보드(N16R8)에? |
|------|-------|-------|--------------------|
| `YD-ESP32-S3-N16R8-MPY-V1.1.bin` | 16MB | 8MB | ✅ **이것** |
| `YD-ESP32-S3-N8R2-MPY-V1.1.bin` | 8MB | 2MB | ❌ 다른 구성 |
| `YD-ESP32-S3-N8R8-MPY-V1.1.bin` | 8MB | 8MB | ❌ 다른 구성 |

본 프로젝트 보드는 **Flash 16MB + PSRAM 8MB(N16R8)** 이므로
**`YD-ESP32-S3-N16R8-MPY-V1.1.bin`** 를 사용합니다. 다른 bin 을 올리면 Flash 를
8MB 로만 인식하거나 PSRAM 설정이 맞지 않아(특히 N8R2 는 2MB) 오동작할 수 있습니다.

> 참고: 이 MicroPython bin 은 벤더 제공 원본(백업) 용도입니다. CSI 연구 단계에서는
> ESP-IDF(C) 기반 펌웨어를 직접 빌드해 사용하게 됩니다.

## 개발 환경

- Ubuntu Linux
- Python 3.10+ (**venv**)
- ESP-IDF 5.x

```bash
python3 -m venv venv
source venv/bin/activate
```

## 현재 단계 (Phase 1): 보드 자동 진단 도구

CSI 개발에 들어가기 전, 구매한 ESP32-S3 보드들의 하드웨어 이상 여부를 자동으로
검사하고 PASS/FAIL 리포트를 생성하는 진단 도구입니다.

```bash
cd tools/board_check
pip install -r requirements.txt
python main.py            # 연결된 모든 보드 검사
```

자세한 사용법은 [`tools/board_check/README.md`](tools/board_check/README.md) 참고.

## 저장소 구조

```
ESP32_WIFI_Loc/
├── hw/
│   └── YD-ESP32-S3/      # 보드 하드웨어 자료(데이터시트/핀맵/벤더 펌웨어)
├── tools/
│   └── board_check/      # Phase 1: 보드 자동 진단 도구
├── docs/                 # 설치/설계 문서
├── scripts/              # 보조 스크립트
├── CLAUDE.md             # Claude Code 작업 가이드라인
├── LICENSE               # AGPL v3
└── README.md
```

## 라이선스

이 프로젝트는 [GNU Affero General Public License v3.0](LICENSE) 하에 공개됩니다.
