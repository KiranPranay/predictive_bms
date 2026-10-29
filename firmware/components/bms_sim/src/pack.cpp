#include "sim/pack.h"

#include <algorithm>
#include <cmath>

#include "bms/sensors.h"

namespace sim {

namespace {

// Illustrative open-circuit voltage of an NMC cell against state of charge, joined by a
// monotone cubic so the slope changes smoothly, as on a real cell.
const double kSoc[] = {0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00};
const double kOcv[] = {3.00, 3.30, 3.42, 3.53, 3.605, 3.67, 3.735, 3.805, 3.885, 3.97, 4.065, 4.18};
constexpr int kPts = sizeof(kSoc) / sizeof(kSoc[0]);

// Node slopes of the Fritsch-Carlson monotone cubic.
const double* node_slopes() {
  static double m[kPts];
  static bool done = false;
  if (done) return m;
  double d[kPts - 1];
  for (int k = 0; k < kPts - 1; ++k) d[k] = (kOcv[k + 1] - kOcv[k]) / (kSoc[k + 1] - kSoc[k]);
  m[0] = d[0];
  m[kPts - 1] = d[kPts - 2];
  for (int k = 1; k < kPts - 1; ++k) {
    const double h0 = kSoc[k] - kSoc[k - 1], h1 = kSoc[k + 1] - kSoc[k];
    const double w0 = 2 * h1 + h0, w1 = h1 + 2 * h0;
    m[k] = (w0 + w1) / (w0 / d[k - 1] + w1 / d[k]);
  }
  done = true;
  return m;
}

constexpr double kAdsLsb = 4.096 / 32768.0;   // PGA +-4.096 V
constexpr double kInaLsb = 2.5e-6;
constexpr double kNtcCodePerMv = 4095.0 * 16.0 / 3300.0;   // 16 conversions summed

double quantise(double v, double lsb) { return std::round(v / lsb) * lsb; }

}  // namespace

double ocv_of_soc(double soc) {
  soc = std::clamp(soc, 0.0, 1.0);
  const double* m = node_slopes();
  int k = 1;
  while (k < kPts - 1 && soc > kSoc[k]) ++k;
  const double h = kSoc[k] - kSoc[k - 1];
  const double u = (soc - kSoc[k - 1]) / h;
  const double h00 = (1 + 2 * u) * (1 - u) * (1 - u), h10 = u * (1 - u) * (1 - u);
  const double h01 = u * u * (3 - 2 * u), h11 = u * u * (u - 1);
  return h00 * kOcv[k - 1] + h10 * h * m[k - 1] + h01 * kOcv[k] + h11 * h * m[k];
}

double soc_of_ocv(double v) {
  double lo = 0.0, hi = 1.0;
  if (v <= ocv_of_soc(lo)) return lo;
  if (v >= ocv_of_soc(hi)) return hi;
  for (int k = 0; k < 50; ++k) {
    const double mid = 0.5 * (lo + hi);
    (ocv_of_soc(mid) < v ? lo : hi) = mid;
  }
  return 0.5 * (lo + hi);
}

double CellTruth::ocv() const { return ocv_of_soc(soc); }

double CellTruth::abnormal_heat_w() const {
  if (heat_growth_c > 0.0) {
    return std::min(heat_w * std::exp((t_core - heat_ref_c) / heat_growth_c), 50.0);
  }
  return heat_w;
}

Pack::Pack(uint64_t seed) : rng_(seed) {
  std::uniform_real_distribution<double> tol(-0.01, 0.01);   // 1 % resistors
  for (int i = 0; i < bms::cfg::kCells; ++i) {
    const double rh = 330e3 * (1.0 + tol(rng_));
    const double rl = 56e3 * (1.0 + tol(rng_));
    sens.tap_gain[i] = (rh + rl) / rl;
    // A matched set: within the Gate 4 limits, end cells cool better than middle cells.
    cell[i].r_ohm = 0.035 * (1.0 + 0.5 * tol(rng_) * 4.0);
    cell[i].capacity_ah = 3.3 * (1.0 + 0.5 * tol(rng_));
    cell[i].r_air = (i == 0 || i == 3) ? 28.0 : 31.0;
  }
}

double Pack::cell_voltage(int i) const {
  const CellTruth& c = cell[i];
  const double i_ext = c.external_ohm > 0.0 ? c.ocv() / c.external_ohm : 0.0;
  return c.ocv() - (i_pack_ + i_ext) * c.r_ohm - c.vp;
}

double Pack::pack_voltage() const {
  double v = 0.0;
  for (int i = 0; i < bms::cfg::kCells; ++i) v += cell_voltage(i);
  return v;
}

double Pack::compute_current() const {
  if (bms_open) return 0.0;
  double i = load_relay ? load_a : 0.0;
  if (charge_relay && charge_a > 0.0) {
    double v_open = 0.0, r_sum = 0.0;
    for (const CellTruth& c : cell) {
      v_open += c.ocv() - c.vp;
      r_sum += c.r_ohm;
    }
    i -= std::clamp((charge_cv_v - v_open) / r_sum, 0.0, charge_a);   // CC, then CV taper
  }
  return i;
}

void Pack::set_uniform_temperature(double c) {
  t_amb = c;
  for (CellTruth& x : cell) x.t_core = x.t_surf = c;
}

void Pack::step(double dt) {
  i_pack_ = compute_current();

  // Hardware BMS: cuts the pack on cell over- or under-voltage, recovers with hysteresis.
  double vmax = -1e9, vmin = 1e9;
  for (int i = 0; i < bms::cfg::kCells; ++i) {
    vmax = std::max(vmax, cell_voltage(i));
    vmin = std::min(vmin, cell_voltage(i));
  }
  if (!bms_open && ((vmax > 4.25 && i_pack_ < 0.0) || (vmin < 2.7 && i_pack_ > 0.0))) {
    bms_open = true;
  } else if (bms_open && vmax < 4.15 && vmin > 3.0) {
    bms_open = false;
  }
  if (bms_open) i_pack_ = 0.0;

  for (int i = 0; i < bms::cfg::kCells; ++i) {
    CellTruth& c = cell[i];
    const double v = cell_voltage(i);
    const double i_ext = c.external_ohm > 0.0 ? c.ocv() / c.external_ohm : 0.0;
    const double i_int = c.internal_ohm > 0.0 ? c.ocv() / c.internal_ohm : 0.0;
    const double i_bal = v > 4.18 ? 0.030 : 0.0;   // balance bleed sits on the BMS board
    const double i_term = i_pack_ + i_ext + i_bal;

    c.soc -= (i_term + i_int) * dt / (c.capacity_ah * 3600.0);
    const double vp_inf = i_term * c.rp_ohm;
    c.vp = vp_inf + (c.vp - vp_inf) * std::exp(-dt / c.tau_p_s);

    const double q_core =
        i_term * i_term * c.r_ohm + i_term * c.vp + c.ocv() * i_int + c.abnormal_heat_w();
    const double q_surf =
        c.external_ohm > 0.0 ? c.external_share * c.ocv() * c.ocv() / c.external_ohm : 0.0;

    const int n = static_cast<int>(std::ceil(dt / 0.05));
    const double h = dt / n;
    for (int k = 0; k < n; ++k) {
      const double flow = (c.t_core - c.t_surf) / c.r_core;
      const double loss = (c.t_surf - t_amb) / c.r_air;
      c.t_core += h * (q_core - flow) / c.c_core;
      c.t_surf += h * (flow - loss + q_surf) / c.c_surf;
    }
  }
  t += dt;
}

bms::RawSample Pack::read() {
  bms::RawSample r;
  r.t_s = t;

  r.ads_ok = !sens.ads_fail;
  double tap = 0.0;
  for (int i = 0; i < bms::cfg::kCells; ++i) {
    tap += cell_voltage(i);
    double v = tap / sens.tap_gain[i] + gauss(sens.ads_noise_v);
    if (i == 1) v += sens.ads_spike_v;
    r.ads_v[i] = static_cast<float>(std::clamp(quantise(v, kAdsLsb), 0.0, 4.096));
  }
  sens.ads_spike_v = 0.0;

  r.ina_ok = !sens.ina_fail;
  r.shunt_v = static_cast<float>(quantise(i_pack_ * sens.shunt_ohm + gauss(sens.ina_noise_v), kInaLsb));
  r.bus_v = static_cast<float>(pack_voltage());

  const bms::Calibration nominal;
  for (int i = 0; i < bms::cfg::kNtcs; ++i) {
    r.ntc_ok[i] = true;
    const NtcMode mode = sens.ntc_mode[i];
    if (mode == NtcMode::Stuck && have_stuck_[i]) {
      r.ntc_mv[i] = stuck_.ntc_mv[i];
      r.ntc_code[i] = stuck_.ntc_code[i];
      continue;
    }
    double temp = i < bms::cfg::kCells ? cell[i].t_surf : t_amb;
    if (mode == NtcMode::Lifted) temp = t_amb + sens.lift_coupling * (temp - t_amb);
    temp += sens.ntc_offset_c[i];
    double mv = bms::ntc_millivolts(static_cast<float>(temp), nominal);
    if (mode == NtcMode::Open) mv = 3100.0;    // the ADC tops out below the 3.3 V rail
    if (mode == NtcMode::Short) mv = 60.0;
    mv += gauss(sens.ntc_noise_mv) + sens.ntc_spike_mv[i];
    sens.ntc_spike_mv[i] = 0.0;
    mv = std::clamp(mv, 0.0, 3300.0);
    r.ntc_mv[i] = static_cast<float>(mv);
    r.ntc_code[i] = static_cast<uint32_t>(std::lround(mv * kNtcCodePerMv));
    if (mode == NtcMode::Stuck) {
      stuck_.ntc_mv[i] = r.ntc_mv[i];
      stuck_.ntc_code[i] = r.ntc_code[i];
      have_stuck_[i] = true;
    } else {
      have_stuck_[i] = false;
    }
  }
  return r;
}

bms::Calibration Pack::calibration() const {
  bms::Calibration c;
  for (int i = 0; i < bms::cfg::kCells; ++i) c.tap_gain[i] = static_cast<float>(sens.tap_gain[i]);
  c.shunt_ohm = static_cast<float>(sens.shunt_ohm);
  return c;
}

bms::ModelParams Pack::fitted_params() const {
  bms::ModelParams p;
  p.mode = bms::ModelMode::Fitted;
  p.thermal.c_core = static_cast<float>(cell[0].c_core);
  p.thermal.c_surf = static_cast<float>(cell[0].c_surf);
  p.thermal.r_core = static_cast<float>(cell[0].r_core);
  for (int i = 0; i < bms::cfg::kCells; ++i) {
    p.thermal.r_air[i] = static_cast<float>(cell[i].r_air);
    p.r_cell_ohm[i] = static_cast<float>(cell[i].r_ohm);
  }
  p.gate4_done = true;
  // Gate 10: rested voltage and charge put in around 3.6, 3.8 and 4.0 V.
  const double points[] = {3.6, 3.8, 4.0};
  p.ocv_points = 3;
  for (int k = 0; k < 3; ++k) {
    const double s = soc_of_ocv(points[k]);
    const double slope = (ocv_of_soc(s + 0.02) - ocv_of_soc(s - 0.02)) / 0.04;
    p.ocv_v[k] = static_cast<float>(points[k]);
    p.ocv_slope[k] = static_cast<float>(slope);
  }
  return p;
}

}  // namespace sim
