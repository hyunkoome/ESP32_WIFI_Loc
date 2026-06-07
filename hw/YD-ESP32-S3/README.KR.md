# YD-ESP32-S3 코어 보드

[English](README.md) | **한국어** | [中文](README.CH.md)

### 소개

YD-ESP32-S3 코어 보드는 源地工作室(VCC-GND Studio)에서 설계했습니다. 구매가 필요하면
www.vcc-gnd.com 에서 확인할 수 있습니다. 이 보드는 ESP32-S3 칩을 사용하며, IoT 응용의
프로토타입 제작은 물론 실제 제품 적용에도 쓸 수 있습니다. **USB Type-C 포트가 2개** 있는데,
하나는 하드웨어 USB-to-UART 변환기(CH343P, 제조사 WCH / 沁恒)이고, 다른 하나는 ESP32-S3의
네이티브 USB 포트입니다.

![](IMG/img1.PNG)

이 안내서는 YD-ESP32-S3 를 빠르게 시작할 수 있도록 돕고, 이 개발 보드에 대한 자세한 정보를
제공합니다.

YD-ESP32-S3 는 Wi-Fi + Bluetooth® LE 모듈인 ESP32-S3-WROOM-1 을 탑재한 입문용 개발
보드입니다.

모듈의 대부분 핀이 보드 양쪽의 핀 헤더로 인출되어 있어, 개발자는 필요에 따라 점퍼선으로 다양한
주변 장치를 쉽게 연결하거나, 보드를 브레드보드에 꽂아 사용할 수 있습니다.

![img](IMG/YD-ESP32-S3.PNG)

1. 이것은 Espressif 의 ESP32-S3 모듈을 사용한 최소 구성의 ESP32-S3 코어 보드입니다.
2. 무선 기능 전용 LDO 회로를 갖추고 있어 전류(전력) 부족을 걱정할 필요가 없습니다.
3. WS2812 RGB LED 가 1개 있습니다(주의: GPIO 로직 레벨로 직접 켜는 방식이 **아니라**,
   주소 지정이 가능한(addressable) LED 입니다).
4. RST 버튼은 외부 리셋용이며, BOOT 버튼은 (RST 버튼과 함께 누르면) 칩을 부트로더(다운로드)
   모드로 진입시킬 수 있고, 리셋 이후에는 사용자 버튼으로 쓸 수 있습니다 — GPIO0 입니다.
5. 보드에 **Type-C 포트가 2개** 있는 것을 알 수 있는데, 하나는 직결 USB(GPIO19 / GPIO20)이고,
   다른 하나는 하드웨어 USB-to-UART 브리지 칩(CH343)을 사용하는 USB-to-UART 포트입니다.

### 하드웨어 소개

![](IMG/img2.PNG)

