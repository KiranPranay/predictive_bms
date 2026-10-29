// bms_sim: runs the supervisor against the simulated pack.
//
//   bms_sim list                       the scenarios and the gate each one rehearses
//   bms_sim run NAME|all [--csv FILE] [--json FILE] [--quiet] [--thermal CC CS RC RU1 RU2 RU3 RU4]
//                                      runs scenarios and checks them; exit code 1 on a failure.
//                                      --thermal replaces the model with fitted values, as printed
//                                      by tools/fit_thermal.py (the Gate 9 to Gate 11 path)
//   bms_sim live [--speed N]           runs a pack in real time (times N), reads commands on
//                                      stdin and writes one JSON snapshot per line on stdout;
//                                      tools/sim_server.py puts the dashboard on top of it

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <iostream>
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
               "       bms_sim run NAME|all [--csv FILE] [--json FILE] [--quiet]\n"
               "                    [--thermal C_CORE C_SURF R_CORE RU1 RU2 RU3 RU4]\n"
               "       bms_sim live [--speed N]\n");
  return 2;
}

int cmd_list() {
  for (const sim::Scenario& s : sim::scenarios())
    std::printf("%-20s gate %-6s %s\n", s.name, s.gate, s.summary);
  return 0;
}

int cmd_run(int argc, char** argv) {
  if (argc < 1) return usage();
  std::string name = argv[0], csv_path, json_path;
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
  return failed ? 1 : 0;
}

// --- live mode --------------------------------------------------------------------------------

struct Inbox {
  std::mutex mu;
  std::deque<std::string> lines;
  std::atomic<bool> closed{false};
};

// Applies one command: the plant commands of sim::apply_command, and these for the controller:
//   reset | restart [crash] | model off|estimates|fitted | speed N
std::string apply(sim::Bench& b, double& speed, const std::string& line) {
  const std::string plant = sim::apply_command(b.pack, line);
  if (!plant.empty()) return plant;
  std::istringstream in(line);
  std::string cmd, word;
  double v = 0.0;
  in >> cmd;
  if (cmd == "reset") {
    return std::string("reset: ") + bms::reset_result_text(b.sup->request_reset());
  } else if (cmd == "restart") {
    in >> word;
    b.restart_controller(word == "crash");
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

void append_sim(const sim::Bench& b, double speed, std::string& out) {
  const sim::Pack& p = b.pack;
  char tmp[512];
  std::snprintf(tmp, sizeof tmp,
                ",\"sim\":{\"speed\":%.1f,\"load_a\":%.2f,\"charge_a\":%.2f,\"t_amb\":%.2f,"
                "\"i_true\":%.3f,\"bms_open\":%s,\"ads_fail\":%s,\"ina_fail\":%s,\"ambient_ntc\":\"%s\","
                "\"cells\":[",
                speed, p.load_a, p.charge_a, p.t_amb, p.pack_current(),
                p.bms_open ? "true" : "false", p.sens.ads_fail ? "true" : "false",
                p.sens.ina_fail ? "true" : "false", sim::ntc_mode_name(p.sens.ntc_mode[4]));
  out += tmp;
  for (int i = 0; i < bms::cfg::kCells; ++i) {
    const sim::CellTruth& c = p.cell[i];
    std::snprintf(tmp, sizeof tmp,
                  "%s{\"t_core\":%.2f,\"t_surf\":%.2f,\"q_w\":%.3f,\"soc\":%.3f,"
                  "\"short_ohm\":%.0f,\"leak_ohm\":%.0f,\"ntc\":\"%s\",\"offset_c\":%.1f}",
                  i ? "," : "", c.t_core, c.t_surf, c.abnormal_heat_w(), c.soc, c.external_ohm,
                  c.internal_ohm, sim::ntc_mode_name(p.sens.ntc_mode[i]), p.sens.ntc_offset_c[i]);
    out += tmp;
  }
  out += "]}";
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
  sim::Bench b(1, bms::ModelMode::Fitted);
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
        const std::string reply = apply(b, speed, inbox.lines.front());
        inbox.lines.pop_front();
        std::fprintf(stderr, "%s\n", reply.c_str());
      }
    }
    b.step();
    const auto now = clock::now();
    if (now - last_out >= std::chrono::milliseconds(250)) {
      last_out = now;
      const bms::Snapshot s = b.snap();
      const int n = bms::write_json(s, buf, sizeof buf);
      if (n > 1) {
        std::string line(buf, n - 1);   // drop the closing brace, add the simulator's view
        append_sim(b, speed, line);
        line += "}\n";
        std::fwrite(line.data(), 1, line.size(), stdout);
        std::fflush(stdout);
      }
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
