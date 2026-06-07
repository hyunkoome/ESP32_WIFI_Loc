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
| WiFi Scan | 진단 펌웨어 AP 스캔 | 펌웨어 없으면 SKIP |
| Stress Test | esptool 연결 N회 반복(옵션) | `--stress N` |

> **WiFi/PSRAM 안내**: 이 두 항목은 esptool만으로는 검사할 수 없어(칩에서 코드
> 실행 필요) 진단 펌웨어가 있을 때만 PASS/FAIL을 판정합니다. 펌웨어가 없으면
> `SKIP`으로 표시되며 전체 결과(Overall)를 FAIL로 만들지 않습니다.
> 펌웨어 빌드는 [`firmware/README.md`](firmware/README.md) 참고.

## 설치

```bash
# 프로젝트 venv 활성화
source /home/hyunkoo/DATA/hdd8TB2/ESP32_WIFI_Loc/venv/bin/activate

# 의존성 설치
cd tools/board_check
pip install -r requirements.txt
```

핵심 의존성은 `esptool`(칩/Flash 조회)과 `pyserial`(UART)입니다.
`colorama`(컬러 출력), `pyudev`(USB 정보), `tqdm`(진행률)는 없으면 자동 폴백합니다.

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

# WiFi/PSRAM 런타임 검사까지(진단 펌웨어 필요)
python main.py --firmware

# 스트레스 테스트 100회
python main.py --stress 100

# 상세 로그
python main.py -v
```

### 주요 옵션

| 옵션 | 설명 |
|------|------|
| `--port DEV` | 검사할 포트 지정(여러 번 가능). 미지정 시 자동 탐색 |
| `--sudo` | esptool/펌웨어 명령을 sudo로 실행 |
| `--firmware` | 진단 펌웨어 flash 후 WiFi/PSRAM 검사 |
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
├── wifi_test.py       # WiFi 스캔 결과 해석
├── psram_test.py      # PSRAM 결과 해석
├── diagnostics.py     # 보드 1대 전체 검사 오케스트레이션 + PASS/FAIL
├── report.py          # 컬러 콘솔 출력 + JSON/로그 저장
├── requirements.txt
├── firmware/          # ESP-IDF 진단 펌웨어(WiFi/PSRAM 런타임 검사)
└── results/           # 검사 결과 저장(자동 생성)
```

## 개별 모듈 단독 실행

각 모듈은 단독 실행으로 빠르게 점검할 수 있습니다.

```bash
python usb_detector.py            # 탐색된 보드 출력
python serial_check.py /dev/ttyACM0
python esptool_wrapper.py /dev/ttyACM0
```
