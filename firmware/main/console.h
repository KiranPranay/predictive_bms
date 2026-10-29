#pragma once

#include "bms/types.h"

// Serial console over the DevKit's USB port (115200 baud). Type "help" for the commands.
namespace console {

void start(const bms::Calibration& cal, const bms::ModelParams& params);

}  // namespace console
