#!/usr/bin/env bash
#
# csi_app.sh  —  CSI 통합 웹 대시보드 기동
# ========================================
# 하나의 웹에서 보드 실시간 감지·role 자동표시·tx/rx 펌웨어 다운로드·CSI 진폭/위상
# 라이브 시각화를 제공한다(csi/web/app.py, FastAPI). config_devices.yaml 의존 없음.
#
# 사용:
#   bash scripts/csi_app.sh                      # 기본 0.0.0.0:8200 (핸드폰 등 LAN 접속 가능)
#   HOST=127.0.0.1 PORT=9200 bash scripts/csi_app.sh   # 로컬 전용/다른 포트로 바꾸려면
#
# 환경변수: HOST(기본 0.0.0.0 = 모든 인터페이스), PORT(기본 8200)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_DIR}/venv"
HOST="${HOST:-0.0.0.0}"
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
echo "  ➜ 이 PC:        http://localhost:${PORT}"
if [ "${HOST}" = "0.0.0.0" ]; then
    LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    [ -n "${LAN_IP}" ] && echo "  ➜ 같은 LAN(폰):  http://${LAN_IP}:${PORT}"
fi
echo "    (종료: Ctrl+C)"
echo
cd "${REPO_DIR}/csi/web"
# --ws-ping-interval 0: uvicorn(websockets) 자동 keepalive ping 비활성.
#   서버 sender 의 send 와 자동 ping 이 같은 소켓에 동시 write 하면 drain 충돌
#   (AssertionError, 모바일에서 빈번)이 난다. keepalive 는 app.js 가 직접 보내는
#   {"action":"ping"}(20초) 으로 대체하므로 서버 자동 ping 은 끈다.
exec python -m uvicorn app:app --host "${HOST}" --port "${PORT}" --ws-ping-interval 0
