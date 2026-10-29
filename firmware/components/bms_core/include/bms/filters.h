#pragma once

#include <cmath>

#include "bms/config.h"

namespace bms {

// Section 8, rule 2: median of the last five samples rejects single spikes.
class Median5 {
 public:
  float push(float v) {
    buf_[pos_] = v;
    pos_ = (pos_ + 1) % 5;
    if (n_ < 5) ++n_;
    float s[5];
    for (int i = 0; i < n_; ++i) s[i] = buf_[i];
    for (int i = 1; i < n_; ++i) {   // insertion sort, at most five values
      float x = s[i];
      int j = i - 1;
      while (j >= 0 && s[j] > x) {
        s[j + 1] = s[j];
        --j;
      }
      s[j + 1] = x;
    }
    value_ = (n_ % 2) ? s[n_ / 2] : 0.5f * (s[n_ / 2 - 1] + s[n_ / 2]);
    return value_;
  }
  float value() const { return value_; }
  bool primed() const { return n_ > 0; }
  void reset() { n_ = pos_ = 0; value_ = NAN; }

 private:
  float buf_[5] = {};
  int n_ = 0;
  int pos_ = 0;
  float value_ = NAN;
};

// Section 8, rule 2: first-order low-pass with a 10 s time constant.
class LowPass {
 public:
  float push(float v) {
    if (std::isnan(value_)) {
      value_ = v;
    } else {
      value_ += kAlpha * (v - value_);
    }
    return value_;
  }
  float value() const { return value_; }
  void reset() { value_ = NAN; }

 private:
  static constexpr float kAlpha = cfg::kDt / (cfg::kTempLowPassS + cfg::kDt);
  float value_ = NAN;
};

// Section 8, rule 3: least-squares slope over the most recent N samples spaced dt apart.
template <int N>
class SlopeWindow {
 public:
  void push(float y) {
    buf_[pos_] = y;
    pos_ = (pos_ + 1) % N;
    if (n_ < N) ++n_;
  }
  bool full() const { return n_ == N; }
  int count() const { return n_; }
  // Slope in units per second; NaN with fewer than two samples.
  float slope(float dt) const {
    if (n_ < 2) return NAN;
    const int start = (n_ < N) ? 0 : pos_;
    const float xm = 0.5f * static_cast<float>(n_ - 1);
    float ym = 0.0f;
    for (int k = 0; k < n_; ++k) ym += buf_[(start + k) % N];
    ym /= static_cast<float>(n_);
    float sxy = 0.0f, sxx = 0.0f;
    for (int k = 0; k < n_; ++k) {
      const float dx = static_cast<float>(k) - xm;
      sxy += dx * (buf_[(start + k) % N] - ym);
      sxx += dx * dx;
    }
    return sxy / (sxx * dt);
  }
  void reset() { n_ = pos_ = 0; }

 private:
  float buf_[N] = {};
  int n_ = 0;
  int pos_ = 0;
};

// Section 8, rule 4: a condition becomes active only after it has held for hold_s, and it
// releases only when the release condition holds, so an output never chatters at a threshold.
class Persist {
 public:
  bool update(bool set_cond, bool release_cond, float dt, float hold_s) {
    if (!active_) {
      if (!set_cond) {
        held_ = 0.0f;
      } else {
        held_ += dt;
        if (held_ >= hold_s - 1e-4f) active_ = true;
      }
    } else if (release_cond) {
      active_ = false;
      held_ = 0.0f;
    }
    return active_;
  }
  bool active() const { return active_; }
  void reset() {
    active_ = false;
    held_ = 0.0f;
  }

 private:
  bool active_ = false;
  float held_ = 0.0f;
};

}  // namespace bms
