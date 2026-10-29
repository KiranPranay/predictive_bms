#include "bms/electrical.h"

#include <cmath>

namespace bms {

float ocv_slope_at(const ModelParams& p, float v) {
  const int n = p.ocv_points;
  if (n < 1) return NAN;
  if (n == 1 || v <= p.ocv_v[0]) return p.ocv_slope[0];
  if (v >= p.ocv_v[n - 1]) return p.ocv_slope[n - 1];
  for (int k = 1; k < n; ++k) {
    if (v <= p.ocv_v[k]) {
      const float f = (v - p.ocv_v[k - 1]) / (p.ocv_v[k] - p.ocv_v[k - 1]);
      return p.ocv_slope[k - 1] + f * (p.ocv_slope[k] - p.ocv_slope[k - 1]);
    }
  }
  return p.ocv_slope[n - 1];
}

// ---------------------------------------------------------------------------------------------
// Section 9.4: online resistance.

void ResistanceTracker::configure(const ModelParams& p) {
  for (int i = 0; i < cfg::kCells; ++i) {
    r0_[i] = p.r_cell_ohm[i];
    n_[i] = pos_[i] = 0;
  }
  gate4_ = p.gate4_done;
  have_prev_ = pending_ = false;
}

void ResistanceTracker::step(const Measurements& m) {
  if (!m.taps_valid || !m.current_valid) {
    have_prev_ = pending_ = false;
    return;
  }
  const float i_now = m.raw_current_a;
  const float* v_now = m.raw_cell_v;

  // A step found on the last sample counts only if it has settled on this one, which also
  // rejects a step that fell between the current and the voltage readings.
  if (pending_) {
    const float di = after_i_ - before_i_;
    bool settled = std::fabs(i_now - after_i_) <= cfg::kStepSettleFrac * std::fabs(di) +
                                                      cfg::kStepSettleA;
    for (int c = 0; c < cfg::kCells && settled; ++c) {
      const float dv = after_v_[c] - before_v_[c];
      settled = std::fabs(v_now[c] - after_v_[c]) <=
                cfg::kStepSettleFrac * std::fabs(dv) + cfg::kStepSettleV;
    }
    if (settled) {
      for (int c = 0; c < cfg::kCells; ++c) {
        const float r = -(after_v_[c] - before_v_[c]) / di;
        if (r > 0.0f && r <= cfg::kResistanceMaxOhm) {
          ring_[c][pos_[c]] = r;
          pos_[c] = (pos_[c] + 1) % cfg::kResistanceSteps;
          if (n_[c] < cfg::kResistanceSteps) ++n_[c];
        }
      }
    }
    pending_ = false;
  }

  if (have_prev_ && std::fabs(i_now - prev_i_) >= cfg::kStepMinA) {
    pending_ = true;
    before_i_ = prev_i_;
    after_i_ = i_now;
    for (int c = 0; c < cfg::kCells; ++c) {
      before_v_[c] = prev_v_[c];
      after_v_[c] = v_now[c];
    }
  }
  for (int c = 0; c < cfg::kCells; ++c) prev_v_[c] = v_now[c];
  prev_i_ = i_now;
  have_prev_ = true;
}

float ResistanceTracker::average_r(int c) const {
  if (n_[c] == 0) return NAN;
  float s = 0.0f;
  for (int k = 0; k < n_[c]; ++k) s += ring_[c][k];
  return s / n_[c];
}

float ResistanceTracker::model_r(int c) const {
  const float avg = n_[c] ? average_r(c) : r0_[c];
  const float lo = r0_[c] * (1.0f - cfg::kResistanceBound);
  const float hi = r0_[c] * (1.0f + cfg::kResistanceBound);
  return avg < lo ? lo : (avg > hi ? hi : avg);
}

bool ResistanceTracker::drift(int c) const {
  if (!gate4_ || n_[c] < cfg::kResistanceDriftMinSteps) return false;
  return std::fabs(average_r(c) - r0_[c]) > cfg::kResistanceBound * r0_[c];
}

// ---------------------------------------------------------------------------------------------
// Section 9.5: rest leak estimate.

void LeakEstimator::configure(const ModelParams& p) {
  params_ = p;
  // Keep the table in rising voltage order for interpolation.
  for (int a = 1; a < params_.ocv_points; ++a)
    for (int b = a; b > 0 && params_.ocv_v[b] < params_.ocv_v[b - 1]; --b) {
      float tv = params_.ocv_v[b];
      params_.ocv_v[b] = params_.ocv_v[b - 1];
      params_.ocv_v[b - 1] = tv;
      float ts = params_.ocv_slope[b];
      params_.ocv_slope[b] = params_.ocv_slope[b - 1];
      params_.ocv_slope[b - 1] = ts;
    }
  restart();
}

void LeakEstimator::restart() {
  rest_start_t_ = -1.0;
  minute_start_t_ = -1.0;
  acc_n_ = 0;
  for (float& a : acc_) a = 0.0f;
  w_n_ = w_pos_ = 0;
  valid_ = false;
  for (float& l : leak_) l = 0.0f;
}

float LeakEstimator::rest_s() const {
  return rest_start_t_ < 0.0 ? 0.0f : static_cast<float>(t_ - rest_start_t_);
}

void LeakEstimator::step(const Measurements& m) {
  t_ = m.t_s;
  if (!enabled()) return;
  if (!m.taps_valid || !m.current_valid) return;   // skip a bad sample; a fault trips anyway

  bool resting = std::fabs(m.current_a) < cfg::kRestCurrentA;
  for (int c = 0; c < cfg::kCells; ++c) {
    if (m.cell_v[c] > cfg::kLeakNoBalanceV) resting = false;   // the BMS may be balancing
  }
  if (!resting) {
    restart();
    return;
  }
  if (rest_start_t_ < 0.0) rest_start_t_ = m.t_s;
  if (m.t_s - rest_start_t_ < cfg::kRestSettleS) return;
  if (minute_start_t_ < 0.0) minute_start_t_ = m.t_s;

  // Compare with the mean of the other three cells: a common drift cancels, and one leaking
  // cell shows its whole leak rather than three quarters of it.
  float sum = 0.0f;
  for (int c = 0; c < cfg::kCells; ++c) sum += m.cell_v[c];
  for (int c = 0; c < cfg::kCells; ++c) {
    acc_[c] += m.cell_v[c] - (sum - m.cell_v[c]) / (cfg::kCells - 1);
  }
  ++acc_n_;

  if (m.t_s - minute_start_t_ < 60.0 - 1e-6) return;
  minute_start_t_ += 60.0;
  for (int c = 0; c < cfg::kCells; ++c) {
    window_[w_pos_][c] = acc_[c] / acc_n_;
    acc_[c] = 0.0f;
  }
  acc_n_ = 0;
  w_pos_ = (w_pos_ + 1) % cfg::kLeakWindowMinutes;
  if (w_n_ < cfg::kLeakWindowMinutes) ++w_n_;
  if (w_n_ < cfg::kLeakWindowMinutes) return;

  // Regression slope over the window, volts per minute, oldest entry first.
  const int n = cfg::kLeakWindowMinutes;
  const float xm = 0.5f * (n - 1);
  const double q_cap_as = cfg::kCapacityAh * 3600.0;
  for (int c = 0; c < cfg::kCells; ++c) {
    float ym = 0.0f;
    for (int k = 0; k < n; ++k) ym += window_[(w_pos_ + k) % n][c];
    ym /= n;
    float sxy = 0.0f, sxx = 0.0f;
    for (int k = 0; k < n; ++k) {
      const float dx = k - xm;
      sxy += dx * (window_[(w_pos_ + k) % n][c] - ym);
      sxx += dx * dx;
    }
    const double slope_v_per_s = (sxy / sxx) / 60.0;
    const float docv = ocv_slope_at(params_, m.cell_v[c]);
    leak_[c] = static_cast<float>(-q_cap_as * slope_v_per_s / docv);
  }
  valid_ = true;
}

}  // namespace bms
