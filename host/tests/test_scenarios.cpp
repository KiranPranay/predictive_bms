// Every simulator scenario is also a test: the supervisor must pass all of its checks.

#include "check.h"
#include "sim/scenario.h"

namespace {

void run_scenario(const char* name) {
  const sim::Scenario* s = sim::find_scenario(name);
  sim::Bench b(s->seed, s->mode);
  sim::Report r;
  s->run(b, r);
  for (const auto& c : r.checks()) {
    if (!c.ok) {
      std::printf("    scenario %s: %s\n", name, c.text.c_str());
      ++check::failures();
    }
  }
  if (r.checks().empty()) ++check::failures();
}

}  // namespace

#define SCENARIO(name) \
  TEST(scenario_##name) { run_scenario(#name); }

SCENARIO(rest)
SCENARIO(discharge_steps)
SCENARIO(discharge_5a)
SCENARIO(charge)
SCENARIO(heat_no_current)
SCENARIO(heat_warning)
SCENARIO(small_fault)
SCENARIO(cell_outlier)
SCENARIO(self_acceleration)
SCENARIO(soft_short)
SCENARIO(internal_leak)
SCENARIO(forecast_hot_day)
SCENARIO(ntc_lift_off)
SCENARIO(ntc_open)
SCENARIO(ntc_short)
SCENARIO(ambient_open)
SCENARIO(ntc_stuck)
SCENARIO(ads_loss)
SCENARIO(ina_loss)
SCENARIO(spikes)
SCENARIO(load_steps)
SCENARIO(cell_high_charge)
SCENARIO(cell_low_discharge)
SCENARIO(overcurrent)
SCENARIO(charge_overtemp)
SCENARIO(temp_spread)
SCENARIO(backstop_unfitted)
SCENARIO(reset_rules)
SCENARIO(fit_log)

TEST(every_scenario_has_a_test) {
  // Keeps this list in step with the scenario library.
  CHECK(sim::scenarios().size() == 29);
}
