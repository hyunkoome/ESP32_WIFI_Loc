# 진단 펌웨어 메인 컴포넌트 등록.
idf_component_register(
    SRCS "diag_main.c"
    INCLUDE_DIRS "."
    # 사용하는 컴포넌트: WiFi, NVS, esp_psram, 이벤트 루프 등
    REQUIRES esp_wifi nvs_flash esp_netif esp_event esp_psram
)
