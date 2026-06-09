# csi/collect — CSI 수집

ESP32-S3 수신 펌웨어(`csi_recv`)의 시리얼 출력을 받아 CSV 로 저장합니다.

## 구성

| 파일 | 역할 |
|------|------|
| `device_map.py` | `../config_devices.yaml` 의 tx/rx 매핑을 읽어 by-id 로 실제 포트 해석 |
| `serial_collector.py` | 시리얼의 `CSI_DATA` 라인을 CSV 로 저장(raw 보존) |
| `requirements.txt` | pyserial (PyYAML 은 device_map 용 — 보통 이미 설치됨) |

## device_map.py

`/dev/ttyACM*` 번호는 연결 순서로 바뀌므로, USB serial 로 보드를 고정 식별합니다.

```bash
python device_map.py              # 사람이 읽는 표(name/role/serial/port/firmware)
python device_map.py --shell      # 셸 파싱용 TSV
python device_map.py --role rx --connected-only
```

## serial_collector.py

포트는 `--port` 로 직접 주거나, `--role`/`--device` 로 자동 해석합니다.

```bash
# rx 역할 보드에서 30초 수집
python serial_collector.py --role rx --duration 30 --out ../../results/csi_run01.csv

# 특정 보드(name) 지정 / 포트 직접 지정
python serial_collector.py --device rx1 --out run.csv
python serial_collector.py --port /dev/ttyACM0 --out run.csv
```

기본은 `CSI_DATA` 라인만 저장합니다. 헤더/로그까지 보려면 `--all-lines`.
출력 CSV 포맷은 `../firmware/csi_recv/main/app_main.c` 의 `ets_printf` 와 동일합니다.

> 수집 CSV(`*.csv`)는 `.gitignore` 로 commit 되지 않습니다. `results/` 아래에 두세요.
