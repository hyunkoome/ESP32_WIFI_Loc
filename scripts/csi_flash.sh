#!/usr/bin/env bash
#
# csi_flash.sh  —  CSI 펌웨어 빌드 + (선택) flash
# ===============================================
# role 펌웨어를 빌드하고 merge-bin 으로 단일 이미지를 만든 뒤, --port 가 주어지면
# 그 포트에 flash 한다. config_devices.yaml 의존 없음 — 보드 선택은 호스트(웹/GUI)의
# 실시간 감지가 담당하고, 이 스크립트는 "role 1개"를 빌드/flash 하는 단위 작업이다.
#   - role: tx  → csi/firmware/csi_send
#   - role: rx  → csi/firmware/csi_recv
#
# 빌드(느림, ESP-IDF 필요)와 flash(빠름, venv esptool)를 분리한다. 호스트의
# csi/common/flasher.py 는 보통 '--build-only' 로 빌드만 시키고 flash 는 esptool 로
# 직접 한다(여러 보드에 빠르게). 아래는 사람이 직접 쓸 때의 편의 인터페이스다.
#
# 사용:
#   bash scripts/csi_flash.sh --role rx --build-only            # 빌드 + merge-bin 만
#   bash scripts/csi_flash.sh --role rx --port /dev/ttyACM0     # 빌드 + flash
#   bash scripts/csi_flash.sh --role tx --port /dev/ttyACM1 --no-build  # flash 만
#   bash scripts/csi_flash.sh --role rx --port /dev/ttyACM0 --clean     # 클린 빌드 + flash
#
# 산출물: csi/firmware/<fw>/build/<role>_merged.bin  (0x0 기준 단일 이미지)
#
# 환경변수:
#   IDF_DIR    ESP-IDF 설치 경로(기본 ~/esp/esp-idf)
#   FLASH_BAUD esptool 통신 보드레이트(기본 460800)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
IDF_DIR="${IDF_DIR:-$HOME/esp/esp-idf}"
FLASH_BAUD="${FLASH_BAUD:-460800}"

# role → 펌웨어 디렉터리명
#   tx=ESP-NOW 송신, rx=통합 수신(ESP-NOW tx + 라우터). 라우터 자격증명은 빌드에 박지
#   않고 호스트가 런타임에 'WIFI_CONNECT' 시리얼 명령으로 주입한다(board_check 패턴).
declare -A ROLE_FW=( [tx]="csi_send" [rx]="csi_recv" )

# --- 인자 파싱 ---------------------------------------------------------------
ROLE=""
PORT=""
NO_BUILD=0
BUILD_ONLY=0
CLEAN=0
while [ $# -gt 0 ]; do
    case "$1" in
        --role)       ROLE="${2:-}"; shift 2 ;;
        --port)       PORT="${2:-}"; shift 2 ;;
        --no-build)   NO_BUILD=1; shift ;;
        --build-only) BUILD_ONLY=1; shift ;;
        --clean)      CLEAN=1; shift ;;
        -h|--help)    sed -n '2,33p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
    esac
done

if [ -z "${ROLE}" ] || [ -z "${ROLE_FW[$ROLE]:-}" ]; then
    echo "사용법: --role <tx|rx> [--port DEV] [--build-only|--no-build] [--clean]" >&2
    exit 2
fi
# flash(빌드 산출물 사용)를 하려면 포트가 필요하다. 빌드만 할 거면 --build-only.
if [ "${BUILD_ONLY}" -eq 0 ] && [ -z "${PORT}" ]; then
    echo "[에러] flash 하려면 --port 가 필요합니다(또는 빌드만 하려면 --build-only)." >&2
    exit 2
fi

FW="${ROLE_FW[$ROLE]}"
FW_DIR="${REPO_DIR}/csi/firmware/${FW}"
MERGED_BIN="${FW_DIR}/build/${ROLE}_merged.bin"

