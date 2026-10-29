#include "bms/thermal.h"

#include <cmath>

namespace bms {

namespace {

constexpr int kN = 5;   // augmented matrix: 3 states and 2 inputs
using Mat = double[kN][kN];

void mat_mul(const Mat a, const Mat b, Mat out) {
  Mat t;
  for (int i = 0; i < kN; ++i)
    for (int j = 0; j < kN; ++j) {
      double s = 0.0;
      for (int k = 0; k < kN; ++k) s += a[i][k] * b[k][j];
      t[i][j] = s;
    }
  for (int i = 0; i < kN; ++i)
    for (int j = 0; j < kN; ++j) out[i][j] = t[i][j];
}

// Matrix exponential by scaling and squaring with a Taylor series. It runs only when the
// parameters change, so plain code is enough.
void expm(const Mat m, Mat out) {
  double norm = 0.0;
  for (int i = 0; i < kN; ++i) {
    double row = 0.0;
    for (int j = 0; j < kN; ++j) row += std::fabs(m[i][j]);
    if (row > norm) norm = row;
  }
  int squarings = 0;
  while (norm > 0.25) {
    norm *= 0.5;
    ++squarings;
  }
  const double scale = std::ldexp(1.0, -squarings);
  Mat a, term, sum;
  for (int i = 0; i < kN; ++i)
    for (int j = 0; j < kN; ++j) {
      a[i][j] = m[i][j] * scale;
      term[i][j] = (i == j) ? 1.0 : 0.0;
      sum[i][j] = term[i][j];
    }
  for (int k = 1; k <= 14; ++k) {
    mat_mul(term, a, term);
    for (int i = 0; i < kN; ++i)
      for (int j = 0; j < kN; ++j) {
        term[i][j] /= k;
        sum[i][j] += term[i][j];
      }
  }
  for (int s = 0; s < squarings; ++s) mat_mul(sum, sum, sum);
  for (int i = 0; i < kN; ++i)
    for (int j = 0; j < kN; ++j) out[i][j] = sum[i][j];
}

}  // namespace

Discrete discretise(const ThermalParams& p, int cell, float h_s) {
  const double cc = p.c_core, cs = p.c_surf, rc = p.r_core, ru = p.r_air[cell];
  const double a1 = 1.0 / (rc * cc);
  const double b1 = 1.0 / (rc * cs);
  const double b2 = 1.0 / (ru * cs);
  Mat m = {};
  // States T_c, T_s, Q_ab; inputs I^2 R and T_amb.
  m[0][0] = -a1;  m[0][1] = a1;          m[0][2] = 1.0 / cc;  m[0][3] = 1.0 / cc;
  m[1][0] = b1;   m[1][1] = -(b1 + b2);                        m[1][4] = b2;
  for (int i = 0; i < kN; ++i)
    for (int j = 0; j < kN; ++j) m[i][j] *= h_s;
  Mat e;
  expm(m, e);
  Discrete d;
  for (int i = 0; i < 3; ++i) {
    for (int j = 0; j < 3; ++j) d.phi[i][j] = static_cast<float>(e[i][j]);
    for (int j = 0; j < 2; ++j) d.gam[i][j] = static_cast<float>(e[i][3 + j]);
  }
  return d;
}

float slow_time_constant_s(const ThermalParams& p, int cell) {
  const double a1 = 1.0 / (p.r_core * p.c_core);
  const double b1 = 1.0 / (p.r_core * p.c_surf);
  const double b2 = 1.0 / (p.r_air[cell] * p.c_surf);
  const double tr = -(a1 + b1 + b2);
  const double det = a1 * b2;
  const double slow = 0.5 * (tr + std::sqrt(tr * tr - 4.0 * det));
  return static_cast<float>(-1.0 / slow);
}

// ---------------------------------------------------------------------------------------------
// Section 9.2: Kalman observer.

void CellObserver::configure(const ThermalParams& p, const KalmanTuning& k, int cell) {
  d_ = discretise(p, cell, cfg::kDt);
  q_[0] = k.core_sd_c * k.core_sd_c;
  q_[1] = k.surf_sd_c * k.surf_sd_c;
  q_[2] = k.heat_sd_w * k.heat_sd_w;
  r_ = k.meas_sd_c * k.meas_sd_c;
  ready_ = false;
}

void CellObserver::reset(float t_surface_c) {
  x_[0] = x_[1] = t_surface_c;
  x_[2] = 0.0f;
  for (auto& row : p_)
    for (float& v : row) v = 0.0f;
  p_[0][0] = 1.0f;     // the core may be warmer than the surface at start
  p_[1][1] = r_;
  p_[2][2] = 0.1f;     // W^2
  ready_ = true;
}

void CellObserver::predict(float p_joule_w, float t_amb_c) {
  float x[3];
  for (int i = 0; i < 3; ++i) {
    x[i] = d_.gam[i][0] * p_joule_w + d_.gam[i][1] * t_amb_c;
    for (int j = 0; j < 3; ++j) x[i] += d_.phi[i][j] * x_[j];
  }
  float fp[3][3];
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) {
      float s = 0.0f;
      for (int k = 0; k < 3; ++k) s += d_.phi[i][k] * p_[k][j];
      fp[i][j] = s;
    }
  for (int i = 0; i < 3; ++i) {
    x_[i] = x[i];
    for (int j = 0; j < 3; ++j) {
      float s = 0.0f;
      for (int k = 0; k < 3; ++k) s += fp[i][k] * d_.phi[j][k];
      p_[i][j] = s;
    }
    p_[i][i] += q_[i];
  }
}

