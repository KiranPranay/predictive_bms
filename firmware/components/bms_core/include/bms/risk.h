#pragma once

#include <cstdint>

#include "bms/filters.h"
#include "bms/types.h"

namespace bms {

// Evidence for one cell on one sample.
struct CellRiskInputs {
  bool thermal_on = false;      // thermal layer running and settled
  float heat_rate = 0.0f;       // abnormal heat as a heating rate, degC/min (9.2)
  float diff_rate = 0.0f;       // the same, minus the mean of the other three cells (9.2)
  bool new_e5 = false;          // a 5-minute confirmation ended on this sample (9.3)
  float e5 = 0.0f;
  float time_to_limit_s = INFINITY;   // 9.6
  bool above_safe = false;      // |I| above this cell's safe current (9.6)
  bool leak_watch = false;      // leak estimate of 20 mA or more (9.5)
  bool drift = false;           // resistance more than 30 % from Gate 4 (9.4)
  float heat_w = 0.0f;          // for the self-acceleration test (9.7)
  float core_c = 0.0f;
};

// Section 9.8 risk level of one cell: 0 Normal, 1 Watch, 2 Warning, 3 Trip.
class CellRisk {
 public:
  void reset();
  int step(const CellRiskInputs& in);
  int level() const { return level_; }
  uint32_t reasons() const { return reasons_; }

 private:
  void clear_thermal();

  Persist diff_watch_, ttl_watch_, above_safe_, heat_warn_, heat_trip_, diff_trip_;
  bool hot_ = false;

  // One entry a second for the 120 s self-acceleration window.
  static constexpr int kHist = static_cast<int>(cfg::kSelfAccelWindowS) + 1;
  float hist_q_[kHist] = {};
  float hist_tc_[kHist] = {};
  int h_n_ = 0;
  int h_pos_ = 0;
  int sub_ = 0;
  int warn_samples_ = 0;   // consecutive samples at Warning or above

  int level_ = 0;
  uint32_t reasons_ = 0;
};

}  // namespace bms
