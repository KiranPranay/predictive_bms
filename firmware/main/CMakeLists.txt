idf_component_register(
  SRCS
    ads1115.cpp
    console.cpp
    ina226.cpp
    main.cpp
    ntc_adc.cpp
    outputs.cpp
    safety_task.cpp
    shared.cpp
    storage.cpp
    telemetry.cpp
  INCLUDE_DIRS .
  PRIV_REQUIRES
    bms_core bms_sim console esp_adc esp_driver_gpio esp_driver_i2c esp_event esp_http_server
    esp_netif esp_system esp_timer esp_wifi nvs_flash
  EMBED_TXTFILES ../../dashboard/index.html)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror=return-type)
