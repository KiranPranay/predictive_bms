#pragma once

#include <cstdint>

#include "esp_adc/adc_oneshot.h"
#include "esp_err.h"

// The five NTC dividers on ADC1, read with the ESP32's own calibration.
namespace ntc_adc {

esp_err_t init();
// Millivolts across each NTC, and the summed raw codes for the flat-line check.
void read(bool ok[5], float mv[5], uint32_t code[5]);

// The ADC1 unit handle, shared with the ACS712 driver (temporary).
adc_oneshot_unit_handle_t adc1_handle();

}  // namespace ntc_adc
