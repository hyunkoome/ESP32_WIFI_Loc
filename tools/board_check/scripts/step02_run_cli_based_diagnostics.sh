#!/usr/bin/env bash
#
# step02_run_cli_based_diagnostics.sh  —  [2단계] 보드 진단 실행
# ====================================================
# [1단계] step01_build_diag_firmware.sh 로 만든 진단 펌웨어(diag_merged.bin)를
# 보드에 올리고, 실제 하드웨어 검사를 수행한다. 반복 실행해도 되는 단계다.
#
#   1) 진단용 Python venv 준비 — 없으면 생성하고 requirements.txt 설치
#   2) python tools/board_check/main.py --firmware 실행
#        - 보드 flash 전체 erase(기존 펌웨어 삭제) -> 진단 펌웨어 다운로드 ->
#          부팅 후 PSRAM / WiFi 스캔 / RGB LED / BOOT 버튼 런타임 검사까지 판정
#
# 즉 esptool 만으로는 SKIP 되던 PSRAM/WiFi/LED/버튼 항목까지 전부 PASS/FAIL 로
# 검사한다.
#
# 사전 준비:
#   1) 보드의 오른쪽 USB-C 포트(COM/CH343, 1A86:55D3)에 케이블 연결(권장).
#   2) bash tools/board_check/scripts/step01_build_diag_firmware.sh  # 펌웨어 빌드(최초 1회)
#
# 사용:
#   bash tools/board_check/scripts/step02_run_cli_based_diagnostics.sh                  # 자동 탐색 후 검사
#   bash tools/board_check/scripts/step02_run_cli_based_diagnostics.sh --port /dev/ttyACM0
#   bash tools/board_check/scripts/step02_run_cli_based_diagnostics.sh --sudo           # 포트 권한 부족 시
#
# 모든 옵션은 그대로 main.py 로 전달된다(--port, --sudo, --stress, --min-ap,
# --jobs, --verbose 등).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# tools/board_check/scripts/ → SCRIPT_DIR/../../.. == 저장소 루트
REPO_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FW_DIR="${REPO_DIR}/tools/board_check/firmware"
VENV_DIR="${REPO_DIR}/venv"
REQ_FILE="${REPO_DIR}/tools/board_check/requirements.txt"
MAIN_PY="${REPO_DIR}/tools/board_check/main.py"
MERGED_BIN="${FW_DIR}/build/diag_merged.bin"

echo "=================================================================="
echo " ESP32-S3 보드 진단 — [2단계] 실행"
echo "   펌웨어 : ${MERGED_BIN}"
echo "=================================================================="

# --- 사전 확인: 병합 바이너리가 있어야 PSRAM/WiFi/LED/버튼 검사가 동작 ---------
if [ ! -f "${MERGED_BIN}" ]; then
    echo "[에러] 진단 펌웨어가 없습니다: ${MERGED_BIN}"
    echo "       먼저 [1단계]를 실행해 펌웨어를 빌드하세요:"
    echo "         bash tools/board_check/scripts/step01_build_diag_firmware.sh"
    exit 1
fi

# --- 1) 진단용 venv 준비 ------------------------------------------------------
echo "[1/2] 진단용 Python venv 준비: ${VENV_DIR}"
if [ ! -d "${VENV_DIR}" ]; then
    echo "      venv 생성 중..."
    python3 -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
# 의존성 설치(이미 설치돼 있으면 빠르게 통과). pyserial/esptool/colorama/PyYAML 등.
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "${REQ_FILE}"

# --- 2) 진단 실행(펌웨어 erase + flash + 런타임 검사 포함) --------------------
echo "[2/2] 진단 실행: main.py --firmware $*"
echo "=================================================================="
# 인자가 없을 때도 set -u 에서 안전하도록 "$@" 사용(빈 배열은 아무것도 전개 안 함).
python "${MAIN_PY}" --firmware "$@"
