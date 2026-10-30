#pragma once

#include <cstdio>
#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "bms/supervisor.h"
#include "sim/pack.h"

namespace sim {

// The simulated pack wired to the supervisor, as on the bench: each sample the supervisor reads
// the sensors, and its relay commands decide what current the pack carries next.
class Bench {
 public:
  explicit Bench(uint64_t seed = 1, bms::ModelMode mode = bms::ModelMode::Fitted);

  Pack pack;
  bms::Calibration cal;
  bms::ModelParams params;
  std::unique_ptr<bms::Supervisor> sup;
  bms::Outputs out;
  std::FILE* csv = nullptr;   // optional log in the firmware's CSV format
  int csv_every = static_cast<int>(bms::cfg::kSampleHz);   // samples per row: 1 Hz by default

  void step();
  void run(double seconds);
  // Runs until stop() holds or max_s has passed; true when stop() held.
  bool run_until(double max_s, const std::function<bool()>& stop);
  bms::Snapshot snap() const;
  double t() const { return pack.t; }
  // Restart the controller. The latch survives, as it does in flash; a crash also latches.
  void restart_controller(bool crash);
  void set_mode(bms::ModelMode mode);

 private:
  int sub_ = 0;
  double boot_t_ = 0.0;   // pack time of the controller's last boot
};

class Report {
 public:
  void expect(bool ok, const std::string& text) { checks_.push_back({ok, text}); }
  void note(const std::string& text) { notes_.push_back(text); }
  bool passed() const;
  struct Check {
    bool ok;
    std::string text;
  };
  const std::vector<Check>& checks() const { return checks_; }
  const std::vector<std::string>& notes() const { return notes_; }

 private:
  std::vector<Check> checks_;
  std::vector<std::string> notes_;
};

struct Scenario {
  const char* name;
  const char* gate;      // the gate whose test it rehearses
  const char* summary;   // what it shows
  void (*run)(Bench& b, Report& r);
  uint64_t seed;
  bms::ModelMode mode;
};

const std::vector<Scenario>& scenarios();
const Scenario* find_scenario(const std::string& name);

std::string fmt(const char* f, ...);

}  // namespace sim
