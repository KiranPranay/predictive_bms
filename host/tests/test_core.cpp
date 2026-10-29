// Unit tests of the portable core: each one checks a formula or rule of the architecture.

#include <cstring>
#include <string>

#include "bms/electrical.h"
#include "bms/filters.h"
#include "bms/risk.h"
#include "bms/sensors.h"
#include "bms/supervisor.h"
#include "bms/thermal.h"
#include "check.h"

using namespace bms;

namespace {

RawSample healthy_raw(double t, const Calibration& cal, float cell_v = 3.70f, float amps = 0.0f,
                      float temp_c = 25.0f) {
  RawSample r;
  r.t_s = t;
  r.ads_ok = true;
  for (int i = 0; i < cfg::kCells; ++i) r.ads_v[i] = cell_v * (i + 1) / cal.tap_gain[i];
  r.ina_ok = true;
  r.shunt_v = amps * cal.shunt_ohm;
  for (int i = 0; i < cfg::kNtcs; ++i) {
    r.ntc_ok[i] = true;
    r.ntc_mv[i] = ntc_millivolts(temp_c, cal);
    r.ntc_code[i] = static_cast<uint32_t>(t * 5) % 7 + 1000;   // never stuck
  }
  return r;
}

Measurements rest_measurements(double t, const float v[4], float amps = 0.0f) {
  Measurements m;
  m.t_s = t;
  m.taps_valid = m.current_valid = true;
  m.current_a = m.raw_current_a = amps;
  for (int i = 0; i < 4; ++i) m.cell_v[i] = m.raw_cell_v[i] = v[i];
  return m;
}

}  // namespace

// --- Section 8: filters ------------------------------------------------------------------------

TEST(median5_rejects_a_single_spike) {
  Median5 m;
  for (float v : {1.0f, 1.0f, 9.0f, 1.0f, 1.0f}) m.push(v);
  CHECK_NEAR(m.value(), 1.0, 1e-6);
}

TEST(lowpass_has_a_10_s_time_constant) {
  LowPass lp;
  lp.push(0.0f);
  for (int k = 0; k < 50; ++k) lp.push(1.0f);   // 10 s at 5 Hz
  CHECK_NEAR(lp.value(), 1.0 - std::exp(-1.0), 0.01);
}

TEST(slope_window_fits_a_straight_line) {
  SlopeWindow<cfg::kSlopeSamples> w;
  for (int k = 0; k < 400; ++k) w.push(20.0f + 0.01f * k * cfg::kDt);   // 0.6 C/min
  CHECK(w.full());
  CHECK_NEAR(w.slope(cfg::kDt) * 60.0, 0.6, 1e-3);
}

TEST(persist_needs_the_hold_time_and_the_release) {
  Persist p;
  for (int k = 0; k < 4; ++k) CHECK(!p.update(true, false, 0.2f, 1.0f));
  CHECK(p.update(true, false, 0.2f, 1.0f));     // the fifth sample makes 1.0 s
  CHECK(p.update(false, false, 0.2f, 1.0f));    // no release yet
  CHECK(!p.update(false, true, 0.2f, 1.0f));
}

// --- Sections 5 and 6: sensors -----------------------------------------------------------------

TEST(ntc_reads_25_c_at_half_supply) {
  Calibration cal;
  CHECK_NEAR(ntc_millivolts(25.0f, cal), 1650.0, 0.01);
  for (float t = 0.0f; t <= 80.0f; t += 5.0f) CHECK_NEAR(ntc_temperature_c(ntc_millivolts(t, cal), cal), t, 0.01);
  CHECK(std::isnan(ntc_temperature_c(0.0f, cal)));
  CHECK(std::isnan(ntc_temperature_c(3300.0f, cal)));
}

TEST(open_and_shorted_ntc_are_invalid) {
  Calibration cal;
  FrontEnd fe(cal);
  const float r[4] = {0.035f, 0.035f, 0.035f, 0.035f};
  RawSample raw = healthy_raw(0.0, cal);
  raw.ntc_mv[1] = 3100.0f;   // open: the ADC tops out
  raw.ntc_mv[3] = 60.0f;     // short
  const Measurements& m = fe.process(raw, r);
  CHECK(m.ntc_valid[0]);
  CHECK(!m.ntc_valid[1]);
  CHECK(!m.ntc_valid[3]);
}

