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
- 설정 파일은 **관심사별로 분리**하고, 모두 commit 포함한다:
  - `config/wifi_config.yaml` — **프로젝트 공통** WiFi 자격증명(접속 테스트용 +
    CSI 라우터 접속용). board_check 진단과 CSI GUI/web 이 함께 쓴다. 사용자 요청으로
    commit 포함(민감값 주의). board_check 의 `config.py` 가 이 파일을 읽어 진단 실행
    시 시리얼로 펌웨어에 런타임 주입하고, CSI 호스트(GUI/web)는 같은 파일을 읽어
    `WIFI_CONNECT` 으로 rx 에 라우터 자격증명을 주입한다(없으면 사용자가 직접 입력).
    **board_check 웹 대시보드는 이 파일을 쓰지 않는다**(사용자가 WiFi 탭에서 직접 입력).
  - CSI tx/rx 보드 식별은 **파일이 아니라 실시간 감지**로 한다 — 보드가 부팅 시
    출력하는 `DEVICE_ROLE` 로 tx/rx 를 자동 판별(`csi/common/role_detect.py`),
    by-id 로 보드 고정 식별(`csi/common/boards.py`). config_devices.yaml 은 없앴다.
  - 전역(프로젝트 공통) 설정은 **루트 `config/`** 아래에 둔다(현재
    `config/wifi_config.yaml`). 새 공통 설정이 생기면 같은 디렉터리에 추가한다.
- 비밀값 / 토큰 / 경로 등 환경 의존 값은 코드에 **하드코딩 금지**(환경변수 또는 위 설정).
- 진단 도구의 상수(VID/PID, 타임아웃, 경로, 검사 항목)는
  `tools/board_check/config.py` 한 곳에 모은다. 값 변경은 가급적 이 파일만.
- 스크립트 위치: board_check 전용 스크립트(`step01~03`, `gen_wifi_creds.py`)는
  `tools/board_check/scripts/`, CSI/공용 스크립트(`csi_flash.sh`,
  `csi_web_monitor.sh`, `install_esp_idf.sh`)는 루트 `scripts/` 에 둔다.

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

---

## 8. 문서 유지보수: `docs/espressif.md` (Espressif 저장소 목록)

`docs/espressif.md` 는 Espressif GitHub 조직의 **공개 저장소 전체**를 본 프로젝트
관련도(★5~★1)로 정리한 표다. 아래 규칙으로 **계속 갱신**한다.

- **언제 갱신하나**:
  - Espressif 에 새 저장소가 생겼거나(목록 재조회 시 차이 발생),
  - 본 프로젝트가 어떤 Espressif 저장소/컴포넌트를 **새로 쓰기 시작**했을 때.
- **목록 재조회**(전체 데이터 한 번에):
  ```bash
  for p in 1 2 3 4; do
    gh api "orgs/espressif/repos?per_page=100&page=$p" \
      --jq '.[] | [.stargazers_count,(.archived|tostring),.name,(.description//"")] | @tsv'
  done
  ```
  스타 내림차순으로 tier 안에서 정렬한다. (작성 시점 317개 = 활성 288 + 보관 29)
- **표 컬럼**: `저장소 | ⭐ | 설명 | 본 프로젝트 적용`
  - 설명은 GitHub description 을 **한국어로 번역**(코드 식별자/고유명사/제품명은
    원문 유지). 🗄️ 는 `archived`(보관) 저장소 표시.
  - **본 프로젝트 적용** 열: 실제로 쓰는 저장소만 `✓ (용도)` 로 표시. 새 의존성
    추가 시 — `tools/board_check/requirements*.txt`,
    `tools/board_check/firmware/main/idf_component.yml`(managed_components),
    `scripts/` 의 ESP-IDF 사용 — 해당 행에 ✓ 를 추가한다.
  - 현재 적용(✓) 3개: **esp-idf**(빌드 SDK), **esptool**(flash·칩 조회),
    **idf-extra-components**(`espressif/led_strip` 컴포넌트의 소스 repo).
  - `esp-csi` 등은 ★ 가 높아도 **CSI 수집 단계 예정**이면 아직 빈칸. 실제 사용 시 ✓.
- **별점(★)** 은 "이 CSI 센싱 프로젝트에 얼마나 직접 쓰이느냐" 기준의 **주관적
  관련도**(저장소 품질/스타와 무관).
- 갱신 후 `docs/espressif.md` 를 링크하는 문서들(루트 `README.md`, `docs/*`,
  `tools/board_check/README.md`, `firmware/README.md`)의 개수 표기도 어긋나면 맞춘다.

---

## 9. 문서 표기/갱신 규칙 (⚠️ 사용자 지시)

- ⛔ **"Phase 1 / Phase 2 / Phase X" 같은 단계 라벨을 `README.md` 및 `docs/`,
  `tools/**/README.md` 등 사용자 문서에 절대 쓰지 않는다.** 로드맵/단계 개념은
  **이 `CLAUDE.md` 안에서만** 관리한다(위 1장 등). 사용자 문서에는 단계 번호 대신
  **내용 중심**으로 표현한다 — 예: "보드 자동 진단", "CSI 수집 단계",
  "완료 / 추가 예정(To do)". (작업 중 무심코 "Phase N" 을 넣지 말 것.)
- **기능이 완료/추가될 때마다** 루트 `README.md` 의 **"개발 진행 상황"**
  (✅ 완료 / ⬜ 추가 예정 To do) 리스트를 같이 갱신한다. 완료한 항목은
  To do → 완료로 옮기고, 새로 할 일이 생기면 To do 에 추가한다.
