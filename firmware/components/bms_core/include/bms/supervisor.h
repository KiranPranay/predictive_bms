#pragma once

#include <cstdint>

#include "bms/electrical.h"
#include "bms/filters.h"
#include "bms/risk.h"
#include "bms/sensors.h"
#include "bms/thermal.h"
#include "bms/types.h"

namespace bms {

enum class EventKind : uint8_t { Info, Watch, Warning, Trip, Sensor, Reset };

struct Event {
  double t_s = 0.0;
  EventKind kind = EventKind::Info;
  int8_t cell = -1;   // 0-3, or -1 for the pack
  char text[96] = {};
};

// Section 8, rule 5: every trip is kept with its time, measurements, reason and relay state.
struct TripRecord {
  double t_s = 0.0;
  TripCode code = TripCode::None;
  int8_t cell = -1;
  uint8_t opened = 0;            // Branch bits opened by this trip
  bool load_was_on = false;
  bool charge_was_on = false;
  float cell_v[cfg::kCells] = {};
  float current_a = 0.0f;
  float temp_c[cfg::kNtcs] = {};
  float heat_w[cfg::kCells] = {};
  float leak_a[cfg::kCells] = {};
  char detail[64] = {};
};

enum class CrossCheck : uint8_t { NotAvailable, Agree, Disagree };

struct CellSnapshot {
  float v = 0.0f;
  float r_model_ohm = 0.0f, r_avg_ohm = NAN;
  int r_steps = 0;
  bool r_drift = false;
  float t_meas = NAN, t_lp = NAN, rise = 0.0f;
  bool rise_valid = false;
  float t_core = NAN, t_surf = NAN, heat_w = NAN, heat_rate = NAN, heat_diff = NAN;
  float f1 = NAN, f5 = NAN;
  bool has_e1 = false, has_e5 = false;
  float e1 = 0.0f, e5 = 0.0f;
  Verdict verdict = Verdict::Pending;
  float rms1_hour = NAN, rms5_hour = NAN, rms1_all = NAN, rms5_all = NAN;
  int n5_all = 0;
  float t_eq = NAN, time_to_limit_s = INFINITY, i_safe = NAN;
  float leak_a = NAN, p_leak_w = NAN;
  CrossCheck cross = CrossCheck::NotAvailable;
  int level = 0;
  uint32_t reasons = 0;
};

constexpr int kSnapshotEvents = 16;
constexpr int kTripLog = 4;

// Everything the dashboard, the console and the log show, copied out of the safety task.
struct Snapshot {
  uint32_t seq = 0;
  double t_s = 0.0;
  State state = State::Startup;
  Mode mode = Mode::Rest;
  ModelMode model = ModelMode::Off;
  bool thermal_ready = false;
  bool ocv_table = false;
  Outputs out;
  int risk = 0;
  uint32_t warnings = 0;
  LatchRecord latch;
  int n_trips = 0;
  TripRecord trips[kTripLog];      // the most recent trips, oldest first
  float pack_v = 0.0f, current_a = 0.0f, t_amb = NAN, i_safe = NAN, t_trip = NAN;
  bool ch_invalid[kChannelCount] = {};
  float ch_invalid_for_s[kChannelCount] = {};
  bool flat_line[cfg::kNtcs] = {};
  float leak_rest_s = 0.0f;
  int leak_minutes = 0;
  bool leak_valid = false;
  CellSnapshot cells[cfg::kCells];
  RawSample raw;
  float raw_temp_c[cfg::kNtcs] = {};
  float raw_tap_v[cfg::kCells] = {};
  int n_events = 0;
  Event events[kSnapshotEvents];   // oldest first
};

class Supervisor {
 public:
  Supervisor(const Calibration& cal, const ModelParams& params);

  void set_calibration(const Calibration& cal);
  void set_params(const ModelParams& params);   // restarts the thermal and electrical layers
  const Calibration& calibration() const { return front_.calibration(); }
  const ModelParams& params() const { return params_; }

  // One 5 Hz sample: returns the relay and alarm commands.
  Outputs step(const RawSample& raw);