TEST(tap_order_negative_cell_and_jump_checks) {
  Calibration cal;
  const float r[4] = {0.035f, 0.035f, 0.035f, 0.035f};
  {
    FrontEnd fe(cal);
    RawSample raw = healthy_raw(0.0, cal);
    raw.ads_v[2] = raw.ads_v[1] * cal.tap_gain[1] / cal.tap_gain[2] - 0.01f;   // tap 3 below tap 2
    CHECK(!fe.process(raw, r).taps_valid);
  }
  {
    FrontEnd fe(cal);
    CHECK(fe.process(healthy_raw(0.0, cal), r).taps_valid);
    RawSample raw = healthy_raw(0.2, cal);
    for (int i = 1; i < 4; ++i) raw.ads_v[i] += 0.150f / cal.tap_gain[i];   // cell 2 jumps 150 mV
    CHECK(!fe.process(raw, r).taps_valid);
  }
  {
    // A 3 A load step drops every cell by 105 mV: explained by the current, so valid.
    FrontEnd fe(cal);
    CHECK(fe.process(healthy_raw(0.0, cal, 3.70f, 0.0f), r).taps_valid);
    const Measurements& m = fe.process(healthy_raw(0.2, cal, 3.70f - 0.105f, 3.0f), r);
    CHECK(m.taps_valid);
    CHECK_NEAR(m.raw_cell_v[2], 3.595, 1e-3);
    CHECK_NEAR(m.raw_current_a, 3.0, 1e-4);
  }
}

// --- Section 9.1 and 9.6: model and forecasts --------------------------------------------------

TEST(model_settles_at_ambient_plus_heat_times_resistance) {
  ThermalParams p;
  const Discrete d = discretise(p, 0, 10.0f);
  float x[3] = {25.0f, 25.0f, 0.0f};
  for (int k = 0; k < 2000; ++k) {   // 20 000 s, many time constants
    float n[3];
    for (int i = 0; i < 3; ++i) {
      n[i] = d.gam[i][0] * 1.0f + d.gam[i][1] * 25.0f;   // 1 W of I^2 R
      for (int j = 0; j < 3; ++j) n[i] += d.phi[i][j] * x[j];
    }
    for (int i = 0; i < 3; ++i) x[i] = n[i];
  }
  CHECK_NEAR(x[1], 25.0 + 1.0 * p.r_air[0], 0.01);                  // surface
  CHECK_NEAR(x[0], 25.0 + 1.0 * (p.r_air[0] + p.r_core), 0.01);     // core
}

TEST(slow_time_constant_is_near_total_heat_capacity_times_resistance) {
  ThermalParams p;
  const float tau = slow_time_constant_s(p, 0);
  CHECK(tau > 1350.0f && tau < 1450.0f);   // about 45 J/C x 32 C/W
}

TEST(safe_current_matches_the_architecture_example) {
  // 9.6: about 30 C/W and 35 mOhm in still air at 25 C ambient give near 5 A.
  ThermalParams p;
  const Forecast f = forecast(p, 0, 0.035f, 0.0f, 25.0f, 25.0f, 0.0f, 55.0f, 1400.0f);
  CHECK_NEAR(f.i_safe_a, std::sqrt(1.0 / 0.035), 1e-3);
  CHECK(std::isinf(f.time_to_limit_s));
  // 5 A at 35 C ambient: settles above 55 C, so a finite time to the limit.
  const Forecast g = forecast(p, 0, 0.035f, 5.0f, 35.0f, 40.0f, 0.0f, 55.0f, 1400.0f);
  const double t_eq = 35.0 + 25.0 * 0.035 * 30.0;
  CHECK_NEAR(g.t_eq_c, t_eq, 1e-3);
  CHECK_NEAR(g.time_to_limit_s, 1400.0 * std::log((t_eq - 40.0) / (t_eq - 55.0)), 0.5);
}