# --- 빌드 단계 (--no-build 가 아니면) ----------------------------------------
if [ "${NO_BUILD}" -eq 0 ]; then
    # 활성 venv 해제 (ESP-IDF 가 자체 Python 환경을 쓰므로 충돌 방지)
    if [ -n "${VIRTUAL_ENV:-}" ]; then
        echo "[알림] 활성 Python venv 해제: ${VIRTUAL_ENV}"
        venv_bin="${VIRTUAL_ENV}/bin"; new_path=""
        IFS=':' read -ra _parts <<< "${PATH}"
        for p in "${_parts[@]}"; do
            [ "${p}" = "${venv_bin}" ] && continue
            new_path="${new_path:+${new_path}:}${p}"
        done
        export PATH="${new_path}"; unset VIRTUAL_ENV
    fi

    if [ ! -f "${IDF_DIR}/export.sh" ]; then
        echo "[0] ESP-IDF 미설치 — 설치를 시작합니다(수 분 소요): ${IDF_DIR}"
        bash "${SCRIPT_DIR}/install_esp_idf.sh"
    fi
    echo "[1] ESP-IDF 환경 활성화: ${IDF_DIR}"
    # shellcheck disable=SC1091
    source "${IDF_DIR}/export.sh" >/dev/null

    cd "${FW_DIR}"
    if [ "${CLEAN}" -eq 1 ]; then
        echo "[build] 클린 빌드 (build/ 삭제)"
        rm -rf "${FW_DIR}/build"
        # 삭제가 실제로 됐는지 검증(권한 문제로 일부가 남으면 클린 빌드가 깨짐).
        if [ -e "${FW_DIR}/build" ]; then
            echo "[에러] '${FW_DIR}/build' 삭제 실패 — 폴더가 아직 남아 있습니다." >&2
            echo "       확인: ls -ld '${FW_DIR}/build'  /  필요 시: sudo rm -rf '${FW_DIR}/build'" >&2
            exit 1
        fi
        echo "[build] ✓ build/ 삭제 확인 — 처음부터 새로 빌드합니다."
    fi
    echo "[build] role=${ROLE} (${FW}) 빌드"
    idf.py set-target esp32s3
    idf.py build
    # 부트로더+파티션+앱을 0x0 기준 단일 이미지로 병합(esptool flash 단순화).
    echo "[build] merge-bin → ${MERGED_BIN}"
    idf.py merge-bin -o "${MERGED_BIN}"
fi

# --- flash 단계 --------------------------------------------------------------
if [ "${BUILD_ONLY}" -eq 1 ]; then
    echo "[done] 빌드만 수행. 산출물: ${MERGED_BIN}"
    exit 0
fi
if [ -z "${PORT}" ]; then
    echo "[done] --port 미지정 — flash 생략. 산출물: ${MERGED_BIN}"
    exit 0
fi
if [ ! -f "${MERGED_BIN}" ]; then
    echo "[에러] 병합 바이너리가 없습니다: ${MERGED_BIN}" >&2
    echo "       먼저 빌드하세요: bash scripts/csi_flash.sh --role ${ROLE} --build-only" >&2
    exit 1
fi

# flash 는 ESP-IDF 가 아니라 venv 의 esptool 로 한다(빌드와 분리, 빠름).
VENV_PY="${REPO_DIR}/venv/bin/python"
[ -x "${VENV_PY}" ] || VENV_PY="python3"
echo "[flash] role=${ROLE} → ${PORT} (esptool, baud=${FLASH_BAUD})"
"${VENV_PY}" -m esptool --chip esp32s3 -p "${PORT}" -b "${FLASH_BAUD}" \
    --before default_reset --after hard_reset write_flash 0x0 "${MERGED_BIN}"
echo
echo "=============================================="
echo " 완료: role=${ROLE} → ${PORT}"
echo " 부팅 후 호스트가 DEVICE_ROLE 로 자동 감지합니다."
echo "=============================================="
