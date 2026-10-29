#include "storage.h"

#include <cstring>

#include "nvs.h"
#include "nvs_flash.h"

namespace storage {

namespace {

constexpr const char* kNamespace = "bms";
constexpr uint32_t kVersion = 1;   // change when a stored struct changes meaning

template <typename T>
struct Record {
  uint32_t version;
  uint32_t size;
  T value;
};

template <typename T>
bool load_blob(const char* key, T& out) {
  nvs_handle_t h;
  if (nvs_open(kNamespace, NVS_READONLY, &h) != ESP_OK) return false;
  Record<T> rec;
  size_t len = sizeof rec;
  const esp_err_t err = nvs_get_blob(h, key, &rec, &len);
  nvs_close(h);
  if (err != ESP_OK || len != sizeof rec || rec.version != kVersion || rec.size != sizeof(T))
    return false;
  std::memcpy(&out, &rec.value, sizeof(T));
  return true;
}

template <typename T>
esp_err_t save_blob(const char* key, const T& v) {
  nvs_handle_t h;
  esp_err_t err = nvs_open(kNamespace, NVS_READWRITE, &h);
  if (err != ESP_OK) return err;
  Record<T> rec;
  std::memset(&rec, 0, sizeof rec);
  rec.version = kVersion;
  rec.size = sizeof(T);
  std::memcpy(&rec.value, &v, sizeof(T));
  err = nvs_set_blob(h, key, &rec, sizeof rec);
  if (err == ESP_OK) err = nvs_commit(h);
  nvs_close(h);
  return err;
}

}  // namespace

esp_err_t init() {
  esp_err_t err = nvs_flash_init();
  if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    nvs_flash_erase();
    err = nvs_flash_init();
  }
  return err;
}

bool load(bms::Calibration& cal) { return load_blob("cal", cal); }
bool load(bms::ModelParams& params) { return load_blob("model", params); }
bool load(bms::LatchRecord& latch) { return load_blob("latch", latch); }
esp_err_t save(const bms::Calibration& cal) { return save_blob("cal", cal); }
esp_err_t save(const bms::ModelParams& params) { return save_blob("model", params); }
esp_err_t save(const bms::LatchRecord& latch) { return save_blob("latch", latch); }

}  // namespace storage
