/*
 * diag_main.c
 * ===========
 * ESP32-S3 진단 펌웨어. 부팅하면 아래 검사를 "한 번만" 수행해 결과 문자열을
 * 만들어 두고, 그 결과를 시리얼(UART/USB)로 "주기적으로 반복" 출력한다.
 * 호스트(firmware.py)가 이 출력을 파싱한다.
 *
 *   1) 칩 정보(코어 수/모델)        -> DIAG_CHIP   {...}
 *   2) PSRAM 존재/용량              -> DIAG_PSRAM  {...}
 *   3) RGB LED(WS2812) 점등 테스트  -> DIAG_LED    {...}
 *   4) BOOT 버튼(GPIO0) 입력 확인   -> DIAG_BUTTON {...}
 *   5) WiFi AP 스캔(개수/최강 RSSI) -> DIAG_WIFI   {...}
 *   6) 완료 표시                    -> DIAG_DONE
 *
 * 한 사이클은 "DIAG_START -> 각 결과 라인 -> DIAG_DONE" 이며, 약 2초마다 반복된다.
 * 이렇게 반복 출력하는 이유: flash 직후 보드가 재부팅하며 결과를 즉시 뱉는데,
 * 호스트가 그 시점에 아직 시리얼을 열지 못했으면 앞쪽 라인(특히 DIAG_PSRAM)을
 * 놓친다. 반복 출력하면 호스트가 언제 연결하든 완전한 한 사이클을 받을 수 있다.
 * (검사 자체는 부팅 시 1회만 수행하므로 LED 는 한 번만 점등, WiFi 도 1회만 스캔.)
 *
 * 출력 형식은 "DIAG_<KEY> <json>\n" 한 줄. 파싱이 쉽도록 일반 로그(ESP_LOGI)는
 * 최소화하고 결과 라인은 printf로 직접 출력한다.
 *
 * ESP-IDF 5.x 기준. 빌드/플래시 방법은 firmware/README.md 참고.
 */

#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "driver/gpio.h"
#include "esp_chip_info.h"
#include "esp_event.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "led_strip.h"
#include "nvs_flash.h"

#if __has_include("esp_psram.h")
#include "esp_psram.h"
#define HAVE_ESP_PSRAM 1
#endif

static const char *TAG = "diag";

/* 스캔할 최대 AP 개수. */
#define MAX_AP_RECORDS 32

/* YD-ESP32-S3 (V1.4) 보드 핀 배치. */
#define RGB_LED_GPIO     48  /* 온보드 WS2812 RGB LED */
#define BOOT_BUTTON_GPIO 0   /* BOOT 버튼(부팅 후 일반 입력으로 사용 가능) */

/* ----------------------------------------------------------------------- */
/* 칩 정보 출력                                                            */
/* ----------------------------------------------------------------------- */
static void report_chip(char *out, size_t n)
{
    esp_chip_info_t info;
    esp_chip_info(&info);

    const char *model = "UNKNOWN";
    switch (info.model) {
        case CHIP_ESP32:   model = "ESP32";    break;
        case CHIP_ESP32S2: model = "ESP32-S2"; break;
        case CHIP_ESP32S3: model = "ESP32-S3"; break;
        case CHIP_ESP32C3: model = "ESP32-C3"; break;
        default:           model = "UNKNOWN";  break;
    }
    /* DIAG_CHIP {"cores":2,"model":"ESP32-S3","revision":2} */
    snprintf(out, n, "DIAG_CHIP {\"cores\":%d,\"model\":\"%s\",\"revision\":%d}",
             info.cores, model, info.revision);
}

/* ----------------------------------------------------------------------- */
/* PSRAM 검사                                                              */
/* ----------------------------------------------------------------------- */
static void report_psram(char *out, size_t n)
{
    size_t psram_size = 0;
    int present = 0;

#ifdef HAVE_ESP_PSRAM
    /* ESP-IDF 5.x: esp_psram_is_initialized() / esp_psram_get_size() */
    if (esp_psram_is_initialized()) {
        present = 1;
        psram_size = esp_psram_get_size();
    }
#endif

    /* 폴백: heap_caps로 SPIRAM 용량을 직접 조회(메뉴얼 초기화 환경 대비). */
    if (!present) {
        size_t caps_total = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
        if (caps_total > 0) {
            present = 1;
            psram_size = caps_total;
        }
    }

    /* DIAG_PSRAM {"present":true,"size":8388608} */
    snprintf(out, n, "DIAG_PSRAM {\"present\":%s,\"size\":%u}",
             present ? "true" : "false", (unsigned)psram_size);
}

