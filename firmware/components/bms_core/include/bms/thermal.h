#pragma once

#include <cmath>
#include <cstdint>

#include "bms/types.h"

namespace bms {

// Section 9.1, for one cell, over a time step h:
//   x(k+1) = phi * x(k) + gam * u(k),  x = [T_c, T_s, Q_ab],  u = [I^2 R, T_amb]
// Exact discretisation (matrix exponential), so long steps such as the 5-minute forecast are
// one multiplication.
struct Discrete {
  float phi[3][3] = {};
  float gam[3][2] = {};
};
Discrete discretise(const ThermalParams& p, int cell, float h_s);

// The slower of the two thermal time constants, seconds (section 9.6, tau).
float slow_time_constant_s(const ThermalParams& p, int cell);

// Abnormal heat expressed as the heating rate it causes, degC/min (section 9.2).
inline float heat_rate_c_per_min(const ThermalParams& p, float q_w) {
  return q_w / (p.c_core + p.c_surf) * 60.0f;
}

// Section 9.2: Kalman observer of [T_c, T_s, Q_ab] for one cell.
class CellObserver {
 public:
  void configure(const ThermalParams& p, const KalmanTuning& k, int cell);
  void reset(float t_surface_c);
  // Predicts over the last interval with its inputs, then corrects with the new reading.
  void step(float p_joule_w, float t_amb_c, float t_meas_c);
  // Predicts only, when the reading is not valid.
  void predict(float p_joule_w, float t_amb_c);

  bool ready() const { return ready_; }
  float core_c() const { return x_[0]; }
  float surface_c() const { return x_[1]; }
  float heat_w() const { return x_[2]; }
  const Discrete& step_model() const { return d_; }

 private:
  Discrete d_;
  float q_[3] = {};
  float r_ = 0.0f;
  float x_[3] = {};
  float p_[3][3] = {};
  bool ready_ = false;
};

// Root-mean-square error over the last hour (60 one-minute buckets) and since it was cleared.
class RmsRecord {
 public:
  void add(double t_s, float e);
  float rms_hour(double t_s) const;   // NaN when empty
  float rms_all() const;              // NaN when empty
  int count_all() const { return n_all_; }
  void clear();

 private:
  struct Bucket {
    int64_t minute = -1;
    float sum_sq = 0.0f;
    int n = 0;
  };
  Bucket b_[60];
  double sum_sq_all_ = 0.0;
  int n_all_ = 0;
};

enum class Verdict : uint8_t { Pending, Normal, Unconfirmed, Hot, Cold };

// Section 9.3: every 10 s, forecast the surface temperature 1 and 5 minutes ahead from the
// present observer state, assuming the present inputs continue. When the time arrives, the
// healthy model (Q_ab = 0), started from the stored state and run with the inputs actually
// measured in between, is compared with the reading: e = measured - predicted.
class Predictor {
 public:
  void configure(const ThermalParams& p, int cell);
  void restart();          // drops the pending predictions, keeps the accuracy record
  void clear_record();

  struct Ended {
    bool h1 = false, h5 = false;
    float e1 = 0.0f, e5 = 0.0f;
    float mean_abs_i5 = 0.0f;   // mean |I| over the 5-minute horizon
  };
  // Advances every pending prediction by one sample with the inputs of the last interval and
  // confirms those whose time has come against t_meas_c.
  Ended advance(double t_s, float p_joule_w, float t_amb_c, float abs_i, float t_meas_c);
  // Starts new predictions when 10 s have passed; u_now are the present inputs.
  void maybe_start(double t_s, const CellObserver& obs, float p_joule_w, float t_amb_c);

  float forecast1_c() const { return f1_; }
  float forecast5_c() const { return f5_; }
  bool has_e1() const { return has_e1_; }
  bool has_e5() const { return has_e5_; }
  float last_e1() const { return e1_; }
  float last_e5() const { return e5_; }
  Verdict verdict() const { return verdict_; }
  const RmsRecord& rms1() const { return rms1_; }
  const RmsRecord& rms5() const { return rms5_; }

 private:
  struct Shadow {
    bool used = false;
    float tc = 0.0f, ts = 0.0f;
    float elapsed_s = 0.0f;
    float sum_abs_i = 0.0f;
    int n = 0;
  };
  static constexpr int kSlots1 = 7;    // 60 s / 10 s + 1
  static constexpr int kSlots5 = 31;   // 300 s / 10 s + 1

  void start(Shadow* slots, int n, float tc, float ts);
  void step_shadow(Shadow& s, float p_joule_w, float t_amb_c, float abs_i);

  Discrete d_step_, d_h1_, d_h5_;
  Shadow s1_[kSlots1];
  Shadow s5_[kSlots5];
  double next_start_t_ = -1.0;
  float f1_ = NAN, f5_ = NAN;
  bool has_e1_ = false, has_e5_ = false;
  float e1_ = 0.0f, e5_ = 0.0f;
  Verdict verdict_ = Verdict::Pending;
  RmsRecord rms1_, rms5_;
};

// Section 9.6 operating forecasts for one cell.
struct Forecast {
  float t_eq_c = NAN;        // settling surface temperature at the present current
  float time_to_limit_s = INFINITY;   // INFINITY when the limit is never reached
  float i_safe_a = NAN;      // safe continuous current
};
Forecast forecast(const ThermalParams& p, int cell, float r_cell_ohm, float abs_i, float t_amb_c,
                  float t_surface_c, float heat_w, float t_trip_c, float tau_s);

}  // namespace bms
