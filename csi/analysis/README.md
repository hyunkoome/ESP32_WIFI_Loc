# csi/analysis — CSI 파싱·전처리

수집된 CSV(`csi/collect/serial_collector.py` 출력)를 진폭/위상 배열로 변환합니다.

## 구성

| 파일 | 역할 |
|------|------|
| `csi_parser.py` | CSV → `CsiPacket`(seq/mac/rssi + 진폭/위상). 헤드리스/배치용 경량 파서 |
| `csi_data_read_parse_ref.py` | esp-csi 원본 GUI 뷰어(PyQt5). 참고용 — 실시간 파형 뷰 |
| `requirements.txt` | numpy (경량 파서용) |
| `requirements-viewer.txt` | 원본 GUI 뷰어용(PyQt5/pyqtgraph 등, 무거움) |

## csi_parser.py

```bash
# 수집 CSV 요약(앞 5패킷 + 총 개수)
python csi_parser.py ../../results/csi_run01.csv
```

라이브러리로 사용:

```python
from csi_parser import iter_packets

for pkt in iter_packets("results/csi_run01.csv"):
    amp = pkt.amplitude()   # numpy 배열: 서브캐리어별 |H|
    pha = pkt.phase()       # 서브캐리어별 위상(rad)
```

`data` 컬럼은 `"[i0,q0,i1,q1,...]"` 형태로, 각 `(i, q)` 쌍이 한 서브캐리어의
복소수입니다. `to_complex()` 가 이를 복소 배열로 풀어줍니다.

> 이 단계의 출력(진폭/위상)이 [`../../sensing/`](../../sensing/) 응용 계층의 입력입니다.
