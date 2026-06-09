# csi — CSI 데이터 획득 계층

WiFi **CSI**(Channel State Information)를 ESP32-S3 로 수집하는 계층입니다.
펌웨어(송신/수신) + 호스트 측 공용 백엔드·수집·파싱·웹/GUI 대시보드를 포함합니다.

> 이 계층은 **데이터 획득**까지만 책임집니다. presence / 다중 인원 / pose / 위치
> 추정의 **응용 계층**은 [`../sensing/`](../sensing/) 에 있습니다.
> (목표: 카메라·기타 센서 없이 WiFi CSI 만으로 실내 다중 인원 감지 + 자세/위치 추정.)

송수신은 **ESP-NOW 기반**이라 라우터/AP 가 필요 없습니다(전용 tx↔rx 페어). 보드는
펌웨어가 부팅 시 출력하는 **`DEVICE_ROLE` 로 tx/rx 를 자동 감지**하므로, 디바이스
매핑 파일(config_devices.yaml)이 필요 없습니다 — **연결만 하면** 호스트가 알아봅니다.

## 구조

```
csi/
├── firmware/
│   ├── csi_recv/   # 수신 펌웨어(ESP-NOW CSI 수신) — rx. 부팅 시 DEVICE_ROLE 출력
│   └── csi_send/   # 송신 펌웨어(ESP-NOW 패킷 송신) — tx. 부팅 시 DEVICE_ROLE 출력
├── common/         # web/GUI 공용 백엔드(UI 프레임워크 무관)
│   ├── boards.py        # 보드 실시간 감지(by-id) — board_check usb_detector 재사용
│   ├── role_detect.py   # 시리얼 DEVICE_ROLE → tx/rx 자동 판별
│   ├── csi_stream.py    # CSI_DATA → 진폭/위상 스트림
│   ├── flasher.py       # role 펌웨어 빌드/flash (csi_flash.sh 래퍼)
│   └── port_lock.py     # 포트 직렬화 락
├── web/            # 웹 대시보드(FastAPI): 보드 감지·role·tx/rx flash·진폭/위상 라이브
├── gui/            # 데스크톱 GUI(PyQt5+pyqtgraph): web 과 동일 백엔드
├── collect/serial_collector.py  # 시리얼 CSI 라인 → CSV 저장 (--role 실시간 감지)
└── analysis/csi_parser.py       # CSV → 진폭/위상 배열 파싱
```

## 빠른 시작 (보드 연결만 하면 됨)

보드를 USB 로 연결하면 호스트가 실시간 감지하고 `DEVICE_ROLE` 로 tx/rx 를 표시합니다.

```bash
# 웹 대시보드 — 보드 감지 + tx/rx 다운로드 + CSI 진폭/위상 라이브
bash scripts/csi_app.sh           # http://127.0.0.1:8200

# 또는 데스크톱 GUI (동일 기능)
bash scripts/csi_gui.sh
```

대시보드에서 각 보드에 **tx 또는 rx 펌웨어를 골라 다운로드**하고, rx 를 선택해 **CSI
진폭/위상 파형**을 실시간으로 봅니다. 사람이 **tx–rx 사이(2~5m 권장)** 를 지나가면
파형이 변합니다(붙여 두면 감지 영역이 없어 변화가 안 보입니다).

## 명령줄 도구

```bash
# 펌웨어 빌드/flash (대시보드가 내부적으로 호출하는 것과 동일)
bash scripts/csi_flash.sh --role rx --port /dev/ttyACM0   # 빌드+flash
bash scripts/csi_flash.sh --role tx --build-only          # 빌드만(merge-bin 산출)

# CSI 수집 → CSV (--role 은 연결 보드를 실시간 감지해 선택)
python csi/collect/serial_collector.py --role rx --out results/csi_run01.csv

# 파싱/확인
python csi/analysis/csi_parser.py results/csi_run01.csv
```

## 위치 정확도 (다중 rx 앵커)

CSI 로 **위치/다중 인원/pose** 정확도를 높이려면 **rx(수신/앵커) 보드를 여러 곳에
분산** 배치합니다(`tx 1 + rx 다수`). ESP32-S3 는 안테나 1개(SISO)라 **보드 분산이 곧
공간 다양성**입니다 — 링크(=tx×rx)가 많고 넓게 퍼질수록 정확해집니다. 여러 rx 의 CSI 를
모아 [`../sensing/`](../sensing/) 에서 위치/pose 를 추정합니다.

## 참고

- 각 하위 상세: [collect](collect/README.md) · [analysis](analysis/README.md) ·
  [web](web/README.md) · [firmware](firmware/README.md)
- 기반 코드: [espressif/esp-csi](https://github.com/espressif/esp-csi)
  (`reference/esp-csi`, Apache-2.0) 의 get-started / esp-radar 예제.
- (참고) reference esp-radar 의 PyQt GUI 동작 확인: `scripts/run_reference_csi_tool.sh`
