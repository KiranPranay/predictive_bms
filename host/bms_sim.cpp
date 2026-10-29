// bms_sim: runs the supervisor against the simulated pack.
//
//   bms_sim list                       the scenarios and the gate each one rehearses
//   bms_sim run NAME|all [--csv FILE] [--json FILE] [--report FILE] [--quiet]
//                    [--thermal CC CS RC RU1 RU2 RU3 RU4]
//                                      runs scenarios and checks them; exit code 1 on a failure.
//                                      --report writes every result and check as JSON.
//                                      --thermal replaces the model with fitted values, as printed
//                                      by tools/fit_thermal.py (the Gate 9 to Gate 11 path)
//   bms_sim live [--speed N]           runs a pack in real time (times N), reads commands on
//                                      stdin and writes one JSON snapshot per line on stdout;
//                                      tools/sim_server.py puts the dashboard on top of it. A
//                                      twin pack with only fixed limits runs alongside, for
//                                      comparison.

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <iostream>
#include <memory>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>

#include "bms/supervisor.h"
#include "sim/commands.h"
#include "sim/scenario.h"

namespace {

int usage() {
  std::fprintf(stderr,
               "usage: bms_sim list\n"
               "       bms_sim run NAME|all [--csv FILE] [--json FILE] [--report FILE] [--quiet]\n"
               "                    [--thermal C_CORE C_SURF R_CORE RU1 RU2 RU3 RU4]\n"
               "       bms_sim live [--speed N]\n");
  return 2;
}

std::string json_str(const std::string& v) {
  std::string out = "\"";
  for (char ch : v) {
    if (ch == '"' || ch == '\\') {
      out += '\\';
      out += ch;
    } else if (static_cast<unsigned char>(ch) < 0x20) {
      out += ' ';
    } else {
      out += ch;
    }
  }
  return out + "\"";
}

int cmd_list() {
  for (const sim::Scenario& s : sim::scenarios())
    std::printf("%-20s gate %-6s %s\n", s.name, s.gate, s.summary);
  return 0;
}

int cmd_run(int argc, char** argv) {
  if (argc < 1) return usage();
  std::string name = argv[0], csv_path, json_path, report_path;
  bool quiet = false;
  bool thermal = false;
  bms::ThermalParams fitted;
  for (int i = 1; i < argc; ++i) {
    if (!std::strcmp(argv[i], "--thermal") && i + 7 < argc) {
      float v[7];
      for (float& x : v) x = std::strtof(argv[++i], nullptr);
      fitted.c_core = v[0];
      fitted.c_surf = v[1];
      fitted.r_core = v[2];
      for (int k = 0; k < 4; ++k) fitted.r_air[k] = v[3 + k];
      thermal = true;
    } else if (!std::strcmp(argv[i], "--csv") && i + 1 < argc) {
      csv_path = argv[++i];
    } else if (!std::strcmp(argv[i], "--json") && i + 1 < argc) {
      json_path = argv[++i];
    } else if (!std::strcmp(argv[i], "--report") && i + 1 < argc) {
      report_path = argv[++i];
    } else if (!std::strcmp(argv[i], "--quiet")) {
      quiet = true;
    } else {
      return usage();
    }
  }
  std::vector<const sim::Scenario*> list;
  if (name == "all") {
    for (const sim::Scenario& s : sim::scenarios()) list.push_back(&s);
  } else if (const sim::Scenario* s = sim::find_scenario(name)) {
    list.push_back(s);
  } else {
    std::fprintf(stderr, "no scenario called '%s' (see: bms_sim list)\n", name.c_str());
    return 2;
  }
  if (list.size() > 1 && (!csv_path.empty() || !json_path.empty())) {
    std::fprintf(stderr, "--csv and --json need a single scenario\n");
    return 2;
  }

  int failed = 0;
  std::string report = "[";
  for (const sim::Scenario* sc : list) {
    sim::Bench b(sc->seed, sc->mode);
    if (thermal) {
      b.params.thermal = fitted;
      b.sup->set_params(b.params);
    }
    std::FILE* csv = nullptr;
    if (!csv_path.empty()) {
      csv = std::fopen(csv_path.c_str(), "w");
      if (!csv) {
        std::perror(csv_path.c_str());
        return 2;
      }
      char header[512];
      bms::write_csv_header(header, sizeof header);
      std::fprintf(csv, "%s\n", header);
      b.csv = csv;
    }
    sim::Report r;
    sc->run(b, r);
    if (csv) std::fclose(csv);
    if (!json_path.empty()) {
      static char buf[24 * 1024];
      if (std::FILE* f = std::fopen(json_path.c_str(), "w")) {
        const bms::Snapshot s = b.snap();
        if (bms::write_json(s, buf, sizeof buf)) std::fprintf(f, "%s\n", buf);
        std::fclose(f);
      }
    }
    const bool ok = r.passed();
    if (!ok) ++failed;
    if (!report_path.empty()) {
      report += report.size() > 1 ? "," : "";
      report += "{\"name\":" + json_str(sc->name) + ",\"gate\":" + json_str(sc->gate) +
                ",\"summary\":" + json_str(sc->summary) + ",\"pass\":" + (ok ? "true" : "false") +
                ",\"checks\":[";
      for (size_t k = 0; k < r.checks().size(); ++k) {
        const auto& c = r.checks()[k];
        report += (k ? "," : "") + std::string("{\"ok\":") + (c.ok ? "true" : "false") +
                  ",\"text\":" + json_str(c.text) + "}";
      }
      report += "],\"notes\":[";
      for (size_t k = 0; k < r.notes().size(); ++k) report += (k ? "," : "") + json_str(r.notes()[k]);
      report += "]}";
    }
    std::printf("%s  %-20s %s\n", ok ? "PASS" : "FAIL", sc->name, sc->summary);
    if (!quiet || !ok) {
      for (const auto& c : r.checks())
        std::printf("      %s %s\n", c.ok ? "ok  " : "FAIL", c.text.c_str());
      for (const auto& n : r.notes()) std::printf("      note %s\n", n.c_str());
    }
  }
  if (list.size() > 1) {
    std::printf("\n%zu scenarios, %d failed\n", list.size(), failed);
  }
  if (!report_path.empty()) {
    if (std::FILE* f = std::fopen(report_path.c_str(), "w")) {
      std::fprintf(f, "%s]\n", report.c_str());
      std::fclose(f);
    }
  }
  return failed ? 1 : 0;
}

// --- live mode --------------------------------------------------------------------------------

struct Inbox {
  std::mutex mu;
  std::deque<std::string> lines;
  std::atomic<bool> closed{false};
};

// The comparison pack: the same cells and the same faults, protected only by fixed limits
// (voltage, current, 45 C while charging, 55 C), as a conventional BMS is. It reads the true
// surface temperatures, which is generous to it.
struct FixedLimit {
  bool load_open = false, charge_open = false;
  double trip_t = -1.0;
  std::string reason;
  double hot_at_trip = NAN;

