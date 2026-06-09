/*
 * SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
 * SPDX-License-Identifier: Apache-2.0
 *
 * csi_recv — 통합 CSI 수신(rx). 두 신호원의 CSI 를 수집해 출력하고, 호스트(웹/GUI)가
 * mac 으로 신호원을 골라(router/tx/all) 분석한다(재flash 불필요).
 *   - tx(ESP-NOW): broadcast peer → tx MAC(1a:00:..) 의 CSI (부팅 즉시)
 *   - 라우터(AP):  호스트가 'WIFI_CONNECT <ssid>\t<pw>' 시리얼 명령을 보내면 그 AP 로
 *                  STA 접속 + 게이트웨이 ping → 라우터 BSSID 의 CSI
 *
 * ⚠ 자격증명을 펌웨어/빌드에 박지 않는다(board_check diag_main.c 와 동일한 런타임 주입).
 *   호스트가 cli_wifi_config.yaml 을 읽거나 사용자가 직접 입력해 WIFI_CONNECT 로 보낸다.
 * ⚠ 채널: 라우터에 접속하면 그 채널로 고정된다. tx(ESP-NOW)도 같은 채널이어야 동시
 *   수신된다(라우터 채널 ≠ tx 채널이면 라우터만 보임).
 *
 * 출처: espressif/esp-csi get-started csi_recv / csi_recv_router (Apache-2.0) 통합 +
 *       board_check diag_main.c 의 WIFI_CONNECT 런타임 주입 패턴.
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "nvs_flash.h"
#include "esp_mac.h"
#include "rom/ets_sys.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "esp_event.h"
#include "esp_now.h"
#include "driver/uart.h"

#include "lwip/inet.h"
#include "ping/ping_sock.h"
#include "esp_csi_gain_ctrl.h"

#define CONFIG_LESS_INTERFERENCE_CHANNEL  11   /* 라우터 미접속 시 ESP-NOW 채널 */
#define CONFIG_WIFI_BANDWIDTH             WIFI_BW_HT40
#define CONFIG_PING_FREQUENCY             100   /* 라우터 ping Hz */
#define CONFIG_FORCE_GAIN                 0
#if CONFIG_IDF_TARGET_ESP32S3 || CONFIG_IDF_TARGET_ESP32C3
#define CONFIG_GAIN_CONTROL               1
#endif
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(6, 0, 0)
#define ESP_IF_WIFI_STA ESP_MAC_WIFI_STA
#endif

static const char *TAG = "csi_recv";
/* tx(csi_send) 의 고정 MAC. 호스트는 이 mac 으로 'tx' 신호를 구분한다. */
static const uint8_t TX_MAC[6] = {0x1a, 0x00, 0x00, 0x00, 0x00, 0x00};

static uint8_t s_ap_bssid[6] = {0};
static bool s_have_bssid = false;
static esp_ping_handle_t s_ping = NULL;

/* ---- CSI 콜백: 라우터 BSSID 또는 tx MAC 의 패킷만 출력(나머지 무시) ---- */
static void wifi_csi_rx_cb(void *ctx, wifi_csi_info_t *info)
{
    if (!info || !info->buf) {
        return;
    }
    bool is_tx = (memcmp(info->mac, TX_MAC, 6) == 0);
    bool is_router = (s_have_bssid && memcmp(info->mac, s_ap_bssid, 6) == 0);
    if (!is_tx && !is_router) {
        return;
    }

    const wifi_pkt_rx_ctrl_t *rx_ctrl = &info->rx_ctrl;
    static int s_count = 0;
    float compensate_gain = 1.0f;
    static uint8_t agc_gain = 0;
    static int8_t fft_gain = 0;
#if CONFIG_GAIN_CONTROL
    static uint8_t agc_gain_baseline = 0;
    static int8_t fft_gain_baseline = 0;
    esp_csi_gain_ctrl_get_rx_gain(rx_ctrl, &agc_gain, &fft_gain);
    if (s_count < 100) {
        esp_csi_gain_ctrl_record_rx_gain(agc_gain, fft_gain);
    } else if (s_count == 100) {
        esp_csi_gain_ctrl_get_rx_gain_baseline(&agc_gain_baseline, &fft_gain_baseline);
#if CONFIG_FORCE_GAIN
        esp_csi_gain_ctrl_set_rx_force_gain(agc_gain_baseline, fft_gain_baseline);
#endif
    }
    esp_csi_gain_ctrl_get_gain_compensation(&compensate_gain, agc_gain, fft_gain);
    ESP_LOGD(TAG, "compensate_gain %f, agc_gain %d, fft_gain %d", compensate_gain, agc_gain, fft_gain);
#endif

    if (!s_count) {
        ESP_LOGI(TAG, "================ CSI RECV ================");
        ets_printf("type,id,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_format,len,first_word,data\n");
    }
    /* mac 컬럼으로 호스트가 신호원(tx=1a:00.. / router=AP BSSID)을 구분한다. */
    ets_printf("CSI_DATA,%d," MACSTR ",%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d",
               s_count, MAC2STR(info->mac), rx_ctrl->rssi, rx_ctrl->rate, rx_ctrl->sig_mode,
               rx_ctrl->mcs, rx_ctrl->cwb, rx_ctrl->smoothing, rx_ctrl->not_sounding,
               rx_ctrl->aggregation, rx_ctrl->stbc, rx_ctrl->fec_coding, rx_ctrl->sgi,
               rx_ctrl->noise_floor, rx_ctrl->ampdu_cnt, rx_ctrl->channel, rx_ctrl->secondary_channel,
               rx_ctrl->timestamp, rx_ctrl->ant, rx_ctrl->sig_len, rx_ctrl->sig_mode);
    /* compensate_gain 은 약신호(RSSI 낮음)에서 0 에 가까워(예: 0.002) raw 를 0 으로
     * 반올림시킨다 — 라우터 CSI 가 전부 0 으로 보이던 원인. 시각화에는 raw buf 를 그대로
     * 출력한다(거리별 정규화가 필요하면 2차에서 호스트가 한다). */
    ets_printf(",%d,%d,\"[%d", info->len, info->first_word_invalid, info->buf[0]);
    for (int i = 1; i < info->len; i++) {
        ets_printf(",%d", info->buf[i]);
    }
    ets_printf("]\"\n");

    s_count++;
}

