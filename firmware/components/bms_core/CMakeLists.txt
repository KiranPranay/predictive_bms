# The supervisor's algorithms in portable C++17. ESP-IDF builds this folder as a component; the
# PC build in host/ adds it as a plain library, so the tests run the same code as the ESP32.
set(BMS_CORE_SRCS
    src/electrical.cpp
    src/risk.cpp
    src/sensors.cpp
    src/supervisor.cpp
    src/telemetry.cpp
    src/thermal.cpp)

if(ESP_PLATFORM)
  idf_component_register(SRCS ${BMS_CORE_SRCS} INCLUDE_DIRS include)
  target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror=return-type)
else()
  add_library(bms_core STATIC ${BMS_CORE_SRCS})
  target_include_directories(bms_core PUBLIC include)
  target_compile_features(bms_core PUBLIC cxx_std_17)
  if(MSVC)
    target_compile_options(bms_core PRIVATE /W4)
  else()
    target_compile_options(bms_core PRIVATE -Wall -Wextra -Wpedantic -Wshadow -Werror=return-type)
  endif()
endif()