/* ----------------------------------------------------------------------- */
/* RGB LED(WS2812) 점등 테스트                                             */
/*  - led_strip(RMT 백엔드)로 LED를 초기화하고 R->G->B 순서로 점등한다.    */
/*  - 초기화/점등 API가 모두 성공하면 ok=true. 실제 발광은 육안 확인용.    */
/* ----------------------------------------------------------------------- */
/* RGB LED(WS2812) 핸들. 초기 점등 검사 후에도 해제하지 않고 유지해, app_main
 * 루프에서 계속 순환 점등(R->G->B->R...)하는 데 재사용한다. 초기화 실패 시 NULL. */
static led_strip_handle_t g_led_strip = NULL;

static void report_led(char *out, size_t n)
{
    int ok = 0;

    led_strip_config_t strip_cfg = {
        .strip_gpio_num = RGB_LED_GPIO,
        .max_leds = 1,
        .led_pixel_format = LED_PIXEL_FORMAT_GRB,  /* WS2812 는 GRB 순서 */
        .led_model = LED_MODEL_WS2812,
        .flags = { .invert_out = false },
    };
    led_strip_rmt_config_t rmt_cfg = {
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 10 * 1000 * 1000,  /* 10MHz */
        .flags = { .with_dma = false },
    };

    esp_err_t err = led_strip_new_rmt_device(&strip_cfg, &rmt_cfg, &g_led_strip);
    if (err == ESP_OK && g_led_strip != NULL) {
        ok = 1;
        /* 초기 R -> G -> B 순차 점등(낮은 밝기 30/255)으로 육안 확인.
         * led_strip_del 하지 않고 핸들을 유지해, app_main 루프가 계속 순환시킨다. */
        const uint8_t colors[3][3] = {
            {30, 0, 0}, {0, 30, 0}, {0, 0, 30},
        };
        for (int i = 0; i < 3; i++) {
            led_strip_set_pixel(g_led_strip, 0, colors[i][0], colors[i][1], colors[i][2]);
            led_strip_refresh(g_led_strip);
            vTaskDelay(pdMS_TO_TICKS(250));
        }
    } else {
        ESP_LOGE(TAG, "LED init failed: %s", esp_err_to_name(err));
        g_led_strip = NULL;
    }

    /* DIAG_LED {"ok":true,"gpio":48} */
    snprintf(out, n, "DIAG_LED {\"ok\":%s,\"gpio\":%d}", ok ? "true" : "false", RGB_LED_GPIO);
}

