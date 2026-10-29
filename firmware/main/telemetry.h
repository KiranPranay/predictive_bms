#pragma once

// Wi-Fi and the dashboard (Objective 5). Nothing here is part of the safety chain: the safety
// task never waits for it, and every protection works with Wi-Fi off.
namespace telemetry {

void start();
void wifi_on();
void wifi_off();
bool wifi_running();

}  // namespace telemetry
