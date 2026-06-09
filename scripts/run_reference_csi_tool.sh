#!/usr/bin/env bash
#
# run_reference_csi_tool.sh  —  reference esp-radar console_test PyQt GUI 동작 확인
# ==============================================================================
# reference/esp-csi 의 esp_csi_tool.py(PyQt5 + pyqtgraph) 를 기동해 본다.
#
# ⚠️ 주의 — 호환성:
#   이 GUI 는 reference 의 console_test 펌웨어(esp-radar 라이브러리, 2,000,000 baud,
#   'csi --output' 등 콘솔 명령)를 가정한다. 본 프로젝트의 csi_recv(ESP-NOW,
#   921600 baud, CSI_DATA 만 출력)와는 보드레이트/프로토콜이 달라 그대로는 호환되지
#   않는다. 따라서 이 스크립트의 목적은:
#     1) reference GUI 의 의존성 설치 + import/기동 가능 여부 확인
#     2) (선택) console_test 펌웨어를 올린 보드와의 파형 표시 확인
#   본 프로젝트의 보드로 파형을 보려면 우리 web(csi_app.sh)/GUI(csi_gui.sh)를 쓴다.
#
# 사용:
#   bash scripts/run_reference_csi_tool.sh                 # import 검증만(디스플레이 불필요)
#   bash scripts/run_reference_csi_tool.sh /dev/ttyACM0    # GUI 기동(디스플레이 필요)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_DIR}/venv"
REF="${REPO_DIR}/reference/esp-csi/examples/esp-radar/console_test/tools"
PORT="${1:-}"

if [ ! -d "${REF}" ]; then
    echo "[에러] reference 경로가 없습니다: ${REF}" >&2
    exit 1
fi

echo "[1/3] venv + reference 의존성 설치 (pandas/scipy/PyQt5 등 — 다소 무거움)"
if [ ! -d "${VENV_DIR}" ]; then python3 -m venv "${VENV_DIR}"; fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "${REF}/requirements.txt"

echo "[2/3] GUI 모듈 import 검증(디스플레이 없이)"
if python -c "import sys; sys.path.insert(0, '${REF}'); import esp_csi_tool_gui" 2>/dev/null; then
    echo "      ✓ esp_csi_tool_gui import OK — 의존성/문법 정상"
else
    echo "      ✗ import 실패 — 위 의존성 설치 로그를 확인하세요." >&2
fi

if [ -z "${PORT}" ]; then
    echo "[3/3] 포트 미지정 — GUI 기동은 생략합니다."
    echo "      기동하려면:  bash scripts/run_reference_csi_tool.sh /dev/ttyACM0"
    echo "      (console_test 펌웨어를 올린 보드여야 파형이 보입니다.)"
    exit 0
fi

echo "[3/3] GUI 기동: esp_csi_tool.py -p ${PORT}"
echo "      (창이 뜨지 않으면 디스플레이/원격 X11 을 확인하세요.)"
cd "${REF}"
exec python esp_csi_tool.py -p "${PORT}"