static void wifi_csi_init(void)
{
    /* LLTF 중심: 라우터 ping 응답(legacy/non-HT)과 tx(HT) 둘 다 LLTF 부분의 CSI 를
     * 받는다. HT-LTF(htltf_en)를 켜면 legacy 패킷에서 그 부분이 0 으로 채워져 raw_csi
     * 가 전부 0 이 되는 문제가 있었다(원본 csi_recv_router 와 동일 설정으로 수정). */
    wifi_csi_config_t csi_config = {
        .lltf_en           = true,
        .htltf_en          = false,
        .stbc_htltf2_en    = false,
        .ltf_merge_en      = true,
        .channel_filter_en = true,
        .manu_scale        = true,
        .shift             = true,
    };
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));  /* ESP-NOW + 라우터 둘 다 */
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(wifi_csi_rx_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
}

static void esp_now_setup(void)
{
    ESP_ERROR_CHECK(esp_now_init());
    ESP_ERROR_CHECK(esp_now_set_pmk((uint8_t *)"pmk1234567890123"));
    esp_now_peer_info_t peer = {
        .channel = 0,  /* 0 = 현재 채널 */
        .ifidx   = WIFI_IF_STA,
        .encrypt = false,
        .peer_addr = {0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
    };
    ESP_ERROR_CHECK(esp_now_add_peer(&peer));
}

/* GOT_IP 후 라우터 게이트웨이로 주기 ping(CSI 트리거)을 시작한다. */
static void wifi_ping_router_start(void)
{
    if (s_ping) {
        esp_ping_stop(s_ping);
        esp_ping_delete_session(s_ping);
        s_ping = NULL;
    }
    esp_ping_config_t ping_config = ESP_PING_DEFAULT_CONFIG();
    ping_config.count           = 0;
    ping_config.interval_ms     = 1000 / CONFIG_PING_FREQUENCY;
    ping_config.task_stack_size = 3072;
    ping_config.data_size       = 1;

    esp_netif_ip_info_t local_ip;
    esp_netif_get_ip_info(esp_netif_get_handle_from_ifkey("WIFI_STA_DEF"), &local_ip);
    ESP_LOGI(TAG, "got ip:" IPSTR ", gw:" IPSTR, IP2STR(&local_ip.ip), IP2STR(&local_ip.gw));
    ping_config.target_addr.u_addr.ip4.addr = ip4_addr_get_u32(&local_ip.gw);
    ping_config.target_addr.type = ESP_IPADDR_TYPE_V4;

    esp_ping_callbacks_t cbs = {0};
    esp_ping_new_session(&ping_config, &cbs, &s_ping);
    esp_ping_start(s_ping);
}

static void wifi_event_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        s_have_bssid = false;  /* 라우터 CSI 중단(tx 는 계속). 사용자가 재명령. */
        ESP_LOGW(TAG, "라우터 연결 끊김");
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        wifi_ap_record_t ap;
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
            memcpy(s_ap_bssid, ap.bssid, 6);
            s_have_bssid = true;
            ESP_LOGI(TAG, "라우터 접속 — BSSID " MACSTR " ch=%d", MAC2STR(s_ap_bssid), ap.primary);
        }
        wifi_ping_router_start();
        ets_printf("CSI_WIFI {\"connected\":true}\n");
    }
}

