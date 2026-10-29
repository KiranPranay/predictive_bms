# ESP-IDF project: the predictive BMS supervisor for an ESP32-WROOM-32 DevKit.
#   . ../.tools/esp-idf/export.sh   (or your own ESP-IDF v5.5)
#   idf.py build flash monitor
cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(predictive_bms)
