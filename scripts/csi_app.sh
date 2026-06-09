#!/usr/bin/env bash
#
# csi_app.sh  —  CSI 통합 웹 대시보드 기동
# ========================================
# 하나의 웹에서 보드 실시간 감지·role 자동표시·tx/rx 펌웨어 다운로드·CSI 진폭/위상
# 라이브 시각화를 제공한다(csi/web/app.py, FastAPI). config_devices.yaml 의존 없음.
#
# 사용:
#   bash scripts/csi_app.sh
#   HOST=0.0.0.0 PORT=9200 bash scripts/csi_app.sh
#
# 환경변수: HOST(기본 127.0.0.1), PORT(기본 8200)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_DIR}/venv"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8200}"

echo "[1/2] venv + 의존성 준비"
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install --quiet --upgrade pip
# 웹(FastAPI/uvicorn) + 보드 감지/flash(esptool, pyserial 등 board_check 의존).
python -m pip install --quiet -r "${REPO_DIR}/csi/web/requirements-web.txt"
python -m pip install --quiet -r "${REPO_DIR}/tools/board_check/requirements.txt"

echo "[2/2] 웹 서버 기동"
echo
echo "  ➜ 브라우저에서 열기:  http://${HOST}:${PORT}"
echo "    (종료: Ctrl+C)"
echo
cd "${REPO_DIR}/csi/web"
exec python -m uvicorn app:app --host "${HOST}" --port "${PORT}"
