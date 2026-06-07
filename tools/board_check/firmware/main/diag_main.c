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
#include "freertos/event_groups.h"
#include "freertos/task.h"

#include "driver/gpio.h"
#include "driver/temperature_sensor.h"
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

/* Bluetooth LE (NimBLE) — BT 활성 빌드에서만 포함. */
#ifdef CONFIG_BT_NIMBLE_ENABLED
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "host/ble_gap.h"
#include "host/util/util.h"
#endif

/* WiFi 접속 테스트용 자격증명. step01_build_diag_firmware.sh 가 config.yaml 에서
 * 읽어 wifi_credentials.h 로 생성한다(빌드 시 주입, gitignore 처리). 헤더가 없거나
 * 값이 비어 있으면 접속 테스트는 생략(SKIP)된다. */
#if __has_include("wifi_credentials.h")
#include "wifi_credentials.h"
#endif
#ifndef DIAG_WIFI_SSID
#define DIAG_WIFI_SSID ""
#endif
#ifndef DIAG_WIFI_PASSWORD
#define DIAG_WIFI_PASSWORD ""
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
/* 버튼 상태 전역: 유휴 레벨과 "부팅 후 한 번이라도 눌림" 래치.
 * 호스트의 대화형 버튼 검사(--button-test)가 ever_pressed 를 감시한다. */
static int g_button_idle = 1;
static volatile int g_button_ever_pressed = 0;

/* 현재 버튼 상태로 DIAG_BUTTON 라인을 구성(눌림은 active-low: 0 이면 눌림). */
static void build_button_line(char *out, size_t n)
{
    int pressed_now = (gpio_get_level(BOOT_BUTTON_GPIO) == 0);
    if (pressed_now) {
        g_button_ever_pressed = 1;
    }
    /* DIAG_BUTTON {"idle_level":1,"pressed_now":false,"ever_pressed":false,"gpio":0} */
    snprintf(out, n,
             "DIAG_BUTTON {\"idle_level\":%d,\"pressed_now\":%s,"
             "\"ever_pressed\":%s,\"gpio\":%d}",
             g_button_idle, pressed_now ? "true" : "false",
             g_button_ever_pressed ? "true" : "false", BOOT_BUTTON_GPIO);
}

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

    g_button_idle = gpio_get_level(BOOT_BUTTON_GPIO);

    /* 초기 약 0.5초 눌림 폴링(부팅 중 눌려 있으면 래치). */
    for (int i = 0; i < 10; i++) {
        if (gpio_get_level(BOOT_BUTTON_GPIO) == 0) {
            g_button_ever_pressed = 1;
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }

    build_button_line(out, n);
}

/* JSON 문자열 값에 안전하도록 ", \\, 제어문자를 이스케이프해 dst 로 복사한다.
 * (WiFi SSID 등 외부 문자열을 JSON 으로 내보낼 때 사용.) */
static void json_escape(const char *src, char *dst, size_t dst_n)
{
    size_t j = 0;
    for (size_t i = 0; src[i] != '\0' && j + 2 < dst_n; i++) {
        unsigned char c = (unsigned char)src[i];
        if (c == '"' || c == '\\') {
            dst[j++] = '\\';
            dst[j++] = (char)c;
        } else if (c < 0x20) {
            dst[j++] = ' ';  /* 제어문자는 공백으로 단순 치환 */
        } else {
            dst[j++] = (char)c;
        }
    }
    dst[j] = '\0';
}

/* ----------------------------------------------------------------------- */
/* WiFi AP 스캔                                                            */
/*  - 전 채널 스캔 후 요약(개수/최강 RSSI)과 AP 목록(ssid/rssi/채널)을 출력.*/
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

    /* DIAG_WIFI {"ap_count":15,"strongest_rssi":-42,
     *            "aps":[{"ssid":"AP","rssi":-42,"ch":6}, ...]} */
    int off = snprintf(out, n, "DIAG_WIFI {\"ap_count\":%d,", ap_count);
    if (have_rssi) {
        off += snprintf(out + off, (off < (int)n) ? n - off : 0,
                        "\"strongest_rssi\":%d,\"aps\":[", strongest);
    } else {
        off += snprintf(out + off, (off < (int)n) ? n - off : 0,
                        "\"strongest_rssi\":null,\"aps\":[");
    }
    for (int i = 0; i < num; i++) {
        char ssid_esc[80];
        json_escape((const char *)records[i].ssid, ssid_esc, sizeof(ssid_esc));
        off += snprintf(out + off, (off < (int)n) ? n - off : 0,
                        "%s{\"ssid\":\"%s\",\"rssi\":%d,\"ch\":%d}",
                        i ? "," : "", ssid_esc, records[i].rssi, records[i].primary);
        if (off >= (int)n - 4) { break; }  /* 버퍼 한계 방지(이후 AP 생략) */
    }
    snprintf(out + off, (off < (int)n) ? n - off : 0, "]}");
    return;

