#include "telemetry.h"

#include <cstdio>
#include <cstring>

#include "bms/supervisor.h"
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "sdkconfig.h"
#include "shared.h"

extern const char index_html_start[] asm("_binary_index_html_start");
extern const char index_html_end[] asm("_binary_index_html_end");

namespace telemetry {

namespace {

constexpr const char* kTag = "telemetry";
bool running = false;
bool station = false;
bool ready = false;   // Wi-Fi set up without errors

esp_err_t get_index(httpd_req_t* req) {
  httpd_resp_set_type(req, "text/html; charset=utf-8");
  // EMBED_TXTFILES adds a closing zero, which is not sent.
  return httpd_resp_send(req, index_html_start, index_html_end - index_html_start - 1);
}

esp_err_t get_state(httpd_req_t* req) {
  // The server runs one handler at a time, so static buffers are safe here.
  static bms::Snapshot snap;
  static char buf[16 * 1024];
  bool bench = false;
  shared::read(snap, &bench);
  int n = bms::write_json(snap, buf, sizeof buf - 64);
  if (n <= 1) {
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "snapshot too large");
    return ESP_FAIL;
  }
  // Add what only the firmware knows, before the closing brace.
  n += std::snprintf(buf + n - 1, sizeof buf - n, ",\"bench_sim\":%s,\"source\":\"esp32\"}",
                     bench ? "true" : "false") - 1;
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  return httpd_resp_send(req, buf, n);
}

void start_server() {
  httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
  cfg.stack_size = 8192;
  cfg.core_id = 0;
  cfg.task_priority = tskIDLE_PRIORITY + 3;
  httpd_handle_t server = nullptr;
  if (httpd_start(&server, &cfg) != ESP_OK) {
    ESP_LOGE(kTag, "web server did not start");
    return;
  }
  httpd_uri_t index = {};
  index.uri = "/";
  index.method = HTTP_GET;
  index.handler = get_index;
  httpd_register_uri_handler(server, &index);
  httpd_uri_t state = {};
  state.uri = "/api/state";
  state.method = HTTP_GET;
  state.handler = get_state;
  httpd_register_uri_handler(server, &state);
}

void on_event(void*, esp_event_base_t base, int32_t id, void* data) {
  if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
    esp_wifi_connect();
  } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
    if (running) esp_wifi_connect();   // keep trying; the safety task does not care
  } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
    const auto* ev = static_cast<ip_event_got_ip_t*>(data);
    ESP_LOGI(kTag, "dashboard: http://" IPSTR "/", IP2STR(&ev->ip_info.ip));
  }
}

}  // namespace

// Wi-Fi errors are logged and the dashboard stays off; they never stop the ESP32.
#define TRY(x)                                                           \
  do {                                                                   \
    const esp_err_t err_ = (x);                                          \
    if (err_ != ESP_OK) {                                                \
      ESP_LOGE(kTag, "%s: %s; no dashboard", #x, esp_err_to_name(err_)); \
      return;                                                            \
    }                                                                    \
  } while (0)

void start() {
  TRY(esp_netif_init());
  TRY(esp_event_loop_create_default());
  station = std::strlen(CONFIG_BMS_WIFI_SSID) > 0;
  if (station) {
    esp_netif_create_default_wifi_sta();
  } else {
    esp_netif_create_default_wifi_ap();
  }
  wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
  TRY(esp_wifi_init(&init));
  TRY(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_event, nullptr));
  TRY(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_event, nullptr));

  wifi_config_t wc = {};
  if (station) {
    std::strncpy(reinterpret_cast<char*>(wc.sta.ssid), CONFIG_BMS_WIFI_SSID, sizeof wc.sta.ssid);
    std::strncpy(reinterpret_cast<char*>(wc.sta.password), CONFIG_BMS_WIFI_PASSWORD,
                 sizeof wc.sta.password);
    TRY(esp_wifi_set_mode(WIFI_MODE_STA));
    TRY(esp_wifi_set_config(WIFI_IF_STA, &wc));
  } else {
    std::strncpy(reinterpret_cast<char*>(wc.ap.ssid), CONFIG_BMS_AP_SSID, sizeof wc.ap.ssid);
    std::strncpy(reinterpret_cast<char*>(wc.ap.password), CONFIG_BMS_AP_PASSWORD,
                 sizeof wc.ap.password);
    wc.ap.ssid_len = std::strlen(CONFIG_BMS_AP_SSID);
    wc.ap.max_connection = 4;
    wc.ap.authmode = std::strlen(CONFIG_BMS_AP_PASSWORD) >= 8 ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;
    TRY(esp_wifi_set_mode(WIFI_MODE_AP));
    TRY(esp_wifi_set_config(WIFI_IF_AP, &wc));
    ESP_LOGI(kTag, "access point %s: dashboard at http://192.168.4.1/", CONFIG_BMS_AP_SSID);
  }
  ready = true;
  start_server();
#if CONFIG_BMS_WIFI_ENABLE
  wifi_on();
#endif
}

void wifi_on() {
  if (running || !ready) return;
  running = true;
  if (esp_wifi_start() != ESP_OK) running = false;
}

void wifi_off() {
  if (!running) return;
  running = false;
  esp_wifi_stop();
}

bool wifi_running() { return running; }

}  // namespace telemetry