/* 런타임 라우터 접속: 호스트의 WIFI_CONNECT 명령에서 호출. */
static void connect_router(const char *ssid, const char *pw)
{
    s_have_bssid = false;
    /* STA 연결 라우터 CSI 는 promiscuous 를 꺼야 받힌다. promiscuous=true(ESP-NOW 용)인
     * 채로 STA 연결 CSI 를 받으면 raw buf 가 전부 0 으로 나오는 문제가 있었다. */
    esp_wifi_set_promiscuous(false);
    wifi_config_t wc = {0};
    strncpy((char *)wc.sta.ssid, ssid, sizeof(wc.sta.ssid) - 1);
    strncpy((char *)wc.sta.password, pw, sizeof(wc.sta.password) - 1);
    esp_wifi_set_config(WIFI_IF_STA, &wc);
    esp_wifi_disconnect();
    esp_wifi_connect();  /* 결과는 wifi_event_handler(GOT_IP/DISCONNECTED) 에서 */
    ESP_LOGI(TAG, "라우터 접속 시도: \"%s\"", ssid);
}

/* ---- 런타임 시리얼 명령(board_check 패턴): "WIFI_CONNECT <ssid>\t<pw>" ---- */
static void handle_command(const char *line)
{
    /* 라우터 연결을 끊고 ESP-NOW 채널로 복귀 — tx 신호원으로 돌아갈 때. */
    if (strcmp(line, "WIFI_DISCONNECT") == 0) {
        s_have_bssid = false;
        if (s_ping) {
            esp_ping_stop(s_ping);
            esp_ping_delete_session(s_ping);
            s_ping = NULL;
        }
        esp_wifi_disconnect();
        esp_wifi_set_channel(CONFIG_LESS_INTERFERENCE_CHANNEL, WIFI_SECOND_CHAN_BELOW);
        esp_wifi_set_promiscuous(true);  /* ESP-NOW(tx) 다시 수신 */
        ets_printf("CSI_WIFI {\"connected\":false}\n");
        return;
    }
    const char *prefix = "WIFI_CONNECT ";
    size_t plen = strlen(prefix);
    if (strncmp(line, prefix, plen) != 0) {
        return;
    }
    const char *rest = line + plen;
    char ssid[64] = {0};
    char pw[64] = {0};
    const char *tab = strchr(rest, '\t');
    if (tab) {
        size_t sl = (size_t)(tab - rest);
        if (sl > sizeof(ssid) - 1) sl = sizeof(ssid) - 1;
        memcpy(ssid, rest, sl);
        strncpy(pw, tab + 1, sizeof(pw) - 1);
    } else {
        strncpy(ssid, rest, sizeof(ssid) - 1);  /* 개방형 AP */
    }
    if (ssid[0] == '\0') {
        return;
    }
    connect_router(ssid, pw);
}

static void serial_cmd_task(void *arg)
{
    char line[160];
    int li = 0;
    uint8_t ch;
    while (1) {
        int nr = uart_read_bytes(UART_NUM_0, &ch, 1, pdMS_TO_TICKS(50));
        if (nr != 1) {
            continue;
        }
        if (ch == '\n' || ch == '\r') {
            line[li] = '\0';
            if (li > 0) {
                handle_command(line);
                uart_flush_input(UART_NUM_0);
            }
            li = 0;
        } else if (li < (int)sizeof(line) - 1) {
            line[li++] = (char)ch;
        }
    }
}

static void wifi_init(void)
{
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, NULL));

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(ESP_IF_WIFI_STA, CONFIG_WIFI_BANDWIDTH));
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    ESP_ERROR_CHECK(esp_wifi_start());
    /* 부팅 시 자동 접속하지 않는다 — 호스트의 WIFI_CONNECT 명령을 기다린다. */
}

void app_main(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    wifi_init();
    /* 라우터 접속 전엔 ESP-NOW 채널 고정(tx 수신). 접속하면 라우터 채널로 옮겨간다. */
    ESP_ERROR_CHECK(esp_wifi_set_channel(CONFIG_LESS_INTERFERENCE_CHANNEL, WIFI_SECOND_CHAN_BELOW));

    esp_now_setup();
    wifi_csi_init();

    /* UART0 RX 드라이버 설치 후 런타임 명령 태스크 시작(CSI 출력은 ets_printf 직접). */
    uart_driver_install(UART_NUM_0, 1024, 0, 0, NULL, 0);
    xTaskCreate(serial_cmd_task, "serial_cmd", 4096, NULL, 5, NULL);

    ESP_LOGI(TAG, "CSI 수신 시작 — tx(ESP-NOW) 즉시, 라우터는 WIFI_CONNECT 명령 대기");

    /* DEVICE_ROLE 을 신호와 무관하게 주기 출력한다. CSI 콜백 안에서만 출력하면 tx/라우터
     * 신호가 없을 때(tx 미연결 등) CSI 가 안 와서 role 이 영영 감지되지 않는다(rx 인데
     * RX 로 안 잡히는 문제의 원인). 1.5초마다 한 줄 보내 호스트가 항상 감지하게 한다. */
    while (1) {
        ets_printf("DEVICE_ROLE {\"role\":\"rx\",\"fw\":\"csi_recv\",\"ver\":1}\n");
        vTaskDelay(pdMS_TO_TICKS(1500));
    }
}
