#include "ntc_adc.h"

#include "board.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"

namespace ntc_adc {

namespace {

adc_oneshot_unit_handle_t unit = nullptr;
adc_cali_handle_t cali = nullptr;

}  // namespace

esp_err_t init() {
  adc_oneshot_unit_init_cfg_t ucfg = {};
  ucfg.unit_id = ADC_UNIT_1;
  esp_err_t err = adc_oneshot_new_unit(&ucfg, &unit);
  if (err != ESP_OK) return err;

  adc_oneshot_chan_cfg_t ccfg = {};
  ccfg.atten = ADC_ATTEN_DB_12;   // about 0.15-2.45 V usable: 4-100 C on a 10k/10k divider
  ccfg.bitwidth = ADC_BITWIDTH_12;
  for (adc_channel_t ch : board::kNtcChannel) {
    err = adc_oneshot_config_channel(unit, ch, &ccfg);
    if (err != ESP_OK) return err;
  }

  adc_cali_line_fitting_config_t cal = {};
  cal.unit_id = ADC_UNIT_1;
  cal.atten = ADC_ATTEN_DB_12;
  cal.bitwidth = ADC_BITWIDTH_12;
#if CONFIG_IDF_TARGET_ESP32
  cal.default_vref = 1100;   // used only when the chip has no eFuse reference
#endif
  err = adc_cali_create_scheme_line_fitting(&cal, &cali);
  if (err != ESP_OK) ESP_LOGW("ntc", "no ADC calibration (%s); Gate 1 offsets must cover it",
                              esp_err_to_name(err));
  return ESP_OK;
}

void read(bool ok[5], float mv[5], uint32_t code[5]) {
  for (int i = 0; i < 5; ++i) {
    ok[i] = false;
    if (!unit) continue;
    uint32_t sum = 0;
    bool good = true;
    for (int k = 0; k < board::kNtcSamples && good; ++k) {
      int raw = 0;
      good = adc_oneshot_read(unit, board::kNtcChannel[i], &raw) == ESP_OK;
      sum += static_cast<uint32_t>(raw);
    }
    if (!good) continue;
    code[i] = sum;
    const int avg = static_cast<int>((sum + board::kNtcSamples / 2) / board::kNtcSamples);
    int v = 0;
    if (cali && adc_cali_raw_to_voltage(cali, avg, &v) == ESP_OK) {
      mv[i] = static_cast<float>(v);
    } else {
      mv[i] = avg * 3300.0f / 4095.0f;   // uncalibrated fallback
    }
    ok[i] = true;
  }
}

adc_oneshot_unit_handle_t adc1_handle() {
  return unit;
}

}  // namespace ntc_adc
