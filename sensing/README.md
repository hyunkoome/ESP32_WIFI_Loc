# sensing — 응용 계층 (presence · multi-person · pose)

WiFi **CSI 만으로**(카메라·기타 센서 없이) 실내 환경에서

- 사람 존재 감지(presence),
- 여러 명 동시 감지(multi-person),
- 각 사람의 자세 추정(pose estimation)

을 수행하는 **추론·학습 코드**가 들어갈 자리다.

## 계층 위치

```
csi/        ── 데이터 획득 계층 (펌웨어 + 시리얼 수집 + 파싱)
   │  raw CSI / 진폭·위상 시계열
   ▼
sensing/    ── 응용 계층 (이 디렉터리)
              전처리 → 특징/표현 → 모델 → presence / count / pose
```

`sensing/` 은 `csi/analysis/csi_parser.py` 가 만든 진폭/위상 배열을 입력으로
받는다. 펌웨어나 시리얼 I/O 는 알 필요가 없다(획득 계층이 책임진다).

## 추가 예정 (To do)

- `dataset/` — 라벨링된 수집 데이터 적재 / 윈도우 분할
- `features/` — CSI 전처리(위상 보정, 잡음 제거, 서브캐리어 선택)
- `models/` — presence / people-counting / pose 모델 정의·학습·추론
- `eval/` — 평가 지표 / 시각화

> 아직 스캐폴딩 단계다. 먼저 `csi/` 로 데이터를 수집·검증한 뒤 채운다.
> 모델 의존성(torch 등)이 정해지면 이 디렉터리에 `requirements.txt` 를 둔다.
