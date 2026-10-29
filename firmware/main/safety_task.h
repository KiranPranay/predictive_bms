#pragma once

#include "bms/types.h"

// The 5 Hz safety task (section 8): reads every sensor, runs the supervisor, drives the relays
// and the alarm, keeps the latch in flash, and feeds the task watchdog. It runs at the highest
// application priority on core 1; Wi-Fi and the web server run on core 0.
namespace safety {

// crashed: the ESP32 restarted after a panic, a watchdog or a brown-out; this latches a
// controller_reset trip (section 10: both relays stay open until a manual reset).
void start(const bms::Calibration& cal, const bms::ModelParams& params,
           const bms::LatchRecord& latch, bool crashed, const char* reset_reason);

}  // namespace safety
