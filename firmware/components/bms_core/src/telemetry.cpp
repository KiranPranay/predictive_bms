#include <cmath>
#include <cstdarg>
#include <cstdio>

#include "bms/supervisor.h"

namespace bms {

namespace {

// Small JSON writer: keeps track of commas, writes NaN and infinity as null.
class Json {
 public:
  Json(char* buf, int cap) : buf_(buf), cap_(cap) {
    if (cap_ > 0) buf_[0] = '\0';
  }
  bool ok() const { return ok_; }
  int length() const { return len_; }

  void begin_obj(const char* key = nullptr) { open(key, '{'); }
  void end_obj() { close('}'); }
  void begin_arr(const char* key = nullptr) { open(key, '['); }
  void end_arr() { close(']'); }

  void num(const char* key, double v, int prec = 3) {
    prefix(key);
    if (std::isfinite(v)) {
      put("%.*f", prec, v);
    } else {
      put("null");
    }
  }
  void integer(const char* key, long v) {
    prefix(key);
    put("%ld", v);
  }
  void boolean(const char* key, bool v) {
    prefix(key);
    put(v ? "true" : "false");
  }
  void str(const char* key, const char* v) {
    prefix(key);
    put("\"");
    for (const char* p = v; *p; ++p) {
      const char c = *p;
      if (c == '"' || c == '\\') {
        put("\\%c", c);
      } else if (static_cast<unsigned char>(c) < 0x20) {
        put(" ");
      } else {
        put("%c", c);
      }
    }
    put("\"");
  }
  void null(const char* key) {
    prefix(key);
    put("null");
  }
  // Names of the set bits as an array of strings.
  void names(const char* key, uint32_t bits, const char* (*list)(uint32_t, char*, int)) {
    char tmp[256];
    list(bits, tmp, sizeof tmp);
    begin_arr(key);
    const char* p = tmp;
    while (*p) {
      char one[48];
      int n = 0;
      while (*p && *p != ',' && n < 47) one[n++] = *p++;
      one[n] = '\0';
      if (*p == ',') ++p;
      str(nullptr, one);
    }
    end_arr();
  }

 private:
  void put(const char* fmt, ...) {
    if (!ok_) return;
    va_list ap;
    va_start(ap, fmt);
    const int w = std::vsnprintf(buf_ + len_, cap_ - len_, fmt, ap);
    va_end(ap);
    if (w < 0 || w >= cap_ - len_) {
      ok_ = false;
      return;
    }
    len_ += w;
  }
  void prefix(const char* key) {
    if (need_comma_[depth_]) put(",");
    need_comma_[depth_] = true;
    if (key) put("\"%s\":", key);
  }
  void open(const char* key, char c) {
    if (depth_ > 0) prefix(key);
    put("%c", c);
    if (depth_ < kDepth - 1) ++depth_;
    need_comma_[depth_] = false;
  }
  void close(char c) {
    put("%c", c);
    if (depth_ > 0) --depth_;
  }

