#pragma once

// Pin map of the ESP32-WROOM-32 DevKit, from architecture sections 6 and 7.

#include "driver/gpio.h"
#include "hal/adc_types.h"

namespace board {

// I2C: ADS1115 (cell taps) and INA226 (pack current), both at 3.3 V.
constexpr gpio_num_t kSda = GPIO_NUM_21;
constexpr gpio_num_t kScl = GPIO_NUM_22;

// Relays: active LOW, 10 kOhm pull-up, normally-open contacts. High or floating = open.
constexpr gpio_num_t kLoadRelay = GPIO_NUM_25;     // K_LOAD: P- to LOAD-
constexpr gpio_num_t kChargeRelay = GPIO_NUM_26;   // K_CHARGE: P- to CHARGE-

// Latched fault buzzer and red LED.
constexpr gpio_num_t kAlarm = GPIO_NUM_27;

// The DevKit's BOOT button, read after start-up: held for 3 s it requests a manual reset.
constexpr gpio_num_t kResetButton = GPIO_NUM_0;
constexpr int kResetHoldMs = 3000;

// NTCs on ADC1 only: ADC2 cannot be used while Wi-Fi is on.
constexpr adc_channel_t kNtcChannel[5] = {
    ADC_CHANNEL_4,   // NTC1, GPIO32
    ADC_CHANNEL_5,   // NTC2, GPIO33
    ADC_CHANNEL_6,   // NTC3, GPIO34
    ADC_CHANNEL_7,   // NTC4, GPIO35
    ADC_CHANNEL_0,   // NTC5 ambient, GPIO36 (VP)
};
constexpr int kNtcSamples = 16;   // conversions summed per reading

// Temporary: ACS712 analog input on ADC1 (GPIO39 / VN)
constexpr adc_channel_t kAcs712Channel = ADC_CHANNEL_3;

}  // namespace board
