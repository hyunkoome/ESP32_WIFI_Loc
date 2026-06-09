#!/usr/bin/env bash
#
# csi_gui.sh  —  CSI 통합 데스크톱 GUI(PyQt5) 기동
# ================================================
# web(csi_app.sh) 과 동일한 csi/common 백엔드를 쓰는 PyQt 데스크톱 앱.
# 보드 실시간 감지·role 자동표시·tx/rx 다운로드·CSI 진폭/위상 실시간 플롯.
#
# 사용: bash scripts/csi_gui.sh
# (디스플레이가 있는 데스크톱 환경에서 실행하세요.)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_DIR}/venv"

echo "[1/2] venv + 의존성 준비"
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "${REPO_DIR}/csi/gui/requirements-gui.txt"
# 보드 감지/flash(usb_detector, esptool) 의존.
python -m pip install --quiet -r "${REPO_DIR}/tools/board_check/requirements.txt"

echo "[2/2] GUI 기동"
exec python "${REPO_DIR}/csi/gui/main.py"
