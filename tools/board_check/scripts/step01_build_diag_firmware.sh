#!/usr/bin/env bash
#
# step01_build_diag_firmware.sh  —  [1단계] 펌웨어 준비(빌드)
# ===========================================================
# 보드 진단 펌웨어(tools/board_check/firmware)를 빌드하고, esptool로 한 번에 flash
# 가능한 병합 바이너리(build/diag_merged.bin)를 생성한다.
#
# 이 단계는 보통 "한 번만" 실행하면 된다(펌웨어 소스를 고치면 다시 실행).
# 실제 보드 검사는 [2단계] tools/board_check/scripts/step02_run_cli_based_diagnostics.sh 로 한다.
#
#   0) ESP-IDF 설치 확인 — 없으면 scripts/install_esp_idf.sh 로 자동 설치
#   1) (필요 시) 활성 venv 해제 — ESP-IDF 환경과 충돌 방지
#   2) ESP-IDF 환경 활성화 (export.sh)
#   3) idf.py set-target esp32s3 && idf.py build
#   4) idf.py merge-bin 으로 부트로더+파티션+앱을 0x0 기준 단일 bin 으로 병합
#
# 생성물: tools/board_check/firmware/build/diag_merged.bin
#         (= config.FIRMWARE_BIN, main.py --firmware 가 이 파일을 flash)
#
# 사용:
#   bash tools/board_check/scripts/step01_build_diag_firmware.sh
#
# 환경변수:
#   IDF_DIR  ESP-IDF 설치 경로(기본 ~/esp/esp-idf)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 이 스크립트는 tools/board_check/scripts/ 에 있다.
#   SCRIPT_DIR/..        == tools/board_check  (BC_DIR)
#   SCRIPT_DIR/../../..  == 저장소 루트        (REPO_DIR)
BC_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FW_DIR="${BC_DIR}/firmware"
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

# --- 0) ESP-IDF 설치 확인 (없으면 자동 설치) ---------------------------------
if [ ! -f "${IDF_DIR}/export.sh" ]; then
    echo "[0/3] ESP-IDF 미설치 — 설치를 시작합니다(수 분 소요): ${IDF_DIR}"
    bash "${REPO_DIR}/scripts/install_esp_idf.sh"
fi

# --- 2) ESP-IDF 환경 활성화 --------------------------------------------------
echo "[1/3] ESP-IDF 환경 활성화: ${IDF_DIR}"
# shellcheck disable=SC1091
source "${IDF_DIR}/export.sh" >/dev/null

# 참고: WiFi 접속 테스트 자격증명은 더 이상 빌드 시 펌웨어에 주입하지 않는다.
# 진단 실행 시점에 호스트(main.py / 웹)가 config/wifi_config.yaml 을 읽어 시리얼 'WIFI_CONNECT'
# 명령으로 런타임 주입한다. 따라서 config/wifi_config.yaml 만 바꿔도 재빌드가 필요 없다.

# --- 3) 빌드 ------------------------------------------------------------------
cd "${FW_DIR}"
# 항상 "완전" 클린 빌드한다: 빌드 폴더(build/)와 자동 복원되는 managed_components/ 를
# 물리적으로 삭제한 뒤 처음부터 다시 빌드한다. 캐시/구버전 컴포넌트로 인한 미묘한
# 빌드 오염을 원천 차단한다. 매번 첫 빌드처럼 수 분 소요되지만 재현성/안정성을 우선.
#   - build/             : idf.py build 산출물(부트로더/앱/오브젝트 캐시 등)
#   - managed_components/: idf_component.yml + dependencies.lock 으로 다시 다운로드됨
echo "[2/3] 완전 클린 빌드 (build/ 삭제 후 처음부터, 수 분 소요)"
rm -rf "${FW_DIR}/build" "${FW_DIR}/managed_components"
# 삭제가 실제로 됐는지 검증한다. 권한 문제(예: 예전에 sudo 로 빌드해 build/ 안에
# root 소유 파일이 남은 경우)로 일부가 안 지워지면 클린 빌드가 깨져 캐시 오염이
# 그대로 남으므로, 넘어가지 말고 여기서 분명히 멈춘다.
for _d in build managed_components; do
    if [ -e "${FW_DIR}/${_d}" ]; then
        echo "[에러] '${FW_DIR}/${_d}' 삭제 실패 — 폴더가 아직 남아 있습니다." >&2
        echo "       소유권/권한을 확인하세요(예전 sudo 빌드 잔재일 수 있음):" >&2
        echo "         ls -ld '${FW_DIR}/${_d}'" >&2
        echo "         sudo rm -rf '${FW_DIR}/${_d}'   # 필요 시" >&2
        exit 1
    fi
done
echo "      ✓ build/ · managed_components/ 삭제 확인 — 처음부터 새로 빌드합니다."
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
