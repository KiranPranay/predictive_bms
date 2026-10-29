#include "bms/risk.h"

#include <algorithm>
#include <cmath>

namespace bms {

void CellRisk::clear_thermal() {
  diff_watch_.reset();
  ttl_watch_.reset();
  above_safe_.reset();
  heat_warn_.reset();
  heat_trip_.reset();
  diff_trip_.reset();
  hot_ = false;
  h_n_ = h_pos_ = sub_ = 0;
  warn_samples_ = 0;
}

void CellRisk::reset() {
  clear_thermal();
  level_ = 0;
  reasons_ = 0;
}

int CellRisk::step(const CellRiskInputs& in) {
  constexpr float dt = cfg::kDt;
  uint32_t r = 0;
  bool trip_self_accel = false;

  if (in.thermal_on) {
    // 9.3: a 5-minute confirmation of +1.0 degC or more raises Watch until one comes back
    // within the "confirmed normal" band.
    if (in.new_e5) {
      if (in.e5 >= cfg::kConfirmHotC) {
        hot_ = true;
      } else if (in.e5 < cfg::kConfirmNormalC) {
        hot_ = false;
      }
    }
    if (hot_) r |= kReasonConfirmHot;

    if (diff_watch_.update(in.diff_rate >= cfg::kDiffWatchCPerMin,
                           in.diff_rate < cfg::kDiffWatchCPerMin - cfg::kHystDiffCPerMin, dt,
                           cfg::kDiffWatchHoldS))
      r |= kReasonHeatDiff;
    if (ttl_watch_.update(in.time_to_limit_s < cfg::kTimeToLimitWatchS,
                          in.time_to_limit_s >= cfg::kTimeToLimitWatchS + cfg::kHystTimeS, dt,
                          0.0f))
      r |= kReasonTimeToLimit;
    if (above_safe_.update(in.above_safe, !in.above_safe, dt, cfg::kAboveSafeHoldS))
      r |= kReasonAboveSafeCurrent;
    if (heat_warn_.update(in.heat_rate >= cfg::kHeatWarnCPerMin,
                          in.heat_rate < cfg::kHeatWarnCPerMin - cfg::kHystRateCPerMin, dt,
                          cfg::kHeatWarnHoldS))
      r |= kReasonHeat;
    if (heat_trip_.update(in.heat_rate >= cfg::kHeatTripCPerMin,
                          in.heat_rate < cfg::kHeatTripCPerMin - cfg::kHystRateCPerMin, dt,
                          cfg::kHeatTripHoldS))
      r |= kReasonHeatTrip;
    if (diff_trip_.update(in.diff_rate >= cfg::kDiffTripCPerMin,
                          in.diff_rate < cfg::kDiffTripCPerMin - cfg::kHystDiffCPerMin, dt,
                          cfg::kDiffTripHoldS))
      r |= kReasonHeatDiffTrip;

    // 9.7 history, once a second.
    if (++sub_ >= static_cast<int>(cfg::kSampleHz)) {
      sub_ = 0;
      hist_q_[h_pos_] = in.heat_w;
      hist_tc_[h_pos_] = in.core_c;
      h_pos_ = (h_pos_ + 1) % kHist;
      if (h_n_ < kHist) ++h_n_;
    }
  } else {
    clear_thermal();
  }

  if (in.leak_watch) r |= kReasonLeak;
  if (in.drift) r |= kReasonResistanceDrift;

  int lvl = (r & (kThermalWatch | kElectricalWatch)) ? 1 : 0;
  if (r & kReasonHeat) lvl = 2;
  if ((r & kThermalWatch) && (r & kElectricalWatch)) {
    r |= kReasonThermalAndElectrical;
    lvl = 2;
  }

  // 9.7: while at Warning, abnormal heat that rose by half or more over the last 120 s while
  // the core warmed by at least 1 degC is feeding itself: trip without waiting. The window
  // starts no earlier than the moment the cell reached Warning, so the sudden start of a steady
  // fault does not count as heat feeding itself (table 9.8 holds a steady 0.4 W at Warning).
  warn_samples_ = (in.thermal_on && lvl >= 2) ? warn_samples_ + 1 : 0;
  const int back = std::min(static_cast<int>(cfg::kSelfAccelWindowS),
                            warn_samples_ / static_cast<int>(cfg::kSampleHz));
  if (back >= 1 && h_n_ > back) {
    const int newest = (h_pos_ + kHist - 1) % kHist;
    const int then = (newest + kHist - back) % kHist;
    const float q0 = hist_q_[then];
    if (q0 > 0.0f && hist_q_[newest] >= (1.0f + cfg::kSelfAccelHeatRise) * q0 &&
        hist_tc_[newest] - hist_tc_[then] >= cfg::kSelfAccelCoreRiseC) {
      trip_self_accel = true;
      r |= kReasonSelfAcceleration;
    }
  }
  if (r & (kReasonHeatTrip | kReasonHeatDiffTrip) || trip_self_accel) lvl = 3;

  level_ = lvl;
  reasons_ = r;
  return lvl;
}

}  // namespace bms
