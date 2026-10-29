#include "bms/sensors.h"

#include <cmath>

namespace bms {

namespace {
constexpr float kKelvin = 273.15f;
constexpr float kT25 = 298.15f;
}  // namespace

float ntc_temperature_c(float mv, const Calibration& cal) {
  if (!(mv > 0.0f) || !(mv < cal.ntc_supply_mv)) return NAN;
  const float r = cal.ntc_pullup_ohm * mv / (cal.ntc_supply_mv - mv);
  const float inv_t = 1.0f / kT25 + std::log(r / cal.ntc_r25_ohm) / cal.ntc_beta;
  return 1.0f / inv_t - kKelvin;
}

float ntc_millivolts(float temp_c, const Calibration& cal) {
  const float t = temp_c + kKelvin;
  const float r = cal.ntc_r25_ohm * std::exp(cal.ntc_beta * (1.0f / t - 1.0f / kT25));
  return cal.ntc_supply_mv * r / (r + cal.ntc_pullup_ohm);
}

void FrontEnd::track(int ch, bool valid) {
  m_.invalid[ch] = !valid;
  if (valid) {
    m_.invalid_for_s[ch] = 0.0f;
    m_.valid_for_s[ch] += cfg::kDt;
    m_.ever_valid[ch] = true;
  } else {
    m_.invalid_for_s[ch] += cfg::kDt;
    m_.valid_for_s[ch] = 0.0f;
  }
}

const Measurements& FrontEnd::process(const RawSample& raw, const float r_cell_ohm[cfg::kCells]) {
  m_.t_s = raw.t_s;

  // Current (section 4): positive means discharge.
  bool current_ok = raw.ina_ok && std::isfinite(raw.shunt_v);
  float current = 0.0f;
  if (current_ok) {
    current = cal_.current_gain * raw.shunt_v / cal_.shunt_ohm + cal_.current_offset_a;
  }
  m_.current_valid = current_ok;
  m_.raw_current_a = current;
  track(kChCurrent, current_ok);
  if (current_ok) m_.current_a = med_current_.push(current);

  // Cell taps (section 5): cumulative taps, cells by adjacent subtraction. Reject a
  // non-monotonic tap order, a negative cell, or a jump of more than 100 mV between adjacent
  // samples that the change of current does not explain.
  bool taps_ok = raw.ads_ok;
  float tap[cfg::kCells] = {};
  float cell[cfg::kCells] = {};
  if (taps_ok) {
    for (int i = 0; i < cfg::kCells; ++i) {
      tap[i] = cal_.tap_gain[i] * raw.ads_v[i] + cal_.tap_offset_v[i];
      if (!std::isfinite(tap[i])) taps_ok = false;
    }
  }
  if (taps_ok) {
    for (int i = 0; i < cfg::kCells; ++i) {
      cell[i] = tap[i] - (i > 0 ? tap[i - 1] : 0.0f);
      if (cell[i] < 0.0f) taps_ok = false;
    }
    if (have_prev_taps_) {
      const float d_i = (current_ok && prev_current_ok_) ? current - prev_current_a_ : 0.0f;
      for (int i = 0; i < cfg::kCells; ++i) {
        const float unexplained = (cell[i] - prev_cell_v_[i]) + r_cell_ohm[i] * d_i;
        if (std::fabs(unexplained) > cfg::kTapJumpMaxV) taps_ok = false;
      }
    }
    // The next jump check compares with this reading, valid or not, so a single spike
    // costs at most two samples.
    for (int i = 0; i < cfg::kCells; ++i) prev_cell_v_[i] = cell[i];
    have_prev_taps_ = true;
  }
  prev_current_ok_ = current_ok;
  prev_current_a_ = current;

  m_.taps_valid = taps_ok;
  track(kChTaps, taps_ok);
  if (taps_ok) {
    for (int i = 0; i < cfg::kCells; ++i) {
      m_.raw_tap_v[i] = tap[i];
      m_.raw_cell_v[i] = cell[i];
      m_.cell_v[i] = med_cell_[i].push(cell[i]);
    }
    m_.pack_v = m_.cell_v[0] + m_.cell_v[1] + m_.cell_v[2] + m_.cell_v[3];
  }

  // Temperatures (section 6). A disconnected, shorted or stuck NTC is a fault, never a valid
  // extreme temperature.
  for (int i = 0; i < cfg::kNtcs; ++i) {
    bool ok = raw.ntc_ok[i];
    float t = NAN;
    if (ok) {
      if (have_code_[i] && raw.ntc_code[i] == last_code_[i]) {
        code_same_s_[i] += cfg::kDt;
      } else {
        code_same_s_[i] = 0.0f;
      }
      last_code_[i] = raw.ntc_code[i];
      have_code_[i] = true;
      m_.flat_line[i] = code_same_s_[i] >= cfg::kFlatLineS;

      t = ntc_temperature_c(raw.ntc_mv[i], cal_) + cal_.ntc_offset_c[i];
      ok = std::isfinite(t) && t >= cfg::kNtcMinC && t <= cfg::kNtcMaxC && !m_.flat_line[i];
    }
    m_.ntc_valid[i] = ok;
    m_.raw_temp_c[i] = t;
    track(kChNtc0 + i, ok);
    if (ok) {
      m_.temp_c[i] = med_temp_[i].push(t);
      m_.temp_lp_c[i] = lp_temp_[i].push(m_.temp_c[i]);
    }
  }

  // Rate of rise (section 8, rule 3): regression over the last 30 s of the low-passed
  // temperature. An invalid sample repeats the held value so the spacing stays even.
  for (int i = 0; i < cfg::kCells; ++i) {
    if (!std::isnan(lp_temp_[i].value())) {
      slope_[i].push(lp_temp_[i].value());
    }
    m_.rise_valid[i] = slope_[i].full();
    m_.rise_c_per_min[i] = m_.rise_valid[i] ? slope_[i].slope(cfg::kDt) * 60.0f : 0.0f;
  }
  return m_;
}

}  // namespace bms
