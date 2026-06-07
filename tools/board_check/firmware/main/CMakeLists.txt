# 진단 펌웨어 메인 컴포넌트 등록.
idf_component_register(
    SRCS "diag_main.c"
    INCLUDE_DIRS "."
    # 사용하는 컴포넌트:
    #   esp_wifi/esp_netif/esp_event/nvs_flash : WiFi 스캔
    #   esp_psram                              : PSRAM 검사
    #   driver                                 : GPIO(BOOT 버튼)
    #   led_strip                              : WS2812 RGB LED (managed component)
    REQUIRES esp_wifi nvs_flash esp_netif esp_event esp_psram driver led_strip
)
