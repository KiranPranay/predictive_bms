#include "safety_task.h"

#include <cstdio>
#include <cstdlib>
#include <memory>

#include "ads1115.h"
#include "bms/supervisor.h"
#include "esp_log.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ina226.h"
#include "ntc_adc.h"
#include "outputs.h"
#include "sdkconfig.h"
#include "shared.h"
#include "storage.h"

#if CONFIG_BMS_BENCH_SIM
#include "sim/commands.h"
#include "sim/pack.h"
#endif

namespace safety {

namespace {

constexpr const char* kTag = "safety";
constexpr int kPeriodMs = 200;

bms::Calibration cal_;
bms::ModelParams params_;
std::unique_ptr<bms::Supervisor> sup_;

void report_reset(bms::ResetResult r) {
  std::printf("Manual reset: %s\n", bms::reset_result_text(r));
}

#if CONFIG_BMS_BENCH_SIM
std::unique_ptr<sim::Pack> pack_;

// A real pack on the taps: the top tap reads more than 1 V.
bool real_pack_present(const bms::RawSample& raw) {
  return raw.ads_ok && cal_.tap_gain[3] * raw.ads_v[3] + cal_.tap_offset_v[3] > 1.0f;
}

// Bench mode swaps the supervisor for one set up for the simulated pack. The latch carries over
// both ways, so entering or leaving bench mode never clears a trip.
void enter_sim() {
  pack_ = std::make_unique<sim::Pack>(1);
  pack_->set_uniform_temperature(25.0);
  const bms::LatchRecord latch = sup_->latch_record();
  sup_ = std::make_unique<bms::Supervisor>(pack_->calibration(), pack_->fitted_params());
  sup_->restore_latch(latch);
}

void leave_sim() {
  pack_.reset();
  const bms::LatchRecord latch = sup_->latch_record();
  sup_ = std::make_unique<bms::Supervisor>(cal_, params_);
  sup_->restore_latch(latch);
}
#endif

void task(void*) {
  ESP_ERROR_CHECK(esp_task_wdt_add(nullptr));
  TickType_t last = xTaskGetTickCount();
  static bms::Snapshot snap;
#if CONFIG_BMS_BENCH_SIM
  static bms::RawSample last_real;
#endif
  // The latch is written whenever it differs from what is in flash. Starting from "unknown"
  // also saves a controller_reset latch added at boot, so a later power cycle keeps it.
  bms::LatchRecord saved;
  bool saved_known = false;
  int log_rate = 0;
  int n = 0;

  for (;;) {
    vTaskDelayUntil(&last, pdMS_TO_TICKS(kPeriodMs));
    const int64_t now_us = esp_timer_get_time();

    shared::Command c;
    while (shared::receive(c)) {
      switch (c.type) {
        case shared::Cmd::Reset:
          report_reset(sup_->request_reset());
          break;
        case shared::Cmd::ApplyCalibration:
          if (shared::take_pending(cal_)) sup_->set_calibration(cal_);
          break;
        case shared::Cmd::ApplyParams:
          if (shared::take_pending(params_)) sup_->set_params(params_);
          break;
        case shared::Cmd::ClearStats:
          sup_->clear_prediction_record();
          break;
        case shared::Cmd::Log:
          log_rate = c.arg;
          if (log_rate) {
            char header[512];
            bms::write_csv_header(header, sizeof header);
            std::printf("CSV,%s\n", header);
          }
          break;
        case shared::Cmd::TestHang:
          std::printf("Watchdog test: the safety task stops now\n");
          for (;;) {
          }
        case shared::Cmd::TestCrash:
          std::printf("Crash test\n");
          std::abort();
#if CONFIG_BMS_BENCH_SIM
        case shared::Cmd::SimOn:
          if (pack_) {
            std::printf("Bench mode is already on\n");
          } else if (real_pack_present(last_real)) {
            std::printf("Refused: a pack is connected to the taps\n");
          } else {
            enter_sim();
            std::printf("Bench mode ON: the sensors are SIMULATED, the relays are REAL\n");
          }
          break;
        case shared::Cmd::SimOff:
          if (pack_) {
            leave_sim();
            std::printf("Bench mode off: real sensors\n");
          }
          break;
        case shared::Cmd::SimLine:
          if (pack_) {
            const std::string reply = sim::apply_command(*pack_, c.text);
            std::printf("%s\n", reply.empty() ? "unknown plant command" : reply.c_str());
          } else {
            std::printf("Bench mode is off\n");
          }
          break;
#else
        case shared::Cmd::SimOn:
        case shared::Cmd::SimOff:
        case shared::Cmd::SimLine:
          std::printf("Bench mode is not in this build (CONFIG_BMS_BENCH_SIM)\n");
          break;
#endif
      }
    }

    bms::RawSample raw;
    raw.t_s = now_us * 1e-6;
    raw.ads_ok = ads1115::read_all(raw.ads_v);
    raw.ina_ok = ina226::read(raw.shunt_v, raw.bus_v);
    ntc_adc::read(raw.ntc_ok, raw.ntc_mv, raw.ntc_code);

#if CONFIG_BMS_BENCH_SIM
    last_real = raw;
    if (pack_ && real_pack_present(raw)) {
      leave_sim();
      std::printf("Bench mode stopped: a pack appeared on the taps\n");
    }
    if (pack_) {
      // Simulated readings, but a real I2C failure still counts (Gate 2 step 4).
      const bool ads_ok = raw.ads_ok, ina_ok = raw.ina_ok;
      raw = pack_->read();
      raw.t_s = now_us * 1e-6;
      raw.ads_ok = raw.ads_ok && ads_ok;
      raw.ina_ok = raw.ina_ok && ina_ok;
    }
#endif

    const bms::Outputs out = sup_->step(raw);
    outputs::apply(out, now_us / 1000);

#if CONFIG_BMS_BENCH_SIM
    if (pack_) {
      pack_->load_relay = out.load_on;
      pack_->charge_relay = out.charge_on;
      pack_->step(kPeriodMs / 1000.0);
    }
    const bool bench = static_cast<bool>(pack_);
#else
    const bool bench = false;
#endif

    if (outputs::reset_button_held(now_us / 1000)) report_reset(sup_->request_reset());

    const bms::LatchRecord now = sup_->latch_record();
    if (!saved_known || now.branches != saved.branches || now.trips != saved.trips ||
        now.first != saved.first || now.cell != saved.cell) {
      const esp_err_t err = storage::save(now);
      if (err == ESP_OK) {
        saved = now;
        saved_known = true;
      } else {
        ESP_LOGE(kTag, "latch not saved: %s", esp_err_to_name(err));   // tried again next sample
      }
    }

    ++n;
    const bool second = n % 5 == 0;
    if (second || log_rate == 5) sup_->snapshot(snap);
    if (second) shared::publish(snap, bench);
    if (log_rate == 5 || (log_rate == 1 && second)) {
      char row[512];
      if (bms::write_csv_row(snap, row, sizeof row)) std::printf("CSV,%s%s\n", row, bench ? ",SIM" : "");
    }
    esp_task_wdt_reset();
  }
}

}  // namespace

void start(const bms::Calibration& cal, const bms::ModelParams& params,
           const bms::LatchRecord& latch, bool crashed, const char* reset_reason) {
  cal_ = cal;
  params_ = params;
  sup_ = std::make_unique<bms::Supervisor>(cal, params);
  sup_->restore_latch(latch);
  if (crashed) {
    char detail[64];
    std::snprintf(detail, sizeof detail, "restart after %s", reset_reason);
    sup_->latch_external(bms::TripCode::ControllerReset, detail);
  }
  xTaskCreatePinnedToCore(task, "safety", 8192, nullptr, configMAX_PRIORITIES - 2, nullptr, 1);
}

}  // namespace safety