| 주요 구성 요소 | 설명 |
| :------------ | ---- |
| ESP32-S3-WROOM-1 | ESP32-S3-WROOM-1 은 범용 Wi-Fi + 저전력 Bluetooth MCU 모듈로, 풍부한 주변장치 인터페이스와 강력한 신경망 연산 능력 및 신호 처리 능력을 갖추고 있으며, AI 및 AIoT 시장을 겨냥해 설계되었습니다. ESP32-S3-WROOM-1 은 PCB 온보드 안테나를 사용합니다. |
| 5 V to 3.3 V LDO | 전원 변환기. 입력 5 V, 출력 3.3 V, 전류 1 A. |
| 핀 헤더(Pin Headers) | flash 의 SPI 버스를 제외한 모든 사용 가능한 GPIO 핀이 보드의 핀 헤더로 인출되어 있습니다. |
| USB-to-UART 포트 | Type-C USB 포트. 보드 전원 공급, 칩에 펌웨어 다운로드, 온보드 USB-to-UART 브리지를 통한 칩과의 통신에 사용할 수 있습니다. |
| BOOT 버튼 | 다운로드 버튼. **BOOT** 키를 누른 채 **Reset** 키를 한 번 누르면 "펌웨어 다운로드" 모드로 진입하여 시리얼 포트로 펌웨어를 다운로드할 수 있습니다. 부팅이 끝난 뒤에는 일반 입력 버튼으로 사용할 수 있으며, 사용되는 IO 는 GPIO0 입니다. |
| Reset 버튼 | 리셋 버튼. |
| USB 포트 | ESP32-S3 USB OTG 포트로, 풀 스피드 USB 1.1 표준을 지원합니다. 이 네이티브 USB 포트는 보드 전원 공급, 펌웨어 다운로드, USB 프로토콜을 통한 칩 통신, JTAG 디버깅에 사용할 수 있습니다. |
| USB-to-UART 브리지 | 칩은 CH343P 이며 제조사는 沁恒(WCH)입니다. 웹사이트: http://www.wch-ic.com/ — 드라이버: http://www.wch-ic.com/products/CH343.html |
| RGB LED | GPIO48 로 구동되는 주소 지정 가능 RGB LED. 모델은 WS2812. |
| PWR LED | 전원 표시등. 보드에 전원이 들어오면 켜지며, 프로그램으로 제어할 수 없습니다. |
| TX LED | ESP32-S3 의 시리얼 TXD 라인에 있는 LED. 시리얼 데이터가 송신될 때 깜빡입니다. 시리얼 기능을 쓰지 않으면 GPIO 로 사용할 수 있습니다 — GPIO43. |
| RX LED | ESP32-S3 의 시리얼 RXD 라인에 있는 LED. 시리얼 데이터가 수신될 때 깜빡입니다. 시리얼 기능을 쓰지 않으면 GPIO 로 사용할 수 있습니다 — GPIO44. |

### 참고

8선(옥탈) SPI flash/PSRAM 을 사용하는 ESP32-S3-WROOM-1 모듈 시리즈를 탑재한 개발 보드에서는
핀 **GPIO35, GPIO36, GPIO37** 이 ESP32-S3 칩과 SPI flash/PSRAM 사이의 내부 통신에 사용되므로
**외부에서 사용할 수 없습니다**.

### 개발 시작 전에

전원을 넣기 전에 개발 보드가 손상 없이 온전한지 확인하세요.

### 기능 블록 다이어그램

YD-ESP32-S3 의 주요 구성 요소와 연결 방식은 아래 그림과 같습니다:

![](IMG/img4.png)

### 두 개의 USB-C 포트 (왼쪽 vs 오른쪽)

보드 하단 가장자리에 USB-C 포트가 두 개 나란히 있습니다. 두 포트는 **서로 호환되지 않습니다** —
각각 다른 칩에 연결되며 용도가 다릅니다.

> **방향 기준:** 부품면(앞면)이 자신을 향하게 하고, 두 USB-C 커넥터가 **아래쪽** 가장자리에 오도록
> 보드를 잡으세요. 각 커넥터 옆의 실크스크린 라벨(**USB** 와 **COM**)이 가장 확실한 기준이므로,
> 보드 레이아웃이 다르면 "왼쪽/오른쪽"보다 라벨을 믿으세요.

| | 왼쪽 포트 | 오른쪽 포트 |
|---|---|---|
| 실크스크린 라벨 | **USB** | **COM** (UART) |
| 연결 대상 | ESP32-S3 **네이티브 USB** (USB-Serial-JTAG), GPIO19 (D−) / GPIO20 (D+) | **CH343P** USB-to-UART 브리지 |
| Linux 장치 | `/dev/ttyACM*` | `/dev/ttyACM*` (CH343) |
| VID:PID | `303a:1001` (다운로드 모드에선 `303a:4001`) | `1A86:55D3` |
| 플래시 자동 리셋 | USB-Serial-JTAG 경유 | DTR/RTS 회로 경유 (가장 안정적) |
| JTAG 디버깅 | ✅ 가능 | ❌ 불가 |

**왼쪽 포트(네이티브 USB — "USB")를 쓸 때:**

