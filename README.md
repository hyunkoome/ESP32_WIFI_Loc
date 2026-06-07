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
| [보드 진단 도구](tools/board_check/README.md) | Phase 1 진단 도구 사용법 |
| [진단 펌웨어](tools/board_check/firmware/README.md) | PSRAM/WiFi/LED/버튼 검사 펌웨어 빌드 |
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

PSRAM/WiFi/LED/버튼 런타임 검사까지 하려면 ESP-IDF 설치 후 진단 펌웨어를 빌드합니다 —
[설치 가이드](docs/install.md) 참고.

```bash
bash scripts/install_esp_idf.sh       # ESP-IDF 설치(최초 1회)
```

## 개발 환경

- Ubuntu Linux / Python 3.10+ (**venv**) / ESP-IDF 5.x
- Python 환경이 **두 개**(진단 도구용 / 펌웨어 빌드용)입니다 — 헷갈리면
  [Python 환경 두 개](docs/python-environments.md) 참고.

## 현재 단계 (Phase 1): 보드 자동 진단 도구

CSI 개발에 들어가기 전, 구매한 ESP32-S3 보드들의 하드웨어 이상 여부를 자동으로
검사하고 PASS/FAIL 리포트를 생성하는 진단 도구입니다. 자세한 사용법은
[`tools/board_check/README.md`](tools/board_check/README.md) 참고.

## 저장소 구조

```
ESP32_WIFI_Loc/
├── hw/
│   └── YD-ESP32-S3/      # 보드 하드웨어 자료(데이터시트/핀맵/벤더 펌웨어)
├── tools/
│   └── board_check/      # Phase 1: 보드 자동 진단 도구 (+ firmware/ 진단 펌웨어)
├── docs/                 # 설치/환경/하드웨어 세부 문서
├── scripts/              # 보조 스크립트 (ESP-IDF 설치 등)
├── CLAUDE.md             # Claude Code 작업 가이드라인
├── LICENSE               # AGPL v3
└── README.md
```

## 라이선스

이 프로젝트는 [GNU Affero General Public License v3.0](LICENSE) 하에 공개됩니다.
