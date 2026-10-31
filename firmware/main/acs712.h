#pragma once

#include "esp_adc/adc_oneshot.h"
#include "esp_err.h"

// ACS712-5A as a temporary replacement for the INA226 (the INA226 module is not available yet).
// The ACS712 output goes to an ADC1 pin; this driver reads it and converts to a synthetic shunt
// voltage that the front end handles unchanged. Revert to ina226.h when the INA226 arrives.
namespace acs712 {

// Call after ntc_adc::init(). The ADC1 unit handle is shared with the NTC driver.
esp_err_t init(adc_oneshot_unit_handle_t adc1, adc_channel_t channel);

// Fills shunt_v with (measured_current * 0.005) so the calibration path works unchanged.
// bus_v is set to 0 (the ACS712 does not measure the bus voltage).
bool read(float& shunt_v, float& bus_v);

}  // namespace acs712