- ESP32-S3 JTAG 디버깅 (JTAG 은 이 포트로만 가능).
- USB 디바이스 기능 개발 (HID, MSC, CDC, TinyUSB 등).
- **펌웨어가 GPIO19 / GPIO20 을 재설정하지 않는다면** 빠른 플래시 / 모니터링.
- 주의: 애플리케이션이 USB 핀(GPIO19 / GPIO20)이나 USB 주변장치를 점유하면 이 포트의 시리얼
  연결이 끊길 수 있습니다. 그럴 땐 수동 다운로드 모드(**BOOT** 누른 채 **RST** 탭 후 **BOOT** 뗌)로
  플래시해야 할 수 있습니다.

**오른쪽 포트(USB-to-UART — "COM")를 쓸 때:**

- **펌웨어 플래시와 시리얼 로그 확인**에 가장 안정적인 선택: CH343 이 자동 리셋(DTR/RTS) 회로를
  구동하므로, **버튼을 누르지 않아도** esptool 이 부트로더에 진입할 수 있습니다.
- 애플리케이션이 네이티브 USB 핀(GPIO19 / GPIO20)을 다른 용도로 쓰더라도 시리얼 로깅이 계속
  동작합니다.
- 기본 개발 / 플래시 포트로 권장. (JTAG 불가.)

**권장:** 일상적인 플래시와 `idf.py monitor` / 시리얼 로깅에는 **오른쪽(COM / UART)** 포트를
사용하세요. JTAG 디버깅이나 USB 디바이스 기능이 특별히 필요할 때만 **왼쪽(네이티브 USB)** 포트를
사용하세요.

### 전원 옵션

다음 세 가지 방식 중 하나를 선택해 보드에 전원을 공급할 수 있습니다:

- USB-to-UART 포트로 전원 공급, 또는 ESP32-S3 네이티브 USB 포트로 전원 공급(둘 중 하나 또는
  둘 다 동시 공급). 기본 공급 방식(**권장**).
- **5V** 와 **G (GND)** 핀 헤더로 전원 공급.
- **3V3** 와 **G (GND)** 핀 헤더로 전원 공급.

### 핀 헤더

아래 표는 보드 양쪽 핀 헤더(P1 과 P2)의 **이름**과 **기능**을 정리한 것입니다. 핀 헤더의 이름은
YD-ESP32-S3 정면도에 표시되어 있으며, 핀 헤더의 번호는 개발 보드 회로도(PDF)와 일치합니다.

#### P1

| 번호 | 이름 | 타입  | 기능 |
| ---- | ---- | ----- | ---- |
| 1    | 3V3  | P     | 3.3 V 전원 |
| 2    | 3V3  | P     | 3.3 V 전원 |
| 3    | RST  | I     | EN |
| 4    | 4    | I/O/T | RTC_GPIO4, GPIO4, TOUCH4, ADC1_CH3 |
| 5    | 5    | I/O/T | RTC_GPIO5, GPIO5, TOUCH5, ADC1_CH4 |
| 6    | 6    | I/O/T | RTC_GPIO6, GPIO6, TOUCH6, ADC1_CH5 |
| 7    | 7    | I/O/T | RTC_GPIO7, GPIO7, TOUCH7, ADC1_CH6 |
| 8    | 15   | I/O/T | RTC_GPIO15, GPIO15, U0RTS, ADC2_CH4, XTAL_32K_P |
| 9    | 16   | I/O/T | RTC_GPIO16, GPIO16, U0CTS, ADC2_CH5, XTAL_32K_N |
| 10   | 17   | I/O/T | RTC_GPIO17, GPIO17, U1TXD, ADC2_CH6 |
| 11   | 18   | I/O/T | RTC_GPIO18, GPIO18, U1RXD, ADC2_CH7, CLK_OUT3 |
| 12   | 8    | I/O/T | RTC_GPIO8, GPIO8, TOUCH8, ADC1_CH7, SUBSPICS1 |
| 13   | 3    | I/O/T | RTC_GPIO3, GPIO3, TOUCH3, ADC1_CH2 |
| 14   | 46   | I/O/T | GPIO46 |
| 15   | 9    | I/O/T | RTC_GPIO9, GPIO9, TOUCH9, ADC1_CH8, FSPIHD, SUBSPIHD |
| 16   | 10   | I/O/T | RTC_GPIO10, GPIO10, TOUCH10, ADC1_CH9, FSPICS0, FSPIIO4, SUBSPICS0 |
| 17   | 11   | I/O/T | RTC_GPIO11, GPIO11, TOUCH11, ADC2_CH0, FSPID, FSPIIO5, SUBSPID |
| 18   | 12   | I/O/T | RTC_GPIO12, GPIO12, TOUCH12, ADC2_CH1, FSPICLK, FSPIIO6, SUBSPICLK |
| 19   | 13   | I/O/T | RTC_GPIO13, GPIO13, TOUCH13, ADC2_CH2, FSPIQ, FSPIIO7, SUBSPIQ |
| 20   | 14   | I/O/T | RTC_GPIO14, GPIO14, TOUCH14, ADC2_CH3, FSPIWP, FSPIDQS, SUBSPIWP |
| 21   | 5V   | P     | 5 V 전원 |
| 22   | G    | G     | 접지(GND) |

