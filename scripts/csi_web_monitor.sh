#!/usr/bin/env bash
#
# csi_web_monitor.sh  —  CSI 웹 모니터 기동
# ==========================================
# 브라우저에서 ESP32-S3 들의 상태(tx/rx 연결 여부)와 rx 보드의 CSI 실시간 수신
# (패킷 rate / RSSI / 서브캐리어 진폭)을 모니터링하는 웹 대시보드(FastAPI)를 띄운다.
#
# 사전 준비:
#   1) config_devices.yaml 에 tx/rx 매핑 작성 (ls /dev/serial/by-id/ 로 serial 확인)
#   2) bash scripts/csi_flash.sh        # 펌웨어 빌드+flash (최초 1회)
#
# 사용:
#   bash scripts/csi_web_monitor.sh
#   HOST=0.0.0.0 PORT=9100 bash scripts/csi_web_monitor.sh
#
# 환경변수:
#   HOST  바인드 주소(기본 127.0.0.1). 다른 PC 에서 접속하려면 0.0.0.0.
#   PORT  포트(기본 8100)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_DIR}/venv"
CSI_DIR="${REPO_DIR}/csi"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8100}"

echo "=================================================================="
echo " ESP32 CSI 웹 모니터"
echo "=================================================================="

# --- 1) venv + 의존성 -------------------------------------------------------
echo "[1/2] Python venv 준비: ${VENV_DIR}"
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "${CSI_DIR}/web/requirements-web.txt"

# --- 2) 웹 서버 기동 --------------------------------------------------------
# import 경로상 web 패키지가 top-level 이 되도록 csi/ 에서 기동한다.
echo "[2/2] 웹 서버 기동"
echo
echo "  ➜ 브라우저에서 열기:  http://${HOST}:${PORT}"
echo "    (종료: Ctrl+C)"
echo
cd "${CSI_DIR}"
exec python -m uvicorn web.app:app --host "${HOST}" --port "${PORT}"
