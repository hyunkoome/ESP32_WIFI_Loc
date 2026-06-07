# Espressif 생태계 가이드

이 프로젝트가 쓰는 칩(ESP32-S3)과 도구(ESP-IDF, esptool)는 모두 **Espressif**
에서 나옵니다. 이 문서는 Espressif 가 무엇이고, GitHub
([github.com/espressif](https://github.com/espressif))의 **공개 저장소 317개 전부**를
**우리 프로젝트(ESP32-S3 WiFi CSI 센싱)와의 관련도** 기준으로 ★5(최우선)~★1(무관)
까지 우선순위를 매겨 정리합니다.

> 데이터 기준: GitHub API 로 조회한 espressif 조직 공개 저장소 **317개**
> (활성 288 + 보관 29). ⭐ 는 GitHub 스타 수, 🗄️ 는 GitHub `archived`(보관) 저장소.
> 각 tier 안에서는 스타 내림차순. 설명은 한국어로 옮겼습니다.
>
> **본 프로젝트 적용** 열의 `✓` 는 이 저장소가 실제로 본 프로젝트에서 쓰이고 있다는
> 뜻입니다(현재 3개: esp-idf, esptool, idf-extra-components 의 led_strip 컴포넌트).
> 빈칸은 미사용(esp-csi 등 ★5/★4 라도 Phase 2 예정이면 아직 빈칸).

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

| 저장소 | ⭐ | 설명 | 본 프로젝트 적용 |
|--------|----|------|----------|
| [esp-idf](https://github.com/espressif/esp-idf) | 18,247 | Espressif 공식 IoT 개발 프레임워크(C/C++ SDK). idf.py·툴체인·FreeRTOS 포함 — 진단/CSI 펌웨어 빌드에 이미 사용 중 | ✓ (펌웨어 빌드 SDK) |
| [esptool](https://github.com/espressif/esptool) | 6,364 | 칩 펌웨어 flash·프로비저닝·칩/Flash 정보 조회 시리얼 유틸. 진단 도구 핵심 의존성 | ✓ (펌웨어 flash·칩 조회) |
| [esp-csi](https://github.com/espressif/esp-csi) | 1,367 | WiFi CSI 기반 응용(실내 위치추정·사람 감지 등) 예제 — **Phase 2 의 출발점** |  |

---

## ★★★★ — 직접 도움 (CSI 수집·신호처리·학습·개발)

CSI 신호처리(FFT/DSP), 온디바이스 추론(DL/NN/TFLite), 펌웨어 테스트, WiFi 스택,
웹/호스트 기반 플래시 등 다음 단계에 바로 닿는 것들.

| 저장소 | ⭐ | 설명 | 본 프로젝트 적용 |
|--------|----|------|----------|
| [vscode-esp-idf-extension](https://github.com/espressif/vscode-esp-idf-extension) | 1,429 | VS Code 용 ESP-IDF 확장(빌드/플래시/디버그) |  |
| [esp-dl](https://github.com/espressif/esp-dl) | 1,035 | AIoT 용 Espressif 딥러닝 추론 라이브러리(온디바이스) |  |
| [esp-dsp](https://github.com/espressif/esp-dsp) | 676 | ESP-IDF 용 DSP 라이브러리(FFT 등) — CSI 신호 전처리에 유용 |  |
| [esp-tflite-micro](https://github.com/espressif/esp-tflite-micro) | 647 | Espressif 칩용 TensorFlow Lite Micro(온디바이스 추론) |  |
| [esp-serial-flasher](https://github.com/espressif/esp-serial-flasher) | 542 | 다른 MCU/호스트에서 Espressif 칩을 flash 하는 라이브러리 |  |
| [esptool-js](https://github.com/espressif/esptool-js) | 496 | WebSerial 기반 브라우저용 esptool(JS 구현) — 웹 플래시 |  |
| [esp-nn](https://github.com/espressif/esp-nn) | 231 | Espressif 칩 최적화 신경망 연산 함수(esp-dl 백엔드) |  |
| [esp32-wifi-lib](https://github.com/espressif/esp32-wifi-lib) | 198 | ESP32 WiFi 스택 사전 컴파일 라이브러리(CSI 의 기반) |  |
| [pytest-embedded](https://github.com/espressif/pytest-embedded) | 141 | 임베디드 테스트용 pytest 플러그인(펌웨어 자동 테스트) |  |
| [esp-launchpad](https://github.com/espressif/esp-launchpad) | 82 | 브라우저 기반 펌웨어 이미지 플래셔(설정형) |  |

---

## ★★★ — 간접 관련 (WiFi/네트워킹·멀티보드·플래시/디버그·보드·빌드 도구)

WiFi 스택/PHY/coexistence, host-MCU 통신(멀티보드 수집), 네트워킹(데이터 전송),
JTAG/디버그, 개발보드 BSP/회로, ESP-IDF 부속 빌드·설치 도구 등.

| 저장소 | ⭐ | 설명 | 본 프로젝트 적용 |
|--------|----|------|----------|
| [arduino-esp32](https://github.com/espressif/arduino-esp32) | 16,893 | ESP32 제품군용 Arduino 코어(우리는 ESP-IDF 사용) |  |
| [esp-iot-solution](https://github.com/espressif/esp-iot-solution) | 2,593 | IoT 디바이스 드라이버·문서·솔루션 모음(주변장치) |  |
| [kicad-libraries](https://github.com/espressif/kicad-libraries) | 1,268 | Espressif 칩/모듈/devkit 용 KiCad 라이브러리(회로 설계) |  |
| [esp-hosted](https://github.com/espressif/esp-hosted) | 999 | 호스트(Linux/MCU) + ESP32 WiFi/BT/BLE 분리 솔루션(멀티보드 수집에 유용) |  |
| [esp-now](https://github.com/espressif/esp-now) | 753 | 비접속형 WiFi 통신 프로토콜(ESP-NOW) |  |
| [esp-mqtt](https://github.com/espressif/esp-mqtt) | 731 | ESP32 MQTT 컴포넌트(데이터 전송) |  |
| [esp-dev-kits](https://github.com/espressif/esp-dev-kits) | 584 | ESP 개발보드 문서·회로도·공장 펌웨어 |  |
| [rust-esp32-example](https://github.com/espressif/rust-esp32-example) | 498 | ESP-IDF 프로젝트에 Rust 통합 예제 |  |
| [openocd-esp32](https://github.com/espressif/openocd-esp32) | 450 | ESP32 JTAG 지원 OpenOCD 분기(디버그) |  |
| [esp-bsp](https://github.com/espressif/esp-bsp) | 424 | Espressif 개발보드 지원 컴포넌트(BSP) |  |
| [esp-usb-bridge](https://github.com/espressif/esp-usb-bridge) | 389 | ESP32-S2/S3 기반 USB↔UART&JTAG 브리지 |  |
| [idf-eclipse-plugin](https://github.com/espressif/idf-eclipse-plugin) | 367 | ESP-IDF 용 Eclipse 플러그인(Espressif-IDE) |  |
| [esp-protocols](https://github.com/espressif/esp-protocols) | 289 | 네트워킹 프로토콜 관련 ESP-IDF 컴포넌트 모음(mDNS/MQTT 등) |  |
| [esp32-arduino-lib-builder](https://github.com/espressif/esp32-arduino-lib-builder) | 199 | ESP32 Arduino 코어용 라이브러리 빌더 |  |
| [esp-gdbstub](https://github.com/espressif/esp-gdbstub) | 166 | 칩에서 동작하는 GDB 스텁(디버그) |  |
| [esp-insights](https://github.com/espressif/esp-insights) | 142 | 연결 기기용 원격 진단/관측 프레임워크(우리 진단과 유사한 결) |  |
| [esp-hosted-mcu](https://github.com/espressif/esp-hosted-mcu) | 134 | esp-hosted 의 MCU 측 펌웨어 |  |
| [idf-installer](https://github.com/espressif/idf-installer) | 124 | ESP-IDF Windows 설치 프로그램 |  |
| [esp-idf-ci-action](https://github.com/espressif/esp-idf-ci-action) | 104 | ESP32 CI 용 GitHub Action |  |
| [esp-idf-cxx](https://github.com/espressif/esp-idf-cxx) | 104 | ESP-IDF 컴포넌트용 C++ 래퍼 클래스 |  |
| [idf-im-ui](https://github.com/espressif/idf-im-ui) | 78 | ESP-IDF 설치 관리자(EIM) GUI |  |
| [freertos-gdb](https://github.com/espressif/freertos-gdb) | 68 | GDB 에서 FreeRTOS 커널 객체 조회 Python 모듈 |  |
| [esp-usb](https://github.com/espressif/esp-usb) | 63 | ESP USB 관련 컴포넌트 모음 |  |
| [idf-component-manager](https://github.com/espressif/idf-component-manager) | 62 | ESP-IDF 컴포넌트 설치 도구 |  |
| [esp-eth-drivers](https://github.com/espressif/esp-eth-drivers) | 56 | ESP-IDF 용 추가 이더넷 드라이버 모음 |  |
| [esp-idf-monitor](https://github.com/espressif/esp-idf-monitor) | 46 | ESP-IDF 시리얼 모니터 도구 |  |
| [idf-env](https://github.com/espressif/idf-env) | 37 | ESP-IDF 설치·관리 도구 |  |
| [esp-debug-adapter](https://github.com/espressif/esp-debug-adapter) | 32 | GDB 와 연동되는 Debug Adapter Protocol 서버 |  |
| [idf-build-apps](https://github.com/espressif/idf-build-apps) | 29 | CI 에서 다수 IDF 앱을 빌드하는 도구 |  |
| [esp-wireless-drivers-3rdparty](https://github.com/espressif/esp-wireless-drivers-3rdparty) | 28 | 3rd party 통합용 WiFi/BT 드라이버 패키지(작업 중) |  |
| [esp-wifi-remote](https://github.com/espressif/esp-wifi-remote) | 27 | 네이티브 WiFi 없는 타깃에서 ESP WiFi 기능 사용(원격 전송) |  |
| [esp-docs](https://github.com/espressif/esp-docs) | 24 | Sphinx 기반 Espressif 문서 빌드 래퍼 |  |
| [idf-clion-plugin](https://github.com/espressif/idf-clion-plugin) | 24 | ESP-IDF 용 CLion 플러그인 |  |
| [esp-amp](https://github.com/espressif/esp-amp) | 23 | ESP AMP(비대칭 멀티프로세싱) |  |
| [esp-idf-sbom](https://github.com/espressif/esp-idf-sbom) | 23 | ESP-IDF SBOM(소프트웨어 명세) 생성 도구 |  |
| [esp-coredump](https://github.com/espressif/esp-coredump) | 19 | ESP-IDF 코어덤프 분석 도구 |  |
| [idf-web-ide](https://github.com/espressif/idf-web-ide) | 19 | Eclipse Theia 기반 ESP-IDF 클라우드/데스크톱 IDE |  |
| [idf-im-cli](https://github.com/espressif/idf-im-cli) 🗄️ | 19 | ESP-IDF 설치 관리자(EIM) CLI |  |
| [esp-idf-size](https://github.com/espressif/esp-idf-size) | 15 | 펌웨어 바이너리 크기 분석 도구 |  |
| [esp-phy-lib](https://github.com/espressif/esp-phy-lib) | 15 | 저수준 RF 함수 사전 컴파일 라이브러리 |  |
| [esp32-arduino-libs](https://github.com/espressif/esp32-arduino-libs) | 15 | ESP32 Arduino v3.x+ 용 사전 컴파일 ESP-IDF 라이브러리 |  |
| [esp-idf-nvs-partition-gen](https://github.com/espressif/esp-idf-nvs-partition-gen) | 13 | NVS 파티션 생성 도구 |  |
| [idf-ci](https://github.com/espressif/idf-ci) | 12 | ESP-IDF 프로젝트 CI/CD 도구(GitLab/GitHub) |  |
| [idf-python-wheels](https://github.com/espressif/idf-python-wheels) | 12 | ESP-IDF 용 Python wheel 빌드(오프라인/온라인 설치) |  |
| [esp-prog-2](https://github.com/espressif/esp-prog-2) | 10 | ESP-Prog 2 디버그/프로그래밍 보드 |  |
| [esp-extconn](https://github.com/espressif/esp-extconn) | 9 | 외부 연결(external connectivity) 컴포넌트 |  |
| [esp-hardware-design-guidelines](https://github.com/espressif/esp-hardware-design-guidelines) | 9 | Espressif 칩/모듈 통합 하드웨어 설계 지침 |  |
| [esp-idf-kconfig](https://github.com/espressif/esp-idf-kconfig) | 9 | ESP-IDF Kconfig 도구 |  |
| [idf-python](https://github.com/espressif/idf-python) | 8 | pip/virtualenv 포함 최소 자립형 Python 배포 |  |
| [esp-idf-panic-decoder](https://github.com/espressif/esp-idf-panic-decoder) | 7 | ESP-IDF panic 백트레이스 디코더 |  |
| [esp-wifi-drv](https://github.com/espressif/esp-wifi-drv) | 7 | ESP 칩용 Linux WiFi 드라이버 |  |
| [esptool-legacy-flasher-stub](https://github.com/espressif/esptool-legacy-flasher-stub) | 7 | esptool 구버전 플래셔 스텁 |  |
| [esp-coex-lib](https://github.com/espressif/esp-coex-lib) | 4 | WiFi/BT coexistence 라이브러리 |  |
| [esp-debug-backend](https://github.com/espressif/esp-debug-backend) | 4 | Python 디버그 백엔드 |  |
| [esp-flasher-stub](https://github.com/espressif/esp-flasher-stub) | 4 | esptool 플래셔 스텁 |  |
| [esp-swift](https://github.com/espressif/esp-swift) | 4 | Swift 코드 통합용 ESP-IDF 컴포넌트 |  |
| [idf-im-lib](https://github.com/espressif/idf-im-lib) | 4 | ESP-IDF 설치 관리자 라이브러리 |  |
| [esp-board-manager](https://github.com/espressif/esp-board-manager) | 3 | ESP 보드 관리 도구 |  |
| [iperf-cmd](https://github.com/espressif/iperf-cmd) | 3 | iperf 명령 ESP 컴포넌트(네트워크 성능 측정) |  |
| [esp-flash-drivers](https://github.com/espressif/esp-flash-drivers) | 2 | 3rd party flash 드라이버 모음 |  |
| [esp-idf-diag](https://github.com/espressif/esp-idf-diag) | 2 | ESP-IDF 진단 정보 수집 도구 |  |
| [esp-self-reflasher](https://github.com/espressif/esp-self-reflasher) | 2 | 기기 자체에서 전체 재플래시(unsafe) 컴포넌트 |  |
| [esp-stub-lib](https://github.com/espressif/esp-stub-lib) | 2 | 플래셔 스텁 라이브러리 |  |
| [esp-sysview](https://github.com/espressif/esp-sysview) | 2 | SEGGER SystemView 호환 트레이싱 컴포넌트 |  |
| [esp-gcov](https://github.com/espressif/esp-gcov) | 1 | 코드 커버리지 수집 ESP-IDF 컴포넌트 |  |
| [esp-test-tools](https://github.com/espressif/esp-test-tools) | 1 | RF 테스트 도구·양산 가이드 등 테스트 리소스 |  |
| [idf-drivers-gdb](https://github.com/espressif/idf-drivers-gdb) | 1 | GDB 에서 ESP-IDF 드라이버 객체 보기 Python 모듈 |  |
| [esp-gpio-tool](https://github.com/espressif/esp-gpio-tool) | 0 | GPIO 점검 도구 |  |
| [esp-pylib](https://github.com/espressif/esp-pylib) | 0 | Espressif Python 프로젝트 공용 로깅/유틸/상수 라이브러리 |  |

---

## ★★ — 생태계 일반 (우리와 약한 관련)

Thread/Zigbee/Matter, 클라우드(RainMaker/AWS/Azure/알리/바이두 등), 멀티미디어
(오디오/카메라/H264), 음성·비전 AI, Mesh, HomeKit, BT/BLE 스택, 보안/부트로더 등.
ESP32 를 쓰지만 CSI 센싱과는 직접 관련이 적음.

| 저장소 | ⭐ | 설명 | 본 프로젝트 적용 |
|--------|----|------|----------|
| [esp32-camera](https://github.com/espressif/esp32-camera) | 2,676 | ESP32 카메라(OV2640 등) 드라이버 |  |
| [esp-adf](https://github.com/espressif/esp-adf) | 2,248 | 멀티미디어(오디오) 고급 개발 프레임워크 |  |
| [esp-who](https://github.com/espressif/esp-who) | 2,083 | 얼굴 검출·인식 프레임워크(영상 AI) |  |
| [esp-drone](https://github.com/espressif/esp-drone) | 1,879 | ESP32/S 시리즈용 미니 드론/쿼드콥터 펌웨어 |  |
| [esp-claw](https://github.com/espressif/esp-claw) | 1,472 | IoT 기기용 "Chat Coding" AI 에이전트 프레임워크 |  |
| [esp-sr](https://github.com/espressif/esp-sr) | 1,389 | 음성 인식(speech recognition) |  |
| [esp-box](https://github.com/espressif/esp-box) | 1,254 | ESP-BOX AIoT 개발 플랫폼 |  |
| [esp-at](https://github.com/espressif/esp-at) | 1,219 | ESP32/C2/C3/C6/ESP8266 용 AT 명령 펌웨어 |  |
| [esp-matter](https://github.com/espressif/esp-matter) | 1,022 | Espressif Matter SDK |  |
| [esp-skainet](https://github.com/espressif/esp-skainet) | 873 | 지능형 음성 비서 |  |
| [esp-mdf](https://github.com/espressif/esp-mdf) 🗄️ | 825 | Mesh 개발 프레임워크(유지보수 축소, esp-mesh-lite 권장) |  |
| [esp-brookesia](https://github.com/espressif/esp-brookesia) | 709 | AIoT 기기용 HMI(인간-기계 상호작용) 개발 프레임워크 |  |
| [esp-homekit-sdk](https://github.com/espressif/esp-homekit-sdk) | 656 | Apple HomeKit SDK |  |
| [esp-apple-homekit-adk](https://github.com/espressif/esp-apple-homekit-adk) | 649 | Apple HomeKit ADK 포팅 |  |
| [esp-rainmaker](https://github.com/espressif/esp-rainmaker) | 609 | 클라우드 연동 IoT 플랫폼 에이전트(펌웨어) |  |
| [esp-zigbee-sdk](https://github.com/espressif/esp-zigbee-sdk) | 369 | Espressif Zigbee SDK |  |
| [esp-webrtc-solution](https://github.com/espressif/esp-webrtc-solution) | 355 | WebRTC 솔루션 |  |
| [esp-aliyun](https://github.com/espressif/esp-aliyun) 🗄️ | 346 | 알리바바 클라우드 IoT(Iotkit) 연동 |  |
| [esp-aws-iot](https://github.com/espressif/esp-aws-iot) | 328 | ESP32 용 AWS IoT SDK |  |
| [esp-va-sdk](https://github.com/espressif/esp-va-sdk) | 312 | 음성 비서 SDK(Alexa/Google 등) |  |
| [esp-iot-bridge](https://github.com/espressif/esp-iot-bridge) | 227 | ESP+다른 MCU 인터넷 접속 브리지 |  |
| [esp-thread-br](https://github.com/espressif/esp-thread-br) | 224 | Thread Border Router SDK |  |
| [esp-jumpstart](https://github.com/espressif/esp-jumpstart) | 207 | 컨셉→양산 가이드 예제 |  |
| [esp-mesh-lite](https://github.com/espressif/esp-mesh-lite) | 206 | 경량 WiFi Mesh(IP 계층 접속) |  |
| [esp-modbus](https://github.com/espressif/esp-modbus) | 186 | Modbus 프로토콜 공식 라이브러리(RS485/TCP) |  |
| [esp-azure](https://github.com/espressif/esp-azure) | 185 | Microsoft Azure IoT 연동 SDK |  |
| [esp-google-iot](https://github.com/espressif/esp-google-iot) 🗄️ | 143 | Google Cloud IoT SDK 컴포넌트 |  |
| [esp-rainmaker-android](https://github.com/espressif/esp-rainmaker-android) | 141 | RainMaker Android 앱 소스 |  |
| [esp-detection](https://github.com/espressif/esp-detection) | 126 | ESP 칩용 경량 실시간 객체 검출(YOLOv11 기반) |  |
| [esp-gmf](https://github.com/espressif/esp-gmf) | 113 | 범용 멀티미디어 프레임워크(ESP-GMF) |  |
| [esp-adf-libs](https://github.com/espressif/esp-adf-libs) | 111 | ESP-ADF 사전 컴파일 라이브러리 |  |
| [esp-nimble](https://github.com/espressif/esp-nimble) | 104 | NimBLE BLE 스택 분기(ESP32/ESP-IDF) |  |
| [esp32-bt-lib](https://github.com/espressif/esp32-bt-lib) | 89 | ESP32 Bluetooth 스택(HCI 하위) 사전 컴파일 라이브러리 |  |
| [esp-ali-smartliving](https://github.com/espressif/esp-ali-smartliving) 🗄️ | 83 | 알리바바 생활 IoT/티몰 정령 연동 |  |
| [esp-qcloud](https://github.com/espressif/esp-qcloud) | 79 | 텐센트 IoT Explorer 연동 |  |
| [esp-video-components](https://github.com/espressif/esp-video-components) | 77 | 카메라 관련 컴포넌트 모음 |  |
| [esp-lowcode-matter](https://github.com/espressif/esp-lowcode-matter) | 66 | Matter 제품용 LowCode 빌더 |  |
| [esp-moonlight](https://github.com/espressif/esp-moonlight) | 66 | ESP-Moonlight 예제 프로젝트 |  |
| [esp-rainmaker-ios](https://github.com/espressif/esp-rainmaker-ios) | 64 | RainMaker iOS 앱 소스 |  |
| [aws-iot-device-sdk-embedded-C](https://github.com/espressif/aws-iot-device-sdk-embedded-C) | 48 | AWS IoT 임베디드 C SDK(ESP-IDF 수정판) |  |
| [esp-privilege-separation](https://github.com/espressif/esp-privilege-separation) | 47 | 권한 분리 프레임워크(보안) |  |
| [connectedhomeip](https://github.com/espressif/connectedhomeip) | 41 | Matter(Project CHIP) 표준 구현 |  |
| [esp-h264-component](https://github.com/espressif/esp-h264-component) | 41 | H264 인코더/디코더 컴포넌트 |  |
| [esp-cryptoauthlib](https://github.com/espressif/esp-cryptoauthlib) | 40 | Microchip cryptoauthlib 분기(보안 요소) |  |
| [esp-faq](https://github.com/espressif/esp-faq) | 40 | 자주 묻는 질문 모음 |  |
| [esp-wolfssl](https://github.com/espressif/esp-wolfssl) | 40 | WolfSSL 포팅(ESP-IDF/ESP8266) |  |
| [openthread](https://github.com/espressif/openthread) | 34 | OpenThread 분기(ESP 패치) |  |
| [esp-bootloader-plus](https://github.com/espressif/esp-bootloader-plus) | 30 | 압축/차등 업그레이드 지원 부트로더 |  |
| [esp-desktop-buddy](https://github.com/espressif/esp-desktop-buddy) | 30 | ESP 데스크톱 버디 SDK |  |
| [esp_secure_cert_mgr](https://github.com/espressif/esp_secure_cert_mgr) | 26 | 보안 인증서 관리 컴포넌트 |  |
| [esp-zboss-lib](https://github.com/espressif/esp-zboss-lib) | 21 | Zigbee(ZBOSS) 사전 컴파일 라이브러리 |  |
| [esp-matter-tools](https://github.com/espressif/esp-matter-tools) | 20 | Matter 개발 도구 |  |
| [esp32c3-bt-lib](https://github.com/espressif/esp32c3-bt-lib) | 20 | ESP32-C3/S3 BT 스택 사전 컴파일 라이브러리 |  |
| [esp-aws-expresslink-eval](https://github.com/espressif/esp-aws-expresslink-eval) | 19 | AWS IoT ExpressLink 평가 펌웨어 |  |
| [esp-baidu-iot](https://github.com/espressif/esp-baidu-iot) 🗄️ | 19 | 바이두 톈궁 IoT 연동 |  |
| [esp-afr-sdk](https://github.com/espressif/esp-afr-sdk) 🗄️ | 17 | Amazon FreeRTOS 베이스 SDK |  |
| [esp-freertos-coremqtt](https://github.com/espressif/esp-freertos-coremqtt) | 16 | FreeRTOS coreMQTT 컴포넌트 |  |
| [esp-rainmaker-mcp](https://github.com/espressif/esp-rainmaker-mcp) | 16 | RainMaker MCP 서버 |  |
| [esp-rainmaker-cli](https://github.com/espressif/esp-rainmaker-cli) | 12 | RainMaker CLI |  |
| [esp-claw-skills-lab](https://github.com/espressif/esp-claw-skills-lab) | 11 | ESP-Claw 스킬 랩 |  |
| [esp-rainmaker-home](https://github.com/espressif/esp-rainmaker-home) | 11 | RainMaker 홈 앱 |  |
| [esp-thread-lib](https://github.com/espressif/esp-thread-lib) | 10 | Thread 프로토콜 사전 컴파일 라이브러리 |  |
| [esp32h2-bt-lib](https://github.com/espressif/esp32h2-bt-lib) | 9 | ESP32-H2 BT 스택 사전 컴파일 라이브러리 |  |
| [esp-welink](https://github.com/espressif/esp-welink) 🗄️ | 9 | 텐센트 微瓴 연동 |  |
| [esp-ble-mesh-lib](https://github.com/espressif/esp-ble-mesh-lib) | 7 | ESP BLE Mesh v1.1 사전 컴파일 라이브러리 |  |
| [esp-rainmaker-common](https://github.com/espressif/esp-rainmaker-common) | 7 | RainMaker 공용 코드 |  |
| [esp-rainmaker-webhooks](https://github.com/espressif/esp-rainmaker-webhooks) | 6 | RainMaker 웹훅 |  |
| [esp-ieee802154-lib](https://github.com/espressif/esp-ieee802154-lib) | 5 | IEEE 802.15.4 사전 컴파일 라이브러리 |  |
| [esp-technical-reference-manual-latex](https://github.com/espressif/esp-technical-reference-manual-latex) | 3 | 기술 레퍼런스 매뉴얼 LaTeX 소스 |  |
| [esp32c6-bt-lib](https://github.com/espressif/esp32c6-bt-lib) | 3 | ESP32-C6 BT 스택 사전 컴파일 라이브러리 |  |
| [esp-chip-errata](https://github.com/espressif/esp-chip-errata) | 2 | 칩 에라타(알려진 오류/해결책) 문서 |  |
| [esp-rainmaker-app-cdf-ts](https://github.com/espressif/esp-rainmaker-app-cdf-ts) | 2 | RainMaker TypeScript CDF |  |
| [esp-rainmaker-app-sdk-ts](https://github.com/espressif/esp-rainmaker-app-sdk-ts) | 2 | RainMaker TypeScript SDK |  |
| [esp-rainmaker-custom-development](https://github.com/espressif/esp-rainmaker-custom-development) | 2 | RainMaker 커스텀 개발 |  |
| [esp-rainmaker-oauth2-integration](https://github.com/espressif/esp-rainmaker-oauth2-integration) | 2 | RainMaker OAuth2 연동 |  |
| [esp-ble-audio-lib](https://github.com/espressif/esp-ble-audio-lib) | 1 | BLE 오디오 사전 컴파일 라이브러리 |  |
| [esp-rainmaker-admin-cli](https://github.com/espressif/esp-rainmaker-admin-cli) | 1 | RainMaker 관리자 CLI |  |

---

## ★ — 거의 무관 (데모/게임·툴체인 내부 포크·구형 ESP8266·내부 CI/문서 등)

게임 포팅(NES/Doom/Quake), 컴파일러·런타임 포크(LLVM/GCC/QEMU/newlib/mbedTLS 등),
구형 ESP8266/ESP31 SDK, 내부 CI·릴리스·문서 자동화, 책/예제 등. 참고용으로만.

| 저장소 | ⭐ | 설명 | 본 프로젝트 적용 |
|--------|----|------|----------|
| [ESP8266_RTOS_SDK](https://github.com/espressif/ESP8266_RTOS_SDK) | 3,547 | ESP8266 용 FreeRTOS 기반 SDK(구형 칩) |  |
| [ESP8266_NONOS_SDK](https://github.com/espressif/ESP8266_NONOS_SDK) | 971 | ESP8266 non-OS SDK(구형) |  |
| [ESP8266_MP3_DECODER](https://github.com/espressif/ESP8266_MP3_DECODER) 🗄️ | 757 | ESP8266 Non-OS MP3 디코더 데모 |  |
| [esp32-nesemu](https://github.com/espressif/esp32-nesemu) | 621 | ESP32 용 NES 에뮬레이터(PoC) |  |
| [ESP8266_AT](https://github.com/espressif/ESP8266_AT) 🗄️ | 471 | ESP8266 AT 펌웨어(유지 안 함, esp-at 사용) |  |
| [esp-idf-template](https://github.com/espressif/esp-idf-template) 🗄️ | 366 | ESP-IDF 템플릿 앱 |  |
| [qemu](https://github.com/espressif/qemu) | 330 | Espressif 패치 QEMU 분기(에뮬레이터) |  |
| [esp32-doom](https://github.com/espressif/esp32-doom) | 289 | ESP32 용 Doom(PrBoom) 포팅 PoC |  |
| [llvm-project](https://github.com/espressif/llvm-project) | 280 | Xtensa 패치 LLVM 분기(컴파일러) |  |
| [esp-idf-provisioning-android](https://github.com/espressif/esp-idf-provisioning-android) | 272 | ESP-IDF 프로비저닝 Android 앱 |  |
| [idf-extra-components](https://github.com/espressif/idf-extra-components) | 244 | ESP-IDF 추가 컴포넌트 모음 | ✓ (led_strip 컴포넌트) |
| [ESP31_RTOS_SDK](https://github.com/espressif/ESP31_RTOS_SDK) 🗄️ | 193 | ESP31B 용 FreeRTOS SDK(구형) |  |
| [book-esp32c3-iot-projects](https://github.com/espressif/book-esp32c3-iot-projects) | 174 | 《ESP32-C3 IoT 공정개발 실전》 책 예제 코드 |  |
| [llvm-xtensa](https://github.com/espressif/llvm-xtensa) 🗄️ | 170 | 구 LLVM-Xtensa(현 llvm-project) |  |
| [esp-idf-provisioning-ios](https://github.com/espressif/esp-idf-provisioning-ios) | 167 | ESP-IDF 프로비저닝 iOS 앱 |  |
| [crosstool-NG](https://github.com/espressif/crosstool-NG) | 152 | Xtensa 지원 crosstool-NG(툴체인 빌드) |  |
| [esp-wasmachine](https://github.com/espressif/esp-wasmachine) | 136 | WASM 앱 실행 머신 |  |
| [esp8266-rtos-sample-code](https://github.com/espressif/esp8266-rtos-sample-code) 🗄️ | 130 | ESP8266 RTOS 예제 코드 |  |
| [usb-pids](https://github.com/espressif/usb-pids) | 116 | Espressif VID 하 고객 할당 USB PID |  |
| [esp-lwip](https://github.com/espressif/esp-lwip) | 109 | lwIP 분기(ESP-IDF 패치, TCP/IP 스택) |  |
| [tensorflow](https://github.com/espressif/tensorflow) | 101 | TensorFlow 분기(ML 프레임워크) |  |
| [openocd-on-esp32](https://github.com/espressif/openocd-on-esp32) | 95 | ESP32-S3 에서 동작하는 OpenOCD 포팅 |  |
| [esp32-c3-book-en](https://github.com/espressif/esp32-c3-book-en) | 94 | ESP32-C3 책(영문) |  |
| [esp32c3-direct-boot-example](https://github.com/espressif/esp32c3-direct-boot-example) | 79 | ESP32-C3 direct boot 예제 |  |
| [svd](https://github.com/espressif/svd) | 75 | Espressif 기기 SVD 파일(레지스터 정의) |  |
| [esp8266-nonos-sample-code](https://github.com/espressif/esp8266-nonos-sample-code) 🗄️ | 67 | ESP8266 non-OS 예제 코드 |  |
| [clang-xtensa](https://github.com/espressif/clang-xtensa) 🗄️ | 61 | 구 Clang-Xtensa(현 llvm-project) |  |
| [xtensa-isa-doc](https://github.com/espressif/xtensa-isa-doc) | 57 | Xtensa ISA 문서 |  |
| [tinyusb](https://github.com/espressif/tinyusb) | 50 | tinyusb 분기(Espressif 패치, USB 스택) |  |
| [binutils-esp32ulp](https://github.com/espressif/binutils-esp32ulp) | 49 | ESP32 ULP 코프로세서용 binutils 분기 |  |
| [esp32-quake](https://github.com/espressif/esp32-quake) | 46 | ESP32-P4 평가보드용 Quake |  |
| [WROVER_KIT_LCD](https://github.com/espressif/WROVER_KIT_LCD) | 45 | ESP-WROVER-KIT LCD Arduino 라이브러리 |  |
| [esp-wdf](https://github.com/espressif/esp-wdf) | 44 | WASM 개발 프레임워크 |  |
| [newlib-esp32](https://github.com/espressif/newlib-esp32) | 38 | ESP32 ROM/IDF 용 newlib 버전(C 라이브러리) |  |
| [esp31-smsemu](https://github.com/espressif/esp31-smsemu) 🗄️ | 38 | ESP31 SMS(세가 마스터 시스템) 에뮬레이터 |  |
| [esp-joylink](https://github.com/espressif/esp-joylink) | 36 | JD joylink 데모 |  |
| [ESP8266_RTOS_ALINK_DEMO](https://github.com/espressif/ESP8266_RTOS_ALINK_DEMO) 🗄️ | 36 | Alink 1.0 데모(구형) |  |
| [esp-ppq](https://github.com/espressif/esp-ppq) | 35 | PPQ 신경망 양자화 도구(오프라인) |  |
| [esp8266-alink-v1.0](https://github.com/espressif/esp8266-alink-v1.0) 🗄️ | 32 | Alink v1.0(구형) |  |
| [esp32-alink-demo](https://github.com/espressif/esp32-alink-demo) 🗄️ | 30 | Alink 데모(embed+SDS) |  |
| [esp32-iotivity](https://github.com/espressif/esp32-iotivity) 🗄️ | 29 | ESP32 OCF/OIC(IoTivity) 지원 가이드 |  |
| [esp8266-alink-sds](https://github.com/espressif/esp8266-alink-sds) 🗄️ | 27 | Alink SDS 데모 |  |
| [mbedtls](https://github.com/espressif/mbedtls) | 26 | mbedTLS 분기(SSL 라이브러리) |  |
| [esp-hal-3rdparty](https://github.com/espressif/esp-hal-3rdparty) | 25 | HAL 3rd party 코드 |  |
| [esp-rom-elfs](https://github.com/espressif/esp-rom-elfs) | 25 | Espressif ROM 바이너리(ELF) |  |
| [esp-toolchain-docs](https://github.com/espressif/esp-toolchain-docs) | 24 | 툴체인/디버거 문서 |  |
| [developer-portal](https://github.com/espressif/developer-portal) | 23 | 개발자 포털 |  |
| [qrcode-demo](https://github.com/espressif/qrcode-demo) | 21 | QR 코드 인식 예제 |  |
| [gh-esp-test-template](https://github.com/espressif/gh-esp-test-template) | 20 | ESP 프로젝트 테스트 템플릿(CI 데모) |  |
| [esp-boost](https://github.com/espressif/esp-boost) | 19 | ESP 칩용 Boost C++ 라이브러리 |  |
| [binutils-gdb](https://github.com/espressif/binutils-gdb) | 18 | sourceware binutils-gdb 비공식 미러 |  |
| [kconfig-frontends](https://github.com/espressif/kconfig-frontends) 🗄️ | 18 | kconfig-frontends 분기(ESP-IDF) |  |
| [esp-workbench](https://github.com/espressif/esp-workbench) | 17 | ESP32 개발환경 관리 도구 |  |
| [esp-hal-components](https://github.com/espressif/esp-hal-components) | 16 | Espressif 칩 HAL 컴포넌트 |  |
| [jupyter-lite-micropython](https://github.com/espressif/jupyter-lite-micropython) | 16 | MicroPython/CircuitPython Jupyter Lite 커널 |  |
| [esp-agents-firmware](https://github.com/espressif/esp-agents-firmware) | 15 | ESP Agents 펌웨어 |  |
| [esp-win-usb-drivers](https://github.com/espressif/esp-win-usb-drivers) | 15 | Windows USB 드라이버 |  |
| [json_parser](https://github.com/espressif/json_parser) | 15 | JSMN 기반 JSON 파서 |  |
| [esp-nuttx-bootloader](https://github.com/espressif/esp-nuttx-bootloader) 🗄️ | 15 | NuttX 사용자용 2차 부트로더/파티션 바이너리 |  |
| [conventional-precommit-linter](https://github.com/espressif/conventional-precommit-linter) | 14 | conventional commit 린트 pre-commit 훅 |  |
| [gcc](https://github.com/espressif/gcc) | 14 | GCC 분기 |  |
| [github-actions](https://github.com/espressif/github-actions) 🗄️ | 14 | Espressif GitHub Actions |  |
| [clang-tidy-runner](https://github.com/espressif/clang-tidy-runner) | 13 | clang-tidy 실행 도구 |  |
| [esp32-alink](https://github.com/espressif/esp32-alink) 🗄️ | 12 | ESP32 Alink 포팅 컴포넌트 |  |
| [midi-workshop](https://github.com/espressif/midi-workshop) | 11 | ESP32-S3 USB MIDI 워크숍 자료 |  |
| [upload-components-ci-action](https://github.com/espressif/upload-components-ci-action) | 11 | 컴포넌트 레지스트리 업로드 GitHub Action |  |
| [.github](https://github.com/espressif/.github) | 10 | Espressif GitHub 메인 페이지 관리 |  |
| [Adafruit-GFX-Library](https://github.com/espressif/Adafruit-GFX-Library) | 10 | Adafruit GFX 그래픽 라이브러리(ESP32 포팅) |  |
| [Arduino-FOC](https://github.com/espressif/Arduino-FOC) | 10 | BLDC/스테퍼 모터 FOC Arduino 라이브러리 |  |
| [check-copyright](https://github.com/espressif/check-copyright) | 10 | 라이선스 SPDX 헤더 검사/추가 스크립트 |  |
| [esp-opencv-component](https://github.com/espressif/esp-opencv-component) | 10 | OpenCV ESP-IDF 컴포넌트 |  |
| [esp32-scummvm](https://github.com/espressif/esp32-scummvm) | 10 | ESP32-P4 ScummVM 포팅 |  |
| [tlsf](https://github.com/espressif/tlsf) | 10 | TLSF(메모리 할당자) ESP-IDF 패치 |  |
| [wasm-micro-runtime](https://github.com/espressif/wasm-micro-runtime) | 10 | WebAssembly Micro Runtime(WAMR) |  |
| [esp8266-dual-cloud](https://github.com/espressif/esp8266-dual-cloud) 🗄️ | 10 | ESP8266 듀얼 클라우드 데모 |  |
| [esp-bist](https://github.com/espressif/esp-bist) | 9 | Espressif 기기용 BIST(자가검사) 라이브러리 |  |
| [esp-idf-security-dashboard](https://github.com/espressif/esp-idf-security-dashboard) | 9 | ESP-IDF 보안 취약점 대시보드 |  |
| [maker-faire-cz](https://github.com/espressif/maker-faire-cz) | 9 | Maker Faire 데모 자료 |  |
| [xtensa-overlays](https://github.com/espressif/xtensa-overlays) | 9 | Xtensa 코어 설정 오버레이(툴체인 빌드) |  |
| [iwidc](https://github.com/espressif/iwidc) | 8 | ESP-IDF Web IDE 데스크톱 컴패니언 |  |
| [sphinx_idf_theme](https://github.com/espressif/sphinx_idf_theme) | 8 | ESP-IDF 문서용 Sphinx 테마 분기 |  |
| [asio](https://github.com/espressif/asio) 🗄️ | 8 | Asio C++ 라이브러리 |  |
| [eclipse-plugin-esp32](https://github.com/espressif/eclipse-plugin-esp32) 🗄️ | 8 | 구 Eclipse 플러그인(현 idf-eclipse-plugin) |  |
| [esp-nvd-mirror](https://github.com/espressif/esp-nvd-mirror) | 7 | NVD(취약점 DB) 미러 |  |
| [sync-jira-actions](https://github.com/espressif/sync-jira-actions) | 7 | Jira 동기화 GitHub Actions |  |
| [doxybook](https://github.com/espressif/doxybook) | 6 | C/C++ API 레퍼런스 Markdown 생성 |  |
| [git-mirror-server](https://github.com/espressif/git-mirror-server) | 6 | Git 미러 호스팅 서버 |  |
| [install-esp-idf-action](https://github.com/espressif/install-esp-idf-action) | 6 | 러너에 ESP-IDF 설치 GitHub Action |  |
| [json_generator](https://github.com/espressif/json_generator) | 6 | 플러시 가능한 간단 JSON 생성기 |  |
| [slidev-esp-template](https://github.com/espressif/slidev-esp-template) | 6 | Slidev 용 Espressif 템플릿 |  |
| [vscode-esp-idf-web-extension](https://github.com/espressif/vscode-esp-idf-web-extension) | 6 | VS Code 용 ESP-IDF Web 확장 |  |
| [zephyr-toolchain](https://github.com/espressif/zephyr-toolchain) | 6 | Zephyr 용 Espressif 칩 툴체인 |  |
| [innosetup-cmdlinerunner](https://github.com/espressif/innosetup-cmdlinerunner) | 5 | InnoSetup 명령 실행 확장 |  |
| [vscode-extension-codespace-test](https://github.com/espressif/vscode-extension-codespace-test) | 5 | Codespaces 에서 ESP-IDF 사용 템플릿(작업 중) |  |
| [esp32e22-fw](https://github.com/espressif/esp32e22-fw) | 4 | ESP32-E22 통합 펌웨어 |  |
| [esp_jrnl](https://github.com/espressif/esp_jrnl) | 4 | ESP-IDF 파일시스템 저널링 컴포넌트 |  |
| [developer-portal-codebase](https://github.com/espressif/developer-portal-codebase) | 3 | 개발자 포털 예제/테스트 코드 |  |
| [esp-aliro](https://github.com/espressif/esp-aliro) | 3 | ESP-Aliro(디지털 키 관련) |  |
| [esp-llvm-embedded-toolchain](https://github.com/espressif/esp-llvm-embedded-toolchain) | 3 | LLVM 기반 임베디드 툴체인 빌드 스크립트 |  |
| [esp32e22-linux-driver](https://github.com/espressif/esp32e22-linux-driver) | 3 | ESP32-E22 Linux 드라이버 모음 |  |
| [esp32s31-bt-lib](https://github.com/espressif/esp32s31-bt-lib) | 3 | 칩 BT 스택 사전 컴파일 라이브러리 |  |
| [example_components](https://github.com/espressif/example_components) | 3 | 예제 컴포넌트 |  |
| [idf-flash-vendor-patches](https://github.com/espressif/idf-flash-vendor-patches) | 3 | flash 벤더 패치 보관 |  |
| [idf_py_exe_tool](https://github.com/espressif/idf_py_exe_tool) | 3 | Windows 에서 idf.py 호출 래퍼(idf.py.exe) |  |
| [aws-quickconnect](https://github.com/espressif/aws-quickconnect) | 2 | AWS QuickConnect 예제/바이너리 |  |
| [cz-plugin-espressif](https://github.com/espressif/cz-plugin-espressif) | 2 | Commitizen Espressif 코드 스타일 플러그인 |  |
| [docs-bot-action](https://github.com/espressif/docs-bot-action) | 2 | 문서 봇 GitHub Action |  |
| [esp-docs-mdbook](https://github.com/espressif/esp-docs-mdbook) | 2 | mdBook 기반 ESP 문서 |  |
| [idf-examples-launchpad-ci-action](https://github.com/espressif/idf-examples-launchpad-ci-action) | 2 | ESP Launchpad 예제 빌드 Action |  |
| [matter_data_model_interpreter](https://github.com/espressif/matter_data_model_interpreter) | 2 | Matter 데이터 모델 인터프리터 |  |
| [opencv](https://github.com/espressif/opencv) | 2 | OpenCV(Espressif 패치) |  |
| [python-binary-action](https://github.com/espressif/python-binary-action) | 2 | Python 바이너리 GitHub Action |  |
| [sync-pr-to-gitlab](https://github.com/espressif/sync-pr-to-gitlab) | 2 | 승인된 PR 을 내부 GitLab 으로 동기화 Action |  |
| [xtensa-dynconfig](https://github.com/espressif/xtensa-dynconfig) | 2 | GNU Xtensa 툴체인 설정 플러그인 생성기 |  |
| [astyle_py](https://github.com/espressif/astyle_py) | 1 | Astyle 포매터 Python 래퍼/pre-commit 훅 |  |
| [blowfish](https://github.com/espressif/blowfish) | 1 | Hugo 블로그 테마(개인 웹사이트) |  |
| [build-and-test-esp-idf-projects-example](https://github.com/espressif/build-and-test-esp-idf-projects-example) | 1 | ESP-IDF 빌드/테스트 예제 |  |
| [build-esp-idf-projects-action](https://github.com/espressif/build-esp-idf-projects-action) | 1 | ESP-IDF 프로젝트 빌드 Action |  |
| [docker-hub-issue-test](https://github.com/espressif/docker-hub-issue-test) | 1 | Docker Hub 이슈 테스트 |  |
| [esp-bool-parser](https://github.com/espressif/esp-bool-parser) | 1 | 불리언 표현식 파서(SOC capability/환경변수 등) |  |
| [esp-btdm-linux-drv](https://github.com/espressif/esp-btdm-linux-drv) | 1 | ESP 칩 Linux Bluetooth 듀얼모드 드라이버 |  |
| [esp-idf-configdep](https://github.com/espressif/esp-idf-configdep) | 1 | ESP-IDF 설정 의존성 도구 |  |
| [esp-product-security](https://github.com/espressif/esp-product-security) | 1 | ESP 제품 보안 문서 |  |
| [esp-toolchain-bin-wrappers](https://github.com/espressif/esp-toolchain-bin-wrappers) | 1 | 툴체인 바이너리 래퍼 |  |
| [esp-xtensaconfig-lib](https://github.com/espressif/esp-xtensaconfig-lib) | 1 | Xtensa CPU 설정 런타임 로딩 플러그인 |  |
| [esp32c2-bt-lib](https://github.com/espressif/esp32c2-bt-lib) | 1 | ESP32-C2 BT 스택 사전 컴파일 라이브러리 |  |
| [esp32c5-bt-lib](https://github.com/espressif/esp32c5-bt-lib) | 1 | ESP32-C5 BT 스택 사전 컴파일 라이브러리 |  |
| [esp_weaver](https://github.com/espressif/esp_weaver) | 1 | ESP 기기 Home Assistant 통합 |  |
| [github-esp-dockerfiles](https://github.com/espressif/github-esp-dockerfiles) | 1 | 셀프호스트 러너용 Dockerfile |  |
| [libuvc](https://github.com/espressif/libuvc) | 1 | libuvc 분기(USB 비디오, Espressif 패치) |  |
| [picolibc](https://github.com/espressif/picolibc) | 1 | picolibc(임베디드 C 라이브러리) 분기 |  |
| [pytest-ignore-test-results](https://github.com/espressif/pytest-ignore-test-results) | 1 | pytest 결과 무시 플러그인 |  |
| [shared-github-dangerjs](https://github.com/espressif/shared-github-dangerjs) | 1 | 재사용 DangerJS CI 워크플로 |  |
| [skills](https://github.com/espressif/skills) | 1 | Espressif 제품/프레임워크용 에이전트 스킬 모음 |  |
| [sphinx_selective_exclude](https://github.com/espressif/sphinx_selective_exclude) | 1 | Sphinx 선택적 제외 확장 |  |
| [test-project-bot](https://github.com/espressif/test-project-bot) | 1 | 테스트 프로젝트 봇 |  |
| [TF-PSA-Crypto](https://github.com/espressif/TF-PSA-Crypto) | 0 | PSA Cryptography API 참조 구현 |  |
| [actions-internal-test](https://github.com/espressif/actions-internal-test) | 0 | GitHub Actions 내부 테스트(비공개용) |  |
| [blockdiag](https://github.com/espressif/blockdiag) | 0 | blockdiag(다이어그램 생성) |  |
| [cJSON](https://github.com/espressif/cJSON) | 0 | 초경량 ANSI C JSON 파서 |  |
| [dependency-driven-ci-action](https://github.com/espressif/dependency-driven-ci-action) | 0 | 파일 변경 기반 ESP-IDF 빌드/테스트 Action |  |
| [esp-ace](https://github.com/espressif/esp-ace) | 0 | ESP-ACE |  |
| [esp-idf-sbom-action](https://github.com/espressif/esp-idf-sbom-action) | 0 | ESP-IDF SBOM GitHub Action |  |
| [esp-idf-size-test](https://github.com/espressif/esp-idf-size-test) | 0 | esp-idf-size 테스트 |  |
| [esp-pwsh-check](https://github.com/espressif/esp-pwsh-check) | 0 | PowerShell 검사 |  |
| [esp-twai-components](https://github.com/espressif/esp-twai-components) | 0 | TWAI(CAN 호환) 컴포넌트 |  |
| [esp32c61-bt-lib](https://github.com/espressif/esp32c61-bt-lib) | 0 | ESP32-C61 BT 라이브러리 |  |
| [esp32h4-bt-lib](https://github.com/espressif/esp32h4-bt-lib) | 0 | ESP32-H4 BT 라이브러리 |  |
| [glibc](https://github.com/espressif/glibc) | 0 | glibc 분기 |  |
| [homebrew-eim](https://github.com/espressif/homebrew-eim) | 0 | EIM 용 Homebrew |  |
| [inno-download-plugin](https://github.com/espressif/inno-download-plugin) | 0 | inno-download-plugin 미러 |  |
| [network_demo](https://github.com/espressif/network_demo) | 0 | 네트워크 데모 |  |
| [no_std-training-test](https://github.com/espressif/no_std-training-test) | 0 | Rust no_std ESP 입문 가이드(분기) |  |
| [opencv_contrib](https://github.com/espressif/opencv_contrib) | 0 | OpenCV contrib 모듈(Espressif 패치) |  |
| [release-sign](https://github.com/espressif/release-sign) | 0 | 릴리스 서명 |  |
| [release-zips-action](https://github.com/espressif/release-zips-action) | 0 | 전체 소스 ZIP 생성 Action |  |
| [test-esp-idf-projects-action](https://github.com/espressif/test-esp-idf-projects-action) | 0 | ESP-IDF 프로젝트 테스트 Action |  |
| [this-month-in-esps](https://github.com/espressif/this-month-in-esps) | 0 | "This Month in ESPs"(소식 모음) |  |

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
