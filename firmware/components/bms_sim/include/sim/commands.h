#pragma once

#include <string>

#include "sim/pack.h"

namespace sim {

// Applies one plant command to the simulated pack:
//   load A | charge A | ambient C | soc 0-1 | clear
//   heat N W | accel N W [GROWTH_C] | short N OHM | leak N OHM
//   lift N | ntc N open|short|stuck|lift|ok | offset N C | ads fail|ok | ina fail|ok
// N is a cell (1-4) or, for ntc and offset, an NTC (1-5; 5 is the ambient NTC).
// Returns a reply, or an empty string when the command is not a plant command.
std::string apply_command(Pack& p, const std::string& line);

const char* ntc_mode_name(NtcMode m);

}  // namespace sim