void CellObserver::step(float p_joule_w, float t_amb_c, float t_meas_c) {
  predict(p_joule_w, t_amb_c);
  // Only T_s is measured: H = [0 1 0].
  const float s = p_[1][1] + r_;
  float k[3];
  for (int i = 0; i < 3; ++i) k[i] = p_[i][1] / s;
  const float innov = t_meas_c - x_[1];
  for (int i = 0; i < 3; ++i) x_[i] += k[i] * innov;
  float row1[3] = {p_[1][0], p_[1][1], p_[1][2]};
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) p_[i][j] -= k[i] * row1[j];
  for (int i = 0; i < 3; ++i)
    for (int j = i + 1; j < 3; ++j) p_[i][j] = p_[j][i] = 0.5f * (p_[i][j] + p_[j][i]);
}

// ---------------------------------------------------------------------------------------------
// Prediction-accuracy record.

void RmsRecord::add(double t_s, float e) {
  const int64_t minute = static_cast<int64_t>(t_s / 60.0);
  Bucket& b = b_[minute % 60];
  if (b.minute != minute) {
    b.minute = minute;
    b.sum_sq = 0.0f;
    b.n = 0;
  }
  b.sum_sq += e * e;
  ++b.n;
  sum_sq_all_ += static_cast<double>(e) * e;
  ++n_all_;
}

float RmsRecord::rms_hour(double t_s) const {
  const int64_t now = static_cast<int64_t>(t_s / 60.0);
  float sum = 0.0f;
  int n = 0;
  for (const Bucket& b : b_) {
    if (b.minute >= 0 && b.minute > now - 60 && b.minute <= now) {
      sum += b.sum_sq;
      n += b.n;
    }
  }
  return n ? std::sqrt(sum / n) : NAN;
}

float RmsRecord::rms_all() const {
  return n_all_ ? static_cast<float>(std::sqrt(sum_sq_all_ / n_all_)) : NAN;
}

void RmsRecord::clear() {
  for (Bucket& b : b_) b = Bucket();
  sum_sq_all_ = 0.0;
  n_all_ = 0;
}

// ---------------------------------------------------------------------------------------------
// Section 9.3: predict and confirm.

void Predictor::configure(const ThermalParams& p, int cell) {
  d_step_ = discretise(p, cell, cfg::kDt);
  d_h1_ = discretise(p, cell, cfg::kHorizon1S);
  d_h5_ = discretise(p, cell, cfg::kHorizon5S);
  restart();
}

void Predictor::restart() {
  for (Shadow& s : s1_) s.used = false;
  for (Shadow& s : s5_) s.used = false;
  next_start_t_ = -1.0;
  f1_ = f5_ = NAN;
  has_e1_ = has_e5_ = false;
  verdict_ = Verdict::Pending;
}

void Predictor::clear_record() {
  rms1_.clear();
  rms5_.clear();
}

void Predictor::start(Shadow* slots, int n, float tc, float ts) {
  for (int i = 0; i < n; ++i) {
    if (!slots[i].used) {
      slots[i] = Shadow();
      slots[i].used = true;
      slots[i].tc = tc;
      slots[i].ts = ts;
      return;
    }
  }
}

