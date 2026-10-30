#include "sim/scenario.h"

#include <algorithm>
#include <cmath>
#include <cstdarg>

namespace sim {

using bms::ModelMode;
using bms::Snapshot;
using bms::TripCode;

std::string fmt(const char* f, ...) {
  char buf[512];
  va_list ap;
  va_start(ap, f);
  std::vsnprintf(buf, sizeof buf, f, ap);
  va_end(ap);
  return buf;
}

bool Report::passed() const {
  if (checks_.empty()) return false;
  for (const Check& c : checks_)
    if (!c.ok) return false;
  return true;
}

// ---------------------------------------------------------------------------------------------

Bench::Bench(uint64_t seed, ModelMode mode) : pack(seed) {
  pack.set_uniform_temperature(25.0);
  for (CellTruth& c : pack.cell) c.soc = 0.5;
  cal = pack.calibration();
  params = pack.fitted_params();
  params.mode = mode;
  sup = std::make_unique<bms::Supervisor>(cal, params);
}

void Bench::step() {
  bms::RawSample raw = pack.read();
  raw.t_s -= boot_t_;   // the controller's clock starts at its own boot
  out = sup->step(raw);
  pack.load_relay = out.load_on;
  pack.charge_relay = out.charge_on;
  if (csv && ++sub_ >= csv_every) {
    sub_ = 0;
    static Snapshot s;
    sup->snapshot(s);
    char line[512];
    if (bms::write_csv_row(s, line, sizeof line)) std::fprintf(csv, "%s\n", line);
  }
  pack.step(bms::cfg::kDt);
}

void Bench::run(double seconds) {
  const long n = std::lround(seconds / bms::cfg::kDt);
  for (long k = 0; k < n; ++k) step();
}

bool Bench::run_until(double max_s, const std::function<bool()>& stop) {
  const long n = std::lround(max_s / bms::cfg::kDt);
  for (long k = 0; k < n; ++k) {
    step();
    if (stop()) return true;
  }
  return false;
}

Snapshot Bench::snap() const {
  Snapshot s;
  sup->snapshot(s);
  return s;
}

void Bench::restart_controller(bool crash) {
  const bms::LatchRecord rec = sup->latch_record();
  sup = std::make_unique<bms::Supervisor>(cal, params);
  boot_t_ = pack.t;
  sup->restore_latch(rec);
  if (crash) sup->latch_external(TripCode::ControllerReset, "restart after a crash or watchdog");
  out = bms::Outputs();
  pack.load_relay = pack.charge_relay = false;   // the pull-ups hold both relays open
}

void Bench::set_mode(ModelMode mode) {
  params.mode = mode;
  sup->set_params(params);
}

// ---------------------------------------------------------------------------------------------
// Helpers.

namespace {

constexpr int kCells = bms::cfg::kCells;

TripCode first_trip(const Bench& b) {
  return static_cast<TripCode>(b.sup->latch_record().first);
}
bool latched(const Bench& b) { return b.sup->latch_record().branches != 0; }
bool has_trip(const Bench& b, TripCode c) {
  return b.sup->latch_record().trips & (1u << static_cast<int>(c));
}
const char* tname(TripCode c) { return bms::trip_name(c); }

// Running record of what the supervisor showed during a run.
struct Track {
  int max_level = 0;
  int max_cell_level[kCells] = {};
  uint32_t reasons[kCells] = {};
  double t_level[4] = {-1, -1, -1, -1};   // first time the pack reached each level
  float max_rate[kCells] = {-1e9f, -1e9f, -1e9f, -1e9f};
  float max_abs_rate = 0.0f;
  float max_ts[kCells] = {-1e9f, -1e9f, -1e9f, -1e9f};
  float max_e5[kCells] = {-1e9f, -1e9f, -1e9f, -1e9f};
  float min_ttl = INFINITY;
  bool ttl_seen = false;
  uint32_t warnings = 0;
  bool alarm_warning = false;
  int samples = 0;