TEST(abnormal_heat_rate_matches_the_architecture) {
  ThermalParams p;   // 45 J/C in total
  CHECK_NEAR(heat_rate_c_per_min(p, 0.375f), 0.5, 1e-4);
  CHECK_NEAR(heat_rate_c_per_min(p, 0.75f), 1.0, 1e-4);
}

// --- Sections 9.2 and 9.3: observer and predictions --------------------------------------------

namespace {
// Advances the model's true state by one sample.
void plant(const Discrete& d, float x[3], float pj, float tamb) {
  float n[3];
  for (int i = 0; i < 3; ++i) {
    n[i] = d.gam[i][0] * pj + d.gam[i][1] * tamb;
    for (int j = 0; j < 3; ++j) n[i] += d.phi[i][j] * x[j];
  }
  for (int i = 0; i < 3; ++i) x[i] = n[i];
}
}  // namespace

TEST(observer_estimates_abnormal_heat_and_core) {
  ThermalParams p;
  KalmanTuning k;
  CellObserver obs;
  obs.configure(p, k, 0);
  obs.reset(25.0f);
  const Discrete d = discretise(p, 0, cfg::kDt);
  float x[3] = {25.0f, 25.0f, 0.5f};   // 0.5 W the observer does not know about
  for (int n = 0; n < 5 * 600; ++n) {
    plant(d, x, 0.2f, 25.0f);
    obs.step(0.2f, 25.0f, x[1]);
  }
  CHECK_NEAR(obs.heat_w(), 0.5, 0.03);
  CHECK_NEAR(obs.core_c(), x[0], 0.1);
}

TEST(prediction_is_confirmed_on_a_healthy_cell_and_not_on_a_faulty_one) {
  ThermalParams p;
  KalmanTuning k;
  const Discrete d = discretise(p, 0, cfg::kDt);
  for (float fault : {0.0f, 0.2f}) {
    CellObserver obs;
    Predictor pred;
    obs.configure(p, k, 0);
    pred.configure(p, 0);
    obs.reset(25.0f);
    float x[3] = {25.0f, 25.0f, 0.0f};
    float worst = 0.0f;
    for (int n = 0; n < 5 * 1200; ++n) {
      if (n == 5 * 300) x[2] = fault;   // the fault starts after 5 minutes
      const double t = n * cfg::kDt;
      const float pj = n < 5 * 600 ? 0.4f : 0.1f;   // a load change half way
      plant(d, x, pj, 25.0f);
      obs.step(pj, 25.0f, x[1]);
      const Predictor::Ended e = pred.advance(t, pj, 25.0f, 2.0f, x[1]);
      if (e.h5 && t > 900.0) worst = std::max(worst, e.e5);
      pred.maybe_start(t, obs, pj, 25.0f);
    }
    if (fault == 0.0f) {
      CHECK(worst < 0.05f);
      CHECK(pred.rms5().rms_all() < 0.05f);
    } else {
      CHECK(worst > 1.0f && worst < 1.5f);   // 9.3: about 1.3 C after five minutes
    }
  }
}

TEST(rms_record_keeps_the_last_hour) {
  RmsRecord r;
  r.add(0.0, 1.0f);
  r.add(30.0, 1.0f);
  r.add(4000.0, 0.5f);
  CHECK_NEAR(r.rms_hour(4000.0), 0.5, 1e-6);
  CHECK_NEAR(r.rms_all(), std::sqrt(2.25 / 3.0), 1e-6);
}

// --- Sections 9.4 and 9.5: electrical evidence -------------------------------------------------

TEST(resistance_from_a_current_step) {
  ModelParams p;
  ResistanceTracker rt;
  rt.configure(p);
  const float v0[4] = {3.70f, 3.70f, 3.70f, 3.70f};
  const float v1[4] = {3.63f, 3.63f, 3.63f, 3.63f};
  for (int k = 0; k < 3; ++k) rt.step(rest_measurements(k * 0.2, v0));
  for (int k = 3; k < 6; ++k) rt.step(rest_measurements(k * 0.2, v1, 2.0f));
  CHECK(rt.steps(0) == 1);
  CHECK_NEAR(rt.average_r(0), 0.035, 1e-4);
}

