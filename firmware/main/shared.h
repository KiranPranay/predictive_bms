#pragma once

#include <cstdint>

#include "bms/supervisor.h"

// What the tasks share. The safety task owns the supervisor; the console and the web server
// only read copies of its snapshot and send it commands, so neither can block a sample.
namespace shared {

enum class Cmd : uint8_t {
  Reset,             // manual reset request (section 8, rule 6)
  ApplyCalibration,  // take the pending calibration
  ApplyParams,       // take the pending model parameters
  ClearStats,        // clear the prediction-accuracy record
  Log,               // arg: 0 off, 1 or 5 lines a second
  SimOn,             // bench mode only
  SimOff,
  SimLine,           // a plant command for the simulated pack, in text
  TestHang,          // Gate 2: stop feeding the watchdog
  TestCrash,         // Gate 2: abort
};

struct Command {
  Cmd type;
  int arg;
  char text[64];
};

void init();

// Safety task side.
void publish(const bms::Snapshot& s, bool bench_sim);
bool receive(Command& c);

// Reader side.
void read(bms::Snapshot& s, bool* bench_sim = nullptr);
bool send(Cmd type, int arg = 0, const char* text = nullptr);

// Calibration and parameters are too large for the queue: they wait here for the safety task.
void set_pending(const bms::Calibration& cal);
void set_pending(const bms::ModelParams& params);
bool take_pending(bms::Calibration& cal);
bool take_pending(bms::ModelParams& params);

}  // namespace shared