#### P2

| 번호 | 이름 | 타입  | 기능 |
| ---- | ---- | ----- | ---- |
| 1    | G    | G     | 접지(GND) |
| 2    | TX   | I/O/T | U0TXD, GPIO43, CLK_OUT1 |
| 3    | RX   | I/O/T | U0RXD, GPIO44, CLK_OUT2 |
| 4    | 1    | I/O/T | RTC_GPIO1, GPIO1, TOUCH1, ADC1_CH0 |
| 5    | 2    | I/O/T | RTC_GPIO2, GPIO2, TOUCH2, ADC1_CH1 |
| 6    | 42   | I/O/T | MTMS, GPIO42 |
| 7    | 41   | I/O/T | MTDI, GPIO41, CLK_OUT1 |
| 8    | 40   | I/O/T | MTDO, GPIO40, CLK_OUT2 |
| 9    | 39   | I/O/T | MTCK, GPIO39, CLK_OUT3, SUBSPICS1 |
| 10   | 38   | I/O/T | GPIO38, FSPIWP, SUBSPIWP |
| 11   | 37   | I/O/T | SPIDQS, GPIO37, FSPIQ, SUBSPIQ |
| 12   | 36   | I/O/T | SPIIO7, GPIO36, FSPICLK, SUBSPICLK |
| 13   | 35   | I/O/T | SPIIO6, GPIO35, FSPID, SUBSPID |
| 14   | 0    | I/O/T | RTC_GPIO0, GPIO0 |
| 15   | 45   | I/O/T | GPIO45 |
| 16   | 48   | I/O/T | GPIO48, SPICLK_N, SUBSPICLK_N_DIFF, RGB LED |
| 17   | 47   | I/O/T | GPIO47, SPICLK_P, SUBSPICLK_P_DIFF |
| 18   | 21   | I/O/T | RTC_GPIO21, GPIO21 |
| 19   | 20   | I/O/T | RTC_GPIO20, GPIO20, U1CTS, ADC2_CH9, CLK_OUT1, USB_D+ |
| 20   | 19   | I/O/T | RTC_GPIO19, GPIO19, U1RTS, ADC2_CH8, CLK_OUT2, USB_D- |
| 21   | G    | G     | 접지(GND) |
| 22   | G    | G     | 접지(GND) |

**P**: 전원(Power); **I**: 입력(Input); **O**: 출력(Output); **T**: 고임피던스(하이임피던스)로
설정 가능(tri-state).

### 핀 배치도

![](IMG/img11.jpg)

### CH340 칩 드라이버 공식 링크

- 영문: http://www.wch-ic.com/products/CH340.html
- 중문: https://www.wch.cn/products/CH340.html?from=list

### MicroPython 펌웨어 다운로드

Windows 에서 Espressif 의 flash 다운로드 도구(`flash_download_tool_3.9.2_0`)를 사용해
ESP32-S3 에 펌웨어를 굽거나 지웁니다.