TEST(leak_of_20_ma_from_6_mv_per_hour) {
  // 9.5 example: 20 mA lowers a mid-charge cell about 6 mV per hour against the others, at
  // roughly 10 mV per 1 % of charge (1.0 V per unit).
  ModelParams p;
  p.ocv_points = 1;
  p.ocv_v[0] = 3.7f;
  p.ocv_slope[0] = 1.0f;
  LeakEstimator le;
  le.configure(p);
  const double slope = 0.006 / 3600.0;
  for (int n = 0; n <= 5 * 95 * 60; ++n) {
    const double t = n * cfg::kDt;
    const float v[4] = {3.70f, static_cast<float>(3.70 - slope * t), 3.70f, 3.70f};
    le.step(rest_measurements(t, v));
  }
  CHECK(le.valid());
  CHECK_NEAR(le.leak_a(1), 3.3 * 0.006, 0.0015);
  CHECK(le.leak_a(0) < 0.0f);
}

TEST(leak_restarts_when_current_flows) {
  ModelParams p;
  p.ocv_points = 1;
  p.ocv_slope[0] = 1.0f;
  LeakEstimator le;
  le.configure(p);
  const float v[4] = {3.7f, 3.7f, 3.7f, 3.7f};
  for (int n = 0; n < 5 * 40 * 60; ++n) le.step(rest_measurements(n * cfg::kDt, v));
  CHECK(le.rest_s() > 2000.0f);
  le.step(rest_measurements(2400.2, v, 0.5f));
  CHECK(le.rest_s() == 0.0f);
}

// --- Sections 9.7 and 9.8: risk ---------------------------------------------------------------

TEST(heat_trips_after_10_s_and_warns_after_30_s) {
  CellRisk r;
  CellRiskInputs in;
  in.thermal_on = true;
  in.heat_rate = 0.6f;
  for (int k = 0; k < 149; ++k) r.step(in);
  CHECK(r.level() == 0);
  r.step(in);   // 30 s
  CHECK(r.level() == 2);
  in.heat_rate = 1.1f;
  for (int k = 0; k < 49; ++k) r.step(in);
  CHECK(r.level() == 2);
  r.step(in);   // 10 s
  CHECK(r.level() == 3 && (r.reasons() & kReasonHeatTrip));
}

TEST(thermal_and_electrical_watch_together_make_warning) {
  CellRisk r;
  CellRiskInputs in;
  in.thermal_on = true;
  in.leak_watch = true;
  CHECK(r.step(in) == 1);
  in.new_e5 = true;
  in.e5 = 1.2f;
  CHECK(r.step(in) == 2);
  CHECK(r.reasons() & kReasonThermalAndElectrical);
  in.new_e5 = true;
  in.e5 = 0.7f;   // between the bands: the watch holds
  CHECK(r.step(in) == 2);
  in.e5 = 0.3f;   // back within the "confirmed normal" band
  CHECK(r.step(in) == 1);
}

TEST(a_steady_fault_is_not_self_acceleration) {
  // Heat that appears suddenly and then holds still stays at Warning (table 9.8).
  CellRisk r;
  CellRiskInputs in;
  in.thermal_on = true;
  in.heat_rate = 0.55f;
  for (int k = 0; k < 5 * 600; ++k) {
    in.heat_w = k < 5 * 20 ? 0.02f * k : 0.41f;
    in.core_c = 25.0f + 0.01f * k;   // warming steadily
    r.step(in);
    CHECK(r.level() <= 2);
  }
}

TEST(self_acceleration_trips_at_warning) {
  CellRisk r;
  CellRiskInputs in;
  in.thermal_on = true;
  in.heat_rate = 0.6f;
  int level = 0;
  double t_trip = -1.0;
  for (int k = 0; k < 5 * 300 && t_trip < 0; ++k) {
    const double t = k * cfg::kDt;
    in.heat_w = static_cast<float>(0.4 * std::exp(t / 250.0));   // x1.6 every 120 s
    in.core_c = static_cast<float>(30.0 + t / 100.0);             // +1.2 C every 120 s
    level = r.step(in);
    if (level == 3) t_trip = t;
  }
  CHECK(level == 3 && (r.reasons() & kReasonSelfAcceleration));
  // Warning from 30 s; the window starts there, so x1.5 and +1 C are reached about 100 s later.
  CHECK(t_trip > 120.0 && t_trip < 160.0);
}