fail:
    ESP_LOGE(TAG, "WiFi scan failed: %s", esp_err_to_name(err));
    snprintf(out, n, "DIAG_WIFI {\"ap_count\":0,\"strongest_rssi\":null,\"error\":\"%s\"}",
             esp_err_to_name(err));
}

/* ----------------------------------------------------------------------- */
/* WiFi 접속 테스트 (config.yaml 자격증명)                                 */
/*  - report_wifi() 가 STA 모드로 WiFi 를 이미 start 한 상태에서 호출된다.  */
/*  - DIAG_WIFI_SSID 가 비어 있으면(자격증명 미설정) attempted=false 로     */
/*    보고하고 생략. 설정돼 있으면 접속 시도 후 IP 획득 여부를 보고한다.    */
/* ----------------------------------------------------------------------- */
#define WIFI_CONN_OK_BIT   BIT0
#define WIFI_CONN_FAIL_BIT BIT1

static EventGroupHandle_t s_wifi_conn_eg;
static char s_wifi_ip[16];
static int s_wifi_retry;

static void wifi_conn_event_handler(void *arg, esp_event_base_t base,
                                    int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        /* 최대 3회 재시도 후 실패 처리(잘못된 비밀번호/범위 밖 등). */
        if (s_wifi_retry < 3) {
            s_wifi_retry++;
            esp_wifi_connect();
        } else {
            xEventGroupSetBits(s_wifi_conn_eg, WIFI_CONN_FAIL_BIT);
        }
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)data;
        snprintf(s_wifi_ip, sizeof(s_wifi_ip), IPSTR, IP2STR(&event->ip_info.ip));
        xEventGroupSetBits(s_wifi_conn_eg, WIFI_CONN_OK_BIT);
    }
}

static void report_wifi_connect(char *out, size_t n)
{
    const char *ssid = DIAG_WIFI_SSID;
    const char *pw = DIAG_WIFI_PASSWORD;

    /* 자격증명 미설정 — 접속 테스트 생략(호스트가 SKIP 처리). */
    if (ssid[0] == '\0') {
        snprintf(out, n, "DIAG_WIFI_CONNECT {\"attempted\":false}");
        return;
    }

    s_wifi_conn_eg = xEventGroupCreate();
    s_wifi_retry = 0;
    s_wifi_ip[0] = '\0';

    esp_event_handler_instance_t inst_wifi, inst_ip;
    esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                        &wifi_conn_event_handler, NULL, &inst_wifi);
    esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                        &wifi_conn_event_handler, NULL, &inst_ip);

    wifi_config_t wc = { 0 };
    strncpy((char *)wc.sta.ssid, ssid, sizeof(wc.sta.ssid) - 1);
    strncpy((char *)wc.sta.password, pw, sizeof(wc.sta.password) - 1);
    esp_wifi_set_config(WIFI_IF_STA, &wc);
    esp_wifi_connect();

    /* IP 획득 또는 실패까지 최대 ~12초 대기. */
    EventBits_t bits = xEventGroupWaitBits(
        s_wifi_conn_eg, WIFI_CONN_OK_BIT | WIFI_CONN_FAIL_BIT,
        pdFALSE, pdFALSE, pdMS_TO_TICKS(12000));

    char ssid_esc[80];
    json_escape(ssid, ssid_esc, sizeof(ssid_esc));
    if (bits & WIFI_CONN_OK_BIT) {
        /* DIAG_WIFI_CONNECT {"attempted":true,"connected":true,"ssid":"..","ip":"x.x.x.x"} */
        snprintf(out, n,
                 "DIAG_WIFI_CONNECT {\"attempted\":true,\"connected\":true,"
                 "\"ssid\":\"%s\",\"ip\":\"%s\"}",
                 ssid_esc, s_wifi_ip);
    } else {
        snprintf(out, n,
                 "DIAG_WIFI_CONNECT {\"attempted\":true,\"connected\":false,"
                 "\"ssid\":\"%s\",\"ip\":null}",
                 ssid_esc);
    }

    /* 정리. */
    esp_event_handler_instance_unregister(IP_EVENT, IP_EVENT_STA_GOT_IP, inst_ip);
    esp_event_handler_instance_unregister(WIFI_EVENT, ESP_EVENT_ANY_ID, inst_wifi);
    esp_wifi_disconnect();
    vEventGroupDelete(s_wifi_conn_eg);
}

