#include "ads1115.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace ads1115 {

namespace {

constexpr uint8_t kRegConversion = 0x00;
constexpr uint8_t kRegConfig = 0x01;
constexpr int kTimeoutMs = 20;
constexpr float kLsbV = 4.096f / 32768.0f;

i2c_master_dev_handle_t dev = nullptr;

bool write_reg(uint8_t reg, uint16_t v) {
  const uint8_t buf[3] = {reg, static_cast<uint8_t>(v >> 8), static_cast<uint8_t>(v)};
  return i2c_master_transmit(dev, buf, sizeof buf, kTimeoutMs) == ESP_OK;
}

bool read_reg(uint8_t reg, uint16_t& v) {
  uint8_t buf[2];
  if (i2c_master_transmit_receive(dev, &reg, 1, buf, 2, kTimeoutMs) != ESP_OK) return false;
  v = static_cast<uint16_t>(buf[0] << 8 | buf[1]);
  return true;
}

// OS = start, MUX = AINx against GND, PGA = +-4.096 V, single-shot, 128 SPS, comparator off.
uint16_t config_for(int ch) {
  return 0x8000 | static_cast<uint16_t>((4 + ch) << 12) | (0b001 << 9) | (1 << 8) | (0b100 << 5) |
         0b11;
}

}  // namespace

esp_err_t init(i2c_master_bus_handle_t bus, uint8_t addr, uint32_t hz) {
  i2c_device_config_t cfg = {};
  cfg.dev_addr_length = I2C_ADDR_BIT_LEN_7;
  cfg.device_address = addr;
  cfg.scl_speed_hz = hz;
  return i2c_master_bus_add_device(bus, &cfg, &dev);
}

bool read_all(float volts[4]) {
  if (!dev) return false;
  for (int ch = 0; ch < 4; ++ch) {
    if (!write_reg(kRegConfig, config_for(ch))) return false;
    vTaskDelay(pdMS_TO_TICKS(9));   // one conversion at 128 SPS takes 7.8 ms
    uint16_t cfg = 0;
    int tries = 0;
    do {
      if (!read_reg(kRegConfig, cfg)) return false;
      if (!(cfg & 0x8000)) vTaskDelay(1);
    } while (!(cfg & 0x8000) && ++tries < 5);
    if (!(cfg & 0x8000)) return false;   // conversion never finished
    uint16_t raw = 0;
    if (!read_reg(kRegConversion, raw)) return false;
    volts[ch] = static_cast<int16_t>(raw) * kLsbV;
  }
  return true;
}

}  // namespace ads1115
