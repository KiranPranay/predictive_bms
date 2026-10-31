// ACS712-5A: temporary replacement for the INA226.
//
// The ACS712 is a Hall-effect current sensor with an analog output centred at VCC/2.
// At 5 V supply the quiescent output is 2.5 V and the sensitivity is 185 mV/A.
// The ESP32 ADC can only read up to about 3.1 V at 12 dB attenuation, so the module must run
// on 3.3 V (the datasheet minimum is 4.5 V, but most modules work at 3.3 V for a demo).
// At 3.3 V the quiescent point drops to about 1.65 V and the sensitivity drops to roughly
// 0.185 * (3.3 / 5.0) = 0.122 V/A.
//
// The driver converts the measured current back into a synthetic shunt voltage (I × 5 mΩ)
// so the front end's calibration path works without changes.
//
// Revert: replace acs712 calls with ina226 calls in main.cpp and safety_task.cpp.

#include "acs712.h"

#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_log.h"

namespace acs712 {

namespace {

constexpr const char* kTag = "acs712";

// When run at 3.3 V the quiescent point is VCC/2 and the sensitivity scales linearly.
constexpr float kVccV = 3.3f;
constexpr float kQuiescentV = kVccV / 2.0f;
constexpr float kSensitivity5A_5V = 0.185f;   // datasheet V/A at 5 V supply
constexpr float kSensitivity = kSensitivity5A_5V * kVccV / 5.0f;   // about 0.122 V/A at 3.3 V
constexpr float kShuntOhm = 0.005f;   // the calibration's shunt_ohm
constexpr int kSamples = 32;          // software averaging, more than the NTCs because the
                                      // ACS712 is noisier

adc_oneshot_unit_handle_t adc = nullptr;
adc_cali_handle_t cali = nullptr;
adc_channel_t ch;

}  // namespace

esp_err_t init(adc_oneshot_unit_handle_t adc1, adc_channel_t channel) {
  adc = adc1;
  ch = channel;
  if (!adc) return ESP_ERR_INVALID_STATE;

  adc_oneshot_chan_cfg_t ccfg = {};
  ccfg.atten = ADC_ATTEN_DB_12;
  ccfg.bitwidth = ADC_BITWIDTH_12;
  esp_err_t err = adc_oneshot_config_channel(adc, ch, &ccfg);
  if (err != ESP_OK) return err;

  // Share calibration parameters with the NTC driver (same unit and attenuation).
  adc_cali_line_fitting_config_t cal = {};
  cal.unit_id = ADC_UNIT_1;
  cal.atten = ADC_ATTEN_DB_12;
  cal.bitwidth = ADC_BITWIDTH_12;
#if CONFIG_IDF_TARGET_ESP32
  cal.default_vref = 1100;
#endif
  err = adc_cali_create_scheme_line_fitting(&cal, &cali);
  if (err != ESP_OK) ESP_LOGW(kTag, "no ADC calibration (%s); raw fallback", esp_err_to_name(err));
  ESP_LOGI(kTag, "ACS712-5A on ADC1 channel %d (temporary, until the INA226 arrives)", ch);
  return ESP_OK;
}

bool read(float& shunt_v, float& bus_v) {
  if (!adc) return false;

  int sum_mv = 0;
  for (int k = 0; k < kSamples; ++k) {
    int raw = 0;
    if (adc_oneshot_read(adc, ch, &raw) != ESP_OK) return false;
    if (cali) {
      int mv = 0;
      adc_cali_raw_to_voltage(cali, raw, &mv);
      sum_mv += mv;
    } else {
      sum_mv += raw * 3300 / 4095;
    }
  }

  const float out_v = static_cast<float>(sum_mv) / (kSamples * 1000.0f);
  const float current_a = (out_v - kQuiescentV) / kSensitivity;

  // Convert to a synthetic shunt voltage so the front end works unchanged.
  shunt_v = current_a * kShuntOhm;
  bus_v = 0.0f;
  return true;
}

}  // namespace acs712

