#pragma once

#include "bms/filters.h"
#include "bms/types.h"

namespace bms {

// NTC conversion (section 6): the NTC sits below a pull-up to the 3.3 V rail.
// Returns NaN when the voltage gives no finite resistance.
float ntc_temperature_c(float mv, const Calibration& cal);
// The inverse, used by the simulator and the tests.
float ntc_millivolts(float temp_c, const Calibration& cal);

// Calibrated, checked and filtered measurements of one sample.
struct Measurements {
  double t_s = 0.0;

  // This sample, after calibration and the plausibility checks.
  bool taps_valid = false;
  float raw_tap_v[cfg::kCells] = {};
  float raw_cell_v[cfg::kCells] = {};
  bool current_valid = false;
  float raw_current_a = 0.0f;
  bool ntc_valid[cfg::kNtcs] = {};
  float raw_temp_c[cfg::kNtcs] = {};

  // After the median-of-5 stage. A channel that is invalid holds its last value.
  float cell_v[cfg::kCells] = {};
  float pack_v = 0.0f;
  float current_a = 0.0f;   // positive = discharge
  float temp_c[cfg::kNtcs] = {};

  // After the 10 s low-pass, and the 30 s regression slope of the cell temperatures.
  float temp_lp_c[cfg::kNtcs] = {};
  bool rise_valid[cfg::kCells] = {};
  float rise_c_per_min[cfg::kCells] = {};

  // Channel status: invalid this sample, and how long it has been invalid or valid.
  bool invalid[kChannelCount] = {};
  float invalid_for_s[kChannelCount] = {};
  float valid_for_s[kChannelCount] = {};
  bool ever_valid[kChannelCount] = {};
  bool flat_line[cfg::kNtcs] = {};
};

class FrontEnd {
 public:
  explicit FrontEnd(const Calibration& cal) : cal_(cal) {}
  void set_calibration(const Calibration& cal) { cal_ = cal; }
  const Calibration& calibration() const { return cal_; }

  // r_cell_ohm: the present resistance of each cell, used to tell a load step from a jump.
  const Measurements& process(const RawSample& raw, const float r_cell_ohm[cfg::kCells]);
  const Measurements& last() const { return m_; }

 private:
  void track(int ch, bool valid);

  Calibration cal_;
  Measurements m_;

  bool have_prev_taps_ = false;
  float prev_cell_v_[cfg::kCells] = {};
  bool prev_current_ok_ = false;
  float prev_current_a_ = 0.0f;

  uint32_t last_code_[cfg::kNtcs] = {};
  float code_same_s_[cfg::kNtcs] = {};
  bool have_code_[cfg::kNtcs] = {};

  Median5 med_cell_[cfg::kCells];
  Median5 med_current_;
  Median5 med_temp_[cfg::kNtcs];
  LowPass lp_temp_[cfg::kNtcs];
  SlopeWindow<cfg::kSlopeSamples> slope_[cfg::kCells];
};

}  // namespace bms
