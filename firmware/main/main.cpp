// Predictive BMS supervisor: start-up order.
//
// 1. Relays held open before anything else (section 3: reset or unpowered control = open).
// 2. Flash: calibration, model parameters and any latched trip.
// 3. Sensors on I2C and ADC1.
// 4. The 5 Hz safety task, then the console, then Wi-Fi and the dashboard, which come last
//    because nothing safe depends on them.

#include "ads1115.h"
#include "board.h"
#include "console.h"
#include "driver/i2c_master.h"
#include "esp_log.h"
#include "esp_system.h"
#include "ina226.h"
#include "ntc_adc.h"
#include "outputs.h"
#include "safety_task.h"
#include "sdkconfig.h"
#include "shared.h"
#include "storage.h"
#include "telemetry.h"

namespace {

constexpr const char* kTag = "main";

// Section 10: after a crash, a watchdog or a brown-out the relays stay open until a manual
// reset; a normal power-up or a deliberate restart does not latch.
const char* abnormal_reset(esp_reset_reason_t r) {
  switch (r) {
    case ESP_RST_PANIC: return "a crash";
    case ESP_RST_INT_WDT: return "the interrupt watchdog";
    case ESP_RST_TASK_WDT: return "the task watchdog";
    case ESP_RST_WDT: return "a watchdog";
    case ESP_RST_BROWNOUT: return "a brown-out";
    default: return nullptr;
  }
}

}  // namespace

extern "C" void app_main(void) {
  outputs::init();
  shared::init();

  ESP_ERROR_CHECK(storage::init());
  bms::Calibration cal;
  bms::ModelParams params;
  bms::LatchRecord latch;
  if (!storage::load(cal)) ESP_LOGW(kTag, "no Gate 1 calibration stored: nominal values in use");
  if (!storage::load(params)) ESP_LOGW(kTag, "no model parameters stored: thermal layer off");
  if (storage::load(latch) && latch.branches) ESP_LOGW(kTag, "a latched trip is kept from before");

  i2c_master_bus_config_t bus_cfg = {};
  bus_cfg.i2c_port = I2C_NUM_0;
  bus_cfg.sda_io_num = board::kSda;
  bus_cfg.scl_io_num = board::kScl;
  bus_cfg.clk_source = I2C_CLK_SRC_DEFAULT;
  bus_cfg.glitch_ignore_cnt = 7;
  bus_cfg.flags.enable_internal_pullup = false;   // 4.7 kOhm pull-ups are on the modules
  i2c_master_bus_handle_t bus = nullptr;
  ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &bus));
  if (ads1115::init(bus, CONFIG_BMS_ADS1115_ADDR, CONFIG_BMS_I2C_HZ) != ESP_OK)
    ESP_LOGE(kTag, "ADS1115 not added");
  if (ina226::init(bus, CONFIG_BMS_INA226_ADDR, CONFIG_BMS_I2C_HZ) != ESP_OK)
    ESP_LOGE(kTag, "INA226 not added");
  if (ntc_adc::init() != ESP_OK) ESP_LOGE(kTag, "NTC ADC not ready");

  const esp_reset_reason_t why = esp_reset_reason();
  const char* abnormal = abnormal_reset(why);
  if (abnormal) ESP_LOGE(kTag, "restarted after %s: both relays stay open until a manual reset",
                         abnormal);
  safety::start(cal, params, latch, abnormal != nullptr, abnormal ? abnormal : "");

  console::start(cal, params);
  telemetry::start();
}