  void update(const Snapshot& s) {
    ++samples;
    max_level = std::max(max_level, s.risk);
    for (int l = 0; l <= s.risk; ++l)
      if (t_level[l] < 0) t_level[l] = s.t_s;
    warnings |= s.warnings;
    if (s.out.alarm == bms::Alarm::Warning) alarm_warning = true;
    for (int i = 0; i < kCells; ++i) {
      const bms::CellSnapshot& c = s.cells[i];
      max_cell_level[i] = std::max(max_cell_level[i], c.level);
      reasons[i] |= c.reasons;
      max_ts[i] = std::max(max_ts[i], c.t_meas);
      if (s.thermal_ready) {
        max_rate[i] = std::max(max_rate[i], c.heat_rate);
        max_abs_rate = std::max(max_abs_rate, std::fabs(c.heat_rate));
        if (c.has_e5) max_e5[i] = std::max(max_e5[i], c.e5);
        if (std::isfinite(c.time_to_limit_s)) {
          ttl_seen = true;
          min_ttl = std::min(min_ttl, c.time_to_limit_s);
        }
      }
    }
  }
};

void expect_healthy_accuracy(const Snapshot& s, Report& r) {
  for (int i = 0; i < kCells; ++i) {
    const float rms = s.cells[i].rms5_all;
    r.expect(std::isfinite(rms) && rms <= 0.5f,
             fmt("cell %d 5-minute prediction error %.3f C RMS over %d checks (limit 0.5)", i + 1,
                 rms, s.cells[i].n5_all));
  }
}

void expect_trip(const Bench& b, Report& r, TripCode code, uint8_t branches) {
  r.expect(first_trip(b) == code,
           fmt("first trip is %s (got %s)", tname(code), tname(first_trip(b))));
  const bool load_open = !b.out.load_on;
  const bool charge_open = !b.out.charge_on;
  const bool want_load = branches & bms::kBranchLoad;
  const bool want_charge = branches & bms::kBranchCharge;
  r.expect(load_open == want_load && charge_open == want_charge,
           fmt("relays: load %s, charge %s (expected load %s, charge %s)",
               load_open ? "open" : "closed", charge_open ? "open" : "closed",
               want_load ? "open" : "closed", want_charge ? "open" : "closed"));
}

// ---------------------------------------------------------------------------------------------
// Healthy operation: the Gate 9 and Gate 10 pass criteria.

void s_rest(Bench& b, Report& r) {
  Track tr;
  b.run_until(30 * 60, [&] { tr.update(b.snap()); return false; });
  const Snapshot s = b.snap();
  r.expect(!latched(b), "no trip in 30 minutes at rest");
  r.expect(tr.max_level == 0, fmt("risk stayed Normal (highest: %s)", bms::level_name(tr.max_level)));
  r.expect(tr.max_abs_rate < 0.25f,
           fmt("abnormal heat within +-0.25 C/min equivalent (largest %.3f)", tr.max_abs_rate));
  r.expect(s.out.load_on && s.out.charge_on, "both branches enabled");
  expect_healthy_accuracy(s, r);
}

void s_discharge_steps(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = 0.75;
  Track tr;
  auto phase = [&](double amps, double minutes) {
    b.pack.load_a = amps;
    b.run_until(minutes * 60, [&] { tr.update(b.snap()); return false; });
  };
  phase(0.0, 2);
  phase(0.25, 5);
  phase(0.5, 5);
  phase(1.0, 5);
  phase(2.0, 5);
  phase(0.0, 10);
  phase(1.0, 15);   // Gate 9 step 7: repeat 1 A and 2 A with the fitted model
  phase(0.0, 10);
  phase(2.0, 15);
  phase(0.0, 10);
  const Snapshot s = b.snap();
  r.expect(!latched(b), "no trip through the 0.25-2 A steps");
  r.expect(tr.max_level == 0, fmt("risk stayed Normal (highest: %s)", bms::level_name(tr.max_level)));
  float worst = -1e9f;
  for (float v : tr.max_rate) worst = std::max(worst, v);
  r.expect(worst < 0.25f, fmt("abnormal heat below 0.25 C/min equivalent at every current "
                              "(largest %.3f)", worst));
  expect_healthy_accuracy(s, r);
  for (int i = 0; i < kCells; ++i) {
    const float est = s.cells[i].r_avg_ohm, truth = static_cast<float>(b.pack.cell[i].r_ohm);
    r.expect(s.cells[i].r_steps >= 3 && std::fabs(est - truth) <= 0.15f * truth,
             fmt("cell %d online resistance %.1f mOhm against Gate 4 %.1f mOhm over %d steps "
                 "(within 15 %%)",
                 i + 1, est * 1e3f, truth * 1e3f, s.cells[i].r_steps));
  }
}

void s_discharge_5a(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = 0.9;
  Track tr;
  b.run(90);
  b.pack.load_a = 4.8;   // the 5.0 A trip is the limit, so the test current sits just below it
  b.run_until(20 * 60, [&] { tr.update(b.snap()); return false; });
  r.expect(!latched(b), "no trip during 20 minutes at 4.8 A");
  r.expect(tr.max_level <= 1, fmt("the heating expected at 5 A is not flagged: highest risk %s",
                                  bms::level_name(tr.max_level)));
  r.expect(tr.warnings & bms::kWarnDischargeCurrent, "the 4.5 A current warning was shown");
  float worst = -1e9f, hottest = -1e9f;
  for (int i = 0; i < kCells; ++i) {
    worst = std::max(worst, tr.max_rate[i]);
    hottest = std::max(hottest, tr.max_ts[i]);
  }
  r.note(fmt("largest abnormal heat %.2f C/min equivalent; hottest cell %.1f C", worst, hottest));
  r.note("Polarisation heat is not in the model, so part of it shows as abnormal heat at high "
         "current. Gate 9 measures how much.");
}

void s_charge(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = 0.3;
  Track tr;
  b.run(90);
  b.pack.charge_a = 1.5;
  const bool reached = b.run_until(3 * 3600, [&] {
    const Snapshot s = b.snap();
    tr.update(s);
    float vmax = 0;
    for (const auto& c : s.cells) vmax = std::max(vmax, c.v);
    return vmax >= 4.10f;   // Gate 10 step 6: end the first charge around 4.10 V per cell
  });
  b.pack.charge_a = 0.0;
  b.run_until(10 * 60, [&] { tr.update(b.snap()); return false; });
  const Snapshot s = b.snap();
  r.expect(reached, "the charge reached 4.10 V per cell");
  r.expect(!latched(b), "no trip during the charge");
  r.expect(tr.max_level == 0, fmt("risk stayed Normal (highest: %s)", bms::level_name(tr.max_level)));
  float worst = -1e9f;
  for (float v : tr.max_rate) worst = std::max(worst, v);
  r.expect(worst < 0.25f,
           fmt("abnormal heat below 0.25 C/min equivalent (largest %.3f)", worst));
  float vmin = 9, vmax = 0;
  for (const auto& c : s.cells) {
    vmin = std::min(vmin, c.v);
    vmax = std::max(vmax, c.v);
  }
  r.expect(vmax - vmin < 0.05f, fmt("cell spread %.0f mV after the charge", (vmax - vmin) * 1e3f));
  expect_healthy_accuracy(s, r);
}

// ---------------------------------------------------------------------------------------------
// Gate 11: the predictive layer.

void s_heat_no_current(Bench& b, Report& r) {
  b.run(120);
  const double t0 = b.t();
  b.pack.cell[1].heat_w = 1.0;   // dummy heater, no current: heat the current cannot explain
  Track tr;
  b.run_until(15 * 60, [&] { tr.update(b.snap()); return latched(b); });
  const Snapshot s = b.snap();
  expect_trip(b, r, TripCode::PredictiveRisk, bms::kBranchBoth);
  r.expect(b.sup->latch_record().cell == 1, "the trip names cell 2");
  r.expect(tr.t_level[2] >= 0, "Warning came before the trip");
  const double dt = b.t() - t0;
  r.expect(dt < 240, fmt("trip %.0f s after the heat began", dt));
  r.expect(tr.max_ts[1] < 40.0f,
           fmt("cell 2 was at %.1f C, far below every fixed temperature limit", tr.max_ts[1]));
  r.expect(s.out.alarm == bms::Alarm::Trip, "alarm on, latched");
}

void s_heat_warning(Bench& b, Report& r) {
  b.run(120);
  b.pack.cell[1].heat_w = 0.41;   // between the 0.5 C/min warning and the 0.6 C/min difference trip
  Track tr;
  b.run_until(25 * 60, [&] { tr.update(b.snap()); return false; });
  const Snapshot s = b.snap();
  r.expect(tr.max_cell_level[1] == 2 && (tr.reasons[1] & bms::kReasonHeat),
           fmt("cell 2 reached Warning on abnormal heat (highest %s)",
               bms::level_name(tr.max_cell_level[1])));
  r.expect(tr.alarm_warning, "the alarm sounded at Warning");
  r.expect(!latched(b), "no trip: Warning keeps both branches on");
  r.expect(s.out.load_on && s.out.charge_on, "both branches still enabled");
  r.expect(tr.max_cell_level[0] == 0 && tr.max_cell_level[2] == 0 && tr.max_cell_level[3] == 0,
           "the other cells stayed Normal");
}

void s_small_fault(Bench& b, Report& r) {
  b.run(120);
  b.pack.cell[2].heat_w = 0.2;   // the architecture's 9.3 example: about 0.27 C/min
  Track tr;
  b.run_until(30 * 60, [&] { tr.update(b.snap()); return false; });
  r.expect(tr.max_e5[2] >= 1.0f,
           fmt("cell 3 came out %.2f C hotter than its 5-minute prediction", tr.max_e5[2]));
  r.expect((tr.reasons[2] & bms::kReasonConfirmHot) && tr.max_cell_level[2] == 1,
           fmt("cell 3 raised Watch on the confirmation (highest %s)",
               bms::level_name(tr.max_cell_level[2])));
  float other = -1e9f;
  for (int i : {0, 1, 3}) other = std::max(other, tr.max_e5[i]);
  r.expect(other < 1.0f, fmt("the other cells stayed within their predictions (largest %.2f C)", other));
  r.expect(!latched(b), "no trip");
}

void s_cell_outlier(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = 0.8;
  b.run(90);
  b.pack.load_a = 2.0;
  b.run(5 * 60);
  b.pack.cell[0].heat_w = 0.55;   // below the 1.0 C/min trip, above the 0.6 C/min difference
  Track tr;
  b.run_until(15 * 60, [&] { tr.update(b.snap()); return latched(b); });
  expect_trip(b, r, TripCode::PredictiveRisk, bms::kBranchBoth);
  r.expect(tr.reasons[0] & bms::kReasonHeatDiffTrip,
           "cell 1 tripped on its difference from the other three, under load");
  r.expect(b.sup->latch_record().cell == 0, "the trip names cell 1");
}

void s_self_acceleration(Bench& b, Report& r) {
  // A replayed heating signal on all four cells (Gate 11 step 3): heat that grows with
  // temperature. The cells stay level with each other, so the cell-to-cell rule cannot act and
  // only the absolute heat rules and the self-acceleration test can.
  b.run(120);
  for (CellTruth& c : b.pack.cell) {
    c.heat_w = 0.2;
    c.heat_ref_c = c.t_core;
    c.heat_growth_c = 3.0;   // doubles every 2.1 C: a reaction feeding itself
  }
  Track tr;
  b.run_until(20 * 60, [&] { tr.update(b.snap()); return latched(b); });
  expect_trip(b, r, TripCode::PredictiveRisk, bms::kBranchBoth);
  uint32_t all = 0, heat_trips = 0;
  for (uint32_t x : tr.reasons) all |= x;
  for (uint32_t x : tr.reasons) heat_trips |= x & bms::kReasonHeatTrip;
  r.expect(all & bms::kReasonSelfAcceleration, "a cell tripped on self-acceleration at Warning");
  r.expect(!heat_trips, "before the 1.0 C/min abnormal-heat trip was needed");
  r.note(fmt("true abnormal heat at the trip %.2f W per cell", b.pack.cell[0].abnormal_heat_w()));
}

void s_load_defect(Bench& b, Report& r) {
  // A defect that adds 60 mOhm to cell 2 (a damaged tab or a weak cell), with heat that grows
  // as the cell warms. Its heat stops when the current stops, so acting early protects the cell.
  for (CellTruth& c : b.pack.cell) c.soc = 0.85;
  b.run(90);
  b.pack.load_a = 3.0;
  b.run(60);
  CellTruth& c = b.pack.cell[1];
  c.defect_ohm = 0.060;
  c.defect_growth_c = 6.0;
  c.defect_ref_c = c.t_core;
  const double t0 = b.t();
  b.run_until(20 * 60, [&] { return latched(b); });
  const double t_trip = b.t() - t0;
  const double t_at_trip = c.t_surf;
  double hottest_after = t_at_trip;
  b.run_until(10 * 60, [&] { hottest_after = std::max(hottest_after, c.t_surf); return false; });
  expect_trip(b, r, TripCode::PredictiveRisk, bms::kBranchBoth);
  r.expect(t_trip < 300, fmt("trip %.0f s after the defect appeared", t_trip));
  r.expect(t_at_trip < 35.0, fmt("cell 2 at %.1f C when the load was cut", t_at_trip));
  r.expect(hottest_after < t_at_trip + 1.5 && c.t_surf < t_at_trip,
           fmt("with the current cut, cell 2 peaked at %.1f C and cooled to %.1f C", hottest_after,
               c.t_surf));
}

void s_soft_short(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = soc_of_ocv(3.70);
  b.run(31 * 60);   // at rest long enough for the voltages to settle
  CellTruth& c = b.pack.cell[1];
  c.external_ohm = 47.0;   // Gate 11 step 6: 47 Ohm across cell 2's taps, bonded to the can
  const double leak_true = c.ocv() / 47.0;
  Track tr;
  const bool warned = b.run_until(150 * 60, [&] {
    const Snapshot s = b.snap();
    tr.update(s);
    return s.cells[1].level >= 2;
  });
  const Snapshot s = b.snap();
  c.external_ohm = 0.0;   // remove the resistor at Warning
  b.run(5 * 60);

  r.expect(warned, "cell 2 reached Warning");
  r.expect(tr.reasons[1] & bms::kReasonThermalAndElectrical,
           "Warning came from thermal and electrical evidence agreeing on cell 2");
  const float est = s.cells[1].leak_a;
  r.expect(std::isfinite(est) && std::fabs(est - leak_true) <= 0.3 * leak_true,
           fmt("cell 2 leak estimate %.1f mA against %.1f mA drawn", est * 1e3f, leak_true * 1e3));
  float other = 0.0f;
  for (int i : {0, 2, 3}) other = std::max(other, s.cells[i].leak_a);
  r.expect(other < bms::cfg::kLeakWatchA,
           fmt("the other cells show no leak (largest %.1f mA)", other * 1e3f));
  r.expect(s.cells[1].heat_w > 0.1f, fmt("cell 2 abnormal heat %.3f W", s.cells[1].heat_w));
  r.expect(tr.max_e5[1] >= 0.5f,
           fmt("cell 2 5-minute confirmation rose to +%.2f C", tr.max_e5[1]));
  r.expect(s.cells[1].cross == bms::CrossCheck::Agree,
           fmt("energy cross-check agrees: heat %.3f W, leak power %.3f W", s.cells[1].heat_w,
               s.cells[1].p_leak_w));
  r.expect(!latched(b), "no trip: a soft short raises Warning, it does not trip");
  r.expect(tr.max_ts[1] < 40.0f, fmt("cell 2 stayed below 40 C (%.1f C)", tr.max_ts[1]));
  r.note(fmt("Warning %.0f minutes after the resistor was fitted",
             (b.t() - 5 * 60 - 31 * 60) / 60.0));
}

void s_internal_leak(Bench& b, Report& r) {
  CellTruth& c = b.pack.cell[3];
  c.internal_ohm = 150.0;   // a soft internal short: 25 mA and 0.09 W, too little to see as heat
  const double leak_true = c.ocv() / 150.0;
  Track tr;
  b.run_until(100 * 60, [&] { tr.update(b.snap()); return false; });
  const Snapshot s = b.snap();
  r.expect(s.leak_valid, "the leak estimate ran after 30 minutes' rest and a 60-minute window");
  const float est = s.cells[3].leak_a;
  r.expect(std::isfinite(est) && std::fabs(est - leak_true) <= 0.25 * leak_true,
           fmt("cell 4 leak estimate %.1f mA against %.1f mA", est * 1e3f, leak_true * 1e3));
  float other = 0.0f;
  for (int i : {0, 1, 2}) other = std::max(other, std::fabs(s.cells[i].leak_a));
  r.expect(other < 0.012f, fmt("the other cells within +-12 mA (largest %.1f mA)", other * 1e3f));
  r.expect((tr.reasons[3] & bms::kReasonLeak) && tr.max_cell_level[3] == 1,
           fmt("cell 4 raised an electrical Watch only (highest %s)",
               bms::level_name(tr.max_cell_level[3])));
}

void s_forecast_hot_day(Bench& b, Report& r) {
  b.pack.set_uniform_temperature(35.0);
  for (CellTruth& c : b.pack.cell) c.soc = 0.95;
  b.run(90);
  b.pack.load_a = 4.6;
  const double t0 = b.t();
  Track tr;
  double t_above = -1, t_ttl = -1;
  float first_ttl = NAN;
  b.run_until(45 * 60, [&] {
    const Snapshot s = b.snap();
    tr.update(s);
    for (const auto& c : s.cells) {
      if (t_above < 0 && (c.reasons & bms::kReasonAboveSafeCurrent)) t_above = b.t() - t0;
      if (t_ttl < 0 && (c.reasons & bms::kReasonTimeToLimit)) t_ttl = b.t() - t0;
      if (std::isnan(first_ttl) && std::isfinite(c.time_to_limit_s)) first_ttl = c.time_to_limit_s;
    }
    return latched(b);
  });
  const Snapshot s = b.snap();
  r.expect(t_above >= 0 && t_above < 120,
           fmt("Watch: 4.6 A is above the safe current at 35 C ambient (after %.0f s; pack safe "
               "current %.2f A)", t_above, s.i_safe));
  r.expect(tr.ttl_seen && std::isfinite(first_ttl),
           fmt("a time to limit was forecast (first forecast %.0f s)", first_ttl));
  r.expect(t_ttl >= 0 && latched(b) && t_ttl < b.t() - t0,
           "Watch for under 10 minutes to the limit came before the limit");
  expect_trip(b, r, TripCode::DischargeTemp, bms::kBranchLoad);
  r.expect(s.seq > 0 && s.t_s > 0, "telemetry continues after the load trip");
  r.note(fmt("first forecast %.0f s to the limit; the limit was reached %.0f s after the load "
             "started", first_ttl, b.t() - t0));
}

void s_ntc_lift_off(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = 0.85;
  b.run(90);
  b.pack.load_a = 3.0;
  b.run(15 * 60);
  b.pack.sens.ntc_mode[2] = NtcMode::Lifted;
  const double t0 = b.t();
  b.run_until(10 * 60, [&] { return latched(b); });
  expect_trip(b, r, TripCode::NtcContact, bms::kBranchBoth);
  r.expect(b.sup->latch_record().cell == 2, "the fault names NTC3");
  r.expect(!has_trip(b, TripCode::PredictiveRisk), "the healthy cells were not blamed");
  r.note(fmt("detected %.0f s after the NTC lifted", b.t() - t0));
}

struct SensorCase {
  const char* what;
  void (*inject)(Pack&);
  TripCode code;
  double max_s;
};

void sensor_fault(Bench& b, Report& r, const SensorCase& sc) {
  b.run(90);
  sc.inject(b.pack);
  const double t0 = b.t();
  b.run_until(sc.max_s + 5, [&] { return latched(b); });
  const double dt = b.t() - t0;
  expect_trip(b, r, sc.code, bms::kBranchBoth);
  r.expect(dt >= bms::cfg::kSensorFaultHoldS - 0.01 && dt <= sc.max_s,
           fmt("%s latched %.1f s after it began (persistence 2 s)", sc.what, dt));
}

void s_ntc_open(Bench& b, Report& r) {
  sensor_fault(b, r, {"NTC2 open", [](Pack& p) { p.sens.ntc_mode[1] = NtcMode::Open; },
                      TripCode::CellNtc, 2.6});
}
void s_ntc_short(Bench& b, Report& r) {
  sensor_fault(b, r, {"NTC4 short", [](Pack& p) { p.sens.ntc_mode[3] = NtcMode::Short; },
                      TripCode::CellNtc, 2.6});
}
void s_ambient_open(Bench& b, Report& r) {
  sensor_fault(b, r, {"ambient NTC open", [](Pack& p) { p.sens.ntc_mode[4] = NtcMode::Open; },
                      TripCode::AmbientNtc, 2.6});
}
void s_ntc_stuck(Bench& b, Report& r) {
  sensor_fault(b, r, {"NTC1 flat line", [](Pack& p) { p.sens.ntc_mode[0] = NtcMode::Stuck; },
                      TripCode::CellNtc, 63.0});
}
void s_ads_loss(Bench& b, Report& r) {
  sensor_fault(b, r, {"ADS1115 bus loss", [](Pack& p) { p.sens.ads_fail = true; },
                      TripCode::TapSensor, 2.6});
}
void s_ina_loss(Bench& b, Report& r) {
  sensor_fault(b, r, {"INA226 bus loss", [](Pack& p) { p.sens.ina_fail = true; },
                      TripCode::CurrentSensor, 2.6});
}

void s_spikes(Bench& b, Report& r) {
  b.run(120);
  Track tr;
  int k = 0;
  b.run_until(4 * 60, [&] {
    tr.update(b.snap());
    if (++k % 50 == 0) {   // every 10 s: one bad tap reading and one bad NTC reading
      b.pack.sens.ads_spike_v = 0.5;
      b.pack.sens.ntc_spike_mv[0] = -400.0;
    }
    return false;
  });
  r.expect(!latched(b), "single-sample spikes did not trip anything");
  r.expect(tr.warnings & bms::kWarnSensor, "each spike was shown as a sensor notice");
  r.expect(tr.max_level == 0, fmt("risk stayed Normal (highest %s)", bms::level_name(tr.max_level)));
}

void s_load_steps(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = 0.8;
  b.run(90);
  Track tr;
  int k = 0;
  b.run_until(10 * 60, [&] {
    tr.update(b.snap());
    if (++k % 100 == 0) b.pack.load_a = b.pack.load_a > 0 ? 0.0 : 3.0;   // 0 <-> 3 A every 20 s
    return false;
  });
  const Snapshot s = b.snap();
  r.expect(!latched(b), "repeated 3 A load steps tripped nothing");
  r.expect(tr.max_level == 0, fmt("risk stayed Normal (highest %s)", bms::level_name(tr.max_level)));
  for (int i = 0; i < kCells; ++i) {
    const float est = s.cells[i].r_avg_ohm, truth = static_cast<float>(b.pack.cell[i].r_ohm);
    r.expect(s.cells[i].r_steps >= 20 && std::fabs(est - truth) <= 0.15f * truth,
             fmt("cell %d resistance %.1f mOhm against %.1f mOhm (%d steps)", i + 1, est * 1e3f,
                 truth * 1e3f, s.cells[i].r_steps));
  }
}

// ---------------------------------------------------------------------------------------------
// Section 8 limits: each trip opens only its own branch.

void s_cell_high_charge(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = 0.80;
  b.pack.cell[2].soc = 0.88;   // one cell ahead of the others
  b.run(90);
  b.pack.charge_a = 1.5;
  b.run_until(90 * 60, [&] { return latched(b); });
  expect_trip(b, r, TripCode::CellHigh, bms::kBranchCharge);
  r.expect(b.sup->latch_record().cell == 2, "the trip names cell 3");
  b.run(5);
  r.expect(std::fabs(b.pack.pack_current()) < 0.01, "the charge current stopped");
}

void s_cell_low_discharge(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = 0.25;
  b.pack.cell[0].soc = 0.14;
  b.run(90);
  b.pack.load_a = 2.0;
  b.run_until(90 * 60, [&] { return latched(b); });
  expect_trip(b, r, TripCode::CellLow, bms::kBranchLoad);
  r.expect(b.sup->latch_record().cell == 0, "the trip names cell 1");
}

void s_overcurrent(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = 0.8;
  b.run(90);
  b.pack.load_a = 5.3;
  const double t0 = b.t();
  b.run_until(10, [&] { return latched(b); });
  expect_trip(b, r, TripCode::DischargeCurrent, bms::kBranchLoad);
  r.expect(b.t() - t0 <= 2.0, fmt("5.3 A load cut after %.1f s", b.t() - t0));

  Bench c(7);
  for (CellTruth& x : c.pack.cell) x.soc = 0.3;
  c.run(90);
  c.pack.charge_a = 1.8;   // a charger that delivers more than 1.5 A
  c.run_until(10, [&] { return latched(c); });
  expect_trip(c, r, TripCode::ChargeCurrent, bms::kBranchCharge);
}

void s_charge_overtemp(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = 0.10;
  b.run(90);
  b.pack.charge_a = 1.5;
  b.run_until(150 * 60, [&] {
    b.pack.t_amb = std::min(50.0, b.pack.t_amb + 0.5 / 60.0 * bms::cfg::kDt);   // 0.5 C/min
    return latched(b);
  });
  expect_trip(b, r, TripCode::ChargeTemp, bms::kBranchCharge);
}

void s_spread(Bench& b, Report& r) {
  b.run(90);
  b.run_until(40 * 60, [&] {
    b.pack.sens.ntc_offset_c[3] += 0.4 / 60.0 * bms::cfg::kDt;   // simulated signal, 0.4 C/min
    return latched(b);
  });
  expect_trip(b, r, TripCode::TempSpread, bms::kBranchBoth);
}

void s_backstop_unfitted(Bench& b, Report& r) {
  b.run(120);
  b.pack.cell[0].heat_w = 1.0;   // about 1.3 C/min
  b.run_until(15 * 60, [&] { return latched(b); });
  expect_trip(b, r, TripCode::RiseRate, bms::kBranchBoth);
  r.note("Model off (section 9.9): the raw limits are 0.5 C/min warning and 1.0 C/min trip.");
}

void s_reset_rules(Bench& b, Report& r) {
  b.run(120);
  b.pack.sens.ntc_mode[1] = NtcMode::Open;
  b.run(5);
  b.pack.sens.ntc_mode[1] = NtcMode::Normal;
  b.run(5);
  r.expect(has_trip(b, TripCode::CellNtc), "an open NTC latched a sensor fault");
  r.expect(b.sup->request_reset() == bms::ResetResult::NotClear,
           "reset refused while the cause has been clear for less than 60 s");
  b.run(61);
  r.expect(latched(b), "the fault stayed latched with the sensor back (no automatic clear)");
  r.expect(b.sup->request_reset() == bms::ResetResult::Accepted, "reset accepted after 60 s clear");
  b.run(1);
  r.expect(b.out.load_on && b.out.charge_on, "both branches enabled after the reset");

  b.restart_controller(true);
  b.run(5);
  r.expect(!b.out.load_on && !b.out.charge_on, "after a crash restart both branches stay open");
  r.expect(has_trip(b, TripCode::ControllerReset), "the restart is latched as controller_reset");
  b.restart_controller(false);
  b.run(5);
  r.expect(latched(b), "a later restart keeps the latch");
  r.expect(b.sup->request_reset() == bms::ResetResult::NotClear,
           "reset refused within 60 s of boot");
  b.run(61);
  r.expect(b.sup->request_reset() == bms::ResetResult::Accepted, "reset accepted after 60 s");

  b.pack.sens.ina_fail = true;
  b.run(3);
  b.pack.sens.ina_fail = false;
  for (CellTruth& c : b.pack.cell) c.soc = soc_of_ocv(4.12);
  b.run(65);
  r.expect(b.sup->request_reset() == bms::ResetResult::CellVoltage,
           "reset refused with a cell above 4.10 V");
}

void s_fit_log(Bench& b, Report& r) {
  for (CellTruth& c : b.pack.cell) c.soc = 0.85;
  b.run(5 * 60);
  b.pack.load_a = 1.0;
  b.run(20 * 60);
  b.pack.load_a = 0.0;
  b.run(40 * 60);
  b.pack.load_a = 2.0;
  b.run(20 * 60);
  b.pack.load_a = 0.0;
  b.run(40 * 60);
  r.expect(!latched(b), "no trip while logging the Gate 9 fit data");
  r.note("Fit with: tools/fit_thermal.py <csv>. True values: c_core 40, c_surf 5, r_core 2.0, "
         "r_air 28/31/31/28.");
}

const std::vector<Scenario> kScenarios = {
    {"rest", "9", "30 minutes at rest: Normal, small abnormal heat, accurate forecasts", s_rest, 1,
     ModelMode::Fitted},
    {"discharge_steps", "9", "0.25-2 A steps: no flags, forecasts within 0.5 C RMS, resistance within 15 %",
     s_discharge_steps, 2, ModelMode::Fitted},
    {"discharge_5a", "9, 11", "4.8 A for 20 minutes: the heating expected near 5 A is not flagged",
     s_discharge_5a, 3, ModelMode::Fitted},
    {"charge", "10", "1.5 A charge to 4.10 V per cell: no flags, small spread", s_charge, 4,
     ModelMode::Fitted},
    {"heat_no_current", "11", "1 W in a cell with no current: Warning, then Trip below 40 C",
     s_heat_no_current, 5, ModelMode::Fitted},
    {"heat_warning", "11", "0.41 W in a cell: Warning and alarm, both branches stay on",
     s_heat_warning, 6, ModelMode::Fitted},
    {"small_fault", "11", "0.2 W in a cell: 5-minute confirmation +1 C raises Watch", s_small_fault,
     7, ModelMode::Fitted},
    {"cell_outlier", "11", "0.55 W in one cell under 2 A: trips on the cell-to-cell difference",
     s_cell_outlier, 8, ModelMode::Fitted},
    {"self_acceleration", "11", "heat growing with temperature in every cell: self-acceleration trip",
     s_self_acceleration, 9, ModelMode::Fitted},
    {"load_defect", "11", "a cell defect heating under 3 A: trips below 35 C, then the cell cools",
     s_load_defect, 30, ModelMode::Fitted},
    {"soft_short", "11", "47 Ohm across cell 2: leak, heat and confirmation agree; Warning",
     s_soft_short, 10, ModelMode::Fitted},
    {"internal_leak", "11", "25 mA internal leak: found electrically, Watch only", s_internal_leak,
     11, ModelMode::Fitted},
    {"forecast_hot_day", "9", "4.6 A at 35 C: safe-current and time-to-limit Watch, then load trip",
     s_forecast_hot_day, 12, ModelMode::Fitted},
    {"ntc_lift_off", "11", "NTC3 lifts under 3 A: sensor-contact fault, both branches open",
     s_ntc_lift_off, 13, ModelMode::Fitted},
    {"ntc_open", "1, 11", "open NTC: sensor fault after 2 s", s_ntc_open, 14, ModelMode::Fitted},
    {"ntc_short", "1, 11", "shorted NTC: sensor fault after 2 s", s_ntc_short, 15,
     ModelMode::Fitted},
    {"ambient_open", "1, 11", "open ambient NTC: sensor fault after 2 s", s_ambient_open, 16,
     ModelMode::Fitted},
    {"ntc_stuck", "11", "flat-line NTC: sensor fault after 60 s", s_ntc_stuck, 17,
     ModelMode::Fitted},
    {"ads_loss", "2", "ADS1115 bus loss: both branches open after 2 s", s_ads_loss, 18,
     ModelMode::Fitted},
    {"ina_loss", "2", "INA226 bus loss: both branches open after 2 s", s_ina_loss, 19,
     ModelMode::Fitted},
    {"spikes", "11", "single-sample spikes: rejected, no trip", s_spikes, 20, ModelMode::Fitted},
    {"load_steps", "9", "0-3 A steps every 20 s: no false trips, resistance tracked", s_load_steps,
     21, ModelMode::Fitted},
    {"cell_high_charge", "10", "one cell reaches 4.15 V on charge: only the charge branch opens",
     s_cell_high_charge, 22, ModelMode::Fitted},
    {"cell_low_discharge", "9", "one cell reaches 3.10 V on discharge: only the load branch opens",
     s_cell_low_discharge, 23, ModelMode::Fitted},
    {"overcurrent", "9, 10", "5.3 A load and 1.8 A charge: each opens only its branch",
     s_overcurrent, 24, ModelMode::Fitted},
    {"charge_overtemp", "10", "45 C while charging: only the charge branch opens", s_charge_overtemp,
     25, ModelMode::Fitted},
    {"temp_spread", "11", "a 10 C spread (simulated signal, model off): both branches open", s_spread,
     26, ModelMode::Off},
    {"backstop_unfitted", "11", "model off: the raw 1.0 C/min backstop trips", s_backstop_unfitted,
     27, ModelMode::Off},
    {"reset_rules", "2", "latches hold through restarts; reset only when the rules allow",
     s_reset_rules, 28, ModelMode::Fitted},
    {"fit_log", "9", "1 A and 2 A discharges with cooling curves, model off: data for the fit",
     s_fit_log, 29, ModelMode::Off},
};

}  // namespace

const std::vector<Scenario>& scenarios() { return kScenarios; }

const Scenario* find_scenario(const std::string& name) {
  for (const Scenario& s : kScenarios)
    if (name == s.name) return &s;
  return nullptr;
}

}  // namespace sim