  void step(const sim::Pack& p) {
    double vmax = -1e9, vmin = 1e9, tmax = -1e9;
    for (int i = 0; i < bms::cfg::kCells; ++i) {
      vmax = std::max(vmax, p.cell_voltage(i));
      vmin = std::min(vmin, p.cell_voltage(i));
      tmax = std::max(tmax, p.cell[i].t_surf);
    }
    const double a = p.pack_current();
    auto trip = [&](bool load, bool charge, const char* why) {
      load_open = load_open || load;
      charge_open = charge_open || charge;
      if (trip_t < 0) {
        trip_t = p.t;
        reason = why;
        hot_at_trip = tmax;
      }
    };
    if (tmax >= bms::cfg::kDischargeTempTripC) trip(true, false, "55 C cell temperature");
    if (a <= -bms::cfg::kRestCurrentA && tmax >= bms::cfg::kChargeTempTripC)
      trip(false, true, "45 C while charging");
    if (vmax >= bms::cfg::kCellHighTripV) trip(false, true, "4.15 V cell voltage");
    if (vmin <= bms::cfg::kCellLowTripV) trip(true, false, "3.10 V cell voltage");
    if (a >= bms::cfg::kDischargeTripA) trip(true, false, "5.0 A discharge");
    if (a <= -bms::cfg::kChargeTripA) trip(false, true, "1.6 A charge");
  }
};

// Everything the live mode runs: the supervised pack and its fixed-limit twin.
struct World {
  std::unique_ptr<sim::Bench> b;
  std::unique_ptr<sim::Pack> twin;
  FixedLimit fixed;
  double fault_t = -1.0, watch_t = -1.0, warn_t = -1.0, trip_t = -1.0;
  std::string trip_code;
  double trip_hot = NAN;
  int epoch = 0;   // counts fresh starts, so a client knows when its new run has begun

  void fresh(double soc, double ambient) {
    ++epoch;
    b = std::make_unique<sim::Bench>(1, bms::ModelMode::Fitted);
    twin = std::make_unique<sim::Pack>(1);
    for (sim::Pack* p : {&b->pack, twin.get()}) {
      p->set_uniform_temperature(ambient);
      for (sim::CellTruth& c : p->cell) c.soc = soc;
    }
    fixed = FixedLimit();
    fault_t = watch_t = warn_t = trip_t = -1.0;
    trip_code.clear();
    trip_hot = NAN;
  }

