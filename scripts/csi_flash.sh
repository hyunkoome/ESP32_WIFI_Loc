#!/usr/bin/env bash
#
# csi_flash.sh  —  CSI 펌웨어 빌드 + 다운로드(flash)
# =====================================================
# config_devices.yaml 의 tx/rx 매핑을 읽어, 각 보드에 역할에 맞는 펌웨어를 flash 한다.
#   - role: tx  → csi/firmware/csi_send
#   - role: rx  → csi/firmware/csi_recv
#
# 보드는 by-id 의 USB serial 로 고정 식별하므로 ttyACM 번호가 바뀌어도 안전하다
# (해석은 csi/collect/device_map.py 가 담당).
#
# 흐름:
#   0) ESP-IDF 설치 확인 (없으면 scripts/install_esp_idf.sh)
#   1) (venv python 으로) config_devices.yaml → 연결된 디바이스 목록 해석
#   2) 활성 venv 해제 → ESP-IDF export.sh 활성화
#   3) role 별 펌웨어 빌드(1회) → 해당 role 의 각 보드 포트에 flash
#
# 사용:
#   bash scripts/csi_flash.sh                # tx, rx 모두 빌드+flash
#   bash scripts/csi_flash.sh --role rx      # rx(csi_recv) 만
#   bash scripts/csi_flash.sh --role tx      # tx(csi_send) 만
#   bash scripts/csi_flash.sh --no-build     # 빌드 생략, flash 만
#   bash scripts/csi_flash.sh --clean        # build/ 삭제 후 클린 빌드
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
VENV_PY="${REPO_DIR}/venv/bin/python"
DEVICE_MAP="${REPO_DIR}/csi/collect/device_map.py"

# role → 펌웨어 디렉터리명 (device_map.py 의 ROLE_FIRMWARE 와 일치해야 함)
declare -A ROLE_FW=( [tx]="csi_send" [rx]="csi_recv" )

# --- 인자 파싱 ---------------------------------------------------------------
ROLE_FILTER=""
NO_BUILD=0
CLEAN=0
while [ $# -gt 0 ]; do
    case "$1" in
        --role)    ROLE_FILTER="${2:-}"; shift 2 ;;
        --no-build) NO_BUILD=1; shift ;;
        --clean)   CLEAN=1; shift ;;
        -h|--help)
            sed -n '2,30p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
    esac
done

if [ -n "${ROLE_FILTER}" ] && [ -z "${ROLE_FW[$ROLE_FILTER]:-}" ]; then
    echo "잘못된 --role 값: ${ROLE_FILTER} (tx 또는 rx)" >&2
    exit 2
fi

# --- 1) 연결된 디바이스 목록 해석 (venv python, ESP-IDF 활성화 전에) ----------
if [ ! -x "${VENV_PY}" ]; then
    echo "venv 가 없습니다: ${VENV_PY}" >&2
    echo "  python -m venv venv && source venv/bin/activate && pip install pyyaml" >&2
    exit 1
fi

get_devices() {
    # 인자: role(선택). 출력: "role<TAB>port<TAB>name<TAB>serial" (연결된 것만)
    local role="$1"
    if [ -n "${role}" ]; then
        "${VENV_PY}" "${DEVICE_MAP}" --role "${role}" --connected-only --shell
    else
        "${VENV_PY}" "${DEVICE_MAP}" --connected-only --shell
    fi
}

echo "[1/3] config_devices.yaml → 연결된 디바이스:"
"${VENV_PY}" "${DEVICE_MAP}" ${ROLE_FILTER:+--role "${ROLE_FILTER}"} || true
echo

# 처리할 role 목록 결정
if [ -n "${ROLE_FILTER}" ]; then
    ROLES=("${ROLE_FILTER}")
else
    ROLES=(rx tx)
fi

# --- 2) ESP-IDF 환경 준비 ----------------------------------------------------
# 활성 venv 해제 (ESP-IDF 가 자체 Python 을 쓰므로 충돌 방지)
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

if [ ! -f "${IDF_DIR}/export.sh" ]; then
    echo "[0/3] ESP-IDF 미설치 — 설치를 시작합니다(수 분 소요): ${IDF_DIR}"
    bash "${SCRIPT_DIR}/install_esp_idf.sh"
fi
echo "[2/3] ESP-IDF 환경 활성화: ${IDF_DIR}"
# shellcheck disable=SC1091
source "${IDF_DIR}/export.sh" >/dev/null

# --- 3) role 별 빌드 + flash --------------------------------------------------
flashed_any=0
for role in "${ROLES[@]}"; do
    fw="${ROLE_FW[$role]}"
    devices="$(get_devices "${role}")"
    if [ -z "${devices}" ]; then
        echo "[skip] role=${role} (${fw}) — 연결된 보드 없음"
        continue
    fi

    fw_dir="${REPO_DIR}/csi/firmware/${fw}"
    echo
    echo "==== role=${role} → ${fw} ===="
    cd "${fw_dir}"

    if [ "${NO_BUILD}" -eq 0 ]; then
        if [ "${CLEAN}" -eq 1 ]; then
            echo "[build] 클린 빌드 (build/ 삭제)"
            rm -rf "${fw_dir}/build"
            # 삭제가 실제로 됐는지 검증(권한 문제로 일부가 남으면 클린 빌드가
            # 깨지므로 넘어가지 말고 멈춘다 — 예전 sudo 빌드 잔재 등).
            if [ -e "${fw_dir}/build" ]; then
                echo "[에러] '${fw_dir}/build' 삭제 실패 — 폴더가 아직 남아 있습니다." >&2
                echo "       소유권/권한 확인: ls -ld '${fw_dir}/build'" >&2
                echo "       필요 시: sudo rm -rf '${fw_dir}/build'" >&2
                exit 1
            fi
            echo "[build] ✓ build/ 삭제 확인 — 처음부터 새로 빌드합니다."
        fi
        idf.py set-target esp32s3
        idf.py build
    fi

    # 같은 펌웨어를 이 role 의 모든 보드에 flash (빌드 산출물 재사용)
    while IFS=$'\t' read -r r port name serial; do
        [ -z "${port}" ] && continue
        echo "[flash] ${name} (serial=${serial}) → ${port}"
        idf.py -p "${port}" -b "${FLASH_BAUD}" flash
        flashed_any=1
    done <<< "${devices}"
done

echo
if [ "${flashed_any}" -eq 1 ]; then
    echo "=============================================="
    echo " 완료. CSI 수집을 시작하려면:"
    echo "     source ${REPO_DIR}/venv/bin/activate"
    echo "     python csi/collect/serial_collector.py --role rx --out results/csi_run01.csv"
    echo "=============================================="
else
    echo "flash 한 보드가 없습니다. config_devices.yaml 의 serial 과 연결 상태를 확인하세요."
fi
