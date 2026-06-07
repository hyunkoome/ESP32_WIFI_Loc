#!/usr/bin/env bash
#
# install_esp_idf.sh
# ==================
# ESP32-S3 펌웨어 빌드에 필요한 ESP-IDF(C SDK)를 설치한다.
#
#   - 클론 위치: ~/esp/esp-idf  (IDF_DIR 환경변수로 변경 가능)
#   - 버전     : v5.4           (IDF_VERSION 환경변수로 변경 가능)
#   - 대상 칩  : esp32s3        (IDF_TARGET 환경변수로 변경 가능)
#
# 멱등성: 이미 클론돼 있으면 다시 받지 않고, toolchain 설치만 다시 수행한다.
# install.sh 가 다운로드하는 Xtensa toolchain/Python 가상환경은 ~/.espressif 에
# 저장된다(저장소 밖이라 commit 영향 없음).
#
# 사용:
#   bash scripts/install_esp_idf.sh
#   IDF_VERSION=v5.4 bash scripts/install_esp_idf.sh   # 버전 지정 예
#
# 설치 후 매 터미널에서 아래로 환경을 활성화해야 한다(IDF_PATH 설정):
#   source ~/esp/esp-idf/export.sh
#
set -euo pipefail

IDF_VERSION="${IDF_VERSION:-v5.4}"
IDF_DIR="${IDF_DIR:-$HOME/esp/esp-idf}"
IDF_TARGET="${IDF_TARGET:-esp32s3}"

# ESP-IDF install.sh 는 자체 Python venv 를 새로 만든다. 외부 venv(예: 이 프로젝트의
# venv/)가 활성화된 상태면 "can not create a virtual environment again" 에러가 나므로,
# 활성 venv 의 흔적(VIRTUAL_ENV 변수 + PATH 의 venv/bin)을 제거한다.
if [ -n "${VIRTUAL_ENV:-}" ]; then
    echo "[알림] 활성 Python venv 해제: ${VIRTUAL_ENV} (ESP-IDF 설치를 위해)"
    venv_bin="${VIRTUAL_ENV}/bin"
    # PATH 에서 venv/bin 토큰만 제거.
    new_path=""
    IFS=':' read -ra _parts <<< "${PATH}"
    for p in "${_parts[@]}"; do
        [ "${p}" = "${venv_bin}" ] && continue
        new_path="${new_path:+${new_path}:}${p}"
    done
    export PATH="${new_path}"
    unset VIRTUAL_ENV
fi

echo "=============================================="
echo " ESP-IDF 설치"
echo "   버전 : ${IDF_VERSION}"
echo "   위치 : ${IDF_DIR}"
echo "   대상 : ${IDF_TARGET}"
echo "=============================================="

# --- 사전 의존성 안내(설치는 sudo 필요하므로 자동 실행하지 않음) ---------------
# ESP-IDF 빌드에는 git, cmake, ninja, python3 등이 필요하다. 없으면 아래 한 줄로:
#   sudo apt update && sudo apt install -y git wget flex bison gperf \
#     python3 python3-pip python3-venv cmake ninja-build ccache \
#     libffi-dev libssl-dev dfu-util libusb-1.0-0
missing=()
for bin in git cmake python3; do
    command -v "$bin" >/dev/null 2>&1 || missing+=("$bin")
done
if [ "${#missing[@]}" -gt 0 ]; then
    echo "[경고] 다음 필수 명령이 없습니다: ${missing[*]}"
    echo "       먼저 아래를 실행하세요(관리자 권한 필요):"
    echo "         sudo apt update && sudo apt install -y git wget flex bison gperf \\"
    echo "           python3 python3-pip python3-venv cmake ninja-build ccache \\"
    echo "           libffi-dev libssl-dev dfu-util libusb-1.0-0"
    exit 1
fi

# --- 1) 소스 클론(없을 때만) -------------------------------------------------
# --depth 1 + --shallow-submodules 로 다운로드 용량/시간을 크게 줄인다.
if [ -d "${IDF_DIR}/.git" ]; then
    echo "[1/2] 이미 클론돼 있음 — 건너뜀: ${IDF_DIR}"
else
    echo "[1/2] ESP-IDF ${IDF_VERSION} 클론 중... (수 분 소요)"
    mkdir -p "$(dirname "${IDF_DIR}")"
    git clone -b "${IDF_VERSION}" --depth 1 --recursive --shallow-submodules \
        https://github.com/espressif/esp-idf.git "${IDF_DIR}"
fi

# --- 2) toolchain / Python 환경 설치 -----------------------------------------
# install.sh 는 Xtensa 컴파일러와 ESP-IDF 전용 Python venv 를 ~/.espressif 에
# 내려받는다. 여러 번 실행해도 안전(이미 받은 건 건너뜀).
echo "[2/2] toolchain 설치 중... (수 분 소요)"
"${IDF_DIR}/install.sh" "${IDF_TARGET}"

echo
echo "=============================================="
echo " 설치 완료!"
echo
echo " 새 터미널마다 아래로 환경을 활성화하세요:"
echo "     source ${IDF_DIR}/export.sh"
echo
echo " 확인:"
echo "     idf.py --version"
echo "=============================================="
