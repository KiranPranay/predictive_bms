#pragma once

// Fixed values of the supervisor.
//
// Every value comes from docs/architecture/current-architecture.md (revision 2.2); the comment
// names the section. A value marked "development value" is not set by the architecture. Those
// values are listed in docs/firmware.md with the gate that confirms or replaces them.

namespace bms::cfg {

constexpr int kCells = 4;
constexpr int kNtcs = 5;      // NTC1-NTC4 on the cells, NTC5 in the air
constexpr int kAmbient = 4;   // index of the ambient NTC

// Section 8, rules 1-3: sampling and filtering.
constexpr float kSampleHz = 5.0f;
constexpr float kDt = 1.0f / kSampleHz;
constexpr int kMedianLength = 5;
constexpr float kTempLowPassS = 10.0f;
constexpr float kSlopeWindowS = 30.0f;
constexpr int kSlopeSamples = 150;   // 30 s at 5 Hz

// Section 8 table: software limits.
constexpr float kCellHighWarnV = 4.10f;
constexpr float kCellHighTripV = 4.15f;   // disable charge
constexpr float kCellLowWarnV = 3.20f;
constexpr float kCellLowTripV = 3.10f;    // disable load
constexpr float kChargeTempWarnC = 40.0f;
constexpr float kChargeTempTripC = 45.0f;     // disable charge
constexpr float kDischargeTempWarnC = 50.0f;
constexpr float kDischargeTempTripC = 55.0f;  // disable load
constexpr float kSpreadWarnC = 7.0f;
constexpr float kSpreadTripC = 10.0f;         // disable both
constexpr float kRiseWarnCPerMin = 1.0f;
constexpr float kRiseWarnHoldS = 30.0f;
constexpr float kRiseTripCPerMin = 2.0f;      // disable both
constexpr float kRiseTripHoldS = 10.0f;
constexpr float kRiseWarnUnfittedCPerMin = 0.5f;   // section 9.9
constexpr float kRiseTripUnfittedCPerMin = 1.0f;   // section 9.9
constexpr float kDischargeWarnA = 4.5f;
constexpr float kDischargeTripA = 5.0f;   // disable load
constexpr float kChargeTripA = 1.6f;      // disable charge
constexpr float kSensorFaultHoldS = 2.0f;

// Section 5: tap plausibility.
constexpr float kTapJumpMaxV = 0.100f;

// Section 8, rule 6: manual reset.
constexpr float kResetCellMinV = 3.20f;
constexpr float kResetCellMaxV = 4.10f;
constexpr float kResetTempMaxC = 40.0f;
constexpr float kResetClearS = 60.0f;

// Section 9.5: the pack is at rest below this current. The same band decides charge,
// discharge and rest for the temperature limits of section 8 and T_trip of section 9.6.
constexpr float kRestCurrentA = 0.020f;

// Section 9.2.
constexpr float kHeatCurrentClampA = 5.0f;
constexpr float kContactHeatW = -0.4f;
constexpr float kContactHoldS = 60.0f;
constexpr float kContactMinCurrentA = 1.0f;

// Section 9.3.
constexpr float kPredictEveryS = 10.0f;
constexpr float kHorizon1S = 60.0f;
constexpr float kHorizon5S = 300.0f;
constexpr float kConfirmNormalC = 0.5f;
constexpr float kConfirmHotC = 1.0f;
constexpr float kConfirmColdC = -1.0f;

// Section 9.4.
constexpr float kStepMinA = 0.5f;
constexpr int kResistanceSteps = 20;
constexpr float kResistanceBound = 0.30f;   // model bound and drift limit, both 30 %

// Section 9.5.
constexpr float kRestSettleS = 30.0f * 60.0f;
constexpr int kLeakWindowMinutes = 60;
constexpr float kLeakNoBalanceV = 4.15f;
constexpr float kCapacityAh = 3.3f;
constexpr float kLeakWatchA = 0.020f;

// Section 9.6.
constexpr float kTimeToLimitWatchS = 600.0f;
constexpr float kAboveSafeHoldS = 30.0f;

// Section 9.7.
constexpr float kSelfAccelWindowS = 120.0f;
constexpr float kSelfAccelHeatRise = 0.5f;   // +50 %
constexpr float kSelfAccelCoreRiseC = 1.0f;

// Section 9.8.
constexpr float kDiffWatchCPerMin = 0.3f;
constexpr float kDiffWatchHoldS = 30.0f;
constexpr float kHeatWarnCPerMin = 0.5f;
constexpr float kHeatWarnHoldS = 30.0f;
constexpr float kHeatTripCPerMin = 1.0f;
constexpr float kHeatTripHoldS = 10.0f;
constexpr float kDiffTripCPerMin = 0.6f;
constexpr float kDiffTripHoldS = 10.0f;

// Section 5: nominal divider, 330 kOhm over 56 kOhm. Gate 1 replaces it per channel.
constexpr float kNominalTapGain = (330.0f + 56.0f) / 56.0f;

// Development values (see docs/firmware.md).
constexpr float kLimitHoldS = 1.0f;          // persistence of the voltage, temperature, spread
                                             // and current limits; Gates 2 and 3
constexpr float kHystV = 0.02f;              // release band of the voltage warnings
constexpr float kHystC = 1.0f;               // release band of the temperature and spread warnings
constexpr float kHystA = 0.2f;               // release band of the current warning
constexpr float kHystRateCPerMin = 0.1f;     // release band of the rate and heat levels
constexpr float kHystDiffCPerMin = 0.05f;    // release band of the cell-to-cell comparison
constexpr float kHystTimeS = 60.0f;          // release band of the time-to-limit watch
constexpr float kNtcMinC = -20.0f;           // a reading outside this range is an open or
constexpr float kNtcMaxC = 100.0f;           // shorted NTC; Gate 1
constexpr float kFlatLineS = 60.0f;          // an NTC code that never changes is stuck; Gate 1
constexpr float kObserverWarmupS = 60.0f;    // no thermal verdict while the observer settles
constexpr float kResistanceMaxOhm = 0.5f;    // a step result above this is discarded
constexpr int kResistanceDriftMinSteps = 3;  // steps needed before a drift verdict
constexpr float kStepSettleFrac = 0.1f;      // a step counts only if, one sample later, the
constexpr float kStepSettleA = 0.02f;        // current and every cell voltage have settled to
constexpr float kStepSettleV = 0.005f;       // within 10 % of their change plus these bands
constexpr float kCrossCheckTolerance = 0.5f; // heat and leak power agree within 50 % ...
constexpr float kCrossCheckFloorW = 0.05f;   // ... or within 0.05 W

}  // namespace bms::cfg