/* ----------------------------------------------------------------------- */
/* BOOT 버튼(GPIO0) 입력 테스트                                            */
/*  - 내부 풀업으로 입력 설정 후 유휴 레벨을 읽는다(정상이면 1).           */
/*  - 짧은 윈도우 동안 눌림(0)도 감지해 부가 정보로 보고한다.             */
/* ----------------------------------------------------------------------- */
static void report_button(char *out, size_t n)
{
    gpio_config_t io = {
        .pin_bit_mask = 1ULL << BOOT_BUTTON_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io);

    int idle = gpio_get_level(BOOT_BUTTON_GPIO);

    /* 약 0.5초간 눌림 여부 폴링(인터랙션은 선택). */
    int pressed = 0;
    for (int i = 0; i < 10; i++) {
        if (gpio_get_level(BOOT_BUTTON_GPIO) == 0) {
            pressed = 1;
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }

    /* DIAG_BUTTON {"idle_level":1,"pressed_now":false,"gpio":0} */
    snprintf(out, n, "DIAG_BUTTON {\"idle_level\":%d,\"pressed_now\":%s,\"gpio\":%d}",
             idle, pressed ? "true" : "false", BOOT_BUTTON_GPIO);
}

/* ----------------------------------------------------------------------- */
/* WiFi AP 스캔                                                            */
/* ----------------------------------------------------------------------- */
static void report_wifi(char *out, size_t n)
{
    int ap_count = -1;
    int strongest = 0;
    int have_rssi = 0;
    esp_err_t err;

    /* WiFi 스택 초기화(STA 모드). */
    err = esp_netif_init();
    if (err != ESP_OK) { goto fail; }
    err = esp_event_loop_create_default();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) { goto fail; }
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    err = esp_wifi_init(&cfg);
    if (err != ESP_OK) { goto fail; }
    err = esp_wifi_set_mode(WIFI_MODE_STA);
    if (err != ESP_OK) { goto fail; }
    err = esp_wifi_start();
    if (err != ESP_OK) { goto fail; }

    /* 블로킹 스캔(전 채널). */
    wifi_scan_config_t scan_cfg = { 0 };
    err = esp_wifi_scan_start(&scan_cfg, true);
    if (err != ESP_OK) { goto fail; }

    uint16_t num = MAX_AP_RECORDS;
    static wifi_ap_record_t records[MAX_AP_RECORDS];
    err = esp_wifi_scan_get_ap_records(&num, records);
    if (err != ESP_OK) { goto fail; }

    ap_count = num;
    for (int i = 0; i < num; i++) {
        if (!have_rssi || records[i].rssi > strongest) {
            strongest = records[i].rssi;
            have_rssi = 1;
        }
    }

    /* DIAG_WIFI {"ap_count":15,"strongest_rssi":-42} */
    if (have_rssi) {
        snprintf(out, n, "DIAG_WIFI {\"ap_count\":%d,\"strongest_rssi\":%d}",
                 ap_count, strongest);
    } else {
        snprintf(out, n, "DIAG_WIFI {\"ap_count\":%d,\"strongest_rssi\":null}", ap_count);
    }
    return;

fail:
    ESP_LOGE(TAG, "WiFi scan failed: %s", esp_err_to_name(err));
    snprintf(out, n, "DIAG_WIFI {\"ap_count\":0,\"strongest_rssi\":null,\"error\":\"%s\"}",
             esp_err_to_name(err));
}

/* ----------------------------------------------------------------------- */
/* 진입점                                                                  */
/* ----------------------------------------------------------------------- */
void app_main(void)
{
    /* NVS 초기화(WiFi 스택이 요구). */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    /* 부팅 직후 약간 대기(주변장치 안정화). */
    vTaskDelay(pdMS_TO_TICKS(300));

    /* --- 검사는 한 번만 수행하고 결과 문자열을 보관한다. ---
     * LED 는 한 번만 점등, WiFi 도 한 번만 스캔한다(아래 반복 루프에서 재실행 안 함).
     */
    static char chip_line[160];
    static char psram_line[160];
    static char led_line[160];
    static char button_line[160];
    static char wifi_line[200];

    report_chip(chip_line, sizeof(chip_line));
    report_psram(psram_line, sizeof(psram_line));
    report_led(led_line, sizeof(led_line));
    report_button(button_line, sizeof(button_line));
    report_wifi(wifi_line, sizeof(wifi_line));

    /* --- 보관한 결과를 약 2초마다 반복 출력한다. ---
     * flash 직후 호스트가 언제 시리얼을 열든 완전한 한 사이클
     * (DIAG_START ... DIAG_DONE)을 받을 수 있도록 한다. 호스트(firmware.py)는
     * DIAG_START 를 본 뒤의 DIAG_DONE 만 완전한 사이클로 인정한다.
     */
    /* RGB LED 순환용 색 테이블(R->G->B). 매 사이클 한 단계씩 전진시킨다. */
    const uint8_t cycle_colors[3][3] = {
        {30, 0, 0}, {0, 30, 0}, {0, 0, 30},
    };
    int color_idx = 0;

    while (1) {
        printf("\nDIAG_START\n");
        printf("%s\n", chip_line);
        printf("%s\n", psram_line);
        printf("%s\n", led_line);
        printf("%s\n", button_line);
        printf("%s\n", wifi_line);
        printf("DIAG_DONE\n");
        fflush(stdout);

        /* RGB LED 를 계속 순환 점등(R->G->B->R...)해 동작을 눈으로 쉽게 확인한다.
         * (PWR LED 는 하드웨어 전원 표시등이라 제어 불가, TX LED 는 위 시리얼
         *  출력 때마다 자동으로 깜빡인다.) */
        if (g_led_strip != NULL) {
            led_strip_set_pixel(g_led_strip, 0,
                                cycle_colors[color_idx][0],
                                cycle_colors[color_idx][1],
                                cycle_colors[color_idx][2]);
            led_strip_refresh(g_led_strip);
            color_idx = (color_idx + 1) % 3;
        }

        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}
