# The simulated pack: the plant for the PC tests, and on the ESP32 the sensor source of the
# bench mode (CONFIG_BMS_BENCH_SIM, off by default) used at Gates 2 and 3 before any cell is
# connected.
set(BMS_SIM_SRCS src/commands.cpp src/pack.cpp)

if(ESP_PLATFORM)
  idf_component_register(SRCS ${BMS_SIM_SRCS} INCLUDE_DIRS include REQUIRES bms_core)
else()
  add_library(bms_plant STATIC ${BMS_SIM_SRCS})
  target_include_directories(bms_plant PUBLIC include)
  target_link_libraries(bms_plant PUBLIC bms_core)
  if(NOT MSVC)
    target_compile_options(bms_plant PRIVATE -Wall -Wextra -Werror=return-type)
  endif()
endif()