  void step() {
    b->step();
    twin->load_a = b->pack.load_a;
    twin->charge_a = b->pack.charge_a;
    twin->t_amb = b->pack.t_amb;
    fixed.step(*twin);
    twin->load_relay = !fixed.load_open;
    twin->charge_relay = !fixed.charge_open;
    twin->step(bms::cfg::kDt);

    const double t = b->t();
    const int risk = b->sup->risk();
    if (risk >= 1 && watch_t < 0) watch_t = t;
    if (risk >= 2 && warn_t < 0) warn_t = t;
    const bms::LatchRecord latch = b->sup->latch_record();
    if (latch.branches && trip_t < 0) {
      trip_t = t;
      trip_code = bms::trip_name(static_cast<bms::TripCode>(latch.first));
      trip_hot = -1e9;
      for (const sim::CellTruth& c : b->pack.cell) trip_hot = std::max(trip_hot, c.t_surf);
    }
  }
};

// True when a plant command starts a fault (not when it removes one).
bool starts_fault(const std::string& line) {
  std::istringstream in(line);
  std::string cmd, a, b;
  in >> cmd >> a >> b;
  if (cmd == "lift") return true;
  if (cmd == "ads" || cmd == "ina") return a == "fail";
  if (cmd == "ntc") return b != "ok";
  if (cmd == "heat" || cmd == "accel" || cmd == "defect" || cmd == "short" || cmd == "leak" ||
      cmd == "offset")
    return std::atof(b.c_str()) != 0.0;
  return false;
}

// Applies one command: the plant commands of sim::apply_command (to both packs), and these:
//   fresh [SOC] [AMBIENT_C] | pause | resume | speed N | reset | restart [crash]
//   | model off|estimates|fitted
std::string apply(World& w, double& speed, bool& paused, const std::string& line) {
  std::istringstream in(line);
  std::string cmd, word;
  double v = 0.0;
  in >> cmd;
  sim::Bench& b = *w.b;
  const std::string plant = sim::apply_command(b.pack, line);
  if (!plant.empty()) {
    sim::apply_command(*w.twin, line);
    if (w.fault_t < 0 && starts_fault(line)) w.fault_t = b.t();
    return plant;
  }
  if (cmd == "fresh") {
    double soc = 0.6, ambient = 25.0;
    in >> soc >> ambient;
    w.fresh(std::clamp(soc, 0.02, 0.98), std::clamp(ambient, -10.0, 60.0));
  } else if (cmd == "pause") {
    paused = true;
  } else if (cmd == "resume") {
    paused = false;
  } else if (cmd == "reset") {
    return std::string("reset: ") + bms::reset_result_text(b.sup->request_reset());
  } else if (cmd == "restart") {
    in >> word;
    b.restart_controller(word == "crash");
    if (word == "crash" && w.fault_t < 0) w.fault_t = b.t();
  } else if (cmd == "model" && in >> word) {
    if (word == "off") {
      b.set_mode(bms::ModelMode::Off);
    } else if (word == "estimates") {
      b.set_mode(bms::ModelMode::Estimates);
    } else if (word == "fitted") {
      b.set_mode(bms::ModelMode::Fitted);
    } else {
      return "usage: model off|estimates|fitted";
    }
  } else if (cmd == "speed" && in >> v) {
    speed = std::clamp(v, 0.1, 600.0);
  } else {
    return "unknown command: " + line;
  }
  return "ok: " + line;
}

const char* num(char* buf, double v, int prec) {
  if (std::isfinite(v)) {
    std::snprintf(buf, 32, "%.*f", prec, v);
  } else {
    std::snprintf(buf, 32, "null");
  }
  return buf;
}

void append_sim(const World& w, double speed, bool paused, std::string& out) {
  const sim::Pack& p = w.b->pack;
  char tmp[640], a[32], b2[32], c[32], d[32], e[32];
  std::snprintf(tmp, sizeof tmp,
                ",\"sim\":{\"epoch\":%d,\"speed\":%.1f,\"paused\":%s,\"load_a\":%.2f,\"charge_a\":%.2f,"
                "\"t_amb\":%.2f,\"i_true\":%.3f,\"bms_open\":%s,\"ads_fail\":%s,\"ina_fail\":%s,"
                "\"ambient_ntc\":\"%s\",\"cells\":[",
                w.epoch, speed, paused ? "true" : "false", p.load_a, p.charge_a, p.t_amb, p.pack_current(),
                p.bms_open ? "true" : "false", p.sens.ads_fail ? "true" : "false",
                p.sens.ina_fail ? "true" : "false", sim::ntc_mode_name(p.sens.ntc_mode[4]));
  out += tmp;
  for (int i = 0; i < bms::cfg::kCells; ++i) {
    const sim::CellTruth& cell = p.cell[i];
    std::snprintf(tmp, sizeof tmp,
                  "%s{\"t_core\":%.2f,\"t_surf\":%.2f,\"q_w\":%.3f,\"soc\":%.3f,"
                  "\"short_ohm\":%.0f,\"leak_ohm\":%.0f,\"defect_mohm\":%.0f,\"ntc\":\"%s\","
                  "\"offset_c\":%.1f}",
                  i ? "," : "", cell.t_core, cell.t_surf,
                  cell.abnormal_heat_w() + cell.defect_heat_w(p.pack_current()), cell.soc,
                  cell.external_ohm, cell.internal_ohm, cell.defect_ohm * 1000.0,
                  sim::ntc_mode_name(p.sens.ntc_mode[i]), p.sens.ntc_offset_c[i]);
    out += tmp;
  }
  const sim::Pack& t = *w.twin;
  double hottest = -1e9;
  for (const sim::CellTruth& cell : t.cell) hottest = std::max(hottest, cell.t_surf);
  std::snprintf(tmp, sizeof tmp,
                "],\"fixed\":{\"load\":%s,\"charge\":%s,\"trip_t\":%s,\"reason\":\"%s\","
                "\"hot_at_trip\":%s,\"hottest\":%.2f,\"cells\":[%.2f,%.2f,%.2f,%.2f]},",
                w.fixed.load_open ? "false" : "true", w.fixed.charge_open ? "false" : "true",
                num(a, w.fixed.trip_t < 0 ? NAN : w.fixed.trip_t, 1), w.fixed.reason.c_str(),
                num(b2, w.fixed.hot_at_trip, 1), hottest, t.cell[0].t_surf, t.cell[1].t_surf,
                t.cell[2].t_surf, t.cell[3].t_surf);
  out += tmp;
  auto opt = [](double v) { return v < 0 ? NAN : v; };
  std::snprintf(tmp, sizeof tmp,
                "\"marks\":{\"fault_t\":%s,\"watch_t\":%s,\"warn_t\":%s,\"trip_t\":%s,"
                "\"trip_code\":\"%s\",\"trip_hot\":%s}}",
                num(a, opt(w.fault_t), 1), num(b2, opt(w.watch_t), 1), num(c, opt(w.warn_t), 1),
                num(d, opt(w.trip_t), 1), w.trip_code.c_str(), num(e, w.trip_hot, 1));
  out += tmp;
}

int cmd_live(int argc, char** argv) {
  double speed = 1.0;
  for (int i = 0; i < argc; ++i) {
    if (!std::strcmp(argv[i], "--speed") && i + 1 < argc) {
      speed = std::atof(argv[++i]);
    } else {
      return usage();
    }
  }
  World w;
  w.fresh(0.6, 25.0);
  bool paused = false;
  Inbox inbox;
  std::thread reader([&inbox] {
    std::string line;
    while (std::getline(std::cin, line)) {
      std::lock_guard<std::mutex> lock(inbox.mu);
      inbox.lines.push_back(line);
    }
    inbox.closed = true;
  });
  reader.detach();

  using clock = std::chrono::steady_clock;
  auto next = clock::now();
  auto last_out = clock::now() - std::chrono::seconds(1);
  static char buf[24 * 1024];
  while (!inbox.closed) {
    {
      std::lock_guard<std::mutex> lock(inbox.mu);
      while (!inbox.lines.empty()) {
        const std::string reply = apply(w, speed, paused, inbox.lines.front());
        inbox.lines.pop_front();
        std::fprintf(stderr, "%s\n", reply.c_str());
      }
    }
    if (!paused) w.step();
    const auto now = clock::now();
    if (now - last_out >= std::chrono::milliseconds(250)) {
      last_out = now;
      const bms::Snapshot s = w.b->snap();
      const int n = bms::write_json(s, buf, sizeof buf);
      if (n > 1) {
        std::string line(buf, n - 1);   // drop the closing brace, add the simulator's view
        append_sim(w, speed, paused, line);
        line += "}\n";
        std::fwrite(line.data(), 1, line.size(), stdout);
        std::fflush(stdout);
      }
    }
    if (paused) {
      std::this_thread::sleep_for(std::chrono::milliseconds(50));
      next = clock::now();
      continue;
    }
    next += std::chrono::microseconds(static_cast<long>(bms::cfg::kDt * 1e6 / speed));
    if (next > clock::now()) {
      std::this_thread::sleep_until(next);
    } else if (clock::now() - next > std::chrono::seconds(1)) {
      next = clock::now();   // too far behind: do not try to catch up
    }
  }
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) return usage();
  const std::string cmd = argv[1];
  if (cmd == "list") return cmd_list();
  if (cmd == "run") return cmd_run(argc - 2, argv + 2);
  if (cmd == "live") return cmd_live(argc - 2, argv + 2);
  return usage();
}
