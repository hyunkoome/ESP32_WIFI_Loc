# CSI 송신 펌웨어 최상위 CMakeLists.
# 출처: espressif/esp-csi examples/get-started/csi_send (Apache-2.0)
# 변경점: esp-csi monorepo 가정(git_describe / 디렉터리명에서 project 명 추출)을
#         제거하고, 독립 ESP-IDF 프로젝트 + CI 빌드가 가능하도록 단순화했다.
#         project 명을 csi_send 로 고정.
# 빌드:  idf.py set-target esp32s3 && idf.py build
cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(csi_send)
