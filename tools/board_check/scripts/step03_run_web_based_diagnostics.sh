#!/usr/bin/env bash
#
# step03_run_web_based_diagnostics.sh  —  [3단계] 웹 대시보드 진단
# =================================================================
# 브라우저에서 보드를 진단하는 웹 대시보드(FastAPI)를 띄운다. 진단 결과를
# 녹색/적색 동그라미로 보여주고, WiFi AP 목록·BLE 기기 목록·온도·GPIO 도
# 표시하며, RGB LED 순환과 BOOT 버튼은 라이브 모니터로 갱신한다.
#
# 기존 CLI 진단 모듈(diagnostics/firmware/usb_detector)을 그대로 재사용한다.
#
# 사전 준비:
#   1) 보드의 오른쪽 USB-C 포트(COM/CH343)에 케이블 연결.
#   2) bash tools/board_check/scripts/step01_build_diag_firmware.sh   # 펌웨어 빌드(최초 1회)
#
# 사용:
#   bash tools/board_check/scripts/step03_run_web_based_diagnostics.sh
#   HOST=0.0.0.0 PORT=9000 bash tools/board_check/scripts/step03_run_web_based_diagnostics.sh
#
# 환경변수:
#   HOST  바인드 주소(기본 127.0.0.1). 다른 PC 에서 접속하려면 0.0.0.0.
#   PORT  포트(기본 8000)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# tools/board_check/scripts/ → SCRIPT_DIR/../../.. == 저장소 루트
REPO_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
VENV_DIR="${REPO_DIR}/venv"
BC_DIR="${REPO_DIR}/tools/board_check"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo "=================================================================="
echo " ESP32-S3 보드 진단 — [3단계] 웹 대시보드"
echo "=================================================================="

# --- 1) venv 준비 + 의존성(진단 + 웹) 설치 ----------------------------------
echo "[1/3] Python venv 준비: ${VENV_DIR}"
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "${BC_DIR}/requirements.txt"
python -m pip install --quiet -r "${BC_DIR}/requirements-web.txt"

# --- 2) 진단 펌웨어 존재 확인(없어도 기동은 함, 런타임 검사만 SKIP) ----------
MERGED_BIN="${BC_DIR}/firmware/build/diag_merged.bin"
if [ ! -f "${MERGED_BIN}" ]; then
    echo "[2/3] ⚠ 진단 펌웨어가 없습니다(${MERGED_BIN})."
    echo "      PSRAM/WiFi/BLE/온도/GPIO 런타임 검사를 하려면 먼저:"
    echo "        bash tools/board_check/scripts/step01_build_diag_firmware.sh"
else
    echo "[2/3] 진단 펌웨어 확인됨"
fi

# --- 3) 웹 서버 기동 ---------------------------------------------------------
echo "[3/3] 웹 서버 기동"
echo
echo "  ➜ 브라우저에서 열기:  http://${HOST}:${PORT}"
echo "    (종료: Ctrl+C)"
echo
cd "${BC_DIR}"
exec python -m uvicorn web.app:app --host "${HOST}" --port "${PORT}"
