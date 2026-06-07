#!/usr/bin/env bash
#
# build_diag_firmware.sh
# ======================
# 보드 진단 펌웨어(tools/board_check/firmware)를 빌드하고, esptool로 한 번에 flash
# 가능한 병합 바이너리(build/diag_merged.bin)를 생성한다.
#
#   1) (필요 시) 활성 venv 해제 — ESP-IDF 환경과 충돌 방지
#   2) ESP-IDF 환경 활성화 (export.sh)
#   3) idf.py set-target esp32s3 && idf.py build
#   4) idf.py merge-bin 으로 부트로더+파티션+앱을 0x0 기준 단일 bin 으로 병합
#
# 생성물: tools/board_check/firmware/build/diag_merged.bin
#         (= config.FIRMWARE_BIN, main.py --firmware 가 이 파일을 flash)
#
# 사용:
#   bash scripts/build_diag_firmware.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
FW_DIR="${REPO_DIR}/tools/board_check/firmware"
IDF_DIR="${IDF_DIR:-$HOME/esp/esp-idf}"
# 절대경로로 지정한다. idf.py merge-bin 은 build/ 디렉터리 안에서 esptool 을
# 실행하므로, 상대경로(build/...)를 주면 build/build/... 가 되어 실패한다.
MERGED_BIN="${FW_DIR}/build/diag_merged.bin"

# --- 1) 활성 venv 해제 (ESP-IDF 가 자체 Python 환경을 쓰므로 충돌 방지) ----------
if [ -n "${VIRTUAL_ENV:-}" ]; then
    echo "[알림] 활성 Python venv 해제: ${VIRTUAL_ENV}"
    venv_bin="${VIRTUAL_ENV}/bin"
    new_path=""
    IFS=':' read -ra _parts <<< "${PATH}"
    for p in "${_parts[@]}"; do
        [ "${p}" = "${venv_bin}" ] && continue
        new_path="${new_path:+${new_path}:}${p}"
    done
    export PATH="${new_path}"
    unset VIRTUAL_ENV
fi

# --- 2) ESP-IDF 환경 활성화 --------------------------------------------------
if [ ! -f "${IDF_DIR}/export.sh" ]; then
    echo "[에러] ESP-IDF 를 찾을 수 없습니다: ${IDF_DIR}"
    echo "       먼저 설치하세요:  bash scripts/install_esp_idf.sh"
    exit 1
fi
echo "[1/3] ESP-IDF 환경 활성화: ${IDF_DIR}"
# shellcheck disable=SC1091
source "${IDF_DIR}/export.sh" >/dev/null

# --- 3) 빌드 ------------------------------------------------------------------
cd "${FW_DIR}"
echo "[2/3] idf.py 빌드 (첫 빌드는 수 분 소요)"
idf.py set-target esp32s3
idf.py build

# --- 4) 병합 바이너리 생성 ----------------------------------------------------
# ESP-IDF 5.3+ 의 idf.py merge-bin 사용. flash_args 를 자동 반영해 0x0 기준 단일
# 이미지를 만든다.
echo "[3/3] 병합 바이너리 생성: ${MERGED_BIN}"
idf.py merge-bin -o "${MERGED_BIN}"

echo
echo "=============================================="
echo " 완료: ${MERGED_BIN}"
echo
echo " 이제 진단 도구로 PSRAM/WiFi/LED/버튼까지 검사:"
echo "     source ${REPO_DIR}/venv/bin/activate"
echo "     python tools/board_check/main.py --firmware"
echo "=============================================="
