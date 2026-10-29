#pragma once

#include "bms/sensors.h"
#include "bms/types.h"

namespace bms {

// dOCV/dSOC at a cell voltage, from the Gate 10 table (volts per unit charge).
// NaN when there is no table.
float ocv_slope_at(const ModelParams& p, float v);

// Section 9.4: R_i = -dV_i / dI at every current step of at least 0.5 A, averaged over the
// last 20 steps. The thermal model uses the average, bounded to +-30 % of the Gate 4 value.
class ResistanceTracker {
 public:
  void configure(const ModelParams& p);
  void step(const Measurements& m);

  float model_r(int cell) const;     // the value the thermal model uses
  float average_r(int cell) const;   // NaN before the first step
  int steps(int cell) const { return n_[cell]; }
  bool drift(int cell) const;        // more than 30 % from the Gate 4 value

 private:
  float r0_[cfg::kCells] = {};
  bool gate4_ = false;
  float ring_[cfg::kCells][cfg::kResistanceSteps] = {};
  int n_[cfg::kCells] = {};
  int pos_[cfg::kCells] = {};

  bool have_prev_ = false;
  float prev_v_[cfg::kCells] = {};
  float prev_i_ = 0.0f;
  bool pending_ = false;
  float before_v_[cfg::kCells] = {}, after_v_[cfg::kCells] = {};
  float before_i_ = 0.0f, after_i_ = 0.0f;
};

// Section 9.5: self-discharge at rest. At rest (|I| < 20 mA, no cell above 4.15 V) and at least
// 30 minutes after the last load or charge, each cell's voltage is compared with the mean of the
// other three every sample; one-minute averages fill a 60-minute window, and its slope gives
//   I_leak = -Q_cap * slope / (dOCV/dSOC).
class LeakEstimator {
 public:
  void configure(const ModelParams& p);
  void step(const Measurements& m);

  bool enabled() const { return params_.ocv_points >= 1; }
  float rest_s() const;
  int minutes() const { return w_n_; }
  bool valid() const { return valid_; }
  float leak_a(int cell) const { return leak_[cell]; }

 private:
  void restart();

  ModelParams params_;
  double t_ = 0.0;
  double rest_start_t_ = -1.0;
  double minute_start_t_ = -1.0;
  float acc_[cfg::kCells] = {};
  int acc_n_ = 0;
  float window_[cfg::kLeakWindowMinutes][cfg::kCells] = {};
  int w_n_ = 0;
  int w_pos_ = 0;
  bool valid_ = false;
  float leak_[cfg::kCells] = {};
};

}  // namespace bms
