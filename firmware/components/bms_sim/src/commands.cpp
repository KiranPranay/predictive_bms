#include "sim/commands.h"

#include <algorithm>
#include <sstream>

namespace sim {

const char* ntc_mode_name(NtcMode m) {
  switch (m) {
    case NtcMode::Open: return "open";
    case NtcMode::Short: return "short";
    case NtcMode::Stuck: return "stuck";
    case NtcMode::Lifted: return "lifted";
    default: return "normal";
  }
}

namespace {

bool index_arg(std::istringstream& in, int n_max, int& idx) {
  int n = 0;
  if (!(in >> n) || n < 1 || n > n_max) return false;
  idx = n - 1;
  return true;
}

}  // namespace

std::string apply_command(Pack& p, const std::string& line) {
  std::istringstream in(line);
  std::string cmd, word;
  in >> cmd;
  int i = 0;
  double v = 0.0;
  const int cells = bms::cfg::kCells, ntcs = bms::cfg::kNtcs;

  if (cmd == "load") {
    if (!(in >> v)) return "usage: load AMPS";
    p.load_a = std::max(0.0, v);
  } else if (cmd == "charge") {
    if (!(in >> v)) return "usage: charge AMPS";
    p.charge_a = std::max(0.0, v);
  } else if (cmd == "ambient") {
    if (!(in >> v)) return "usage: ambient C";
    p.t_amb = v;
  } else if (cmd == "soc") {
    if (!(in >> v)) return "usage: soc [CELL] 0-1";
    double v2 = 0.0;
    if (in >> v2) {   // soc CELL VALUE
      const int n = static_cast<int>(v);
      if (n < 1 || n > cells) return "usage: soc [CELL] 0-1";
      p.cell[n - 1].soc = std::clamp(v2, 0.0, 1.0);
    } else {
      for (CellTruth& c : p.cell) c.soc = std::clamp(v, 0.0, 1.0);
    }
  } else if (cmd == "heat") {
    if (!index_arg(in, cells, i) || !(in >> v)) return "usage: heat CELL WATTS";
    p.cell[i].heat_w = v;
    p.cell[i].heat_growth_c = 0.0;
  } else if (cmd == "accel") {
    if (!index_arg(in, cells, i) || !(in >> v)) return "usage: accel CELL WATTS [GROWTH_C]";
    double growth = 3.0;
    in >> growth;
    p.cell[i].heat_w = v;
    p.cell[i].heat_ref_c = p.cell[i].t_core;
    p.cell[i].heat_growth_c = growth;
  } else if (cmd == "defect") {
    if (!index_arg(in, cells, i) || !(in >> v)) return "usage: defect CELL MILLIOHM [GROWTH_C]";
    double growth = 0.0;
    in >> growth;
    p.cell[i].defect_ohm = std::max(0.0, v) / 1000.0;
    p.cell[i].defect_growth_c = std::max(0.0, growth);
    p.cell[i].defect_ref_c = p.cell[i].t_core;
  } else if (cmd == "short") {
    if (!index_arg(in, cells, i) || !(in >> v)) return "usage: short CELL OHMS (0 removes)";
    p.cell[i].external_ohm = std::max(0.0, v);
  } else if (cmd == "leak") {
    if (!index_arg(in, cells, i) || !(in >> v)) return "usage: leak CELL OHMS (0 removes)";
    p.cell[i].internal_ohm = std::max(0.0, v);
  } else if (cmd == "lift") {
    if (!index_arg(in, cells, i)) return "usage: lift CELL";
    p.sens.ntc_mode[i] = NtcMode::Lifted;
  } else if (cmd == "ntc") {
    if (!index_arg(in, ntcs, i) || !(in >> word)) return "usage: ntc N open|short|stuck|lift|ok";
    if (word == "open") {
      p.sens.ntc_mode[i] = NtcMode::Open;
    } else if (word == "short") {
      p.sens.ntc_mode[i] = NtcMode::Short;
    } else if (word == "stuck") {
      p.sens.ntc_mode[i] = NtcMode::Stuck;
    } else if (word == "lift") {
      p.sens.ntc_mode[i] = NtcMode::Lifted;
    } else if (word == "ok") {
      p.sens.ntc_mode[i] = NtcMode::Normal;
    } else {
      return "usage: ntc N open|short|stuck|lift|ok";
    }
  } else if (cmd == "offset") {
    if (!index_arg(in, ntcs, i) || !(in >> v)) return "usage: offset NTC C";
    p.sens.ntc_offset_c[i] = v;
  } else if (cmd == "ads" || cmd == "ina") {
    if (!(in >> word) || (word != "fail" && word != "ok")) return "usage: " + cmd + " fail|ok";
    (cmd == "ads" ? p.sens.ads_fail : p.sens.ina_fail) = word == "fail";
  } else if (cmd == "clear") {
    for (CellTruth& c : p.cell) {
      c.heat_w = 0.0;
      c.heat_growth_c = 0.0;
      c.external_ohm = 0.0;
      c.internal_ohm = 0.0;
      c.defect_ohm = 0.0;
    }
    for (int k = 0; k < ntcs; ++k) {
      p.sens.ntc_mode[k] = NtcMode::Normal;
      p.sens.ntc_offset_c[k] = 0.0;
    }
    p.sens.ads_fail = p.sens.ina_fail = false;
  } else {
    return "";
  }
  return "ok: " + line;
}

}  // namespace sim
