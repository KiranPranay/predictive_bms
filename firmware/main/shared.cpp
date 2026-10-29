#include "shared.h"

#include <cstring>

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"

namespace shared {

namespace {

SemaphoreHandle_t mu = nullptr;
QueueHandle_t queue = nullptr;
bms::Snapshot latest;
bool latest_sim = false;
bms::Calibration pending_cal;
bms::ModelParams pending_params;
bool has_cal = false, has_params = false;

struct Lock {
  Lock() { xSemaphoreTake(mu, portMAX_DELAY); }
  ~Lock() { xSemaphoreGive(mu); }
};

}  // namespace

void init() {
  mu = xSemaphoreCreateMutex();
  queue = xQueueCreate(8, sizeof(Command));
}

void publish(const bms::Snapshot& s, bool bench_sim) {
  Lock l;
  latest = s;
  latest_sim = bench_sim;
}

void read(bms::Snapshot& s, bool* bench_sim) {
  Lock l;
  s = latest;
  if (bench_sim) *bench_sim = latest_sim;
}

bool send(Cmd type, int arg, const char* text) {
  Command c = {};
  c.type = type;
  c.arg = arg;
  if (text) std::strncpy(c.text, text, sizeof c.text - 1);
  return xQueueSend(queue, &c, 0) == pdTRUE;
}

bool receive(Command& c) { return xQueueReceive(queue, &c, 0) == pdTRUE; }

void set_pending(const bms::Calibration& cal) {
  Lock l;
  pending_cal = cal;
  has_cal = true;
}

void set_pending(const bms::ModelParams& params) {
  Lock l;
  pending_params = params;
  has_params = true;
}

bool take_pending(bms::Calibration& cal) {
  Lock l;
  if (!has_cal) return false;
  cal = pending_cal;
  has_cal = false;
  return true;
}

bool take_pending(bms::ModelParams& params) {
  Lock l;
  if (!has_params) return false;
  params = pending_params;
  has_params = false;
  return true;
}

}  // namespace shared
