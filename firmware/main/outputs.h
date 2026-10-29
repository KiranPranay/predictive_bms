#pragma once

#include <cstdint>

#include "bms/types.h"

// Relay, alarm and reset-button pins.
namespace outputs {

// Sets both relay pins HIGH (contacts open) before enabling them as outputs, so start-up never
// pulses a relay. Call first thing in app_main.
void init();
// Drives the relays and the alarm: steady for a latched trip, 1 Hz for Warning.
void apply(const bms::Outputs& out, int64_t now_ms);
void all_off();
// True once each time the BOOT button has been held for 3 s.
bool reset_button_held(int64_t now_ms);

}  // namespace outputs
