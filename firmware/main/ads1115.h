#pragma once

#include "driver/i2c_master.h"
#include "esp_err.h"

// ADS1115: four single-ended conversions per sample, +-4.096 V range, 128 samples/s.
namespace ads1115 {

esp_err_t init(i2c_master_bus_handle_t bus, uint8_t addr, uint32_t hz);
// Reads A0-A3 in volts. Returns false if any transfer failed.
bool read_all(float volts[4]);

}  // namespace ads1115