// --- Supervisor --------------------------------------------------------------------------------

TEST(each_trip_opens_the_right_branch) {
  CHECK(trip_branches(TripCode::CellHigh) == kBranchCharge);
  CHECK(trip_branches(TripCode::ChargeTemp) == kBranchCharge);
  CHECK(trip_branches(TripCode::ChargeCurrent) == kBranchCharge);
  CHECK(trip_branches(TripCode::CellLow) == kBranchLoad);
  CHECK(trip_branches(TripCode::DischargeTemp) == kBranchLoad);
  CHECK(trip_branches(TripCode::DischargeCurrent) == kBranchLoad);
  CHECK(trip_branches(TripCode::TempSpread) == kBranchBoth);
  CHECK(trip_branches(TripCode::PredictiveRisk) == kBranchBoth);
  CHECK(trip_branches(TripCode::AmbientNtc) == kBranchBoth);
  CHECK(trip_branches(TripCode::ControllerReset) == kBranchBoth);
}

TEST(relays_stay_open_until_every_sensor_is_proven) {
  Calibration cal;
  ModelParams p;
  Supervisor sup(cal, p);
  Outputs o;
  for (int k = 0; k < 9; ++k) o = sup.step(healthy_raw(k * cfg::kDt, cal));
  CHECK(!o.load_on && !o.charge_on);
  o = sup.step(healthy_raw(9 * cfg::kDt, cal));   // 2 s of plausible readings
  CHECK(o.load_on && o.charge_on);
}

TEST(a_restored_latch_keeps_the_relays_open) {
  Calibration cal;
  ModelParams p;
  Supervisor sup(cal, p);
  LatchRecord rec;
  rec.branches = kBranchBoth;
  rec.trips = 1u << static_cast<int>(TripCode::PredictiveRisk);
  rec.first = static_cast<uint8_t>(TripCode::PredictiveRisk);
  sup.restore_latch(rec);
  Outputs o;
  for (int k = 0; k < 50; ++k) o = sup.step(healthy_raw(k * cfg::kDt, cal));
  CHECK(!o.load_on && !o.charge_on && o.alarm == Alarm::Trip);
  CHECK(sup.request_reset() == ResetResult::NotClear);   // within 60 s of boot
  for (int k = 50; k < 400; ++k) o = sup.step(healthy_raw(k * cfg::kDt, cal));
  CHECK(sup.request_reset() == ResetResult::Accepted);
  o = sup.step(healthy_raw(400 * cfg::kDt, cal));
  CHECK(o.load_on && o.charge_on);
}

TEST(json_is_complete_and_has_no_nan) {
  Calibration cal;
  ModelParams p;
  p.mode = ModelMode::Fitted;
  Supervisor sup(cal, p);
  for (int k = 0; k < 5 * 120; ++k) sup.step(healthy_raw(k * cfg::kDt, cal, 3.7f, 1.0f));
  Snapshot s;
  sup.snapshot(s);
  static char buf[24 * 1024];
  const int n = write_json(s, buf, sizeof buf);
  CHECK(n > 100);
  CHECK(buf[0] == '{' && buf[n - 1] == '}');
  for (const char* bad : {"nan", ":inf", ",inf", "-inf", "[inf"}) CHECK(!std::strstr(buf, bad));
  int depth = 0;
  for (int i = 0; i < n; ++i) {
    if (buf[i] == '{' || buf[i] == '[') ++depth;
    if (buf[i] == '}' || buf[i] == ']') --depth;
  }
  CHECK(depth == 0);
  CHECK(write_json(s, buf, 64) == 0);   // too small: reported, not cut short
  char row[512];
  CHECK(write_csv_row(s, row, sizeof row) > 0);
  CHECK(write_csv_header(row, sizeof row) > 0);
}