**참고:** 설치가 필요 없습니다 — 압축만 풀면 바로 사용할 수 있습니다. 톱니바퀴 아이콘을 더블
클릭하고 **ESP32-S3**, **develop**, **USART** 를 선택한 뒤 스크린샷을 참고하세요. 시작 주소는
반드시 **0x00** 이어야 하며, 그 앞의 체크박스를 체크해야 합니다. 다운로드가 안 되면
USB-to-UART 드라이버가 제대로 설치되지 않았을 수 있으니, 드라이버 문제를 먼저 해결한 뒤 다시
다운로드하세요.

![](IMG/img3.png)

**중요:**

Thonny 에 내장된 이른바 "ESP32 다운로더"로 ESP32-S3 에 MicroPython 펌웨어를 굽지 **마세요**
(Thonny 내장 도구는 ESP32-S3 가 아니라 ESP32 용입니다 — 주소도 S3 의 0x00 이 아니라 ESP32 의
0x1000 입니다). 또한 MicroPython 공식에서 제공하는 PSRAM 포함 펌웨어도 사용하지 **마세요**.
구운 뒤 정상 동작하지 않습니다.

올바른 방법은 Espressif 공식 flash 도구를 사용하는 것입니다: **ESP32-S3** 시리얼 다운로드
(**USART**)를 선택하고, 보드의 COM 포트 USB 를 꽂은 뒤, 해당 펌웨어(VCC-GND 에서 개조한
펌웨어)를 선택하고, 시작 주소를 **0x00** 으로 설정하고, 펌웨어 앞의 체크박스를 체크한 다음,
가급적 **지운 뒤 다운로드**하세요.

사용 전에 CH343 USB-to-UART 하드웨어 드라이버를 한 번 업데이트하는 것이 좋습니다. 장치 관리자에서
"...CH343..." 글자가 표시된 COM 포트가 나타나는지 확인하세요.

**Tasmota** 펌웨어를 다운로드하려면 Tasmota 공식의 web 설치 도구를 사용할 수 있습니다:
https://tasmota.github.io/docs/

자신의 펌웨어 파일을 다운로드하려면 Espressif 의 다운로드 도구를 사용할 수 있습니다:
https://www.espressif.com.cn/en/home

ESP32-S3 관련 자료(CH343 하드웨어 시리얼 드라이버, VCC-GND 버전 MicroPython 펌웨어, 펌웨어
다운로드 소프트웨어, MicroPython IDE, 회로도/치수도 등): http://124.222.62.86/yd-data/YD-ESP32-S3/

- Espressif 공식 **ESP-IDF (C 언어)** 로 프로그래밍할 계획이라면, 상세 자료 링크(예제가 곧 API
  레퍼런스 역할):
  https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/get-started/index.html
- **Arduino** 로 프로그래밍할 계획이라면:
  https://docs.espressif.com/projects/arduino-esp32/en/latest/getting_started.html
- **MicroPython** 으로 프로그래밍할 계획이라면(빠른 시작은 ESP32 가이드만 봐도 충분):
  https://docs.micropython.org/en/latest/esp32/quickref.html

### 짝퉁/가품/저질 모방품 문제

저희 源地(YD) 개발 보드를 짝퉁·가품·저질로 모방한 제품이 많으며, 특히 선전 화창베이(深圳华强北)에서
가장 기승을 부립니다. 모방업자들은 보통 저희 보드의 인쇄를 갈아낸 뒤 사진을 찍어 보드를 그대로
베끼는데, 그 결과 짝퉁 제품은 위험 요소가 가득합니다. YD-ESP32(ESP32/S2/S3/C3) 시리즈를 예로 들어,
짝퉁 보드 구매의 위험(잠재 문제)을 정리합니다:

1. 짝퉁 제조사는 이윤을 더 좇기 위해 재생·비공식 부품을 사용하고, 같은 패키지의 값싼 모델로
   임의 교체하며, 마구잡이로 부품을 골라 이윤을 챙깁니다.
2. WS2812 LED 의 신호선을 납땜하지 않아 WS2812 를 쓸 수 없습니다. 이는 모방자가 보드를 검사하지
   않고 손쉽게 비용을 줄인다는 방증입니다.
