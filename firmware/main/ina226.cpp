#include "ina226.h"

#include "esp_log.h"

namespace ina226 {

namespace {

constexpr uint8_t kRegConfig = 0x00;
constexpr uint8_t kRegShunt = 0x01;
constexpr uint8_t kRegBus = 0x02;
constexpr uint8_t kRegMaker = 0xFE;
constexpr int kTimeoutMs = 20;
// Average of 16, 1.1 ms shunt and bus conversions, continuous: a new result every 35 ms.
constexpr uint16_t kConfig = 0x4000 | (0b010 << 9) | (0b100 << 6) | (0b100 << 3) | 0b111;

i2c_master_dev_handle_t dev = nullptr;
bool configured = false;

bool read_reg(uint8_t reg, uint16_t& v) {
  uint8_t buf[2];
  if (i2c_master_transmit_receive(dev, &reg, 1, buf, 2, kTimeoutMs) != ESP_OK) return false;
  v = static_cast<uint16_t>(buf[0] << 8 | buf[1]);
  return true;
}

bool configure() {
  uint16_t maker = 0;
  if (!read_reg(kRegMaker, maker)) return false;
  if (maker != 0x5449) {   // "TI"
    ESP_LOGW("ina226", "unexpected manufacturer ID 0x%04x", maker);
    return false;
  }
  const uint8_t buf[3] = {kRegConfig, kConfig >> 8, kConfig & 0xFF};
  return i2c_master_transmit(dev, buf, sizeof buf, kTimeoutMs) == ESP_OK;
}

}  // namespace

esp_err_t init(i2c_master_bus_handle_t bus, uint8_t addr, uint32_t hz) {
  i2c_device_config_t cfg = {};
  cfg.dev_addr_length = I2C_ADDR_BIT_LEN_7;
  cfg.device_address = addr;
  cfg.scl_speed_hz = hz;
  const esp_err_t err = i2c_master_bus_add_device(bus, &cfg, &dev);
  if (err == ESP_OK) configured = configure();
  return err;
}

bool read(float& shunt_v, float& bus_v) {
  if (!dev) return false;
  if (!configured) {
    configured = configure();   // the module may have lost power; set it up again
    if (!configured) return false;
  }
  uint16_t sh = 0, bu = 0;
  if (!read_reg(kRegShunt, sh) || !read_reg(kRegBus, bu)) {
    configured = false;
    return false;
  }
  shunt_v = static_cast<int16_t>(sh) * 2.5e-6f;
  bus_v = bu * 1.25e-3f;
  return true;
}

}  // namespace ina226
