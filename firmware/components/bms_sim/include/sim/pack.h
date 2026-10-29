#pragma once

// A simulated 4S1P pack, its hardware BMS, its sensors and the faults Gate 11 asks for. The
// supervisor under test only sees the RawSample this produces, as it would on the ESP32.
//
// The plant uses the same two-state thermal structure as the supervisor (architecture 9.1), and
// adds what the supervisor's model leaves out: polarisation heat, noise, quantisation and
// sensor faults. Its numbers are illustrative values for a 3.3 Ah NMC 18650; they are not
// measurements of the project's cells.

#include <cstdint>
#include <random>

#include "bms/types.h"

namespace sim {

struct CellTruth {
  double capacity_ah = 3.3;
  double soc = 0.5;
  double r_ohm = 0.035;        // DC resistance, what a current step measures
  double rp_ohm = 0.008;       // polarisation resistance
  double tau_p_s = 30.0;       // polarisation time constant
  double vp = 0.0;             // polarisation voltage
  double c_core = 40.0, c_surf = 5.0, r_core = 2.0, r_air = 30.0;
  double t_core = 25.0, t_surf = 25.0;

  // Injected faults.
  double heat_w = 0.0;             // abnormal heat into the core (dummy heater or a fault)
  double heat_growth_c = 0.0;      // > 0: heat * exp((T_c - heat_ref_c) / heat_growth_c)
  double heat_ref_c = 25.0;
  double internal_ohm = 0.0;       // internal soft short; its heat is inside the cell
  double external_ohm = 0.0;       // Gate 11 resistor across the cell's taps, bonded to the can
  double external_share = 0.8;     // share of the resistor's heat that enters the cell

  double ocv() const;
  double abnormal_heat_w() const;
};

enum class NtcMode : uint8_t { Normal, Open, Short, Stuck, Lifted };

struct SensorTruth {
  double tap_gain[bms::cfg::kCells] = {};   // true divider ratio of each channel
  double shunt_ohm = 0.005;
  double ads_noise_v = 40e-6;
  double ina_noise_v = 2e-6;
  double ntc_noise_mv = 1.5;
  bool ads_fail = false;
  bool ina_fail = false;
  NtcMode ntc_mode[bms::cfg::kNtcs] = {};
  double ntc_offset_c[bms::cfg::kNtcs] = {};   // a simulated signal offset
  double lift_coupling = 0.25;                 // a lifted bead keeps this share of the rise
  double ads_spike_v = 0.0;                    // added to ADS input A1 on the next reading only
  double ntc_spike_mv[bms::cfg::kNtcs] = {};   // added to an NTC on the next reading only
};

double ocv_of_soc(double soc);
double soc_of_ocv(double v);

class Pack {
 public:
  explicit Pack(uint64_t seed = 1);

  CellTruth cell[bms::cfg::kCells];
  SensorTruth sens;
  double t = 0.0;
  double t_amb = 25.0;

  // External world.
  double load_a = 0.0;      // electronic load, discharge current while the load relay is on
  double charge_a = 0.0;    // charger CC current while the charge relay is on; 0 = unplugged
  double charge_cv_v = 16.8;

  // Supervisor outputs.
  bool load_relay = false;
  bool charge_relay = false;

  // Hardware BMS (layer A): over-charge 4.25 V, over-discharge 2.7 V, balance from 4.18 V.
  bool bms_open = false;

  double pack_current() const { return i_pack_; }
  double cell_voltage(int i) const;
  double pack_voltage() const;

  void step(double dt);
  bms::RawSample read();

  // The calibration and model values a finished Gate 1, 4, 9 and 10 would give for this pack.
  bms::Calibration calibration() const;
  bms::ModelParams fitted_params() const;

  void set_uniform_temperature(double c);

 private:
  double gauss(double sd) { return sd * norm_(rng_); }
  double compute_current() const;

  std::mt19937_64 rng_;
  std::normal_distribution<double> norm_{0.0, 1.0};
  double i_pack_ = 0.0;
  bms::RawSample stuck_;
  bool have_stuck_[bms::cfg::kNtcs] = {};
};

}  // namespace sim