3. 짝퉁 보드는 출고 시 검사하지 않고(비용 절감), 생산 라인에서 나오자마자 포장해 소비자에게
   보냅니다. 공정을 생략해 이윤을 챙기는 것입니다.
4. 사진을 베끼다 보니 여러 곳의 실크스크린(인쇄)이 잘못 베껴져 소비자를 오도하기 쉽습니다.
   모방자 본인도 제대로 이해하지 못합니다.
5. 짝퉁 보드가 베낀 것은 2022년 초기 버전인 1.2 버전이고, 정품은 1.4 버전입니다. 짝퉁은 더 새로운
   기능을 쓸 수 없습니다. 개선 없이 손쉽게만 가는 것입니다.
6. 짝퉁 보드는 제3자 "짝퉁" 모듈(저비용)을 사용하는데, 이 모듈은 임피던스 매칭을 거치지 않아,
   Wi-Fi·Bluetooth 사용 시 소비 전력이 높고 신호가 나쁘며 쉽게 멈춥니다.
7. 시중에서 저희가 쓰는 전용 LDO 를 구할 수 없으니, 짝퉁 보드는 1117 같은 부적합한 모델(저비용)을
   임의로 고릅니다. 이런 모델은 드롭아웃이 커서 쉽게 멈추고 신호가 나쁩니다.
8. 짝퉁 보드는 고드롭아웃 다이오드(순방향 전압 강하 0.7V 초과, 저비용)를 사용해, 후단 LDO 의
   여유 전압이 부족해지고, 결과적으로 소비 전력이 높아지고 쉽게 멈추며 신호가 나빠집니다.
9. 짝퉁 보드는 기본적인 기술 지원을 제공하지 않으며, 자료조차 저희 것을 그대로 복사합니다(그것도
   저희 초기 자료이며, 최신 자료는 모방자가 찾을 생각도 안 합니다). 돈을 받고 나면 나 몰라라 합니다.
10. 짝퉁 보드는 때때로 부팅에 문제가 생겨 바로 부트로더로 진입해 사용할 수 없게 됩니다. 모방자는
    이것이 무슨 문제인지조차 이해하지 못합니다!
11. 모방자는 사진을 보고 베끼다 보니 회로도가 없어, 사용자가 어떻게 사용해야 할지 알 수 없게
    만듭니다. 모방자 본인도 이해하지 못해 제품을 쓰기 어렵게 만듭니다.

일부 모방자는 짝퉁 보드에 "YD-ESP32" 등의 문구를 직접 인쇄해 소비자를 혼란시키고, 심지어 저희
공식 웹사이트인 WWW.VCC-GND.COM 을 짝퉁 모방품에 인쇄하기까지 합니다. 이런 행위는 이미 관련 법률을
위반한 것이며, 저희는 반드시 책임을 묻겠습니다. 소비자 여러분께서는 몇 푼의 일시적 이득을 탐하여
위와 같은 온갖 위험을 떠안고 시간과 노력을 헛되이 낭비하지 마시기 바랍니다. 源地(VCC-GND)와 정품을
지지해 주시고, 구매 시 源地, VCC-GND 상표를 꼭 확인하세요.

### 내부 스위칭 매트릭스를 통해 핀에 임의 기능 할당 가능

각종 ESP32 시리즈 문서 소개에는 I2C, I2S, UART, SPI 등 다양한 주변장치 통신 기능을 갖추고 있다고
명시되어 있습니다. 그런데 기능 핀 배치도에는 이 기능들이 어느 핀에 해당하는지 표시되어 있지
않습니다. 이 의문은 주변장치 핀 배정에서 해소되는데, I2C, I2S, UART, SPI 등의 주변장치 인터페이스는
**임의의 GPIO 핀**으로 정의할 수 있습니다. 따라서 기능 배치도에 따로 표시할 필요가 없습니다.
어차피 어떤 GPIO 든 이 주변장치 인터페이스(I2C, I2S, UART, SPI)에 필요한 핀 기능을 부여할 수 있기
때문입니다.