void Predictor::step_shadow(Shadow& s, float p_joule_w, float t_amb_c, float abs_i) {
  const Discrete& d = d_step_;
  // Healthy model: Q_ab = 0, so the third column of phi does not take part.
  const float tc = d.phi[0][0] * s.tc + d.phi[0][1] * s.ts + d.gam[0][0] * p_joule_w +
                   d.gam[0][1] * t_amb_c;
  const float ts = d.phi[1][0] * s.tc + d.phi[1][1] * s.ts + d.gam[1][0] * p_joule_w +
                   d.gam[1][1] * t_amb_c;
  s.tc = tc;
  s.ts = ts;
  s.elapsed_s += cfg::kDt;
  s.sum_abs_i += abs_i;
  ++s.n;
}

Predictor::Ended Predictor::advance(double t_s, float p_joule_w, float t_amb_c, float abs_i,
                                    float t_meas_c) {
  Ended out;
  // A prediction that ends on an invalid reading is dropped, not confirmed.
  const bool meas_ok = std::isfinite(t_meas_c);
  for (Shadow& s : s1_) {
    if (!s.used) continue;
    step_shadow(s, p_joule_w, t_amb_c, abs_i);
    if (s.elapsed_s >= cfg::kHorizon1S - 1e-3f) {
      out.h1 = meas_ok;
      out.e1 = t_meas_c - s.ts;
      s.used = false;
    }
  }
  for (Shadow& s : s5_) {
    if (!s.used) continue;
    step_shadow(s, p_joule_w, t_amb_c, abs_i);
    if (s.elapsed_s >= cfg::kHorizon5S - 1e-3f) {
      out.h5 = meas_ok;
      out.e5 = t_meas_c - s.ts;
      out.mean_abs_i5 = s.n ? s.sum_abs_i / s.n : 0.0f;
      s.used = false;
    }
  }
  if (out.h1) {
    has_e1_ = true;
    e1_ = out.e1;
    rms1_.add(t_s, out.e1);
  }
  if (out.h5) {
    has_e5_ = true;
    e5_ = out.e5;
    rms5_.add(t_s, out.e5);
    if (std::fabs(e5_) <= cfg::kConfirmNormalC) {
      verdict_ = Verdict::Normal;
    } else if (e5_ >= cfg::kConfirmHotC) {
      verdict_ = Verdict::Hot;
    } else if (e5_ <= cfg::kConfirmColdC) {
      verdict_ = Verdict::Cold;
    } else {
      verdict_ = Verdict::Unconfirmed;
    }
  }
  return out;
}

void Predictor::maybe_start(double t_s, const CellObserver& obs, float p_joule_w,
                            float t_amb_c) {
  if (next_start_t_ < 0.0) next_start_t_ = t_s;
  if (t_s + 1e-6 < next_start_t_) return;
  next_start_t_ += cfg::kPredictEveryS;
  if (next_start_t_ <= t_s) next_start_t_ = t_s + cfg::kPredictEveryS;

  const float x[3] = {obs.core_c(), obs.surface_c(), obs.heat_w()};
  auto ahead = [&](const Discrete& d) {
    float ts = d.gam[1][0] * p_joule_w + d.gam[1][1] * t_amb_c;
    for (int j = 0; j < 3; ++j) ts += d.phi[1][j] * x[j];
    return ts;
  };
  f1_ = ahead(d_h1_);
  f5_ = ahead(d_h5_);
  start(s1_, kSlots1, x[0], x[1]);
  start(s5_, kSlots5, x[0], x[1]);
}

// ---------------------------------------------------------------------------------------------
// Section 9.6: operating forecasts.

Forecast forecast(const ThermalParams& p, int cell, float r_cell_ohm, float abs_i, float t_amb_c,
                  float t_surface_c, float heat_w, float t_trip_c, float tau_s) {
  Forecast f;
  const float r_air = p.r_air[cell];
  const float p_joule = abs_i * abs_i * r_cell_ohm;
  f.t_eq_c = t_amb_c + (p_joule + heat_w) * r_air;
  if (f.t_eq_c <= t_trip_c) {
    f.time_to_limit_s = INFINITY;
  } else if (t_surface_c >= t_trip_c) {
    f.time_to_limit_s = 0.0f;
  } else {
    f.time_to_limit_s = tau_s * std::log((f.t_eq_c - t_surface_c) / (f.t_eq_c - t_trip_c));
  }
  const float allowed_w = (t_trip_c - t_amb_c) / r_air - heat_w;
  f.i_safe_a = allowed_w > 0.0f ? std::sqrt(allowed_w / r_cell_ohm) : 0.0f;
  return f;
}

}  // namespace bms
