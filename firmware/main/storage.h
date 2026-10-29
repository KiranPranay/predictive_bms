#pragma once

#include "bms/types.h"
#include "esp_err.h"

// Flash storage (NVS) of the calibration, the model parameters and the latched trip.
// A record whose size or version does not match is ignored, and the defaults are used.
namespace storage {

esp_err_t init();
bool load(bms::Calibration& cal);
bool load(bms::ModelParams& params);
bool load(bms::LatchRecord& latch);
esp_err_t save(const bms::Calibration& cal);
esp_err_t save(const bms::ModelParams& params);
esp_err_t save(const bms::LatchRecord& latch);

}  // namespace storage
