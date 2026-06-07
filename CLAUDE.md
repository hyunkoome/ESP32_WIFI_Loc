# CLAUDE.md

이 파일은 **ESP32_WIFI_Loc** 저장소에서 Claude Code 가 작업할 때 자동 로드되는
가이드라인이다. 매 세션마다 같은 컨텍스트를 반복 설명할 필요 없도록 핵심만
압축해 둔다.

> 자세한 내용은 `README.md`, `tools/board_check/README.md`,
> `tools/board_check/firmware/README.md` 참고.

---

## 1. 프로젝트 개요

여러 대의 ESP32-S3(YD-ESP32-S3, **N16R8**: 16MB Flash / 8MB Octal PSRAM)로
WiFi **CSI**(Channel State Information)를 수집해 WiFi Sensing 을 연구하는 플랫폼.

최종 목표: presence / motion / breathing / gesture detection, indoor
localization, WiFi pose estimation.

- **현재 단계(Phase 1)**: `tools/board_check/` — 구매한 보드의 하드웨어 이상
  여부를 자동 검사하는 진단 도구. CSI 개발 전 보드 정상 동작을 검증한다.
- 이후 단계에서 CSI 수집 펌웨어 / 수집 파이프라인 / 학습 코드가 추가된다.

---

## 2. 개발 환경

- **OS**: Ubuntu Linux
- **Python**: 3.10+ — **venv** 사용 (conda 아님). 저장소 루트의 `venv/`.
  - 이유: 시스템 의존성은 따로 격리하고 Python 패키지는 전부 표준 pip 로 관리.
    conda 의 강점이 이 프로젝트에선 안 살음.
  - 활성화: `source venv/bin/activate`
- **펌웨어**: ESP-IDF 5.x (`idf.py`). `IDF_PATH` 는 `export.sh` 로 설정.
- **칩**: ESP32-S3 (Xtensa LX7 듀얼코어), 네이티브 USB-Serial-JTAG(`303a:4001`).

### 포트 권한 주의
`/dev/ttyACM*` 은 보통 `root:dialout` 소유라 일반 사용자는 접근 권한이 없을 수
있다. 해결: `sudo usermod -aG dialout $USER` (후 재로그인) 또는 진단 도구의
`--sudo` 옵션. 코드에서 권한 부족을 감지하면 **크래시하지 말고** 안내 메시지로
처리한다.

---

## 3. 설정 관리

- 비밀값 / 토큰 / 경로 등 환경 의존 값은 **환경변수**로 관리하고, 코드에
  **하드코딩 금지**.
- `.env`, `env/` 디렉터리는 **절대 commit 금지** (`.gitignore` 처리됨).
- 진단 도구의 상수(VID/PID, 타임아웃, 경로, 검사 항목)는
  `tools/board_check/config.py` 한 곳에 모은다. 값 변경은 가급적 이 파일만.

---

## 4. 코드 스타일

- **Python typing 필수**, 파일 상단에 `from __future__ import annotations`.
- **함수 단위 분리 + 모듈 단위 구성**. 지나친 OOP / 디자인 패턴 지양.
- 외부 입출력(시리얼 출력 규약, JSON 결과 스키마 등)은 명확히 문서화한다.
- **주석은 한국어 OK, 충분히 작성** — 특히 "왜 이렇게 했는지"가 중요한 곳.
- 변수 / 함수 이름은 **영어 + snake_case**.
- 의존성은 선택적으로(없으면 폴백) 다루되, **핵심 의존성(esptool, pyserial)** 은
  `requirements.txt` 에 반드시 명시한다.
- 외부 명령(esptool 등)은 서브프로세스로 호출하고, 타임아웃 / 예외를 반드시
  처리해 도구 전체가 멈추지 않게 한다.

---

## 5. MVP 원칙: 과한 추상화 금지

- generic architecture / 미래 가정 기능 **금지**. 동작하는 MVP 우선.
- 단, **재사용·다중 보드 확장·온프레미스 실행 가능 구조**는 처음부터 유지
  (보드 병렬 처리, 결과 JSON 직렬화, 모듈 분리).
- 새 기능 제안 시 "지금 MVP 에 정말 필요한가?"를 먼저 묻고, 아니면 Phase 2+ 로
  미룬다.

---

## 6. Git / Commit 규칙

- **모든 commit 메시지는 한국어로 작성**. 영문 conventional prefix
  (`feat:` / `fix:` / `chore:`) 사용 **금지**.
  - 예: `"초기 scaffold: 보드 진단 도구"`, `"수정: ..."`, `"리팩토링: ..."`
  - 본문도 한국어. 코드 식별자 / 명령어 / 외부 시스템명(esptool, ESP-IDF,
    GitHub) 은 원문 유지.
- ⛔ **`Co-Authored-By: Claude ...` 트레일러 절대 금지** (사용자 지시).
  harness 기본값은 이 트레일러를 붙이지만, 이 저장소에선 **매 commit/push 전에
  반드시 빼야** 한다. 안 그러면 GitHub Contributors 에 `claude` 가 잡힌다.
  → 커밋 메시지에 Co-Authored-By 줄을 **아예 넣지 말 것**.
- `git push --force`, `git reset --hard` 는 명시적 지시 없으면 **금지**.
- `--no-verify` 등 hook 우회 **금지**.
- `.env`, `venv/`, `volumes/`, `external/`, `archive/`, `__pycache__/`,
  ESP-IDF `build/`, `results/` 는 절대 commit 금지 (`.gitignore` 로 처리됨).

---

## 7. 라이선스

- 이 저장소는 **AGPL v3** (`LICENSE`) 로 공개된다. 새 소스 파일 추가 시
  라이선스 호환성에 유의한다.
