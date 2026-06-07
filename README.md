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
