# CSI 로깅 데이터셋 (딥러닝 학습용)

CSI GUI(`csi/gui`)의 **Log Static Data / Log Motion Data** 로 수집한 raw CSI.

## 파일 형식
- 이름: `log_<mode>_<serial>_<timestamp>.csv`
  - `mode` = `static` | `motion` (= 라벨), `serial` = rx 보드 시리얼, `timestamp` = 수집 시각
- 컬럼(저장 가능한 값 모두, **전체 float·반올림 없음**):
  `t_sec, source, mac, rssi, rate, n_sub, wander, jitter` + 가변 꼬리
  `raw_csi i/q(2·n_sub개) → amp(n_sub개) → phase(n_sub개)`
  - `t_sec`: 로깅 시작 기준 경과(초), `source`: tx|router, `mac`: 신호원 MAC, `rate`: 실측 Hz
  - `wander`: presence 메트릭(진폭 std), `jitter`: motion 메트릭(도플러 피크)
  - `raw_csi`: i/q 원본(int), `amp`/`phase`: 서브캐리어별 진폭/위상(raw_csi 에서 파생)
  - **딥러닝 입력**: raw_csi(i/q) 또는 amp+phase 무엇이든 사용 가능(서로 복원됨: i=amp·cosφ, q=amp·sinφ)

## 비고
- 샘플링: 호스트 `csi_stream` throttle 로 약 10Hz. 더 조밀한 100Hz raw 가 필요하면 로깅 중
  throttle 을 해제하도록 확장 예정.
- 신호원(tx / wifi router)은 GUI 의 rx 탭에서 선택한 것이 기록된다(향후 컬럼 추가 검토).
