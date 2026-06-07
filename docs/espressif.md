# Espressif 생태계 가이드

이 프로젝트가 쓰는 칩(ESP32-S3)과 도구(ESP-IDF, esptool)는 모두 **Espressif**
에서 나옵니다. 이 문서는 Espressif 가 무엇이고, GitHub
([github.com/espressif](https://github.com/espressif))의 **공개 저장소 317개 전부**를
**우리 프로젝트(ESP32-S3 WiFi CSI 센싱)와의 관련도** 기준으로 ★5(최우선)~★1(무관)
까지 우선순위를 매겨 정리합니다.

> 데이터 기준: GitHub API 로 조회한 espressif 조직 공개 저장소 **317개**
> (활성 288 + `archived` 29). ⭐ 는 GitHub 스타 수. 각 tier 안에서는 스타 내림차순.

---

## Espressif 란

**Espressif Systems(乐鑫科技, 상하이)** 는 저전력 WiFi/BLE SoC 를 만드는
반도체 회사입니다. 대표 제품군:

| 칩 | 특징 | 비고 |
|----|------|------|
| ESP8266 | WiFi 단독, 단일코어 | 1세대, 레거시 |
| ESP32 | WiFi + BT classic/BLE, Xtensa 듀얼코어 | 가장 널리 쓰임 |
| **ESP32-S3** | WiFi + BLE5, Xtensa LX7 듀얼코어, AI 가속(벡터 명령) | **본 프로젝트 보드(N16R8)** |
| ESP32-C 시리즈 | RISC-V 코어 (C3/C6 등) | C6 는 WiFi6/Thread |
| ESP32-H/P 시리즈 | H=802.15.4(Thread/Zigbee), P=고성능 MCU | |

GitHub 계정은 이 칩들을 위한 **공식 SDK·툴·예제의 본진**입니다. 거의 모든
저장소가 오픈소스(주로 Apache-2.0)입니다.

> ⚠️ 라이선스 주의: 본 저장소는 **AGPL v3** 입니다. Espressif 코드(Apache-2.0)를
> 가져다 쓸 때는 호환성에 유의하세요. Apache-2.0 → AGPL-3.0 결합은 일반적으로
> 가능하지만, 반대로 우리 코드를 가져가는 쪽은 AGPL 의무를 따라야 합니다.

---

## 우선순위 기준 (이 프로젝트 관점)

| 별점 | 의미 | 개수 |
|------|------|------|
| ★★★★★ | 지금 이미 쓰거나 Phase 2(CSI 수집)에 **필수** | 3 |
| ★★★★ | CSI 수집·신호처리·학습·개발 도구로 **직접** 도움 | 10 |
| ★★★ | WiFi/네트워킹·멀티보드·플래시/디버그·보드/빌드 도구 등 **간접** 관련 | 69 |
| ★★ | ESP32 생태계 일반(타 프로토콜·클라우드·멀티미디어·음성/비전 AI 등). 우리와 약함 | 77 |
| ★ | 거의 무관(데모/게임/툴체인 내부 포크/구형 ESP8266/내부 CI 등) | 158 |

> ⚠️ 별점은 **"이 CSI 센싱 프로젝트에 얼마나 직접 쓰이느냐"** 기준의 주관적
> 관련도이며, 저장소의 품질/중요도와는 무관합니다. (예: `arduino-esp32` 는
> 스타 1.6만이지만 우리는 ESP-IDF 를 쓰므로 ★3.)

---

## ★★★★★ — 최우선 (지금/Phase 2 필수)

| 왜 중요한가 |
|---|
| **esp-idf**: 진단·CSI 펌웨어를 빌드하는 공식 SDK. 이미 [`install_esp_idf.sh`](../scripts/install_esp_idf.sh) 로 사용 중. |
| **esptool**: 칩에 펌웨어 flash + 칩/Flash 정보 조회. 진단 도구 핵심 의존성([`requirements.txt`](../tools/board_check/requirements.txt)). |
| **esp-csi**: WiFi CSI 수집/응용 예제 — **Phase 2 의 출발점**. presence/motion/위치추정. |

- [esp-idf](https://github.com/espressif/esp-idf) ⭐18247 — Espressif IoT Development Framework. Official development framework for Espressif SoCs.
- [esptool](https://github.com/espressif/esptool) ⭐6364 — Serial utility for flashing, provisioning, and interacting with Espressif SoCs
- [esp-csi](https://github.com/espressif/esp-csi) ⭐1367 — Applications based on Wi-Fi CSI (Channel state information), such as indoor positioning, human detection

---

## ★★★★ — 직접 도움 (CSI 수집·신호처리·학습·개발)

CSI 신호처리(FFT/DSP), 온디바이스 추론(DL/NN/TFLite), 펌웨어 테스트, WiFi 스택,
웹/호스트 기반 플래시 등 다음 단계에 바로 닿는 것들.

- [vscode-esp-idf-extension](https://github.com/espressif/vscode-esp-idf-extension) ⭐1429 — Visual Studio Code extension for ESP-IDF projects
- [esp-dl](https://github.com/espressif/esp-dl) ⭐1035 — Espressif deep-learning library for AIoT applications
- [esp-dsp](https://github.com/espressif/esp-dsp) ⭐676 — DSP library for ESP-IDF
- [esp-tflite-micro](https://github.com/espressif/esp-tflite-micro) ⭐647 — TensorFlow Lite Micro for Espressif Chipsets
- [esp-serial-flasher](https://github.com/espressif/esp-serial-flasher) ⭐542 — Library for flashing Espressif SoCs from other MCUs.
- [esptool-js](https://github.com/espressif/esptool-js) ⭐496 — Javascript implementation of flasher tool for Espressif chips, running in web browser using WebSerial.
- [esp-nn](https://github.com/espressif/esp-nn) ⭐231 — Optimised Neural Network functions for Espressif chipsets
- [esp32-wifi-lib](https://github.com/espressif/esp32-wifi-lib) ⭐198 — ESP32 WiFi stack precompiled libraries
- [pytest-embedded](https://github.com/espressif/pytest-embedded) ⭐141 — A pytest plugin that designed for embedded testing
- [esp-launchpad](https://github.com/espressif/esp-launchpad) ⭐82 — Configurable Browser-based Image Flasher

---

## ★★★ — 간접 관련 (WiFi/네트워킹·멀티보드·플래시/디버그·보드·빌드 도구)

WiFi 스택/PHY/coexistence, host-MCU 통신(멀티보드 수집), 네트워킹(데이터 전송),
JTAG/디버그, 개발보드 BSP/회로, ESP-IDF 부속 빌드·설치 도구 등.

- [arduino-esp32](https://github.com/espressif/arduino-esp32) ⭐16893 — Arduino core for the ESP32 family of SoCs
- [esp-iot-solution](https://github.com/espressif/esp-iot-solution) ⭐2593 — Espressif IoT Library. IoT Device Drivers, Documentations and Solutions.
- [kicad-libraries](https://github.com/espressif/kicad-libraries) ⭐1268 — KiCad libraries for Espressif SoCs, modules, and DevKits.
- [esp-hosted](https://github.com/espressif/esp-hosted) ⭐999 — Hosted Solution (Linux/MCU) with ESP32 (Wi-Fi + BT + BLE)
- [esp-now](https://github.com/espressif/esp-now) ⭐753 — A connectionless Wi-Fi communication protocol
- [esp-mqtt](https://github.com/espressif/esp-mqtt) ⭐731 — ESP32 mqtt component
- [esp-dev-kits](https://github.com/espressif/esp-dev-kits) ⭐584 — Docs, Schematics, Factory Firmwares for ESP Development Kits
- [rust-esp32-example](https://github.com/espressif/rust-esp32-example) ⭐498 — Example of Rust integration into an ESP-IDF project, for ESP32 series of chips
- [openocd-esp32](https://github.com/espressif/openocd-esp32) ⭐450 — OpenOCD branch with ESP32 JTAG support
- [esp-bsp](https://github.com/espressif/esp-bsp) ⭐424 — Board support components for Espressif development boards
- [esp-usb-bridge](https://github.com/espressif/esp-usb-bridge) ⭐389 — USB to UART&JTAG bridge, implemented on ESP32-S2 or ESP32-S3
- [idf-eclipse-plugin](https://github.com/espressif/idf-eclipse-plugin) ⭐367 — Espressif-IDE (ESP-IDF Eclipse Plugin) for ESP-IDF CMake based projects 5.x and above
- [esp-protocols](https://github.com/espressif/esp-protocols) ⭐289 — Collection of ESP-IDF components related to networking protocols
- [esp32-arduino-lib-builder](https://github.com/espressif/esp32-arduino-lib-builder) ⭐199 — (설명 없음)
- [esp-gdbstub](https://github.com/espressif/esp-gdbstub) ⭐166 — (설명 없음)
- [esp-insights](https://github.com/espressif/esp-insights) ⭐142 — ESP Insights: A remote diagnostics/observability framework for connected devices
- [esp-hosted-mcu](https://github.com/espressif/esp-hosted-mcu) ⭐134 — (설명 없음)
- [idf-installer](https://github.com/espressif/idf-installer) ⭐124 — ESP IDF Windows Installer
- [esp-idf-cxx](https://github.com/espressif/esp-idf-cxx) ⭐104 — C++ wrapper classes for ESP-IDF components.
- [esp-idf-ci-action](https://github.com/espressif/esp-idf-ci-action) ⭐104 — GitHub Action for ESP32 CI
- [idf-im-ui](https://github.com/espressif/idf-im-ui) ⭐78 — EIM GUI: Cross-Platform ESP-IDF Installation Manager
- [freertos-gdb](https://github.com/espressif/freertos-gdb) ⭐68 — Python module for operating with freeRTOS kernel objects in GDB
- [esp-usb](https://github.com/espressif/esp-usb) ⭐63 — (설명 없음)
- [idf-component-manager](https://github.com/espressif/idf-component-manager) ⭐62 — Tool for installing ESP-IDF components
- [esp-eth-drivers](https://github.com/espressif/esp-eth-drivers) ⭐56 — Collection of additional Ethernet drivers for ESP-IDF
- [esp-idf-monitor](https://github.com/espressif/esp-idf-monitor) ⭐46 — (설명 없음)
- [idf-env](https://github.com/espressif/idf-env) ⭐37 — idf-env tool helps set up and manage ESP-IDF installations
- [esp-debug-adapter](https://github.com/espressif/esp-debug-adapter) ⭐32 — An implementation of Microsoft Debug Adapter Protocol server which works with GDB.
- [idf-build-apps](https://github.com/espressif/idf-build-apps) ⭐29 — Tool to build multiple IDF applications in CI
- [esp-wireless-drivers-3rdparty](https://github.com/espressif/esp-wireless-drivers-3rdparty) ⭐28 — Wi-Fi and BT drivers packaged for integration into 3rd party repositories. Work in progress.
- [esp-wifi-remote](https://github.com/espressif/esp-wifi-remote) ⭐27 — Allows WiFi-enabled ESP capabilities on remote targets (without native WiFi) using designated transports
- [idf-clion-plugin](https://github.com/espressif/idf-clion-plugin) ⭐24 — CLion plugin for ESP-IDF
- [esp-docs](https://github.com/espressif/esp-docs) ⭐24 — Python based wrapper for Sphinx, intended to simplify and extend Sphinx's functionality to better suit the documentation needs for Espressif's development frameworks
- [esp-idf-sbom](https://github.com/espressif/esp-idf-sbom) ⭐23 — ESP-IDF Software Bill of Materials Generation Tool
- [esp-amp](https://github.com/espressif/esp-amp) ⭐23 — ESP AMP
- [idf-web-ide](https://github.com/espressif/idf-web-ide) ⭐19 — cloud/ desktop IDE for ESP-IDF based on Eclipse Theia
- [idf-im-cli](https://github.com/espressif/idf-im-cli) ⭐19 `archived` — EIM CLI: Cross-Platform ESP-IDF Installation Manager
- [esp-coredump](https://github.com/espressif/esp-coredump) ⭐19 — (설명 없음)
- [esp32-arduino-libs](https://github.com/espressif/esp32-arduino-libs) ⭐15 — Holding precompiled ESP-IDF libraries for ESP32 Arduino v3.x and above
- [esp-phy-lib](https://github.com/espressif/esp-phy-lib) ⭐15 — Precompiled libraries for low-level RF functions in Espressif chips
- [esp-idf-size](https://github.com/espressif/esp-idf-size) ⭐15 — (설명 없음)
- [esp-idf-nvs-partition-gen](https://github.com/espressif/esp-idf-nvs-partition-gen) ⭐13 — NVS Partition Generator tool
- [idf-python-wheels](https://github.com/espressif/idf-python-wheels) ⭐12 — Build Python Wheels for Offline and Online installation of ESP-IDF. Online installation is using Espressif's PyPI
- [idf-ci](https://github.com/espressif/idf-ci) ⭐12 — A tool designed to streamline the CI/CD of ESP-IDF projects, with support for both GitLab CI/CD and GitHub Actions.
- [esp-prog-2](https://github.com/espressif/esp-prog-2) ⭐10 — (설명 없음)
- [esp-idf-kconfig](https://github.com/espressif/esp-idf-kconfig) ⭐9 — (설명 없음)
- [esp-hardware-design-guidelines](https://github.com/espressif/esp-hardware-design-guidelines) ⭐9 — Espressif Hardware Design Guidelines, which documents suggestions on how to integrate Espressif SoCs or modules into a product.
- [esp-extconn](https://github.com/espressif/esp-extconn) ⭐9 — (설명 없음)
- [idf-python](https://github.com/espressif/idf-python) ⭐8 — Project which packages a minimal self-contained Python distributions with pip and virtualenv included.
- [esptool-legacy-flasher-stub](https://github.com/espressif/esptool-legacy-flasher-stub) ⭐7 — (설명 없음)
- [esp-wifi-drv](https://github.com/espressif/esp-wifi-drv) ⭐7 — Linux Wi-Fi driver for ESP chips
- [esp-idf-panic-decoder](https://github.com/espressif/esp-idf-panic-decoder) ⭐7 — (설명 없음)
- [idf-im-lib](https://github.com/espressif/idf-im-lib) ⭐4 — ESP-IDF Installation Manager Libraries
- [esp-swift](https://github.com/espressif/esp-swift) ⭐4 — ESP-IDF component simplifying integration of code written in Swift 
- [esp-flasher-stub](https://github.com/espressif/esp-flasher-stub) ⭐4 — (설명 없음)
- [esp-debug-backend](https://github.com/espressif/esp-debug-backend) ⭐4 — Python debug backend.
- [esp-coex-lib](https://github.com/espressif/esp-coex-lib) ⭐4 — (설명 없음)
- [iperf-cmd](https://github.com/espressif/iperf-cmd) ⭐3 — ESP Component: iperf-cmd
- [esp-board-manager](https://github.com/espressif/esp-board-manager) ⭐3 — (설명 없음)
- [esp-sysview](https://github.com/espressif/esp-sysview) ⭐2 — ESP-IDF component for supporting SEGGER SystemView compatible tracing
- [esp-stub-lib](https://github.com/espressif/esp-stub-lib) ⭐2 — (설명 없음)
- [esp-self-reflasher](https://github.com/espressif/esp-self-reflasher) ⭐2 — Component/Application that enables full and unsafe reflash of Espressif Devices
- [esp-idf-diag](https://github.com/espressif/esp-idf-diag) ⭐2 — (설명 없음)
- [esp-flash-drivers](https://github.com/espressif/esp-flash-drivers) ⭐2 — Project to hold 3rd party flash drivers
- [idf-drivers-gdb](https://github.com/espressif/idf-drivers-gdb) ⭐1 — Python module for user-friendly view ESP-IDF driver objects in GDB
- [esp-test-tools](https://github.com/espressif/esp-test-tools) ⭐1 — This is the documentation for Espressif's ESP Test Tools repository, which provides comprehensive resources including RF testing tools and production guidelines to ensure that products built with Espressif chips meet performance and quality standards.
- [esp-gcov](https://github.com/espressif/esp-gcov) ⭐1 — ESP-IDF component for supporting code coverage collection
- [esp-pylib](https://github.com/espressif/esp-pylib) ⭐0 — Python library for logging, utils and constants for Espressif Systems' Python projects
- [esp-gpio-tool](https://github.com/espressif/esp-gpio-tool) ⭐0 — (설명 없음)

---

## ★★ — 생태계 일반 (우리와 약한 관련)

Thread/Zigbee/Matter, 클라우드(RainMaker/AWS/Azure/알리/바이두 등), 멀티미디어
(오디오/카메라/H264), 음성·비전 AI, Mesh, HomeKit, BT/BLE 스택, 보안/부트로더,
기타 SDK. ESP32 를 쓰지만 CSI 센싱과는 직접 관련이 적음.

- [esp32-camera](https://github.com/espressif/esp32-camera) ⭐2676 — (설명 없음)
- [esp-adf](https://github.com/espressif/esp-adf) ⭐2248 — Espressif Advanced Development Framework for Multimedia Applications
- [esp-who](https://github.com/espressif/esp-who) ⭐2083 — Face detection and recognition framework
- [esp-drone](https://github.com/espressif/esp-drone) ⭐1879 — Mini Drone/Quadcopter Firmware for ESP32 and ESP32-S Series SoCs.
- [esp-claw](https://github.com/espressif/esp-claw) ⭐1472 — ESP-Claw, a "Chat Coding" AI agent framework for IoT devices
- [esp-sr](https://github.com/espressif/esp-sr) ⭐1389 — Speech recognition
- [esp-box](https://github.com/espressif/esp-box) ⭐1254 — The ESP-BOX is a new generation AIoT development platform released by Espressif Systems.
- [esp-at](https://github.com/espressif/esp-at) ⭐1219 — AT application for ESP32/ESP32-C2/ESP32-C3/ESP32-C6/ESP8266
- [esp-matter](https://github.com/espressif/esp-matter) ⭐1022 — Espressif's SDK for Matter
- [esp-skainet](https://github.com/espressif/esp-skainet) ⭐873 — Espressif intelligent voice assistant
- [esp-mdf](https://github.com/espressif/esp-mdf) ⭐825 `archived` — Espressif Mesh Development Framework, limited maintain, recommend to use https://github.com/espressif/esp-mesh-lite
- [esp-brookesia](https://github.com/espressif/esp-brookesia) ⭐709 — ESP-Brookesia is a human-machine interaction development framework designed for AIoT devices.
- [esp-homekit-sdk](https://github.com/espressif/esp-homekit-sdk) ⭐656 — (설명 없음)
- [esp-apple-homekit-adk](https://github.com/espressif/esp-apple-homekit-adk) ⭐649 — This is a port for Apple's Open Source HomeKit ADK
- [esp-rainmaker](https://github.com/espressif/esp-rainmaker) ⭐609 — ESP RainMaker Agent for firmware development
- [esp-zigbee-sdk](https://github.com/espressif/esp-zigbee-sdk) ⭐369 — Espressif Zigbee SDK
- [esp-webrtc-solution](https://github.com/espressif/esp-webrtc-solution) ⭐355 — (설명 없음)
- [esp-aliyun](https://github.com/espressif/esp-aliyun) ⭐346 `archived` — Aliyun Iotkit-embedded, support esp32 & esp8266.
- [esp-aws-iot](https://github.com/espressif/esp-aws-iot) ⭐328 — AWS IoT SDK for ESP32 based chipsets
- [esp-va-sdk](https://github.com/espressif/esp-va-sdk) ⭐312 — Espressif's Voice Assistant SDK: Alexa, Google Voice Assistant, Google DialogFlow
- [esp-iot-bridge](https://github.com/espressif/esp-iot-bridge) ⭐227 — A smart bridge to make both ESP and the other MCU or smart device can access the Internet.
- [esp-thread-br](https://github.com/espressif/esp-thread-br) ⭐224 — Espressif Thread Border Router SDK
- [esp-jumpstart](https://github.com/espressif/esp-jumpstart) ⭐207 — Jumpstart from concept to production
- [esp-mesh-lite](https://github.com/espressif/esp-mesh-lite) ⭐206 — A lite version Wi-Fi Mesh, each node can access the network over the IP layer.
- [esp-modbus](https://github.com/espressif/esp-modbus) ⭐186 — ESP-Modbus - the officially suppported library for Modbus protocol (serial RS485 + TCP over WiFi or Ethernet).
- [esp-azure](https://github.com/espressif/esp-azure) ⭐185 — SDK to connect ESP8266 and ESP32 to Microsoft Azure IoT services
- [esp-google-iot](https://github.com/espressif/esp-google-iot) ⭐143 `archived` — Google Cloud IoT SDK as an ESP-IDF Component
- [esp-rainmaker-android](https://github.com/espressif/esp-rainmaker-android) ⭐141 — ESP RainMaker Android app sources
- [esp-detection](https://github.com/espressif/esp-detection) ⭐126 — Lightweight real-time object detection on ESP series chips, based on Ultralytics YOLOv11
- [esp-gmf](https://github.com/espressif/esp-gmf) ⭐113 — Espressif General Multimedia Framework (ESP-GMF)
- [esp-adf-libs](https://github.com/espressif/esp-adf-libs) ⭐111 — (설명 없음)
- [esp-nimble](https://github.com/espressif/esp-nimble) ⭐104 — A fork of NimBLE stack, for use with ESP32 and ESP-IDF
- [esp32-bt-lib](https://github.com/espressif/esp32-bt-lib) ⭐89 — ESP32 Bluetooth stack (below HCI layer) precompiled libraries
- [esp-ali-smartliving](https://github.com/espressif/esp-ali-smartliving) ⭐83 `archived` — 阿里云生活物联网平台 & 天猫精灵 IoT 开放平台
- [esp-qcloud](https://github.com/espressif/esp-qcloud) ⭐79 — 基于 ESP-IDF 原生开发接入腾讯 IoT Explorer，支持 ESP32/ESP32S2，快速实现腾讯连连控制。
- [esp-video-components](https://github.com/espressif/esp-video-components) ⭐77 — Collections of components to be used for camera related functionalities.
- [esp-moonlight](https://github.com/espressif/esp-moonlight) ⭐66 — (설명 없음)
- [esp-lowcode-matter](https://github.com/espressif/esp-lowcode-matter) ⭐66 — ESP LowCode: For Building Matter-enabled connected products
- [esp-rainmaker-ios](https://github.com/espressif/esp-rainmaker-ios) ⭐64 — ESP RainMaker iOS app sources
- [aws-iot-device-sdk-embedded-C](https://github.com/espressif/aws-iot-device-sdk-embedded-C) ⭐48 — SDK for connecting to AWS IoT from a device using embedded C (minor modifications for use with Espressif ESP-IDF)
- [esp-privilege-separation](https://github.com/espressif/esp-privilege-separation) ⭐47 — Espressif Privilege Separation Framework
- [esp-h264-component](https://github.com/espressif/esp-h264-component) ⭐41 — H264 encoder/decoder of espressif
- [connectedhomeip](https://github.com/espressif/connectedhomeip) ⭐41 — Matter (formerly Project CHIP) is creating more connections between more objects, simplifying development for manufacturers and increasing compatibility for consumers,  guided by the Connectivity Standards Alliance (formerly Zigbee Alliance).
- [esp-wolfssl](https://github.com/espressif/esp-wolfssl) ⭐40 — WolfSSL port for ESP-IDF & ESP8266_RTOS_SDK
- [esp-faq](https://github.com/espressif/esp-faq) ⭐40 — (설명 없음)
- [esp-cryptoauthlib](https://github.com/espressif/esp-cryptoauthlib) ⭐40 — Release only fork of https://github.com/MicrochipTech/cryptoauthlib
- [openthread](https://github.com/espressif/openthread) ⭐34 — Espressif fork of OpenThread project, used to maintain ESP-specific patches and release branches
- [esp-desktop-buddy](https://github.com/espressif/esp-desktop-buddy) ⭐30 — ESP Desktop Buddy SDK
- [esp-bootloader-plus](https://github.com/espressif/esp-bootloader-plus) ⭐30 — An enhanced bootloader to support compression upgrade and diff compression upgrade.
- [esp_secure_cert_mgr](https://github.com/espressif/esp_secure_cert_mgr) ⭐26 — Espressif Secure Certificate Manager Component
- [esp-zboss-lib](https://github.com/espressif/esp-zboss-lib) ⭐21 — (설명 없음)
- [esp32c3-bt-lib](https://github.com/espressif/esp32c3-bt-lib) ⭐20 — ESP32-C3/S3 Bluetooth stack (below HCI layer) precompiled libraries
- [esp-matter-tools](https://github.com/espressif/esp-matter-tools) ⭐20 — (설명 없음)
- [esp-baidu-iot](https://github.com/espressif/esp-baidu-iot) ⭐19 `archived` — Baidu 天工物联网平台 support for ESP32 & ESP8266.
- [esp-aws-expresslink-eval](https://github.com/espressif/esp-aws-expresslink-eval) ⭐19 — Espressif AWS IoT ExpressLink Evaluation and Firmware Repository
- [esp-afr-sdk](https://github.com/espressif/esp-afr-sdk) ⭐17 `archived` — Espressif Base SDK for (Amazon) FreeRTOS
- [esp-rainmaker-mcp](https://github.com/espressif/esp-rainmaker-mcp) ⭐16 — ESP RainMaker MCP server
- [esp-freertos-coremqtt](https://github.com/espressif/esp-freertos-coremqtt) ⭐16 — (설명 없음)
- [esp-rainmaker-cli](https://github.com/espressif/esp-rainmaker-cli) ⭐12 — (설명 없음)
- [esp-rainmaker-home](https://github.com/espressif/esp-rainmaker-home) ⭐11 — ESP RainMaker Home App
- [esp-claw-skills-lab](https://github.com/espressif/esp-claw-skills-lab) ⭐11 — ESP-Claw Skills Lab
- [esp-thread-lib](https://github.com/espressif/esp-thread-lib) ⭐10 — Thread protocol related precompiled libraries for ESP-IDF
- [esp32h2-bt-lib](https://github.com/espressif/esp32h2-bt-lib) ⭐9 — ESP32-H2 Bluetooth stack (below HCI layer) precompiled libraries
- [esp-welink](https://github.com/espressif/esp-welink) ⭐9 `archived` — Tencent 微瓴 support for ESP32 & ESP8266.
- [esp-rainmaker-common](https://github.com/espressif/esp-rainmaker-common) ⭐7 — ESP RainMaker Common
- [esp-ble-mesh-lib](https://github.com/espressif/esp-ble-mesh-lib) ⭐7 — Pre-compiled libraries for ESP BLE Mesh v1.1
- [esp-rainmaker-webhooks](https://github.com/espressif/esp-rainmaker-webhooks) ⭐6 — Rainmaker Web hooks Project
- [esp-ieee802154-lib](https://github.com/espressif/esp-ieee802154-lib) ⭐5 — IEEE-802.15.4 precompiled libraries.
- [esp32c6-bt-lib](https://github.com/espressif/esp32c6-bt-lib) ⭐3 — ESP32-C6 Bluetooth stack (below HCI layer) precompiled libraries
- [esp-technical-reference-manual-latex](https://github.com/espressif/esp-technical-reference-manual-latex) ⭐3 — Espressif Technical Reference Manuals in LaTeX for Espressif SoCs.
- [esp-rainmaker-oauth2-integration](https://github.com/espressif/esp-rainmaker-oauth2-integration) ⭐2 — ESP RainMaker OAuth2 Integration
- [esp-rainmaker-custom-development](https://github.com/espressif/esp-rainmaker-custom-development) ⭐2 — ESP RainMaker Custom Development
- [esp-rainmaker-app-sdk-ts](https://github.com/espressif/esp-rainmaker-app-sdk-ts) ⭐2 — ESP RainMaker SDK in TypeScript
- [esp-rainmaker-app-cdf-ts](https://github.com/espressif/esp-rainmaker-app-cdf-ts) ⭐2 — ESP RainMaker Base CDF for TypeScript
- [esp-chip-errata](https://github.com/espressif/esp-chip-errata) ⭐2 — Espressif chip errata, which documents the known errors in SoCs and the solutions to solve the errors
- [esp-rainmaker-admin-cli](https://github.com/espressif/esp-rainmaker-admin-cli) ⭐1 — (설명 없음)
- [esp-ble-audio-lib](https://github.com/espressif/esp-ble-audio-lib) ⭐1 — (설명 없음)

---

## ★ — 거의 무관 (데모/게임·툴체인 내부 포크·구형 ESP8266·내부 CI/문서 등)

게임 포팅(NES/Doom/Quake), 컴파일러·런타임 포크(LLVM/GCC/QEMU/newlib/mbedTLS 등),
구형 ESP8266/ESP31 SDK, 내부 CI·릴리스·문서 자동화, 책/예제 등. 참고용으로만.

- [ESP8266_RTOS_SDK](https://github.com/espressif/ESP8266_RTOS_SDK) ⭐3547 — Latest ESP8266 SDK based on FreeRTOS, esp-idf style.
- [ESP8266_NONOS_SDK](https://github.com/espressif/ESP8266_NONOS_SDK) ⭐971 — ESP8266 nonOS SDK
- [ESP8266_MP3_DECODER](https://github.com/espressif/ESP8266_MP3_DECODER) ⭐757 `archived` — A demo that should be run with ESP8266 Non-OS SDK
- [esp32-nesemu](https://github.com/espressif/esp32-nesemu) ⭐621 — Proof-of-concept NES emulator for the ESP32
- [ESP8266_AT](https://github.com/espressif/ESP8266_AT) ⭐471 `archived` — This project is not maintained, please use https://github.com/espressif/esp-at.
- [esp-idf-template](https://github.com/espressif/esp-idf-template) ⭐366 `archived` — Template application for https://github.com/espressif/esp-idf
- [qemu](https://github.com/espressif/qemu) ⭐330 — Fork of QEMU with Espressif patches. See Wiki for details.
- [esp32-doom](https://github.com/espressif/esp32-doom) ⭐289 — A proof-of-concept port of PrBoom to the ESP32. Needs psram hardware.
- [llvm-project](https://github.com/espressif/llvm-project) ⭐280 — Fork of LLVM with Xtensa specific patches. To be upstreamed.
- [esp-idf-provisioning-android](https://github.com/espressif/esp-idf-provisioning-android) ⭐272 — Android Provisioning application for ESP-IDF Unified provisioning
- [idf-extra-components](https://github.com/espressif/idf-extra-components) ⭐244 — Additional components for ESP-IDF, maintained by Espressif
- [ESP31_RTOS_SDK](https://github.com/espressif/ESP31_RTOS_SDK) ⭐193 `archived` — ESP31B SDK based on FreeRTOS. For ESP32 please see http://github.com/espressif/esp-idf
- [book-esp32c3-iot-projects](https://github.com/espressif/book-esp32c3-iot-projects) ⭐174 — 《ESP32-C3 物联网工程开发实战》配套代码
- [llvm-xtensa](https://github.com/espressif/llvm-xtensa) ⭐170 `archived` — This repository is archived. See https://github.com/espressif/llvm-project instead.
- [esp-idf-provisioning-ios](https://github.com/espressif/esp-idf-provisioning-ios) ⭐167 — (설명 없음)
- [crosstool-NG](https://github.com/espressif/crosstool-NG) ⭐152 — crosstool-NG with support for Xtensa
- [esp-wasmachine](https://github.com/espressif/esp-wasmachine) ⭐136 — The Machine which can run WASM applications.
- [esp8266-rtos-sample-code](https://github.com/espressif/esp8266-rtos-sample-code) ⭐130 `archived` — (설명 없음)
- [usb-pids](https://github.com/espressif/usb-pids) ⭐116 — Customer-allocated USB PIDs under the Espressif VID
- [esp-lwip](https://github.com/espressif/esp-lwip) ⭐109 — Fork of lwIP (https://savannah.nongnu.org/projects/lwip/) with ESP-IDF specific patches
- [tensorflow](https://github.com/espressif/tensorflow) ⭐101 — An Open Source Machine Learning Framework for Everyone
- [openocd-on-esp32](https://github.com/espressif/openocd-on-esp32) ⭐95 — OpenOCD port running on ESP32-S3 microcontrollers
- [esp32-c3-book-en](https://github.com/espressif/esp32-c3-book-en) ⭐94 — Read the book here:
- [esp32c3-direct-boot-example](https://github.com/espressif/esp32c3-direct-boot-example) ⭐79 — Example of ESP32-C3 (rev. 3 and later) "direct boot" feature.
- [svd](https://github.com/espressif/svd) ⭐75 — SVD files for Espressif devices
- [esp8266-nonos-sample-code](https://github.com/espressif/esp8266-nonos-sample-code) ⭐67 `archived` — (설명 없음)
- [clang-xtensa](https://github.com/espressif/clang-xtensa) ⭐61 `archived` — This repository is archived. See https://github.com/espressif/llvm-project instead.
- [xtensa-isa-doc](https://github.com/espressif/xtensa-isa-doc) ⭐57 — (설명 없음)
- [tinyusb](https://github.com/espressif/tinyusb) ⭐50 — Fork of tinyusb project with Espressif-specific patches.
- [binutils-esp32ulp](https://github.com/espressif/binutils-esp32ulp) ⭐49 — Binutils fork with support for the ESP32 ULP co-processor
- [esp32-quake](https://github.com/espressif/esp32-quake) ⭐46 — Quake for the ESP32-P4 evaluation board
- [WROVER_KIT_LCD](https://github.com/espressif/WROVER_KIT_LCD) ⭐45 — Arduino library for displays found on ESP-WROVER-KIT
- [esp-wdf](https://github.com/espressif/esp-wdf) ⭐44 — Espressif WASM Development Framework.
- [newlib-esp32](https://github.com/espressif/newlib-esp32) ⭐38 — Version of newlib used in ESP32 ROM and ESP-IDF
- [esp31-smsemu](https://github.com/espressif/esp31-smsemu) ⭐38 `archived` — (설명 없음)
- [esp-joylink](https://github.com/espressif/esp-joylink) ⭐36 — Demo project for JD joylink, support esp32 & esp8266.
- [ESP8266_RTOS_ALINK_DEMO](https://github.com/espressif/ESP8266_RTOS_ALINK_DEMO) ⭐36 `archived` — Alink 1.0 早期版本
- [esp-ppq](https://github.com/espressif/esp-ppq) ⭐35 — PPL Quantization Tool (PPQ) is a powerful offline neural network quantization tool.
- [esp8266-alink-v1.0](https://github.com/espressif/esp8266-alink-v1.0) ⭐32 `archived` — alink v1.0
- [esp32-alink-demo](https://github.com/espressif/esp32-alink-demo) ⭐30 `archived` — Demo project for alink, include embed and SDS
- [esp32-iotivity](https://github.com/espressif/esp32-iotivity) ⭐29 `archived` — Guide you to make your ESP32 support OCF/OIC.
- [esp8266-alink-sds](https://github.com/espressif/esp8266-alink-sds) ⭐27 `archived` — Demo project for alink SDS
- [mbedtls](https://github.com/espressif/mbedtls) ⭐26 — An open source, portable, easy to use, readable and flexible SSL library
- [esp-rom-elfs](https://github.com/espressif/esp-rom-elfs) ⭐25 — Espressif ROM binaries
- [esp-hal-3rdparty](https://github.com/espressif/esp-hal-3rdparty) ⭐25 — (설명 없음)
- [esp-toolchain-docs](https://github.com/espressif/esp-toolchain-docs) ⭐24 — Repository with documentation related to toolchains and debuggers maintained by Espressif
- [developer-portal](https://github.com/espressif/developer-portal) ⭐23 — Developer Portal
- [qrcode-demo](https://github.com/espressif/qrcode-demo) ⭐21 — QR code recognition example
- [gh-esp-test-template](https://github.com/espressif/gh-esp-test-template) ⭐20 — ESP Project Testing Template (CI Project Template/Demo)
- [esp-boost](https://github.com/espressif/esp-boost) ⭐19 — Boost C++ libraries for ESP Series SoCs (ESP32, ESP32-S3, ESP32-P4, etc.)
- [kconfig-frontends](https://github.com/espressif/kconfig-frontends) ⭐18 `archived` — Fork of kconfig-frontends project with some modifications for use with ESP-IDF
- [binutils-gdb](https://github.com/espressif/binutils-gdb) ⭐18 — Unofficial mirror of sourceware binutils-gdb repository. Updated daily.
- [esp-workbench](https://github.com/espressif/esp-workbench) ⭐17 — Navigate in the world of ESP32 with easy. Tool for maintaining development environment.
- [jupyter-lite-micropython](https://github.com/espressif/jupyter-lite-micropython) ⭐16 — Jupyter Lite kernel for micropython and circuitpython
- [esp-hal-components](https://github.com/espressif/esp-hal-components) ⭐16 — HAL (hardware abstraction layer) components for Espressif chips
- [json_parser](https://github.com/espressif/json_parser) ⭐15 — JSON Parser on top of JSMN
- [esp-win-usb-drivers](https://github.com/espressif/esp-win-usb-drivers) ⭐15 — (설명 없음)
- [esp-nuttx-bootloader](https://github.com/espressif/esp-nuttx-bootloader) ⭐15 `archived` — This repository provides 2nd stage bootloader and partition table binaries for NuttX users of ESP chips.
- [esp-agents-firmware](https://github.com/espressif/esp-agents-firmware) ⭐15 — ESP Agents Firmware
- [github-actions](https://github.com/espressif/github-actions) ⭐14 `archived` — Github Actions developed/used by Espressif
- [gcc](https://github.com/espressif/gcc) ⭐14 — (설명 없음)
- [conventional-precommit-linter](https://github.com/espressif/conventional-precommit-linter) ⭐14 — Pre-commit hook script for linting conventional commit style
- [clang-tidy-runner](https://github.com/espressif/clang-tidy-runner) ⭐13 — (설명 없음)
- [esp32-alink](https://github.com/espressif/esp32-alink) ⭐12 `archived` — This is a porting of alink in esp32, it's just a  component, you can use it as submodule in your project. Please refer to esp32-alink-demo.
- [upload-components-ci-action](https://github.com/espressif/upload-components-ci-action) ⭐11 — GitHub Action to upload ESP-IDF components to the component registry
- [midi-workshop](https://github.com/espressif/midi-workshop) ⭐11 — Repository with materials for ESP32-S3 USB MIDI workshop in Brno on 2024/05/17
- [wasm-micro-runtime](https://github.com/espressif/wasm-micro-runtime) ⭐10 — WebAssembly Micro Runtime (WAMR)
- [tlsf](https://github.com/espressif/tlsf) ⭐10 — This repository contains Espressif patches to TLSF, used in ESP-IDF
- [esp8266-dual-cloud](https://github.com/espressif/esp8266-dual-cloud) ⭐10 `archived` — esp8266 dual cloud support demo, now support alink + joylink.
- [esp32-scummvm](https://github.com/espressif/esp32-scummvm) ⭐10 — ScummVM port to ESP32-P4
- [esp-opencv-component](https://github.com/espressif/esp-opencv-component) ⭐10 — OpenCV library as an ESP-IDF component
- [check-copyright](https://github.com/espressif/check-copyright) ⭐10 — Pre-commit/gitlab-ci script for checking and adding license SPDX headers
- [Arduino-FOC](https://github.com/espressif/Arduino-FOC) ⭐10 — Arduino FOC for BLDC and Stepper motors - Arduino Based Field Oriented Control Algorithm Library
- [Adafruit-GFX-Library](https://github.com/espressif/Adafruit-GFX-Library) ⭐10 — Adafruit GFX graphics core library, forked to add ESP32 support
- [.github](https://github.com/espressif/.github) ⭐10 — Admin project + DevRel managing Espressif Github main page
- [xtensa-overlays](https://github.com/espressif/xtensa-overlays) ⭐9 — Configuration overlays of Xtensa cores used by Espressif. These overlays are applied when building GCC, Binutils, GDB, Newlib.
- [maker-faire-cz](https://github.com/espressif/maker-faire-cz) ⭐9 — This repository hosts resources for all the demos presented by Espressif at maker Faire
- [esp-idf-security-dashboard](https://github.com/espressif/esp-idf-security-dashboard) ⭐9 — ESP-IDF Security Vulnerability Dashboard
- [esp-bist](https://github.com/espressif/esp-bist) ⭐9 — Bist Library for Espressif Devices
- [sphinx_idf_theme](https://github.com/espressif/sphinx_idf_theme) ⭐8 — Fork of the Read The Docs Sphinx theme, used for ESP-IDF documentation
- [iwidc](https://github.com/espressif/iwidc) ⭐8 — ESP IDF Web IDE Desktop Companion
- [eclipse-plugin-esp32](https://github.com/espressif/eclipse-plugin-esp32) ⭐8 `archived` — This repository is archived. Please use https://github.com/espressif/idf-eclipse-plugin instead.
- [asio](https://github.com/espressif/asio) ⭐8 `archived` — Asio C++ Library
- [sync-jira-actions](https://github.com/espressif/sync-jira-actions) ⭐7 — GitHub Actions for syncing the project with the Espressif Jira system
- [esp-nvd-mirror](https://github.com/espressif/esp-nvd-mirror) ⭐7 — (설명 없음)
- [zephyr-toolchain](https://github.com/espressif/zephyr-toolchain) ⭐6 — Toolchain for Espressif chips for use in Zephyr
- [vscode-esp-idf-web-extension](https://github.com/espressif/vscode-esp-idf-web-extension) ⭐6 — ESP-IDF Web Extension for Visual Studio Code
- [slidev-esp-template](https://github.com/espressif/slidev-esp-template) ⭐6 — Espressif template for Slidev (https://sli.dev/)
- [json_generator](https://github.com/espressif/json_generator) ⭐6 — A simple JSON generator with flushing capability
- [install-esp-idf-action](https://github.com/espressif/install-esp-idf-action) ⭐6 — GitHub action to install ESP-IDF to the runner
- [git-mirror-server](https://github.com/espressif/git-mirror-server) ⭐6 — Host Git repository mirrors with ease
- [doxybook](https://github.com/espressif/doxybook) ⭐6 — Generate single-file API reference in Markdown for C/C++
- [vscode-extension-codespace-test](https://github.com/espressif/vscode-extension-codespace-test) ⭐5 — Template repository to use ESP-IDF in Github Codespaces. 🚧 Work in progress! 🚧 
- [innosetup-cmdlinerunner](https://github.com/espressif/innosetup-cmdlinerunner) ⭐5 — Extension for InnoSetup for executing and processing stdout of shell commands
- [esp_jrnl](https://github.com/espressif/esp_jrnl) ⭐4 — ESP-IDF file-system journaling component
- [esp32e22-fw](https://github.com/espressif/esp32e22-fw) ⭐4 — Unified firmware for ESP32-E22
- [idf_py_exe_tool](https://github.com/espressif/idf_py_exe_tool) ⭐3 — idf.py.exe, wrapper tool to invoke idf.py on Windows
- [idf-flash-vendor-patches](https://github.com/espressif/idf-flash-vendor-patches) ⭐3 — Project to hold possible patches for flash vendors
- [example_components](https://github.com/espressif/example_components) ⭐3 — (설명 없음)
- [esp32s31-bt-lib](https://github.com/espressif/esp32s31-bt-lib) ⭐3 — (설명 없음)
- [esp32e22-linux-driver](https://github.com/espressif/esp32e22-linux-driver) ⭐3 — Collection of Linux drivers for ESP32E22
- [esp-llvm-embedded-toolchain](https://github.com/espressif/esp-llvm-embedded-toolchain) ⭐3 — Scripts and tools for building LLVM based toolchain. Forked from https://github.com/ARM-software/LLVM-embedded-toolchain-for-Arm
- [esp-aliro](https://github.com/espressif/esp-aliro) ⭐3 — (설명 없음)
- [developer-portal-codebase](https://github.com/espressif/developer-portal-codebase) ⭐3 — This repository contains Developer Portal examples, testing code, and other related coding for articles, tutorials,  and workshops.
- [xtensa-dynconfig](https://github.com/espressif/xtensa-dynconfig) ⭐2 — Configuration plugin generator for the GNU xtensa toolchain
- [sync-pr-to-gitlab](https://github.com/espressif/sync-pr-to-gitlab) ⭐2 — GitHub Action - Sync approved PRs to internal codebase (Gitlab)
- [python-binary-action](https://github.com/espressif/python-binary-action) ⭐2 — (설명 없음)
- [opencv](https://github.com/espressif/opencv) ⭐2 — OpenCV with Espressif patches
- [matter_data_model_interpreter](https://github.com/espressif/matter_data_model_interpreter) ⭐2 — Matter Data Model Interpreter
- [idf-examples-launchpad-ci-action](https://github.com/espressif/idf-examples-launchpad-ci-action) ⭐2 — Action that builds examples for ESP Launchpad
- [esp-docs-mdbook](https://github.com/espressif/esp-docs-mdbook) ⭐2 — (설명 없음)
- [docs-bot-action](https://github.com/espressif/docs-bot-action) ⭐2 — (설명 없음)
- [cz-plugin-espressif](https://github.com/espressif/cz-plugin-espressif) ⭐2 — Commitizen tools plugin with Espressif code style
- [aws-quickconnect](https://github.com/espressif/aws-quickconnect) ⭐2 — AWS QuickConnect Example and Binaries
- [test-project-bot](https://github.com/espressif/test-project-bot) ⭐1 — (설명 없음)
- [sphinx_selective_exclude](https://github.com/espressif/sphinx_selective_exclude) ⭐1 — Sphinx extension (plugin) to make ".only::" directive work like you expect. (Plus some other goodies for selective indexes.)
- [skills](https://github.com/espressif/skills) ⭐1 — Collections of agent skills for Espressif products and frameworks
- [shared-github-dangerjs](https://github.com/espressif/shared-github-dangerjs) ⭐1 — This is a reusable GitHub Action CI DangerJS workflow for Espressif GitHub projects.
- [pytest-ignore-test-results](https://github.com/espressif/pytest-ignore-test-results) ⭐1 — (설명 없음)
- [picolibc](https://github.com/espressif/picolibc) ⭐1 — (설명 없음)
- [libuvc](https://github.com/espressif/libuvc) ⭐1 — a fork of libuvc, cross-platform library for USB video devices, with Espressif-specific patches
- [github-esp-dockerfiles](https://github.com/espressif/github-esp-dockerfiles) ⭐1 — Dockerfiles for Espressif Github self-hosted runners
- [esp_weaver](https://github.com/espressif/esp_weaver) ⭐1 — An integration that seamlessly integrates ESP devices into Home Assistant.
- [esp32c5-bt-lib](https://github.com/espressif/esp32c5-bt-lib) ⭐1 — (설명 없음)
- [esp32c2-bt-lib](https://github.com/espressif/esp32c2-bt-lib) ⭐1 — (설명 없음)
- [esp-xtensaconfig-lib](https://github.com/espressif/esp-xtensaconfig-lib) ⭐1 — GCC/binutils/GDB plugin for run-time loading of Xtensa CPU configuration
- [esp-toolchain-bin-wrappers](https://github.com/espressif/esp-toolchain-bin-wrappers) ⭐1 — (설명 없음)
- [esp-product-security](https://github.com/espressif/esp-product-security) ⭐1 — ESP Product Security Documentation
- [esp-idf-configdep](https://github.com/espressif/esp-idf-configdep) ⭐1 — (설명 없음)
- [esp-btdm-linux-drv](https://github.com/espressif/esp-btdm-linux-drv) ⭐1 — Linux Bluetooth dual mode driver for ESP chips
- [esp-bool-parser](https://github.com/espressif/esp-bool-parser) ⭐1 — A lightweight tool for parsing boolean expressions with support for diverse operand types, including SOC capabilities, environment variables, strings, booleans, and integers.
- [docker-hub-issue-test](https://github.com/espressif/docker-hub-issue-test) ⭐1 — (설명 없음)
- [build-esp-idf-projects-action](https://github.com/espressif/build-esp-idf-projects-action) ⭐1 — (설명 없음)
- [build-and-test-esp-idf-projects-example](https://github.com/espressif/build-and-test-esp-idf-projects-example) ⭐1 — (설명 없음)
- [blowfish](https://github.com/espressif/blowfish) ⭐1 — Personal Website & Blog Theme for Hugo
- [astyle_py](https://github.com/espressif/astyle_py) ⭐1 — Python wrapper and pre-commit hook for Astyle formatter (http://astyle.sourceforge.net/)
- [this-month-in-esps](https://github.com/espressif/this-month-in-esps) ⭐0 — (설명 없음)
- [test-esp-idf-projects-action](https://github.com/espressif/test-esp-idf-projects-action) ⭐0 — (설명 없음)
- [release-zips-action](https://github.com/espressif/release-zips-action) ⭐0 — Espressif GitHub Action to create full-source ZIPs (with submodules) on tag push.
- [release-sign](https://github.com/espressif/release-sign) ⭐0 — (설명 없음)
- [opencv_contrib](https://github.com/espressif/opencv_contrib) ⭐0 — OpenCV's extra modules with Espressif patches
- [no_std-training-test](https://github.com/espressif/no_std-training-test) ⭐0 — (Fork of) Getting-started guide on using the Rust with Espressif SoCs using no_std.
- [network_demo](https://github.com/espressif/network_demo) ⭐0 — (설명 없음)
- [inno-download-plugin](https://github.com/espressif/inno-download-plugin) ⭐0 — Mirror of https://bitbucket.org/mitrich_k/inno-download-plugin
- [homebrew-eim](https://github.com/espressif/homebrew-eim) ⭐0 — Homebrew for EIM
- [glibc](https://github.com/espressif/glibc) ⭐0 — (설명 없음)
- [esp32h4-bt-lib](https://github.com/espressif/esp32h4-bt-lib) ⭐0 — (설명 없음)
- [esp32c61-bt-lib](https://github.com/espressif/esp32c61-bt-lib) ⭐0 — esp32c61-bt-lib
- [esp-twai-components](https://github.com/espressif/esp-twai-components) ⭐0 — TWAI (CAN compatible) components for ESP-IDF
- [esp-pwsh-check](https://github.com/espressif/esp-pwsh-check) ⭐0 — (설명 없음)
- [esp-idf-size-test](https://github.com/espressif/esp-idf-size-test) ⭐0 — (설명 없음)
- [esp-idf-sbom-action](https://github.com/espressif/esp-idf-sbom-action) ⭐0 — (설명 없음)
- [esp-ace](https://github.com/espressif/esp-ace) ⭐0 — (설명 없음)
- [dependency-driven-ci-action](https://github.com/espressif/dependency-driven-ci-action) ⭐0 — GitHub Action to build & test your ESP-IDF projects based on file changes
- [cJSON](https://github.com/espressif/cJSON) ⭐0 — Ultralightweight JSON parser in ANSI C
- [blockdiag](https://github.com/espressif/blockdiag) ⭐0 — (설명 없음)
- [actions-internal-test](https://github.com/espressif/actions-internal-test) ⭐0 — Private internal test repo for Espressif's GitHub Actions
- [TF-PSA-Crypto](https://github.com/espressif/TF-PSA-Crypto) ⭐0 — Reference implementation of the PSA Cryptography API

---

## 관련 문서

- [설치 가이드](install.md) — ESP-IDF/esptool 설치 순서
- [펌웨어 가이드](firmware-guide.md) — MicroPython / ESP-IDF 펌웨어
- [Python 환경 두 개](python-environments.md) — 프로젝트 venv vs ESP-IDF venv
- [보드 진단 도구](../tools/board_check/README.md) — 현재 단계 진단 도구

> CSI(Channel State Information)는 WiFi 신호의 부반송파별 진폭·위상으로, 사람이
> 움직이면 변합니다 — 이를 분석해 존재/움직임/호흡/제스처/실내위치를 추정하는 것이
> 본 프로젝트의 목표입니다. Phase 2 에서 [esp-csi](https://github.com/espressif/esp-csi)
> 기반으로 수집 펌웨어를 구성할 예정입니다.
