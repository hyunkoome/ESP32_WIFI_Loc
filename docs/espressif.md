# Espressif 생태계 가이드

이 프로젝트가 쓰는 칩(ESP32-S3)과 도구(ESP-IDF, esptool)는 모두 **Espressif**
에서 나옵니다. 이 문서는 Espressif 가 무엇이고, GitHub
([github.com/espressif](https://github.com/espressif))에 어떤 저장소가 있으며,
그중 **우리 프로젝트와 직접 관련된 것**이 무엇인지 정리합니다.

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

## 우리 프로젝트와 직접 관련된 저장소

지금(진단 도구) 또는 다음 단계(CSI 수집)에서 실제로 쓰거나 참고할 핵심입니다.

| 저장소 | 무엇 | 우리 쓰임새 |
|--------|------|-------------|
| [esp-idf](https://github.com/espressif/esp-idf) | ESP32 공식 C/C++ 개발 프레임워크(SDK). `idf.py`·툴체인·FreeRTOS·드라이버 포함 | 진단 펌웨어 빌드. [`scripts/install_esp_idf.sh`](../scripts/install_esp_idf.sh) 가 `~/esp/esp-idf` 로 clone |
| [esptool](https://github.com/espressif/esptool) | 칩에 펌웨어를 굽고(flash) 칩/Flash 정보를 읽는 Python 도구 | 진단 도구 핵심 의존성([`requirements.txt`](../tools/board_check/requirements.txt)). 부트로더/Flash/칩 ID 검사 |
| [esp-csi](https://github.com/espressif/esp-csi) | **WiFi CSI**(Channel State Information) 수집·응용 예제 | **Phase 2(CSI 수집)의 핵심 참고 자료** — presence/motion 등 |
| [esp-dl](https://github.com/espressif/esp-dl) | ESP32-S3 on-device 딥러닝 추론 라이브러리 | (선택) CSI 추론을 보드에서 직접 돌릴 때 |

> ESP-IDF 와 esptool 의 **버전 체계가 다른 이유**(예: ESP-IDF 5.4 vs esptool
> 5.3.0)는 [루트 README 의 버전 이야기](../README.md) 참고. 둘은 별개 도구입니다.

---

## 그 밖의 주요 저장소 (참고)

당장은 안 쓰지만 ESP32 생태계에서 자주 보게 되는 것들.

| 저장소 | 무엇 |
|--------|------|
| [arduino-esp32](https://github.com/espressif/arduino-esp32) | Arduino 코어 — Arduino IDE/PlatformIO 에서 ESP32 개발 |
| [esp-iot-solution](https://github.com/espressif/esp-iot-solution) | 센서/디스플레이/USB 등 주변장치 드라이버·예제 모음 |
| [esp-bsp](https://github.com/espressif/esp-bsp) | 보드 지원 패키지(개발보드별 디스플레이/버튼 등 묶음) |
| [esp-who](https://github.com/espressif/esp-who) | 얼굴인식 등 ESP32 영상 AI 프레임워크 |
| [esp-adf](https://github.com/espressif/esp-adf) | 오디오 개발 프레임워크 |
| [esp-rainmaker](https://github.com/espressif/esp-rainmaker) | 클라우드 연동 IoT 플랫폼(앱/프로비저닝) |
| [esp-dsp](https://github.com/espressif/esp-dsp) | ESP32 최적화 DSP(FFT 등) 라이브러리 — CSI 신호처리에 유용할 수 있음 |
| [esp-protocols](https://github.com/espressif/esp-protocols) | mDNS/ASIO/MQTT 등 네트워크 프로토콜 컴포넌트 |

> ESP-IDF 의 **managed components**(`idf.py` 가 자동으로 받는 외부 컴포넌트)는
> Espressif Component Registry([components.espressif.com](https://components.espressif.com))
> 에서 옵니다. 실제로 우리 펌웨어 빌드 시
> [`firmware/managed_components/`](../tools/board_check/firmware/managed_components/)
> 아래로 받아집니다.

---

## CSI 란 (Phase 2 미리보기)

**CSI(Channel State Information)** 는 WiFi 신호가 송신기→수신기로 전파되며 겪는
채널 특성(부반송파별 진폭·위상)입니다. 사람이 움직이면 전파 경로가 바뀌고 CSI 가
변하므로, 이를 분석해 **존재 감지·움직임·호흡·제스처·실내 위치 추정**을 할 수
있습니다 — 본 프로젝트의 최종 목표입니다.

ESP32-S3 는 펌웨어에서 CSI 콜백을 등록해 패킷마다 CSI 를 뽑을 수 있고,
[esp-csi](https://github.com/espressif/esp-csi) 가 그 수집/시각화 예제를
제공합니다. Phase 2 에서 이 저장소를 기반으로 수집 펌웨어를 구성할 예정입니다.

---

## 관련 문서

- [설치 가이드](install.md) — ESP-IDF/esptool 설치 순서
- [펌웨어 가이드](firmware-guide.md) — MicroPython / ESP-IDF 펌웨어
- [Python 환경 두 개](python-environments.md) — 프로젝트 venv vs ESP-IDF venv
- [보드 진단 도구](../tools/board_check/README.md) — 현재 단계 진단 도구
