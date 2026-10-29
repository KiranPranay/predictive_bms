#include "console.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "bms/supervisor.h"
#include "esp_console.h"
#include "sdkconfig.h"
#include "shared.h"
#include "storage.h"
#include "telemetry.h"

namespace console {

namespace {

// The console keeps its own copy of what is stored, edits it, saves it, then hands it to the
// safety task.
bms::Calibration cal_;
bms::ModelParams params_;
bms::Snapshot snap_;

bool num(const char* s, float& out) {
  char* end = nullptr;
  out = std::strtof(s, &end);
  return end != s && *end == '\0' && std::isfinite(out);
}

bool parse_index(const char* s, int n_max, int& out) {
  char* end = nullptr;
  const long v = std::strtol(s, &end, 10);
  if (end == s || *end != '\0' || v < 1 || v > n_max) return false;
  out = static_cast<int>(v) - 1;
  return true;
}

int usage(const char* text) {
  std::printf("usage: %s\n", text);
  return 1;
}

void save_cal() {
  if (storage::save(cal_) != ESP_OK) std::printf("warning: calibration not saved to flash\n");
  shared::set_pending(cal_);
  shared::send(shared::Cmd::ApplyCalibration);
}

void save_params() {
  if (storage::save(params_) != ESP_OK) std::printf("warning: parameters not saved to flash\n");
  shared::set_pending(params_);
  shared::send(shared::Cmd::ApplyParams);
}

const char* fmt_f(float v, const char* f, char* buf, int cap) {
  if (std::isfinite(v)) {
    std::snprintf(buf, cap, f, v);
  } else {
    std::snprintf(buf, cap, "-");
  }
  return buf;
}

// --- status ------------------------------------------------------------------------------------

int cmd_status(int, char**) {
  bool bench = false;
  shared::read(snap_, &bench);
  const bms::Snapshot& s = snap_;
  char w[160], a[16], b[16], c[16], d[16];
  std::printf("%s  t=%.0f s  state %s  mode %s  model %s%s  risk %s\n",
              bench ? "BENCH MODE (simulated sensors)" : "", s.t_s, bms::state_name(s.state),
              bms::mode_name(s.mode), bms::model_name(s.model),
              s.thermal_ready ? "" : " (not running)", bms::level_name(s.risk));
  std::printf("pack %.3f V  %.3f A  ambient %s C  safe current %s A  relays: load %s, charge %s\n",
              s.pack_v, s.current_a, fmt_f(s.t_amb, "%.2f", a, sizeof a),
              fmt_f(s.i_safe, "%.2f", b, sizeof b), s.out.load_on ? "ON" : "open",
              s.out.charge_on ? "ON" : "open");
  std::printf("warnings: %s\n", bms::warning_list(s.warnings, w, sizeof w)[0] ? w : "none");
  for (int i = 0; i < bms::cfg::kCells; ++i) {
    const bms::CellSnapshot& x = s.cells[i];
    std::printf("cell %d  %.4f V  %4.1f mOhm  T_s %6s  T_c %6s  Q %7s W  5-min %s  %s\n", i + 1,
                x.v, x.r_model_ohm * 1e3f, fmt_f(x.t_meas, "%.2f", a, sizeof a),
                fmt_f(x.t_core, "%.2f", b, sizeof b), fmt_f(x.heat_w, "%.3f", c, sizeof c),
                fmt_f(x.f5, "%.2f", d, sizeof d), bms::level_name(x.level));
  }
  if (s.latch.branches) {
    std::printf("LATCHED: first %s; load %s, charge %s held open\n",
                bms::trip_name(static_cast<bms::TripCode>(s.latch.first)),
                (s.latch.branches & bms::kBranchLoad) ? "is" : "not",
                (s.latch.branches & bms::kBranchCharge) ? "is" : "not");
  }
  return 0;
}

int cmd_raw(int, char**) {
  shared::read(snap_);
  const bms::RawSample& r = snap_.raw;
  std::printf("ADS1115 %s: A0 %.5f  A1 %.5f  A2 %.5f  A3 %.5f V\n", r.ads_ok ? "ok" : "FAIL",
              r.ads_v[0], r.ads_v[1], r.ads_v[2], r.ads_v[3]);
  std::printf("taps (calibrated): %.4f  %.4f  %.4f  %.4f V\n", snap_.raw_tap_v[0],
              snap_.raw_tap_v[1], snap_.raw_tap_v[2], snap_.raw_tap_v[3]);
  std::printf("INA226 %s: shunt %.1f uV  bus %.3f V  current %.4f A\n", r.ina_ok ? "ok" : "FAIL",
              r.shunt_v * 1e6f, r.bus_v, snap_.current_a);
  for (int i = 0; i < bms::cfg::kNtcs; ++i) {
    std::printf("NTC%d %s: %.0f mV  code %lu  %.2f C%s\n", i + 1, r.ntc_ok[i] ? "ok" : "FAIL",
                r.ntc_mv[i], static_cast<unsigned long>(r.ntc_code[i]), snap_.raw_temp_c[i],
                snap_.flat_line[i] ? "  (flat line)" : "");
  }
  return 0;
}

int cmd_events(int, char**) {
  shared::read(snap_);
  for (int k = 0; k < snap_.n_events; ++k) {
    const bms::Event& e = snap_.events[k];
    std::printf("%9.1f s  %-7s %s\n", e.t_s, bms::event_kind_name(e.kind), e.text);
  }
  for (int k = 0; k < snap_.n_trips; ++k) {
    const bms::TripRecord& t = snap_.trips[k];
    std::printf("trip at %.1f s: %s (%s); V %.3f %.3f %.3f %.3f; I %.3f A; T %.1f %.1f %.1f %.1f "
                "%.1f C; relays were load %s charge %s\n",
                t.t_s, bms::trip_name(t.code), t.detail, t.cell_v[0], t.cell_v[1], t.cell_v[2],
                t.cell_v[3], t.current_a, t.temp_c[0], t.temp_c[1], t.temp_c[2], t.temp_c[3],
                t.temp_c[4], t.load_was_on ? "on" : "off", t.charge_was_on ? "on" : "off");
  }
  return 0;
}

int cmd_reset(int, char**) {
  shared::send(shared::Cmd::Reset);
  return 0;
}

int cmd_log(int argc, char** argv) {
  if (argc != 2) return usage("log off|1|5   (CSV lines start with CSV,)");
  const int rate = !std::strcmp(argv[1], "1") ? 1 : !std::strcmp(argv[1], "5") ? 5 : 0;
  shared::send(shared::Cmd::Log, rate);
  return 0;
}

int cmd_stats(int argc, char** argv) {
  if (argc != 2 || std::strcmp(argv[1], "clear")) return usage("stats clear");
  shared::send(shared::Cmd::ClearStats);
  return 0;
}

// --- calibration (Gate 1) ---------------------------------------------------------------------

int cmd_cal(int argc, char** argv) {
  const char* help =
      "cal show | cal tap N GAIN OFFSET_V | cal shunt OHM GAIN OFFSET_A | cal ntc N OFFSET_C | "
      "cal vref MV";
  if (argc < 2) return usage(help);
  const char* what = argv[1];
  float f[3];
  int i = 0;
  if (!std::strcmp(what, "show")) {
    for (int k = 0; k < 4; ++k)
      std::printf("tap %d: gain %.6f  offset %.5f V\n", k + 1, cal_.tap_gain[k], cal_.tap_offset_v[k]);
    std::printf("shunt %.6f Ohm  gain %.5f  offset %.4f A\n", cal_.shunt_ohm, cal_.current_gain,
                cal_.current_offset_a);
    std::printf("NTC supply %.1f mV  pull-up %.0f Ohm  R25 %.0f Ohm  beta %.0f\n",
                cal_.ntc_supply_mv, cal_.ntc_pullup_ohm, cal_.ntc_r25_ohm, cal_.ntc_beta);
    for (int k = 0; k < 5; ++k) std::printf("NTC%d offset %.2f C\n", k + 1, cal_.ntc_offset_c[k]);
    return 0;
  }
  if (!std::strcmp(what, "tap") && argc == 5 && parse_index(argv[2], 4, i) && num(argv[3], f[0]) &&
      num(argv[4], f[1])) {
    cal_.tap_gain[i] = f[0];
    cal_.tap_offset_v[i] = f[1];
  } else if (!std::strcmp(what, "shunt") && argc == 5 && num(argv[2], f[0]) && f[0] > 0 &&
             num(argv[3], f[1]) && num(argv[4], f[2])) {
    cal_.shunt_ohm = f[0];
    cal_.current_gain = f[1];
    cal_.current_offset_a = f[2];
  } else if (!std::strcmp(what, "ntc") && argc == 4 && parse_index(argv[2], 5, i) && num(argv[3], f[0])) {
    cal_.ntc_offset_c[i] = f[0];
  } else if (!std::strcmp(what, "vref") && argc == 3 && num(argv[2], f[0]) && f[0] > 3000 &&
             f[0] < 3600) {
    cal_.ntc_supply_mv = f[0];
  } else {
    return usage(help);
  }
  save_cal();
  std::printf("saved\n");
  return 0;
}

// --- model (Gates 4, 9 and 10) ------------------------------------------------------------------

int cmd_model(int argc, char** argv) {
  const char* help =
      "model show | model mode off|estimates|fitted | model thermal C_CORE C_SURF R_CORE RU1 RU2 "
      "RU3 RU4 | model r0 R1 R2 R3 R4 (mOhm, Gate 4) | model ocv V1 S1 [V2 S2 ...] | model ocv "
      "clear | model kalman MEAS_C CORE_C SURF_C HEAT_W";
  if (argc < 2) return usage(help);
  const char* what = argv[1];
  bms::ModelParams p = params_;
  if (!std::strcmp(what, "show")) {
    const bms::ThermalParams& t = p.thermal;
    std::printf("mode %s\n", bms::model_name(p.mode));
    std::printf("thermal: c_core %.2f J/C  c_surf %.2f J/C  r_core %.3f C/W  r_air %.2f %.2f %.2f "
                "%.2f C/W\n",
                t.c_core, t.c_surf, t.r_core, t.r_air[0], t.r_air[1], t.r_air[2], t.r_air[3]);
    std::printf("Gate 4 resistance%s: %.2f %.2f %.2f %.2f mOhm\n", p.gate4_done ? "" : " (estimate)",
                p.r_cell_ohm[0] * 1e3f, p.r_cell_ohm[1] * 1e3f, p.r_cell_ohm[2] * 1e3f,
                p.r_cell_ohm[3] * 1e3f);
    std::printf("OCV table: %d points\n", p.ocv_points);
    for (int k = 0; k < p.ocv_points; ++k)
      std::printf("  %.3f V  dOCV/dSOC %.3f V\n", p.ocv_v[k], p.ocv_slope[k]);
    std::printf("kalman: meas %.4f C  core %.4f C  surf %.4f C  heat %.4f W\n", p.kalman.meas_sd_c,
                p.kalman.core_sd_c, p.kalman.surf_sd_c, p.kalman.heat_sd_w);
    return 0;
  }
  float f[16];
  if (!std::strcmp(what, "mode") && argc == 3) {
    if (!std::strcmp(argv[2], "off")) {
      p.mode = bms::ModelMode::Off;
    } else if (!std::strcmp(argv[2], "estimates")) {
      p.mode = bms::ModelMode::Estimates;
    } else if (!std::strcmp(argv[2], "fitted")) {
      p.mode = bms::ModelMode::Fitted;
    } else {
      return usage(help);
    }
  } else if (!std::strcmp(what, "thermal") && argc == 9) {
    for (int k = 0; k < 7; ++k)
      if (!num(argv[2 + k], f[k]) || f[k] <= 0) return usage(help);
    p.thermal.c_core = f[0];
    p.thermal.c_surf = f[1];
    p.thermal.r_core = f[2];
    for (int k = 0; k < 4; ++k) p.thermal.r_air[k] = f[3 + k];
  } else if (!std::strcmp(what, "r0") && argc == 6) {
    for (int k = 0; k < 4; ++k)
      if (!num(argv[2 + k], f[k]) || f[k] <= 0) return usage(help);
    for (int k = 0; k < 4; ++k) p.r_cell_ohm[k] = f[k] / 1000.0f;
    p.gate4_done = true;
  } else if (!std::strcmp(what, "ocv") && argc == 3 && !std::strcmp(argv[2], "clear")) {
    p.ocv_points = 0;
  } else if (!std::strcmp(what, "ocv") && argc >= 4 && argc % 2 == 0 &&
             (argc - 2) / 2 <= bms::kOcvMaxPoints) {
    const int n = (argc - 2) / 2;
    for (int k = 0; k < n; ++k) {
      if (!num(argv[2 + 2 * k], p.ocv_v[k]) || !num(argv[3 + 2 * k], p.ocv_slope[k]) ||
          p.ocv_slope[k] <= 0)
        return usage(help);
    }
    p.ocv_points = n;
  } else if (!std::strcmp(what, "kalman") && argc == 6) {
    for (int k = 0; k < 4; ++k)
      if (!num(argv[2 + k], f[k]) || f[k] <= 0) return usage(help);
    p.kalman.meas_sd_c = f[0];
    p.kalman.core_sd_c = f[1];
    p.kalman.surf_sd_c = f[2];
    p.kalman.heat_sd_w = f[3];
  } else {
    return usage(help);
  }
  params_ = p;
  save_params();
  std::printf("saved; the thermal layer restarts\n");
  if (p.mode == bms::ModelMode::Estimates)
    std::printf("note: estimates are for development on dummy heat sources (architecture 9.9)\n");
  return 0;
}

// --- Gate 2 and bench mode ---------------------------------------------------------------------

int cmd_test(int argc, char** argv) {
  if (argc == 2 && !std::strcmp(argv[1], "hang")) {
    shared::send(shared::Cmd::TestHang);
  } else if (argc == 2 && !std::strcmp(argv[1], "crash")) {
    shared::send(shared::Cmd::TestCrash);
  } else {
    return usage("test hang | test crash   (Gate 2: both relays must open and stay open)");
  }
  return 0;
}

int cmd_wifi(int argc, char** argv) {
  if (argc == 2 && !std::strcmp(argv[1], "off")) {
    telemetry::wifi_off();
  } else if (argc == 2 && !std::strcmp(argv[1], "on")) {
    telemetry::wifi_on();
  } else if (argc != 1) {
    return usage("wifi [on|off]");
  }
  std::printf("Wi-Fi %s\n", telemetry::wifi_running() ? "on" : "off");
  return 0;
}

int cmd_sim(int argc, char** argv) {
  if (argc == 2 && !std::strcmp(argv[1], "on")) {
    shared::send(shared::Cmd::SimOn);
  } else if (argc == 2 && !std::strcmp(argv[1], "off")) {
    shared::send(shared::Cmd::SimOff);
  } else if (argc >= 2) {
    char line[64] = {};
    int len = 0;
    for (int k = 1; k < argc && len < 62; ++k)
      len += std::snprintf(line + len, sizeof line - len, "%s%s", k > 1 ? " " : "", argv[k]);
    shared::send(shared::Cmd::SimLine, 0, line);
  } else {
    return usage("sim on|off | sim PLANT-COMMAND   (e.g. sim load 2, sim heat 2 0.5)");
  }
  return 0;
}

void add(const char* name, const char* help, esp_console_cmd_func_t fn) {
  esp_console_cmd_t c = {};
  c.command = name;
  c.help = help;
  c.func = fn;
  ESP_ERROR_CHECK(esp_console_cmd_register(&c));
}

}  // namespace

void start(const bms::Calibration& cal, const bms::ModelParams& params) {
  cal_ = cal;
  params_ = params;
  esp_console_repl_t* repl = nullptr;
  esp_console_repl_config_t rc = ESP_CONSOLE_REPL_CONFIG_DEFAULT();
  rc.prompt = "bms> ";
  rc.max_cmdline_length = 160;
  esp_console_dev_uart_config_t uc = ESP_CONSOLE_DEV_UART_CONFIG_DEFAULT();
  ESP_ERROR_CHECK(esp_console_new_repl_uart(&uc, &rc, &repl));
  ESP_ERROR_CHECK(esp_console_register_help_command());
  add("status", "Pack, cells, relays and risk", cmd_status);
  add("raw", "Raw sensor readings, for calibration", cmd_raw);
  add("events", "Recent events and trip records", cmd_events);
  add("reset", "Manual reset of latched trips (also: hold BOOT for 3 s)", cmd_reset);
  add("log", "log off|1|5: CSV telemetry lines for the Gate 9 fit", cmd_log);
  add("stats", "stats clear: clear the prediction-accuracy record", cmd_stats);
  add("cal", "Gate 1 calibration: cal show | tap | shunt | ntc | vref", cmd_cal);
  add("model", "Model: show | mode | thermal | r0 | ocv | kalman", cmd_model);
  add("test", "Gate 2: test hang | test crash", cmd_test);
  add("wifi", "wifi on|off: the dashboard link (protections never depend on it)", cmd_wifi);
  add("sim", "Bench mode (CONFIG_BMS_BENCH_SIM): sim on|off | sim PLANT-COMMAND", cmd_sim);
  ESP_ERROR_CHECK(esp_console_start_repl(repl));
}

}  // namespace console
