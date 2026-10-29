# PC build: the supervisor core, the pack simulator, and the tests.
#   cmake -S host -B build/host && cmake --build build/host && ctest --test-dir build/host
cmake_minimum_required(VERSION 3.16)
project(predictive_bms_host CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_subdirectory(../firmware/components/bms_core bms_core)
add_subdirectory(../firmware/components/bms_sim bms_plant)

find_package(Threads REQUIRED)

add_library(bms_scenarios STATIC sim/scenario.cpp)
target_include_directories(bms_scenarios PUBLIC .)
target_link_libraries(bms_scenarios PUBLIC bms_plant)

add_executable(bms_sim bms_sim.cpp)
target_link_libraries(bms_sim PRIVATE bms_scenarios Threads::Threads)

add_executable(bms_tests tests/test_main.cpp tests/test_core.cpp tests/test_scenarios.cpp)
target_link_libraries(bms_tests PRIVATE bms_scenarios)

if(NOT MSVC)
  foreach(t bms_scenarios bms_sim bms_tests)
    target_compile_options(${t} PRIVATE -Wall -Wextra -Werror=return-type)
  endforeach()
endif()

enable_testing()
add_test(NAME core_unit_tests COMMAND bms_tests unit WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
add_test(NAME scenarios COMMAND bms_tests scenario_ WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
