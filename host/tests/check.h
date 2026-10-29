#pragma once

// A small test harness, so the PC build needs nothing beyond a C++17 compiler.

#include <cmath>
#include <cstdio>
#include <vector>

namespace check {

struct Case {
  const char* name;
  void (*fn)();
};

inline std::vector<Case>& registry() {
  static std::vector<Case> cases;
  return cases;
}

inline int& failures() {
  static int n = 0;
  return n;
}

struct Registrar {
  Registrar(const char* name, void (*fn)()) { registry().push_back({name, fn}); }
};

}  // namespace check

#define TEST(name)                                          \
  static void name();                                       \
  static check::Registrar reg_##name(#name, name);          \
  static void name()

#define CHECK(cond)                                                              \
  do {                                                                           \
    if (!(cond)) {                                                               \
      std::printf("    %s:%d: CHECK(%s) failed\n", __FILE__, __LINE__, #cond);   \
      ++check::failures();                                                       \
    }                                                                            \
  } while (0)

#define CHECK_NEAR(a, b, tol)                                                          \
  do {                                                                                 \
    const double a_ = (a), b_ = (b), t_ = (tol);                                       \
    if (!(std::fabs(a_ - b_) <= t_)) {                                                 \
      std::printf("    %s:%d: %s = %.6g, expected %.6g +- %.3g\n", __FILE__, __LINE__, \
                  #a, a_, b_, t_);                                                     \
      ++check::failures();                                                             \
    }                                                                                  \
  } while (0)