  // Section 8, rule 6: deliberate manual reset of the latched trips.
  ResetResult request_reset();

  // The latch survives a restart: the firmware stores latch_record() whenever
  // latch_version() changes, and restores it at boot.
  void restore_latch(const LatchRecord& rec);
  LatchRecord latch_record() const { return latch_; }
  uint32_t latch_version() const { return latch_version_; }
  // A trip found outside the samples, such as a restart after a crash.
  void latch_external(TripCode code, const char* detail);

  void clear_prediction_record();
  void snapshot(Snapshot& s) const;
  const Measurements& measurements() const { return front_.last(); }
  State state() const { return state_; }

 private:
  void run_electrical(const Measurements& m);
  void run_thermal(const Measurements& m);
  void check_limits(const Measurements& m);
  void update_state(const Measurements& m);
  void trip(TripCode code, int cell, const char* detail);
  void log(EventKind kind, int cell, const char* fmt, ...);
  void reset_trip_timers();

  ModelParams params_;
  FrontEnd front_;
  ResistanceTracker resist_;
  LeakEstimator leak_;
  CellObserver obs_[cfg::kCells];
  Predictor pred_[cfg::kCells];
  CellRisk risk_[cfg::kCells];
  float tau_s_[cfg::kCells] = {};

  RawSample raw_;
  double t_ = 0.0;
  uint32_t seq_ = 0;
  State state_ = State::Startup;
  Mode mode_ = Mode::Rest;
  Outputs out_;

  // Thermal layer state.
  bool thermal_on_ = false;
  double thermal_start_t_ = -1.0;
  bool have_prev_u_ = false;
  float prev_pj_[cfg::kCells] = {};
  float prev_tamb_ = 0.0f;
  float prev_abs_i_ = 0.0f;
  float r_model_[cfg::kCells] = {};
  Forecast fc_[cfg::kCells];
  float heat_rate_[cfg::kCells] = {};
  float heat_diff_[cfg::kCells] = {};
  CrossCheck cross_[cfg::kCells] = {};
  float p_leak_[cfg::kCells] = {};
  Persist contact_[cfg::kCells];
  int pack_risk_ = 0;
  int last_level_[cfg::kCells] = {};

  // Section 8 limits.
  Persist warn_high_, trip_high_, warn_low_, trip_low_;
  Persist warn_ctemp_, trip_ctemp_, warn_dtemp_, trip_dtemp_;
  Persist warn_spread_, trip_spread_, warn_rise_, trip_rise_;
  Persist warn_dcur_, trip_dcur_, trip_ccur_;
  uint32_t warnings_ = 0;
  double last_cond_t_ = 0.0;   // last time any trip condition was present

  LatchRecord latch_;
  uint32_t latch_version_ = 0;
  bool proven_ = false;   // every channel has read plausibly for 2 s since start
  TripRecord trip_log_[kTripLog];
  int trip_n_ = 0;
  int trip_pos_ = 0;

  static constexpr int kEvents = 32;
  Event events_[kEvents];
  int ev_n_ = 0;
  int ev_pos_ = 0;
};

// Names used by the dashboard, the console and the log.
const char* trip_name(TripCode c);
const char* state_name(State s);
const char* mode_name(Mode m);
const char* model_name(ModelMode m);
const char* verdict_name(Verdict v);
const char* level_name(int level);
const char* reset_result_text(ResetResult r);
const char* event_kind_name(EventKind k);
uint8_t trip_branches(TripCode c);
// Writes the names of the set bits, separated by commas; returns buf.
const char* reason_list(uint32_t reasons, char* buf, int cap);
const char* warning_list(uint32_t warnings, char* buf, int cap);

// Telemetry: JSON for the dashboard and CSV for the Gate 9 fit. Each returns the length
// written, or 0 when the buffer is too small.
int write_json(const Snapshot& s, char* buf, int cap);
int write_csv_header(char* buf, int cap);
int write_csv_row(const Snapshot& s, char* buf, int cap);

}  // namespace bms
