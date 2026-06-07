/*
 * diag_main.c
 * ===========
 * ESP32-S3 진단 펌웨어. 부팅하면 다음을 수행하고 결과를 시리얼(UART/USB)로
 * 출력한 뒤 무한 대기한다. 호스트(firmware.py)가 이 출력을 파싱한다.
 *
 *   1) 칩 정보(코어 수/모델)        -> DIAG_CHIP  {...}
 *   2) PSRAM 존재/용량              -> DIAG_PSRAM {...}
 *   3) WiFi AP 스캔(개수/최강 RSSI) -> DIAG_WIFI  {...}
 *   4) 완료 표시                    -> DIAG_DONE
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

#include "esp_chip_info.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_wifi.h"
#include "nvs_flash.h"

#if __has_include("esp_psram.h")
#include "esp_psram.h"
#define HAVE_ESP_PSRAM 1
#endif

static const char *TAG = "diag";

/* 스캔할 최대 AP 개수. */
#define MAX_AP_RECORDS 32

/* ----------------------------------------------------------------------- */
/* 칩 정보 출력                                                            */
/* ----------------------------------------------------------------------- */
static void report_chip(void)
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
    printf("DIAG_CHIP {\"cores\":%d,\"model\":\"%s\",\"revision\":%d}\n",
           info.cores, model, info.revision);
}

/* ----------------------------------------------------------------------- */
/* PSRAM 검사                                                              */
/* ----------------------------------------------------------------------- */
static void report_psram(void)
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
    printf("DIAG_PSRAM {\"present\":%s,\"size\":%u}\n",
           present ? "true" : "false", (unsigned)psram_size);
}

/* ----------------------------------------------------------------------- */
/* WiFi AP 스캔                                                            */
/* ----------------------------------------------------------------------- */
static void report_wifi(void)
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
        printf("DIAG_WIFI {\"ap_count\":%d,\"strongest_rssi\":%d}\n",
               ap_count, strongest);
    } else {
        printf("DIAG_WIFI {\"ap_count\":%d,\"strongest_rssi\":null}\n", ap_count);
    }
    return;

fail:
    ESP_LOGE(TAG, "WiFi scan failed: %s", esp_err_to_name(err));
    printf("DIAG_WIFI {\"ap_count\":0,\"strongest_rssi\":null,\"error\":\"%s\"}\n",
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

    /* 호스트 파서가 시작을 인지할 수 있도록 약간 대기 후 출력. */
    vTaskDelay(pdMS_TO_TICKS(300));

    printf("\nDIAG_START\n");
    report_chip();
    report_psram();
    report_wifi();
    printf("DIAG_DONE\n");
    fflush(stdout);

    /* 결과 출력 후 유휴 상태로 대기. */
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
