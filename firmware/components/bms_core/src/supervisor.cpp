#include "bms/supervisor.h"

#include <algorithm>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstring>

namespace bms {

namespace {

const char* const kTripNames[] = {
    "none",           "cell_high",         "cell_low",       "charge_temp",
    "discharge_temp", "temp_spread",       "rise_rate",      "discharge_current",
    "charge_current", "predictive_risk",   "tap_sensor",     "current_sensor",
    "cell_ntc",       "ambient_ntc",       "ntc_contact",    "controller_reset"};
static_assert(sizeof(kTripNames) / sizeof(kTripNames[0]) == static_cast<int>(TripCode::Count),
              "a trip code has no name");

const char* const kReasonNames[] = {
    "confirm_hot", "heat_diff", "time_to_limit", "above_safe_current",
    "leak",        "resistance_drift", "heat",   "thermal_and_electrical",
    "heat_trip",   "heat_diff_trip",   "self_acceleration"};

const char* const kWarningNames[] = {"cell_high",      "cell_low",  "charge_temp",
                                     "discharge_temp", "temp_spread", "rise_rate",
                                     "discharge_current", "sensor"};

const char* bit_list(uint32_t bits, const char* const* names, int n, char* buf, int cap) {
  int len = 0;
  buf[0] = '\0';
  for (int b = 0; b < n; ++b) {
    if (!(bits & (1u << b))) continue;
    const int w = std::snprintf(buf + len, cap - len, "%s%s", len ? "," : "", names[b]);
    if (w < 0 || w >= cap - len) break;
    len += w;
  }
  return buf;
}

const char* branch_text(uint8_t b) {
  switch (b & kBranchBoth) {
    case kBranchLoad: return "load";
    case kBranchCharge: return "charge";
    case kBranchBoth: return "load and charge";
    default: return "none";
  }
}

}  // namespace

const char* trip_name(TripCode c) {
  const int i = static_cast<int>(c);
  return (i >= 0 && i < static_cast<int>(TripCode::Count)) ? kTripNames[i] : "unknown";
}

const char* state_name(State s) {
  switch (s) {
    case State::Startup: return "startup";
    case State::Run: return "run";
    case State::Tripped: return "tripped";
  }
  return "unknown";
}

const char* mode_name(Mode m) {
  switch (m) {
    case Mode::Rest: return "rest";
    case Mode::Charge: return "charge";
    case Mode::Discharge: return "discharge";
  }
  return "unknown";
}

const char* model_name(ModelMode m) {
  switch (m) {
    case ModelMode::Off: return "off";
    case ModelMode::Estimates: return "estimates";
    case ModelMode::Fitted: return "fitted";
  }
  return "unknown";
}

const char* verdict_name(Verdict v) {
  switch (v) {
    case Verdict::Pending: return "pending";
    case Verdict::Normal: return "normal";
    case Verdict::Unconfirmed: return "unconfirmed";
    case Verdict::Hot: return "hot";
    case Verdict::Cold: return "cold";
  }
  return "unknown";
}

const char* level_name(int level) {
  static const char* const names[] = {"normal", "watch", "warning", "trip"};
  return (level >= 0 && level <= 3) ? names[level] : "unknown";
}

const char* reset_result_text(ResetResult r) {
  switch (r) {
    case ResetResult::Accepted: return "accepted";
    case ResetResult::NotLatched: return "nothing is latched";
    case ResetResult::CellVoltage: return "a cell is outside 3.20-4.10 V";
    case ResetResult::Temperature: return "an NTC reads 40 C or more";
    case ResetResult::SensorsInvalid: return "a sensor reading is not plausible";
    case ResetResult::NotClear: return "the cause has not been clear for 60 s";
  }
  return "unknown";
}

const char* event_kind_name(EventKind k) {
  switch (k) {
    case EventKind::Info: return "info";
    case EventKind::Watch: return "watch";
    case EventKind::Warning: return "warning";
    case EventKind::Trip: return "trip";
    case EventKind::Sensor: return "sensor";
    case EventKind::Reset: return "reset";
  }
  return "unknown";
}

uint8_t trip_branches(TripCode c) {
  switch (c) {
    case TripCode::CellHigh:
    case TripCode::ChargeTemp:
    case TripCode::ChargeCurrent:
      return kBranchCharge;
    case TripCode::CellLow:
    case TripCode::DischargeTemp:
    case TripCode::DischargeCurrent:
      return kBranchLoad;
    case TripCode::None:
      return 0;
    default:
      return kBranchBoth;   // everything ambiguous opens both branches
  }
}

const char* reason_list(uint32_t reasons, char* buf, int cap) {
  return bit_list(reasons, kReasonNames, sizeof(kReasonNames) / sizeof(kReasonNames[0]), buf,
                  cap);
}

const char* warning_list(uint32_t warnings, char* buf, int cap) {
  return bit_list(warnings, kWarningNames, sizeof(kWarningNames) / sizeof(kWarningNames[0]), buf,
                  cap);
}

// ---------------------------------------------------------------------------------------------

Supervisor::Supervisor(const Calibration& cal, const ModelParams& params) : front_(cal) {
  set_params(params);
}

void Supervisor::set_calibration(const Calibration& cal) { front_.set_calibration(cal); }

void Supervisor::set_params(const ModelParams& params) {
  params_ = params;
  resist_.configure(params);
  leak_.configure(params);
  for (int i = 0; i < cfg::kCells; ++i) {
    obs_[i].configure(params.thermal, params.kalman, i);
    pred_[i].configure(params.thermal, i);
    pred_[i].clear_record();
    risk_[i].reset();
    contact_[i].reset();
    tau_s_[i] = slow_time_constant_s(params.thermal, i);
    fc_[i] = Forecast();
    heat_rate_[i] = heat_diff_[i] = 0.0f;
    cross_[i] = CrossCheck::NotAvailable;
    p_leak_[i] = NAN;
    last_level_[i] = 0;
    r_model_[i] = resist_.model_r(i);
  }
  thermal_start_t_ = -1.0;
  have_prev_u_ = false;
  pack_risk_ = 0;
}

void Supervisor::log(EventKind kind, int cell, const char* fmt, ...) {
  Event& e = events_[ev_pos_];
  e.t_s = t_;
  e.kind = kind;
  e.cell = static_cast<int8_t>(cell);
  va_list ap;
  va_start(ap, fmt);
  std::vsnprintf(e.text, sizeof(e.text), fmt, ap);
  va_end(ap);
  ev_pos_ = (ev_pos_ + 1) % kEvents;
  if (ev_n_ < kEvents) ++ev_n_;
}

Outputs Supervisor::step(const RawSample& raw) {
  ++seq_;
  raw_ = raw;
  const Measurements& m = front_.process(raw, r_model_);
  t_ = m.t_s;
  if (m.ever_valid[kChCurrent]) {
    if (m.current_a <= -cfg::kRestCurrentA) {
      mode_ = Mode::Charge;
    } else if (m.current_a >= cfg::kRestCurrentA) {
      mode_ = Mode::Discharge;
    } else {
      mode_ = Mode::Rest;
    }
  }
  run_electrical(m);
  run_thermal(m);
  check_limits(m);
  update_state(m);
  return out_;
}

void Supervisor::run_electrical(const Measurements& m) {
  resist_.step(m);   // section 9.9: runs from the first power-up
  leak_.step(m);     // runs once the Gate 10 table exists
  for (int i = 0; i < cfg::kCells; ++i) r_model_[i] = resist_.model_r(i);
}

void Supervisor::run_thermal(const Measurements& m) {
  thermal_on_ = params_.mode != ModelMode::Off;
  const bool cur_ok = m.current_valid;
  const bool amb_ok = m.ntc_valid[cfg::kAmbient];
  const float abs_i = std::fabs(m.current_a);
  const float abs_i_heat = std::min(abs_i, cfg::kHeatCurrentClampA);   // 9.2 clamp
  const float t_amb = m.temp_lp_c[cfg::kAmbient];
  bool new_e5[cfg::kCells] = {};

  if (thermal_on_ && thermal_start_t_ < 0.0) {
    bool all = cur_ok && amb_ok;
    for (int i = 0; i < cfg::kCells; ++i) all = all && m.ntc_valid[i];
    if (all) {
      for (int i = 0; i < cfg::kCells; ++i) {
        obs_[i].reset(m.temp_c[i]);
        pred_[i].restart();
      }
      thermal_start_t_ = t_;
      have_prev_u_ = false;
    }
  }
  const bool running = thermal_on_ && thermal_start_t_ >= 0.0;
  const bool settled = running && (t_ - thermal_start_t_) >= cfg::kObserverWarmupS;

  if (running) {
    float pj_now[cfg::kCells];
    for (int i = 0; i < cfg::kCells; ++i) pj_now[i] = abs_i_heat * abs_i_heat * r_model_[i];
    for (int i = 0; i < cfg::kCells; ++i) {
      const bool meas_ok = m.ntc_valid[i];
      if (have_prev_u_) {
        if (meas_ok) {
          obs_[i].step(prev_pj_[i], prev_tamb_, m.temp_c[i]);
        } else {
          obs_[i].predict(prev_pj_[i], prev_tamb_);
        }
        const Predictor::Ended e =
            pred_[i].advance(t_, prev_pj_[i], prev_tamb_, prev_abs_i_, meas_ok ? m.temp_c[i] : NAN);
        new_e5[i] = e.h5;
        // 9.3 and section 10: a 5-minute confirmation 1 degC or more too cold under load
        // means the NTC has probably lifted off its cell.
        if (settled && e.h5 && e.e5 <= cfg::kConfirmColdC &&
            e.mean_abs_i5 >= cfg::kContactMinCurrentA) {
          char d[64];
          std::snprintf(d, sizeof d, "5-min confirmation %.2f C at %.1f A", e.e5, e.mean_abs_i5);
          trip(TripCode::NtcContact, i, d);
        }
      }
      if (cur_ok && amb_ok) pred_[i].maybe_start(t_, obs_[i], pj_now[i], t_amb);
    }
    if (cur_ok && amb_ok) {
      for (int i = 0; i < cfg::kCells; ++i) prev_pj_[i] = pj_now[i];
      prev_tamb_ = t_amb;
      prev_abs_i_ = abs_i;
      have_prev_u_ = true;
    }
  }

  // 9.2: heating rate of the abnormal heat, and each cell against the other three. In the mean
  // of the others a negative value counts as zero: negative abnormal heat is a sensor-contact
  // sign (checked below), and it must not make the healthy cells look hot.
  float sum_pos = 0.0f;
  for (int i = 0; i < cfg::kCells; ++i) {
    heat_rate_[i] = running ? heat_rate_c_per_min(params_.thermal, obs_[i].heat_w()) : 0.0f;
    sum_pos += std::max(0.0f, heat_rate_[i]);
  }
  for (int i = 0; i < cfg::kCells; ++i) {
    heat_diff_[i] =
        heat_rate_[i] - (sum_pos - std::max(0.0f, heat_rate_[i])) / (cfg::kCells - 1);
  }

  // 9.6: forecasts. A negative abnormal heat is noise here and is not allowed to make a
  // forecast more hopeful.
  const float t_trip = mode_ == Mode::Charge ? cfg::kChargeTempTripC : cfg::kDischargeTempTripC;
  for (int i = 0; i < cfg::kCells; ++i) {
    if (settled && amb_ok) {
      fc_[i] = forecast(params_.thermal, i, r_model_[i], abs_i, t_amb, obs_[i].surface_c(),
                        std::max(0.0f, obs_[i].heat_w()), t_trip, tau_s_[i]);
    } else {
      fc_[i] = Forecast();
    }
  }

  // 9.2: persistent negative abnormal heat under load means the NTC reads cooler than its own
  // current can explain.
  for (int i = 0; i < cfg::kCells; ++i) {
    const bool cond =
        settled && obs_[i].heat_w() < cfg::kContactHeatW && abs_i >= cfg::kContactMinCurrentA;
    if (contact_[i].update(cond, !cond, cfg::kDt, cfg::kContactHoldS)) {
      char d[64];
      std::snprintf(d, sizeof d, "abnormal heat %.2f W at %.1f A for 60 s", obs_[i].heat_w(),
                    abs_i);
      trip(TripCode::NtcContact, i, d);
    }
  }

  // 9.5: leak watch and the energy cross-check.
  const bool leak_ok = leak_.valid();
  for (int i = 0; i < cfg::kCells; ++i) {
    p_leak_[i] = leak_ok ? m.cell_v[i] * leak_.leak_a(i) : NAN;
    cross_[i] = CrossCheck::NotAvailable;
    if (leak_ok && settled && leak_.leak_a(i) >= cfg::kLeakWatchA) {
      const float tol = std::max(cfg::kCrossCheckTolerance * p_leak_[i], cfg::kCrossCheckFloorW);
      cross_[i] = std::fabs(obs_[i].heat_w() - p_leak_[i]) <= tol ? CrossCheck::Agree
                                                                    : CrossCheck::Disagree;
    }
  }

  // 9.8: risk level of each cell; the pack takes the highest.
  pack_risk_ = 0;
  for (int i = 0; i < cfg::kCells; ++i) {
    CellRiskInputs in;
    in.thermal_on = settled;
    in.heat_rate = heat_rate_[i];
    in.diff_rate = heat_diff_[i];
    in.new_e5 = new_e5[i];
    in.e5 = pred_[i].last_e5();
    in.time_to_limit_s = settled ? fc_[i].time_to_limit_s : INFINITY;
    in.above_safe = settled && abs_i >= cfg::kRestCurrentA && abs_i > fc_[i].i_safe_a;
    in.leak_watch = leak_ok && leak_.leak_a(i) >= cfg::kLeakWatchA;
    in.drift = resist_.drift(i);
    in.heat_w = obs_[i].heat_w();
    in.core_c = obs_[i].core_c();
    const int lvl = risk_[i].step(in);
    if (lvl != last_level_[i]) {
      char r[160];
      reason_list(risk_[i].reasons(), r, sizeof r);
      static const EventKind kinds[] = {EventKind::Info, EventKind::Watch, EventKind::Warning,
                                        EventKind::Trip};
      log(kinds[lvl], i, "Cell %d risk %s%s%s", i + 1, level_name(lvl), r[0] ? ": " : "", r);
      last_level_[i] = lvl;
    }
    if (lvl == 3) {
      char r[64];
      trip(TripCode::PredictiveRisk, i, reason_list(risk_[i].reasons() & ~kThermalWatch &
                                                        ~kElectricalWatch, r, sizeof r));
    }
    pack_risk_ = std::max(pack_risk_, lvl);
  }
}

void Supervisor::check_limits(const Measurements& m) {
  constexpr float dt = cfg::kDt;
  constexpr float hold = cfg::kLimitHoldS;
  uint32_t w = 0;
  bool cond = false;
  char d[64];

  // Sensor plausibility (section 8) and failures (section 10): one invalid sample is a
  // warning; 2 s of invalid samples latches a fault that opens both branches.
  for (int ch = 0; ch < kChannelCount; ++ch) {
    if (!m.invalid[ch]) continue;
    w |= kWarnSensor;
    cond = true;
    if (m.invalid_for_s[ch] < cfg::kSensorFaultHoldS) continue;
    if (ch == kChTaps) {
      trip(TripCode::TapSensor, -1, "ADS1115 read or tap plausibility failed for 2 s");
    } else if (ch == kChCurrent) {
      trip(TripCode::CurrentSensor, -1, "INA226 read failed for 2 s");
    } else {
      const int n = ch - kChNtc0;
      std::snprintf(d, sizeof d, "NTC%d %s for 2 s", n + 1,
                    m.flat_line[n] ? "stuck (code unchanged)" : "open, short or unreadable");
      trip(n == cfg::kAmbient ? TripCode::AmbientNtc : TripCode::CellNtc,
           n == cfg::kAmbient ? -1 : n, d);
    }
  }

  // Cell voltages.
  if (m.ever_valid[kChTaps]) {
    const int hi = static_cast<int>(std::max_element(m.cell_v, m.cell_v + cfg::kCells) - m.cell_v);
    const int lo = static_cast<int>(std::min_element(m.cell_v, m.cell_v + cfg::kCells) - m.cell_v);
    const float vmax = m.cell_v[hi], vmin = m.cell_v[lo];
    if (warn_high_.update(vmax >= cfg::kCellHighWarnV, vmax < cfg::kCellHighWarnV - cfg::kHystV,
                          dt, hold))
      w |= kWarnCellHigh;
    if (trip_high_.update(vmax >= cfg::kCellHighTripV, false, dt, hold)) {
      std::snprintf(d, sizeof d, "cell %d at %.3f V", hi + 1, vmax);
      trip(TripCode::CellHigh, hi, d);
    }
    if (warn_low_.update(vmin <= cfg::kCellLowWarnV, vmin > cfg::kCellLowWarnV + cfg::kHystV, dt,
                         hold))
      w |= kWarnCellLow;
    if (trip_low_.update(vmin <= cfg::kCellLowTripV, false, dt, hold)) {
      std::snprintf(d, sizeof d, "cell %d at %.3f V", lo + 1, vmin);
      trip(TripCode::CellLow, lo, d);
    }
    cond = cond || vmax >= cfg::kCellHighTripV || vmin <= cfg::kCellLowTripV;
  }

  // Cell temperatures, spread and rate of rise.
  bool temps_seen = true;
  for (int i = 0; i < cfg::kCells; ++i) temps_seen = temps_seen && m.ever_valid[kChNtc0 + i];
  if (temps_seen) {
    const float* t = m.temp_lp_c;
    const int hot = static_cast<int>(std::max_element(t, t + cfg::kCells) - t);
    const float tmax = t[hot];
    const float tmin = *std::min_element(t, t + cfg::kCells);
    if (mode_ == Mode::Charge) {
      if (warn_ctemp_.update(tmax >= cfg::kChargeTempWarnC,
                             tmax < cfg::kChargeTempWarnC - cfg::kHystC, dt, hold))
        w |= kWarnChargeTemp;
      if (trip_ctemp_.update(tmax >= cfg::kChargeTempTripC, false, dt, hold)) {
        std::snprintf(d, sizeof d, "cell %d at %.1f C while charging", hot + 1, tmax);
        trip(TripCode::ChargeTemp, hot, d);
      }
      cond = cond || tmax >= cfg::kChargeTempTripC;
    } else {
      warn_ctemp_.reset();
      trip_ctemp_.reset();
    }
    if (warn_dtemp_.update(tmax >= cfg::kDischargeTempWarnC,
                           tmax < cfg::kDischargeTempWarnC - cfg::kHystC, dt, hold))
      w |= kWarnDischargeTemp;
    if (trip_dtemp_.update(tmax >= cfg::kDischargeTempTripC, false, dt, hold)) {
      std::snprintf(d, sizeof d, "cell %d at %.1f C", hot + 1, tmax);
      trip(TripCode::DischargeTemp, hot, d);
    }
    const float spread = tmax - tmin;
    if (warn_spread_.update(spread >= cfg::kSpreadWarnC, spread < cfg::kSpreadWarnC - cfg::kHystC,
                            dt, hold))
      w |= kWarnSpread;
    if (trip_spread_.update(spread >= cfg::kSpreadTripC, false, dt, hold)) {
      std::snprintf(d, sizeof d, "spread %.1f C", spread);
      trip(TripCode::TempSpread, -1, d);
    }

    // Raw rate-of-rise backstop; the unfitted limits apply until the model is fitted (9.9).
    const bool fitted = params_.mode == ModelMode::Fitted;
    const float warn_lim = fitted ? cfg::kRiseWarnCPerMin : cfg::kRiseWarnUnfittedCPerMin;
    const float trip_lim = fitted ? cfg::kRiseTripCPerMin : cfg::kRiseTripUnfittedCPerMin;
    float rmax = -INFINITY;
    int rcell = -1;
    for (int i = 0; i < cfg::kCells; ++i) {
      if (m.rise_valid[i] && m.rise_c_per_min[i] > rmax) {
        rmax = m.rise_c_per_min[i];
        rcell = i;
      }
    }
    if (rcell >= 0) {
      if (warn_rise_.update(rmax >= warn_lim, rmax < warn_lim - cfg::kHystRateCPerMin, dt,
                            cfg::kRiseWarnHoldS))
        w |= kWarnRise;
      if (trip_rise_.update(rmax >= trip_lim, false, dt, cfg::kRiseTripHoldS)) {
        std::snprintf(d, sizeof d, "cell %d rising %.2f C/min (limit %.1f)", rcell + 1, rmax,
                      trip_lim);
        trip(TripCode::RiseRate, rcell, d);
      }
      cond = cond || rmax >= trip_lim;
    }
    cond = cond || tmax >= cfg::kDischargeTempTripC || spread >= cfg::kSpreadTripC;
  }

  // Pack current: positive is discharge.
  if (m.ever_valid[kChCurrent]) {
    const float a = m.current_a;
    if (warn_dcur_.update(a >= cfg::kDischargeWarnA, a < cfg::kDischargeWarnA - cfg::kHystA, dt,
                          hold))
      w |= kWarnDischargeCurrent;
    if (trip_dcur_.update(a >= cfg::kDischargeTripA, false, dt, hold)) {
      std::snprintf(d, sizeof d, "discharge %.2f A", a);
      trip(TripCode::DischargeCurrent, -1, d);
    }
    if (trip_ccur_.update(a <= -cfg::kChargeTripA, false, dt, hold)) {
      std::snprintf(d, sizeof d, "charge %.2f A", -a);
      trip(TripCode::ChargeCurrent, -1, d);
    }
    cond = cond || a >= cfg::kDischargeTripA || a <= -cfg::kChargeTripA;
  }

  // Predictive trip conditions, for the reset rule.
  for (int i = 0; i < cfg::kCells; ++i) {
    if (risk_[i].level() >= 3) cond = true;
    if (thermal_on_ && thermal_start_t_ >= 0.0 && obs_[i].heat_w() < cfg::kContactHeatW &&
        std::fabs(m.current_a) >= cfg::kContactMinCurrentA)
      cond = true;
  }

  const uint32_t added = w & ~warnings_;
  if (added) {
    char names[128];
    log(EventKind::Info, -1, "Warning: %s", warning_list(added, names, sizeof names));
  }
  warnings_ = w;
  if (cond) last_cond_t_ = t_;
}

void Supervisor::update_state(const Measurements& m) {
  if (!proven_) {
    bool ok = true;
    for (int ch = 0; ch < kChannelCount; ++ch)
      ok = ok && m.valid_for_s[ch] >= cfg::kSensorFaultHoldS - 1e-4f;
    if (ok) {
      proven_ = true;
      if (!latch_.branches) log(EventKind::Info, -1, "Sensors plausible for 2 s: branches enabled");
    }
  }
  state_ = latch_.branches ? State::Tripped : (proven_ ? State::Run : State::Startup);
  out_.load_on = proven_ && !(latch_.branches & kBranchLoad);
  out_.charge_on = proven_ && !(latch_.branches & kBranchCharge);
  out_.alarm = latch_.branches ? Alarm::Trip : (pack_risk_ >= 2 ? Alarm::Warning : Alarm::Off);
}

void Supervisor::trip(TripCode code, int cell, const char* detail) {
  const uint32_t bit = 1u << static_cast<int>(code);
  if (latch_.trips & bit) return;
  const uint8_t br = trip_branches(code);
  const Measurements& m = front_.last();

  TripRecord& r = trip_log_[trip_pos_];
  r = TripRecord();
  r.t_s = t_;
  r.code = code;
  r.cell = static_cast<int8_t>(cell);
  r.opened = br;
  r.load_was_on = out_.load_on;
  r.charge_was_on = out_.charge_on;
  for (int i = 0; i < cfg::kCells; ++i) {
    r.cell_v[i] = m.cell_v[i];
    r.heat_w[i] = thermal_start_t_ >= 0.0 ? obs_[i].heat_w() : NAN;
    r.leak_a[i] = leak_.valid() ? leak_.leak_a(i) : NAN;
  }
  for (int i = 0; i < cfg::kNtcs; ++i) r.temp_c[i] = m.temp_lp_c[i];
  r.current_a = m.current_a;
  std::snprintf(r.detail, sizeof r.detail, "%s", detail ? detail : "");
  trip_pos_ = (trip_pos_ + 1) % kTripLog;
  if (trip_n_ < kTripLog) ++trip_n_;

  latch_.trips |= bit;
  latch_.branches |= br;
  if (latch_.first == 0) {
    latch_.first = static_cast<uint8_t>(code);
    latch_.cell = static_cast<int8_t>(cell);
  }
  ++latch_version_;
  log(EventKind::Trip, cell, "TRIP %s: %s; %s held open", trip_name(code), r.detail,
      branch_text(br));
}

void Supervisor::reset_trip_timers() {
  for (Persist* p : {&trip_high_, &trip_low_, &trip_ctemp_, &trip_dtemp_, &trip_spread_,
                     &trip_rise_, &trip_dcur_, &trip_ccur_})
    p->reset();
  for (Persist& p : contact_) p.reset();
}

ResetResult Supervisor::request_reset() {
  ResetResult res = ResetResult::Accepted;
  const Measurements& m = front_.last();
  if (!latch_.branches) {
    res = ResetResult::NotLatched;
  } else {
    for (int ch = 0; ch < kChannelCount; ++ch)
      if (m.invalid[ch] || !m.ever_valid[ch]) res = ResetResult::SensorsInvalid;
    if (res == ResetResult::Accepted) {
      for (int i = 0; i < cfg::kCells; ++i)
        if (!(m.cell_v[i] >= cfg::kResetCellMinV && m.cell_v[i] <= cfg::kResetCellMaxV))
          res = ResetResult::CellVoltage;
    }
    if (res == ResetResult::Accepted) {
      for (int i = 0; i < cfg::kNtcs; ++i)
        if (!(m.temp_lp_c[i] < cfg::kResetTempMaxC)) res = ResetResult::Temperature;
    }
    if (res == ResetResult::Accepted && t_ - last_cond_t_ < cfg::kResetClearS) {
      res = ResetResult::NotClear;
    }
  }
  if (res == ResetResult::Accepted) {
    latch_ = LatchRecord();
    ++latch_version_;
    reset_trip_timers();
    log(EventKind::Reset, -1, "Manual reset accepted");
  } else if (res != ResetResult::NotLatched) {
    log(EventKind::Reset, -1, "Manual reset refused: %s", reset_result_text(res));
  }
  return res;
}

void Supervisor::restore_latch(const LatchRecord& rec) {
  if (!rec.branches) return;
  latch_ = rec;
  log(EventKind::Trip, rec.cell, "Latched trip kept from before the restart: %s; %s held open",
      trip_name(static_cast<TripCode>(rec.first)), branch_text(rec.branches));
}

void Supervisor::latch_external(TripCode code, const char* detail) { trip(code, -1, detail); }

void Supervisor::clear_prediction_record() {
  for (Predictor& p : pred_) p.clear_record();
}

void Supervisor::snapshot(Snapshot& s) const {
  const Measurements& m = front_.last();
  s.seq = seq_;
  s.t_s = t_;
  s.state = state_;
  s.mode = mode_;
  s.model = params_.mode;
  s.thermal_ready = thermal_on_ && thermal_start_t_ >= 0.0 &&
                    (t_ - thermal_start_t_) >= cfg::kObserverWarmupS;
  s.ocv_table = leak_.enabled();
  s.out = out_;
  s.risk = pack_risk_;
  s.warnings = warnings_;
  s.latch = latch_;
  s.n_trips = trip_n_;
  for (int k = 0; k < trip_n_; ++k)
    s.trips[k] = trip_log_[(trip_pos_ - trip_n_ + k + kTripLog) % kTripLog];
  // A channel that has never read plausibly has no value yet (null in the JSON), not zero.
  const bool taps_seen = m.ever_valid[kChTaps];
  s.pack_v = taps_seen ? m.pack_v : NAN;
  s.current_a = m.ever_valid[kChCurrent] ? m.current_a : NAN;
  s.t_amb = m.ever_valid[kChNtc0 + cfg::kAmbient] ? m.temp_lp_c[cfg::kAmbient] : NAN;
  s.t_trip = mode_ == Mode::Charge ? cfg::kChargeTempTripC : cfg::kDischargeTempTripC;
  for (int ch = 0; ch < kChannelCount; ++ch) {
    s.ch_invalid[ch] = m.invalid[ch];
    s.ch_invalid_for_s[ch] = m.invalid_for_s[ch];
  }
  for (int i = 0; i < cfg::kNtcs; ++i) {
    s.flat_line[i] = m.flat_line[i];
    s.raw_temp_c[i] = m.raw_temp_c[i];
  }
  s.leak_rest_s = leak_.rest_s();
  s.leak_minutes = leak_.minutes();
  s.leak_valid = leak_.valid();

  const bool running = thermal_on_ && thermal_start_t_ >= 0.0;
  float i_safe = INFINITY;
  for (int i = 0; i < cfg::kCells; ++i) {
    CellSnapshot& c = s.cells[i];
    c = CellSnapshot();
    const bool ntc_seen = m.ever_valid[kChNtc0 + i];
    c.v = taps_seen ? m.cell_v[i] : NAN;
    s.raw_tap_v[i] = m.raw_tap_v[i];
    c.r_model_ohm = r_model_[i];
    c.r_avg_ohm = resist_.average_r(i);
    c.r_steps = resist_.steps(i);
    c.r_drift = resist_.drift(i);
    c.t_meas = ntc_seen ? m.temp_c[i] : NAN;
    c.t_lp = ntc_seen ? m.temp_lp_c[i] : NAN;
    c.rise = m.rise_c_per_min[i];
    c.rise_valid = m.rise_valid[i];
    if (running) {
      const Predictor& p = pred_[i];
      c.t_core = obs_[i].core_c();
      c.t_surf = obs_[i].surface_c();
      c.heat_w = obs_[i].heat_w();
      c.heat_rate = heat_rate_[i];
      c.heat_diff = heat_diff_[i];
      c.f1 = p.forecast1_c();
      c.f5 = p.forecast5_c();
      c.has_e1 = p.has_e1();
      c.has_e5 = p.has_e5();
      c.e1 = p.last_e1();
      c.e5 = p.last_e5();
      c.verdict = p.verdict();
      c.rms1_hour = p.rms1().rms_hour(t_);
      c.rms5_hour = p.rms5().rms_hour(t_);
      c.rms1_all = p.rms1().rms_all();
      c.rms5_all = p.rms5().rms_all();
      c.n5_all = p.rms5().count_all();
      c.t_eq = fc_[i].t_eq_c;
      c.time_to_limit_s = fc_[i].time_to_limit_s;
      c.i_safe = fc_[i].i_safe_a;
      if (std::isfinite(c.i_safe)) i_safe = std::min(i_safe, c.i_safe);
    }
    if (leak_.valid()) {
      c.leak_a = leak_.leak_a(i);
      c.p_leak_w = p_leak_[i];
    }
    c.cross = cross_[i];
    c.level = risk_[i].level();
    c.reasons = risk_[i].reasons();
  }
  s.i_safe = std::isfinite(i_safe) ? i_safe : NAN;
  s.raw = raw_;
  s.n_events = std::min(ev_n_, kSnapshotEvents);
  for (int k = 0; k < s.n_events; ++k)
    s.events[k] = events_[(ev_pos_ - s.n_events + k + kEvents) % kEvents];
}

}  // namespace bms
