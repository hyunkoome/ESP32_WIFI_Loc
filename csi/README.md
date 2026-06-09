# csi — CSI 데이터 획득 계층

WiFi **CSI**(Channel State Information)를 ESP32-S3 로 수집하는 계층입니다.
펌웨어(송신/수신) + 호스트 측 수집·파싱·웹 모니터를 포함합니다.

> 이 계층은 **데이터 획득**까지만 책임집니다. 수집한 CSI 로 presence / 다중 인원 /
> pose 를 추정하는 **응용 계층**은 [`../sensing/`](../sensing/) 에 있습니다.
> (목표: 카메라·기타 센서 없이 WiFi CSI 만으로 실내 다중 인원 감지 + 자세 추정.)

기반 코드: [espressif/esp-csi](https://github.com/espressif/esp-csi)
(`reference/esp-csi`, Apache-2.0)의 get-started 예제.

## 구조

```
csi/
├── config_devices.yaml      # tx/rx 디바이스 매핑 (by-id serial → 역할)
├── firmware/
│   ├── csi_recv/            # 수신 펌웨어 (ESP-NOW CSI 수신) — rx 역할
│   └── csi_send/            # 송신 펌웨어 (ESP-NOW 패킷 송신) — tx 역할
├── collect/
│   ├── device_map.py        # config_devices.yaml → 실제 포트 해석(by-id)
│   └── serial_collector.py  # 시리얼 CSI 라인 → CSV 저장
├── analysis/
│   └── csi_parser.py        # CSV → 진폭/위상 배열 파싱
└── web/                     # 웹 모니터(FastAPI): 디바이스 상태 + CSI 라이브
```

송수신은 **ESP-NOW 기반**이라 라우터/AP 가 필요 없습니다(전용 tx↔rx 페어).

## 디바이스 매핑 (tx/rx)

여러 ESP32-S3 를 `/dev/ttyACM*` 번호 대신 **USB serial 로 고정 식별**합니다.
번호는 연결 순서에 따라 바뀌지만 serial 은 보드 고유값입니다.

```bash
# 1) 보드 serial 확인
ls /dev/serial/by-id/
#   usb-1a86_USB_Single_Serial_5C4C092284-if00 → serial 은 5C4C092284

# 2) config_devices.yaml 작성 (.example 복사)
cp csi/config_devices.yaml.example csi/config_devices.yaml
#   role(tx/rx) + serial + name 을 채운다. tx/rx 여러 개 가능.

# 3) 매핑 확인 (어느 보드가 어느 포트로 잡혔는지)
python csi/collect/device_map.py
```

## 전체 워크플로

```bash
source venv/bin/activate
pip install -r csi/collect/requirements.txt -r csi/analysis/requirements.txt

# 1) 펌웨어 빌드 + flash (role 에 맞는 펌웨어를 각 보드에 자동 배포)
bash scripts/csi_flash.sh            # tx, rx 모두
#   bash scripts/csi_flash.sh --role rx   # rx 만

# 2) CSI 수집 (rx 보드의 시리얼 → CSV)
python csi/collect/serial_collector.py --role rx --out results/csi_run01.csv

# 3) 파싱/확인
python csi/analysis/csi_parser.py results/csi_run01.csv

# 4) (선택) 웹 모니터 — 브라우저에서 상태 + CSI 라이브
bash scripts/csi_web_monitor.sh      # http://127.0.0.1:8100
```

각 단계 상세는 하위 README 참고: [collect](collect/README.md) ·
[analysis](analysis/README.md) · [web](web/README.md) · [firmware](firmware/README.md).