/* ----------------------------------------------------------------------- */
/* BLE 스캔 (NimBLE)                                                       */
/*  - NimBLE 호스트를 초기화하고 약 5초간 BLE 광고를 수동(passive) 스캔해   */
/*    주변 기기 개수/목록(주소·RSSI·이름)을 보고한다. ESP32-S3 는 BLE 전용. */
/* ----------------------------------------------------------------------- */
#ifdef CONFIG_BT_NIMBLE_ENABLED

#define BLE_MAX_DEV       24
#define BLE_SCAN_DONE_BIT BIT0
#define BLE_SCAN_MS       5000

typedef struct {
    uint8_t addr[6];
    int rssi;
    char name[32];
} ble_dev_t;

static EventGroupHandle_t s_ble_eg;
static ble_dev_t s_ble_devs[BLE_MAX_DEV];
static int s_ble_count;

static int ble_gap_event(struct ble_gap_event *event, void *arg)
{
    if (event->type == BLE_GAP_EVENT_DISC) {
        const uint8_t *a = event->disc.addr.val;
        /* 이미 본 주소면 RSSI 만 갱신(중복 광고 제거). */
        for (int i = 0; i < s_ble_count; i++) {
            if (memcmp(s_ble_devs[i].addr, a, 6) == 0) {
                s_ble_devs[i].rssi = event->disc.rssi;
                return 0;
            }
        }
        if (s_ble_count < BLE_MAX_DEV) {
            ble_dev_t *d = &s_ble_devs[s_ble_count];
            memcpy(d->addr, a, 6);
            d->rssi = event->disc.rssi;
            d->name[0] = '\0';
            struct ble_hs_adv_fields fields;
            if (ble_hs_adv_parse_fields(&fields, event->disc.data,
                                        event->disc.length_data) == 0) {
                if (fields.name != NULL && fields.name_len > 0) {
                    int ln = fields.name_len < 31 ? fields.name_len : 31;
                    memcpy(d->name, fields.name, ln);
                    d->name[ln] = '\0';
                }
            }
            s_ble_count++;
        }
    } else if (event->type == BLE_GAP_EVENT_DISC_COMPLETE) {
        xEventGroupSetBits(s_ble_eg, BLE_SCAN_DONE_BIT);
    }
    return 0;
}

static void ble_on_sync(void)
{
    uint8_t own_addr_type;
    if (ble_hs_id_infer_auto(0, &own_addr_type) != 0) {
        own_addr_type = BLE_OWN_ADDR_PUBLIC;
    }
    struct ble_gap_disc_params disc = { 0 };
    disc.passive = 1;            /* 수동 스캔(광고만 수신). */
    disc.filter_duplicates = 0;  /* 중복은 호스트 코드에서 직접 제거. */
    ble_gap_disc(own_addr_type, BLE_SCAN_MS, &disc, ble_gap_event, NULL);
}

static void ble_host_task(void *param)
{
    nimble_port_run();             /* nimble_port_stop() 호출 시까지 블로킹. */
    nimble_port_freertos_deinit();
}

