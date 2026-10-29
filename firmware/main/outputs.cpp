#include "outputs.h"

#include "board.h"
#include "sdkconfig.h"

namespace outputs {

namespace {

constexpr int kRelayOn = 0;    // active LOW
constexpr int kRelayOff = 1;
#if CONFIG_BMS_ALARM_ACTIVE_LOW
constexpr int kAlarmOn = 0;
#else
constexpr int kAlarmOn = 1;
#endif

int64_t pressed_since_ms = -1;
bool reported = false;

void alarm(bool on) { gpio_set_level(board::kAlarm, on ? kAlarmOn : !kAlarmOn); }

}  // namespace

void init() {
  gpio_set_level(board::kLoadRelay, kRelayOff);
  gpio_set_level(board::kChargeRelay, kRelayOff);
  gpio_set_level(board::kAlarm, !kAlarmOn);
  gpio_config_t out = {};
  out.pin_bit_mask = (1ULL << board::kLoadRelay) | (1ULL << board::kChargeRelay) |
                     (1ULL << board::kAlarm);
  out.mode = GPIO_MODE_OUTPUT;
  gpio_config(&out);
  all_off();

  gpio_config_t in = {};
  in.pin_bit_mask = 1ULL << board::kResetButton;
  in.mode = GPIO_MODE_INPUT;
  in.pull_up_en = GPIO_PULLUP_ENABLE;
  gpio_config(&in);
}

void all_off() {
  gpio_set_level(board::kLoadRelay, kRelayOff);
  gpio_set_level(board::kChargeRelay, kRelayOff);
}

void apply(const bms::Outputs& out, int64_t now_ms) {
  gpio_set_level(board::kLoadRelay, out.load_on ? kRelayOn : kRelayOff);
  gpio_set_level(board::kChargeRelay, out.charge_on ? kRelayOn : kRelayOff);
  switch (out.alarm) {
    case bms::Alarm::Trip: alarm(true); break;
    case bms::Alarm::Warning: alarm((now_ms / 500) % 2 == 0); break;
    default: alarm(false); break;
  }
}

bool reset_button_held(int64_t now_ms) {
  if (gpio_get_level(board::kResetButton) != 0) {
    pressed_since_ms = -1;
    reported = false;
    return false;
  }
  if (pressed_since_ms < 0) pressed_since_ms = now_ms;
  if (!reported && now_ms - pressed_since_ms >= board::kResetHoldMs) {
    reported = true;
    return true;
  }
  return false;
}

}  // namespace outputs
