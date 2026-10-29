// Runs every registered test. An argument selects: "unit" runs the unit tests, any other text
// runs the tests whose name contains it (for example "scenario_" or "leak").

#include <cstring>

#include "check.h"

int main(int argc, char** argv) {
  const char* filter = argc > 1 ? argv[1] : nullptr;
  int run = 0, failed = 0;
  for (const check::Case& c : check::registry()) {
    if (filter) {
      const bool scenario = std::strncmp(c.name, "scenario_", 9) == 0;
      if (!std::strcmp(filter, "unit") ? scenario : !std::strstr(c.name, filter)) continue;
    }
    const int before = check::failures();
    c.fn();
    ++run;
    const bool ok = check::failures() == before;
    if (!ok) ++failed;
    std::printf("%s  %s\n", ok ? "ok  " : "FAIL", c.name);
  }
  std::printf("\n%d tests, %d failed\n", run, failed);
  return (failed || run == 0) ? 1 : 0;
}
