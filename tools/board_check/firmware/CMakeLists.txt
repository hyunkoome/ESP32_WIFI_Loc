# ESP32-S3 진단 펌웨어 프로젝트 최상위 CMakeLists.
# 빌드:  idf.py set-target esp32s3 && idf.py build
cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32s3_diag)