static void report_ble(char *out, size_t n)
{
    s_ble_count = 0;
    s_ble_eg = xEventGroupCreate();

    esp_err_t err = nimble_port_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "nimble_port_init failed: %s", esp_err_to_name(err));
        snprintf(out, n,
                 "DIAG_BLE {\"ok\":false,\"devices\":0,\"list\":[],\"error\":\"init\"}");
        vEventGroupDelete(s_ble_eg);
        return;
    }
    ble_hs_cfg.sync_cb = ble_on_sync;
    nimble_port_freertos_init(ble_host_task);

    /* 스캔 완료까지 대기(스캔 시간 + 여유). */
    xEventGroupWaitBits(s_ble_eg, BLE_SCAN_DONE_BIT, pdFALSE, pdFALSE,
                        pdMS_TO_TICKS(BLE_SCAN_MS + 3000));

    /* NimBLE 정지/해제(다음 검사·반복 출력에 영향 없도록). */
    if (nimble_port_stop() == 0) {
        nimble_port_deinit();
    }
    vEventGroupDelete(s_ble_eg);

    /* JSON: 요약 + 기기 목록(addr/rssi/name). */
    int off = snprintf(out, n, "DIAG_BLE {\"ok\":true,\"devices\":%d,\"list\":[",
                       s_ble_count);
    for (int i = 0; i < s_ble_count; i++) {
        char name_esc[64];
        json_escape(s_ble_devs[i].name, name_esc, sizeof(name_esc));
        const uint8_t *a = s_ble_devs[i].addr;
        /* NimBLE 주소는 리틀엔디안 — 사람이 읽는 순서로 뒤집어 표기. */
        off += snprintf(out + off, (off < (int)n) ? n - off : 0,
                        "%s{\"addr\":\"%02x:%02x:%02x:%02x:%02x:%02x\","
                        "\"rssi\":%d,\"name\":\"%s\"}",
                        i ? "," : "", a[5], a[4], a[3], a[2], a[1], a[0],
                        s_ble_devs[i].rssi, name_esc);
        if (off >= (int)n - 4) { break; }
    }
    snprintf(out + off, (off < (int)n) ? n - off : 0, "]}");
}

#else  /* BT 비활성 빌드 폴백 */
static void report_ble(char *out, size_t n)
{
    snprintf(out, n, "DIAG_BLE {\"ok\":false,\"devices\":0,\"list\":[],\"error\":\"BT disabled\"}");
}
#endif

/* ----------------------------------------------------------------------- */
/* 내장 온도센서                                                           */
/*  - ESP32-S3 내장 temperature sensor 를 설치/활성화해 칩 온도를 읽는다.  */
/*  - 동작 자체(설치+읽기 성공) 확인이 목적. 절대값은 칩 다이 온도라 실온  */
/*    보다 높게(보통 30~50도) 나오는 게 정상.                              */
/* ----------------------------------------------------------------------- */
static void report_temp(char *out, size_t n)
{
    int ok = 0;
    float celsius = 0.0f;

    temperature_sensor_handle_t ts = NULL;
    /* 측정 범위 10~80도(센서가 자동으로 적절한 레인지를 고른다). */
    temperature_sensor_config_t ts_cfg = TEMPERATURE_SENSOR_CONFIG_DEFAULT(10, 80);

    esp_err_t err = temperature_sensor_install(&ts_cfg, &ts);
    if (err == ESP_OK) {
        err = temperature_sensor_enable(ts);
    }
    if (err == ESP_OK) {
        err = temperature_sensor_get_celsius(ts, &celsius);
        if (err == ESP_OK) {
            ok = 1;
        }
    }
    if (ts != NULL) {
        temperature_sensor_disable(ts);
        temperature_sensor_uninstall(ts);
    }

    if (ok) {
        /* DIAG_TEMP {"ok":true,"celsius":42.5} */
        snprintf(out, n, "DIAG_TEMP {\"ok\":true,\"celsius\":%.1f}", celsius);
    } else {
        ESP_LOGE(TAG, "temp sensor failed: %s", esp_err_to_name(err));
        snprintf(out, n, "DIAG_TEMP {\"ok\":false,\"celsius\":null,\"error\":\"%s\"}",
                 esp_err_to_name(err));
    }
}

