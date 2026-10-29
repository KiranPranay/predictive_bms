#pragma once

#include <cstdint>

#include "bms/config.h"

namespace bms {

// One reading of every sensor, as the drivers deliver it. The core turns it into
// calibrated, checked and filtered measurements.
struct RawSample {
  double t_s = 0.0;                        // monotonic time, seconds
  bool ads_ok = false;                     // all four ADS1115 conversions were read
  float ads_v[cfg::kCells] = {};           // volts at ADS1115 inputs A0-A3 (taps B1, B2, B3, B+)
  bool ina_ok = false;                     // the INA226 was read
  float shunt_v = 0.0f;                    // INA226 shunt voltage, volts
  float bus_v = 0.0f;                      // INA226 bus voltage, volts (logged only)
  bool ntc_ok[cfg::kNtcs] = {};            // the ADC conversion succeeded
  float ntc_mv[cfg::kNtcs] = {};           // millivolts across each NTC
  uint32_t ntc_code[cfg::kNtcs] = {};      // raw code sum, for the flat-line check
};

// Gate 1 calibration of the sensing channels.
struct Calibration {
  float tap_gain[cfg::kCells] = {cfg::kNominalTapGain, cfg::kNominalTapGain,
                                 cfg::kNominalTapGain, cfg::kNominalTapGain};
  float tap_offset_v[cfg::kCells] = {};    // tap volts = gain * ADC volts + offset
  float shunt_ohm = 0.005f;                // section 4: 5 mOhm external shunt
  float current_gain = 1.0f;               // -1 when the shunt sense leads are reversed
  float current_offset_a = 0.0f;
  float ntc_supply_mv = 3300.0f;           // measured 3.3 V rail that feeds the pull-ups
  float ntc_pullup_ohm = 10000.0f;         // section 6: 10 kOhm 1 % pull-up
  float ntc_r25_ohm = 10000.0f;            // section 6: 10k B3950 bead
  float ntc_beta = 3950.0f;
  float ntc_offset_c[cfg::kNtcs] = {};     // added after conversion
};

// Section 9.9: the thermal layer is off until the parameters are fitted at Gate 9.
// "Estimates" runs it on estimated values for development on dummy heat sources, with the
// raw rate-of-rise backstop kept at the unfitted limits.
enum class ModelMode : uint8_t { Off = 0, Estimates = 1, Fitted = 2 };

// Section 9.1 thermal parameters.
struct ThermalParams {
  float c_core = 40.0f;   // J/degC  } placeholders: the sum matches the 45 J/degC estimate;
  float c_surf = 5.0f;    // J/degC  } the split and r_core are replaced at Gate 9
  float r_core = 2.0f;    // degC/W  }
  float r_air[cfg::kCells] = {30.0f, 30.0f, 30.0f, 30.0f};   // degC/W, estimate
};

// Kalman tuning (development values, confirmed at Gates 9 and 11). A larger surface term lets
// the observer follow fast changes at the can, such as the Gate 11 resistor, without reading
// them as a burst of core heat; a larger heat term finds a fault sooner but with more noise.
struct KalmanTuning {
  float meas_sd_c = 0.05f;      // NTC noise after the median stage
  float core_sd_c = 0.005f;     // model error per sample, core
  float surf_sd_c = 0.010f;     // model error per sample, surface
  float heat_sd_w = 0.003f;     // random walk of the abnormal heat per sample
};

constexpr int kOcvMaxPoints = 8;

struct ModelParams {
  ModelMode mode = ModelMode::Off;
  ThermalParams thermal;
  KalmanTuning kalman;
  bool gate4_done = false;                          // r_cell_ohm holds Gate 4 measurements
  float r_cell_ohm[cfg::kCells] = {0.035f, 0.035f, 0.035f, 0.035f};   // estimate until Gate 4
  int ocv_points = 0;                               // Gate 10 table; 0 = leak estimate off
  float ocv_v[kOcvMaxPoints] = {};                  // rested cell voltage
  float ocv_slope[kOcvMaxPoints] = {};              // dOCV/dSOC, volts per unit charge
};

enum class State : uint8_t { Startup, Run, Tripped };
enum class Mode : uint8_t { Rest, Charge, Discharge };
enum class Alarm : uint8_t { Off, Warning, Trip };

enum Branch : uint8_t { kBranchLoad = 1, kBranchCharge = 2, kBranchBoth = 3 };

// Every cause that latches a trip.
enum class TripCode : uint8_t {
  None = 0,
  CellHigh,          // 4.15 V, charge
  CellLow,           // 3.10 V, load
  ChargeTemp,        // 45 degC while charging, charge
  DischargeTemp,     // 55 degC, load
  TempSpread,        // 10 degC, both
  RiseRate,          // raw dT/dt backstop, both
  DischargeCurrent,  // 5.0 A, load
  ChargeCurrent,     // 1.6 A, charge
  PredictiveRisk,    // section 9.8 level 3, both
  TapSensor,         // ADS1115 or tap plausibility, both
  CurrentSensor,     // INA226, both
  CellNtc,           // NTC1-4 open, short or stuck, both
  AmbientNtc,        // NTC5, both
  NtcContact,        // NTC lifted off its cell (9.2, 9.3), both
  ControllerReset,   // the ESP32 restarted after a crash or watchdog, both
  Count
};

// Section 8 warnings.
enum Warning : uint32_t {
  kWarnCellHigh = 1u << 0,
  kWarnCellLow = 1u << 1,
  kWarnChargeTemp = 1u << 2,
  kWarnDischargeTemp = 1u << 3,
  kWarnSpread = 1u << 4,
  kWarnRise = 1u << 5,
  kWarnDischargeCurrent = 1u << 6,
  kWarnSensor = 1u << 7,   // one invalid sample
};

// Section 9.8 reasons for a cell's risk level.
enum Reason : uint32_t {
  kReasonConfirmHot = 1u << 0,          // watch, thermal
  kReasonHeatDiff = 1u << 1,            // watch, thermal
  kReasonTimeToLimit = 1u << 2,         // watch, thermal
  kReasonAboveSafeCurrent = 1u << 3,    // watch, thermal
  kReasonLeak = 1u << 4,                // watch, electrical
  kReasonResistanceDrift = 1u << 5,     // watch, electrical
  kReasonHeat = 1u << 6,                // warning
  kReasonThermalAndElectrical = 1u << 7,  // warning
  kReasonHeatTrip = 1u << 8,            // trip
  kReasonHeatDiffTrip = 1u << 9,        // trip
  kReasonSelfAcceleration = 1u << 10,   // trip
};
constexpr uint32_t kThermalWatch =
    kReasonConfirmHot | kReasonHeatDiff | kReasonTimeToLimit | kReasonAboveSafeCurrent;
constexpr uint32_t kElectricalWatch = kReasonLeak | kReasonResistanceDrift;

// Sensor channels, for plausibility.
enum Channel : uint8_t {
  kChTaps = 0,
  kChCurrent = 1,
  kChNtc0 = 2,   // kChNtc0 + i for NTC i, i = 0..4
  kChannelCount = 7
};

struct Outputs {
  bool load_on = false;
  bool charge_on = false;
  Alarm alarm = Alarm::Off;
};

// The part of the latch kept in flash, so a restart never clears a trip.
struct LatchRecord {
  uint8_t branches = 0;   // Branch bits held open
  uint32_t trips = 0;     // bit (1 << TripCode)
  uint8_t first = 0;      // TripCode of the first trip
  int8_t cell = -1;
};

enum class ResetResult : uint8_t {
  Accepted,
  NotLatched,
  CellVoltage,      // a cell outside 3.20-4.10 V
  Temperature,      // an NTC at 40 degC or more
  SensorsInvalid,   // a channel is not plausible
  NotClear,         // the cause has not been clear for 60 s
};

}  // namespace bms
