#pragma once

#include "driver/i2c_master.h"
#include "esp_err.h"

// INA226 with the external 5 mOhm shunt (section 4). Only the raw shunt and bus voltages are
// read; the core turns them into current with the Gate 1 calibration.
namespace ina226 {

esp_err_t init(i2c_master_bus_handle_t bus, uint8_t addr, uint32_t hz);
bool read(float& shunt_v, float& bus_v);

}  // namespace ina226