/* ----------------------------------------------------------------------- */
/* GPIO 일괄 점검                                                          */
/*  - 자유롭게 쓸 수 있는(주변장치/스트래핑/플래시/PSRAM/USB 가 아닌) GPIO */
/*    들을 대상으로, 내부 풀업/풀다운을 걸고 입력으로 읽어 핀이 의도대로   */
/*    HIGH/LOW 로 동작하는지 확인한다(외부 배선 없이 가능한 비침습 검사).  */
/*  - 풀업→1, 풀다운→0 이 모두 맞으면 그 핀은 정상으로 본다.              */
/* ----------------------------------------------------------------------- */
static void report_gpio(char *out, size_t n)
{
    /* 안전한 자유 GPIO 목록(YD-ESP32-S3 N16R8 기준).
     * 제외: 0(BOOT), 3/45/46(스트래핑), 19/20(USB), 26~37(플래시/Octal PSRAM),
     *       43/44(UART TX/RX), 48(RGB LED). */
    static const int pins[] = {
        1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 21, 38, 47,
    };
    const int num_pins = sizeof(pins) / sizeof(pins[0]);

    int tested = 0;
    int passed = 0;
    char failed[96];
    failed[0] = '\0';

    for (int i = 0; i < num_pins; i++) {
        int pin = pins[i];
        gpio_config_t io = {
            .pin_bit_mask = 1ULL << pin,
            .mode = GPIO_MODE_INPUT,
            .pull_up_en = GPIO_PULLUP_ENABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
            .intr_type = GPIO_INTR_DISABLE,
        };
        if (gpio_config(&io) != ESP_OK) {
            continue;  /* 설정 자체 실패한 핀은 집계에서 제외 */
        }
        tested++;
        vTaskDelay(pdMS_TO_TICKS(2));
        int hi = gpio_get_level(pin);  /* 풀업 → 1 기대 */

        /* 풀다운으로 바꿔 0 기대. */
        io.pull_up_en = GPIO_PULLUP_DISABLE;
        io.pull_down_en = GPIO_PULLDOWN_ENABLE;
        gpio_config(&io);
        vTaskDelay(pdMS_TO_TICKS(2));
        int lo = gpio_get_level(pin);  /* 풀다운 → 0 기대 */

        if (hi == 1 && lo == 0) {
            passed++;
        } else {
            /* 실패한 핀 번호를 목록에 추가(외부 배선이 연결된 핀은 여기 잡힐 수 있음). */
            char tmp[8];
            snprintf(tmp, sizeof(tmp), "%s%d", failed[0] ? "," : "", pin);
            strncat(failed, tmp, sizeof(failed) - strlen(failed) - 1);
        }
    }

    /* DIAG_GPIO {"ok":true,"tested":20,"passed":20,"failed":[]} */
    snprintf(out, n,
             "DIAG_GPIO {\"ok\":%s,\"tested\":%d,\"passed\":%d,\"failed\":[%s]}",
             (passed == tested && tested > 0) ? "true" : "false",
             tested, passed, failed);
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
    static char wifi_line[2048];  /* AP 목록(ssid/rssi/ch)까지 담으므로 크게 */
    static char wifi_conn_line[200];
    static char ble_line[2048];   /* 기기 목록(addr/rssi/name)까지 담으므로 크게 */
    static char temp_line[160];
    static char gpio_line[200];

    report_chip(chip_line, sizeof(chip_line));
    report_psram(psram_line, sizeof(psram_line));
    report_led(led_line, sizeof(led_line));
    report_button(button_line, sizeof(button_line));
    report_wifi(wifi_line, sizeof(wifi_line));
    report_wifi_connect(wifi_conn_line, sizeof(wifi_conn_line));
    report_ble(ble_line, sizeof(ble_line));
    report_temp(temp_line, sizeof(temp_line));
    report_gpio(gpio_line, sizeof(gpio_line));

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
        printf("%s\n", wifi_conn_line);
        printf("%s\n", ble_line);
        printf("%s\n", temp_line);
        printf("%s\n", gpio_line);
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

        /* 2초 대기 동안 BOOT 버튼을 50ms 간격으로 폴링해 눌림을 놓치지 않는다.
         * (호스트의 대화형 버튼 검사가 다음 사이클의 ever_pressed 로 확인) */
        for (int t = 0; t < 40; t++) {
            if (gpio_get_level(BOOT_BUTTON_GPIO) == 0) {
                g_button_ever_pressed = 1;
            }
            vTaskDelay(pdMS_TO_TICKS(50));
        }
        build_button_line(button_line, sizeof(button_line));
    }
}