  static constexpr int kDepth = 8;
  char* buf_;
  int cap_;
  int len_ = 0;
  bool ok_ = true;
  int depth_ = 0;
  bool need_comma_[kDepth] = {};
};

const char* cross_name(CrossCheck c) {
  switch (c) {
    case CrossCheck::Agree: return "agree";
    case CrossCheck::Disagree: return "disagree";
    default: return "n/a";
  }
}

const char* alarm_name(Alarm a) {
  switch (a) {
    case Alarm::Warning: return "warning";
    case Alarm::Trip: return "trip";
    default: return "off";
  }
}

const char* trips_list(uint32_t bits, char* buf, int cap) {
  int len = 0;
  buf[0] = '\0';
  for (int c = 1; c < static_cast<int>(TripCode::Count); ++c) {
    if (!(bits & (1u << c))) continue;
    const int w = std::snprintf(buf + len, cap - len, "%s%s", len ? "," : "",
                                trip_name(static_cast<TripCode>(c)));
    if (w < 0 || w >= cap - len) break;
    len += w;
  }
  return buf;
}

void channel_status(Json& j, const Snapshot& s, int ch, const char* key) {
  // "fault" once the 2 s persistence has run out; the latch then holds the trip.
  const char* v = !s.ch_invalid[ch] ? "ok"
                  : s.ch_invalid_for_s[ch] >= cfg::kSensorFaultHoldS ? "fault"
                                                                     : "notice";
  j.str(key, v);
}

}  // namespace

int write_json(const Snapshot& s, char* buf, int cap) {
  Json j(buf, cap);
  j.begin_obj();
  j.integer("seq", static_cast<long>(s.seq));
  j.num("t", s.t_s, 1);
  j.str("state", state_name(s.state));
  j.str("mode", mode_name(s.mode));
  j.str("model", model_name(s.model));
  j.boolean("thermal_ready", s.thermal_ready);
  j.boolean("ocv_table", s.ocv_table);
  j.integer("risk", s.risk);
  j.str("risk_name", level_name(s.risk));
  j.begin_obj("relays");
  j.boolean("load", s.out.load_on);
  j.boolean("charge", s.out.charge_on);
  j.end_obj();
  j.str("alarm", alarm_name(s.out.alarm));
  j.names("warnings", s.warnings, warning_list);

  j.begin_obj("pack");
  j.num("v", s.pack_v, 3);
  j.num("i", s.current_a, 3);
  j.num("p", s.pack_v * s.current_a, 2);
  j.num("t_amb", s.t_amb, 2);
  j.num("i_safe", s.i_safe, 2);
  j.num("t_trip", s.t_trip, 0);
  j.end_obj();

  j.begin_obj("latch");
  j.boolean("load", s.latch.branches & kBranchLoad);
  j.boolean("charge", s.latch.branches & kBranchCharge);
  j.names("trips", s.latch.trips, trips_list);
  j.str("first", trip_name(static_cast<TripCode>(s.latch.first)));
  j.end_obj();

  j.begin_arr("trip_log");   // newest first
  for (int k = s.n_trips - 1; k >= 0; --k) {
    const TripRecord& r = s.trips[k];
    j.begin_obj();
    j.num("t", r.t_s, 1);
    j.str("code", trip_name(r.code));
    j.integer("cell", r.cell >= 0 ? r.cell + 1 : 0);
    j.str("detail", r.detail);
    j.boolean("load_was_on", r.load_was_on);
    j.boolean("charge_was_on", r.charge_was_on);
    j.num("i", r.current_a, 3);
    j.begin_arr("v");
    for (float v : r.cell_v) j.num(nullptr, v, 3);
    j.end_arr();
    j.begin_arr("t_c");
    for (float v : r.temp_c) j.num(nullptr, v, 2);
    j.end_arr();
    j.begin_arr("heat_w");
    for (float v : r.heat_w) j.num(nullptr, v, 3);
    j.end_arr();
    j.begin_arr("leak_ma");
    for (float v : r.leak_a) j.num(nullptr, v * 1000.0f, 1);
    j.end_arr();
    j.end_obj();
  }
  j.end_arr();

  j.begin_obj("sensors");
  channel_status(j, s, kChTaps, "taps");
  channel_status(j, s, kChCurrent, "current");
  j.begin_arr("ntc");
  for (int i = 0; i < cfg::kNtcs; ++i) channel_status(j, s, kChNtc0 + i, nullptr);
  j.end_arr();
  j.end_obj();

  j.begin_obj("leak");
  j.num("rest_min", s.leak_rest_s / 60.0, 1);
  j.integer("window_min", s.leak_minutes);
  j.boolean("valid", s.leak_valid);
  j.end_obj();

  j.begin_arr("cells");
  for (int i = 0; i < cfg::kCells; ++i) {
    const CellSnapshot& c = s.cells[i];
    j.begin_obj();
    j.num("v", c.v, 4);
    j.num("r_mohm", c.r_model_ohm * 1000.0f, 1);
    j.num("r_avg_mohm", c.r_avg_ohm * 1000.0f, 1);
    j.integer("r_steps", c.r_steps);
    j.num("t_s", c.t_meas, 2);
    j.num("t_lp", c.t_lp, 2);
    j.num("rise", c.rise_valid ? c.rise : NAN, 2);
    j.num("t_c", c.t_core, 2);
    j.num("q_w", c.heat_w, 3);
    j.num("q_rate", c.heat_rate, 3);
    j.num("q_diff", c.heat_diff, 3);
    j.num("f1", c.f1, 2);
    j.num("f5", c.f5, 2);
    j.num("e1", c.has_e1 ? c.e1 : NAN, 2);
    j.num("e5", c.has_e5 ? c.e5 : NAN, 2);
    j.str("verdict", verdict_name(c.verdict));
    j.num("rms1_hour", c.rms1_hour, 3);
    j.num("rms5_hour", c.rms5_hour, 3);
    j.num("rms1_all", c.rms1_all, 3);
    j.num("rms5_all", c.rms5_all, 3);
    j.integer("n5_all", c.n5_all);
    j.num("t_eq", c.t_eq, 1);
    j.num("ttl_s", c.time_to_limit_s, 0);   // null when the limit is never reached
    j.num("i_safe", c.i_safe, 2);
    j.num("leak_ma", c.leak_a * 1000.0f, 1);
    j.num("p_leak_w", c.p_leak_w, 3);
    j.str("cross", cross_name(c.cross));
    j.integer("level", c.level);
    j.names("reasons", c.reasons, reason_list);
    j.end_obj();
  }
  j.end_arr();

  j.begin_arr("events");   // newest first
  for (int k = s.n_events - 1; k >= 0; --k) {
    const Event& e = s.events[k];
    j.begin_obj();
    j.num("t", e.t_s, 1);
    j.str("kind", event_kind_name(e.kind));
    j.integer("cell", e.cell >= 0 ? e.cell + 1 : 0);
    j.str("text", e.text);
    j.end_obj();
  }
  j.end_arr();
  j.end_obj();
  return j.ok() ? j.length() : 0;
}

int write_csv_header(char* buf, int cap) {
  const int w = std::snprintf(
      buf, cap,
      "t_s,mode,load,charge,risk,current_a,v1,v2,v3,v4,ts1,ts2,ts3,ts4,t_amb,"
      "tc1,tc2,tc3,tc4,q1_w,q2_w,q3_w,q4_w,r1_mohm,r2_mohm,r3_mohm,r4_mohm");
  return (w > 0 && w < cap) ? w : 0;
}

int write_csv_row(const Snapshot& s, char* buf, int cap) {
  int len = std::snprintf(buf, cap, "%.1f,%s,%d,%d,%d,%.4f", s.t_s, mode_name(s.mode),
                          s.out.load_on ? 1 : 0, s.out.charge_on ? 1 : 0, s.risk, s.current_a);
  auto add = [&](float v, int prec) {
    if (len <= 0 || len >= cap) return;
    const int w = std::isfinite(v) ? std::snprintf(buf + len, cap - len, ",%.*f", prec, v)
                                   : std::snprintf(buf + len, cap - len, ",");
    len = (w < 0 || w >= cap - len) ? 0 : len + w;
  };
  for (const CellSnapshot& c : s.cells) add(c.v, 4);
  for (const CellSnapshot& c : s.cells) add(c.t_meas, 3);
  add(s.t_amb, 3);
  for (const CellSnapshot& c : s.cells) add(c.t_core, 3);
  for (const CellSnapshot& c : s.cells) add(c.heat_w, 4);
  for (const CellSnapshot& c : s.cells) add(c.r_model_ohm * 1000.0f, 2);
  return (len > 0 && len < cap) ? len : 0;
}

}  // namespace bms
