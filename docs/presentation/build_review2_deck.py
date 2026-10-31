#!/usr/bin/env python3
"""Build the streamlined Major Project Stage-1 Review-2 presentation deck.

Usage:
    .venv/bin/python docs/presentation/build_review2_deck.py

Outputs:
    - docs/presentation/Predictive_BMS_Stage1_Review2.pptx
    - docs/presentation/Predictive_BMS_Stage1_Review2.pdf (via LibreOffice export)
    - Mirrored copies in docs/build-guide/

Theme: "banded" 4:3 (10 in x 7.5 in) matching BVRIT EEE Review-2 departmental standard.
"""

import os
import sys
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import deck_common
from deck_common import (
    Presentation, Inches, configure, WARNINGS, SLIDE_H, SLIDE_W,
    title_slide, content_slide, two_section_slide, image_slide,
    two_image_slide, image_and_text_slide, wide_image_slide, table_slide, closing_slide,
)

PPTX_OUT = os.path.join(HERE, "Predictive_BMS_Stage1_Review2.pptx")
PDF_OUT = os.path.join(HERE, "Predictive_BMS_Stage1_Review2.pdf")
BUILD_GUIDE_DIR = os.path.abspath(os.path.join(HERE, "../build-guide"))
PICS_DIR = os.path.abspath(os.path.join(HERE, "../../pics"))
IMG_DIR = os.path.join(HERE, "images")

configure(
    review_label="Stage-1 Review-2",
    export_date="31-10-2026",
    diagram_dir=IMG_DIR,
    review_heading="Major Project Stage-1 Review-2 Presentation",
    title_lines=["Predictive Thermal Battery Management System",
                 "for Li-ion Battery Packs"],
    theme="banded",
)

LIT_HEAD = ["S.No", "Paper Title", "Outcomes", "Limitation / Research Gap"]
LIT_W = [0.60, 2.60, 3.05, 3.05]

LITERATURE_1 = [
    ["[1]", "Thermal runaway mechanism of lithium ion battery for electric vehicles: A review (Feng et al., 2018)",
     "Reviewed how thermal runaway starts and spreads through a chain of heat-producing reactions inside the cell.",
     "Explains reaction physics, but does not give an on-board method to detect it early."],
    ["[2]", "Battery management system: An overview of its application in the smart grid and electric vehicles (Rahimi-Eichi et al., 2013)",
     "Showed that a BMS needs accurate state estimation and ways to protect the battery from hazardous conditions.",
     "Focuses on state-of-charge and state-of-health estimation, not on early thermal warning."],
    ["[3]", "Protection devices in commercial 18650 lithium-ion batteries (Xu et al., 2021)",
     "Opened four commercial 18650 cells. Only current interrupt device (CID) and top vent are fitted in every cell.",
     "These are destructive last-resort devices. Pack-level monitoring and early warning are not covered."],
    ["[4]", "Advanced fault diagnosis for lithium-ion battery systems: A review of fault mechanisms (Hu et al., 2020)",
     "Reviewed internal battery faults, sensor faults and actuator faults, and how each one can be diagnosed.",
     "A comprehensive review only. It does not build or test a low-cost embedded diagnostic system."],
    ["[5]", "A critical review of thermal runaway prediction and early-warning methods (Zhang et al., 2023)",
     "Grouped early-warning methods into electrochemistry-based, big-data and artificial intelligence methods.",
     "Existing methods rely on complex electrochemical models, massive datasets, or heavy AI training."],
]

LITERATURE_2 = [
    ["[6]", "An online data-driven fault diagnosis and thermal runaway early warning for electric vehicle batteries (Sun et al., 2022)",
     "Found the cell heading for thermal runaway before it happened, using voltage and temperature data from real vehicles.",
     "Compares many cells statistically in large EV packs; unsuitable for standalone small packs."],
    ["[7]*", "BASE PAPER: A neural network based method for thermal fault detection in lithium-ion batteries (Ojo et al., IEEE TIE, 2021)",
     "LSTM neural network predicts surface temperature 4.5 s ahead; flags gaps > 0.69 °C as thermal runaway precursor.",
     "Requires 65 min GPU training, retraining as cell ages; blind to slow faults (< 9.2 °C/min); 0.5% false alarms (~36/hr)."],
    ["[8]", "A combined data-driven and model-based algorithm for accurate battery thermal runaway warning (Chen et al., 2024)",
     "Combined K-Means clustering with the Bernardi heat equation and warned 25 minutes before thermal runaway.",
     "Its 1 °C/s limit confirms runaway after initiation; it is not an early preventative warning."],
    ["[9]", "Online parameterization of lumped thermal dynamics in cylindrical lithium ion batteries (Lin et al., 2013)",
     "Showed that only surface temperature can be measured while core is hotter, and estimated core temperature.",
     "Needs complex online parameter identification, and was tested on one 26650 cell, not a 4S pack."],
    ["[10]", "Cloud-based battery condition monitoring platform for large-scale BESS using IoT (Adhikaree et al., 2017)",
     "Sent battery module data over IoT links to Google Cloud, where cell states were evaluated.",
     "Depends strictly on the cloud and network. Protection must keep working even when Wi-Fi is lost."],
]

REFERENCES_1 = [
    "X. Feng, M. Ouyang, X. Liu, L. Lu, Y. Xia, and X. He, “Thermal runaway mechanism of lithium ion battery for electric vehicles: A review,” Energy Storage Mater., vol. 10, pp. 246–267, Jan. 2018.",
    "H. Rahimi-Eichi, U. Ojha, F. Baronti, and M.-Y. Chow, “Battery management system: An overview of its application in the smart grid and electric vehicles,” IEEE Ind. Electron. Mag., vol. 7, no. 2, pp. 4–16, Jun. 2013.",
    "J. Xu, C. Shen, T. Wang, and Z. Hao, “Protection devices in commercial 18650 lithium-ion batteries,” J. Energy Storage, vol. 38, p. 102570, Jun. 2021.",
    "X. Hu, K. Zhang, K. Liu, X. Lin, S. Dey, and S. Onori, “Advanced fault diagnosis for lithium-ion battery systems: A review of fault mechanisms, fault features, and diagnosis procedures,” IEEE Ind. Electron. Mag., vol. 14, no. 3, pp. 65–91, Sep. 2020.",
    "G. Zhang, H. Sheng, H. Lang, and Y. Wang, “A critical review of thermal runaway prediction and early-warning methods for lithium-ion batteries,” Renewable Sustainable Energy Rev., vol. 182, p. 113379, Aug. 2023.",
]

REFERENCES_2 = [
    "Z. Sun et al., “An online data-driven fault diagnosis and thermal runaway early warning for electric vehicle batteries,” IEEE Trans. Power Electron., vol. 37, no. 10, pp. 12636–12646, Oct. 2022.",
    "O. Ojo, H. Lang, Y. Kim, X. Hu, B. Mu, and X. Lin, “A neural network based method for thermal fault detection in lithium-ion batteries,” IEEE Trans. Ind. Electron., vol. 68, no. 5, pp. 4068–4078, May 2021. (Base Paper)",
    "Q. Chen, Y. He, N. Fang, and G. Yu, “A combined data-driven and model-based algorithm for accurate battery thermal runaway warning,” Sensors, vol. 24, no. 15, Art. no. 4964, Jul. 2024.",
    "X. Lin et al., “Online parameterization of lumped thermal dynamics in cylindrical lithium ion batteries for core temperature estimation and health monitoring,” IEEE Trans. Control Syst. Technol., vol. 21, no. 5, pp. 1745–1755, Sep. 2013.",
    "N. Adhikaree, T. Kim, J. Vagdoda, A. Ochoa, P. J. Hernandez, and Y. Lee, “Cloud-based battery condition monitoring platform for large-scale BESS using IoT,” in Proc. IEEE IECON, 2017, pp. 1004–1009.",
    "L. Torres-Castro, A. M. Bates, N. B. Johnson, G. Quintana, and L. Gray, “Early detection of Li-ion battery thermal runaway using commercial diagnostic technologies,” J. Electrochem. Soc., vol. 171, no. 2, Art. no. 020520, Feb. 2024.",
]


def get_board_b_pics():
    """Find any user-provided photos in pics/ directory, else empty list."""
    valid_exts = (".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG")
    found = []
    if os.path.exists(PICS_DIR):
        for f in sorted(os.listdir(PICS_DIR)):
            if f.endswith(valid_exts):
                found.append(os.path.join(PICS_DIR, f))
    return found


def build():
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    n = 1

    # 1. Title Slide
    title_slide(prs, n, """
Good morning respected committee members and my guide Dr. M. Rupesh.
I am Muskan Sulathana (Roll No: 23WH1A0208), presenting my Major Project Stage-1 Review-2
on the 'Predictive Thermal Battery Management System for Li-ion Battery Packs'.
"""); n += 1

    # 2. Contents
    content_slide(prs, n, "Contents", [
        "1.  Abstract & Problem Statement",
        "2.  Literature Survey & Base Paper Identification",
        "3.  Problem Analysis, Research Gap & Objectives",
        "4.  Methodology & Safety Algorithm Flowchart",
        "5.  System Architecture & Block Diagram",
        "6.  Mathematical Formulation: Two-Node Thermal Model",
        "7.  KiCad Circuit Simulation Model",
        "8.  KiCad Transient Simulation Results",
        "9.  Dynamic Defect Simulation & 5-Min Forecast",
        "10. Performance Comparison: Predictive BMS vs Fixed BMS",
        "11. Hardware Implementation: Board A (Cell Taps)",
        "12. Hardware Implementation: Board B (Supervisor Bring-Up)",
        "13. Live ESP32 Web Dashboard & Telemetry",
        "14. Conclusion, Project Timeline & References",
    ], """
Here is the outline of my Stage-1 Review-2 presentation. We will cover the foundation,
the literature survey and base paper, system architecture, KiCad simulation results,
and our hardware prototype and live dashboard demonstration.
""", size=15); n += 1

    # 3. Abstract
    content_slide(prs, n, "Abstract", [
        "Lithium-ion cells offer high energy density but suffer catastrophic thermal runaway under internal defects, dendrite formation, overcharging, and soft micro-shorts.",
        "Conventional BMS boards rely solely on fixed passive thresholds (e.g., 55 °C surface limit). They act reactively after the outer can is already hot, cannot detect uncooled core heat, and are completely blind to faults at zero current.",
        "This project develops an autonomous, predictive, dual-layer battery management system for a 4S1P Panasonic NCR18650GA Li-ion pack:",
        "    • Layer A (Hardware BMS): Autonomous, non-programmable backstop for primary short-circuit and cell over/under-voltage protection.",
        "    • Layer B (Predictive Supervisor): ESP32 MCU running a 2-node lumped-parameter thermal observer and discrete Kalman filter at 5 Hz.",
        "Key Engineering Advantages:",
        "    • Physics-based estimation running directly on a low-cost $4 microcontroller without GPU/cloud dependency.",
        "    • Detects abnormal heat generation (Q_ab in Watts) down to 0.2 W, isolating core faults before external heating.",
        "    • Provides 5-minute thermal forecasting and autonomous relay contactor disconnection, acting 5.0 minutes earlier and keeping cells 27.1 °C cooler.",
    ], """
This abstract summarizes our core innovation: replacing reactive fixed limits
with a real-time, physics-based Kalman observer running directly on an embedded ESP32.
It operates 5.0 minutes earlier than conventional BMS, ensuring true preventative protection.
""", size=14); n += 1

    # 4. Problem Statement
    content_slide(prs, n, "Problem Statement", [
        "Thermal runaway in Li-ion cells initiates inside the electrode jellyroll via internal defects, dendrites, or local micro-shorts before surface temperature rises.",
        "Critical Vulnerabilities of Existing Battery Management Systems:",
        "    1. Fixed Reactive Thresholds: Intervene only after surface exceeds 55 °C or 60 °C—by then, internal exothermic chain reactions are already self-sustaining.",
        "    2. Core Thermal Blindspot: Surface NTCs lag core temperature by several degrees during dynamic discharge; internal runaway begins at the core.",
        "    3. Zero-Current Rest Blindspot: When pack current is zero (vehicle parked / charging paused), conventional BMS cannot detect internal leakage heating.",
        "    4. Deep-Learning Limitations: Research algorithms (like our base paper) use heavy LSTM networks requiring GPU training, retraining as cells age, and cannot run on cheap microcontrollers.",
        "Need: An on-board, embedded, physics-based observer that isolates abnormal fault heat in Watts and acts preventatively before runaway becomes unstoppable.",
    ], """
The fundamental problem in battery safety is that conventional BMS units are purely reactive.
By the time an external surface thermistor reaches 55 °C, internal chemical decomposition is
already self-accelerating. We need an observer that estimates internal heat in Watts.
""", size=14); n += 1

    # 5. Literature Survey 1
    table_slide(prs, n, "Literature Survey", LIT_HEAD, LITERATURE_1, """
Here is Part 1 of our literature survey covering thermal runaway mechanisms, BMS overviews,
commercial 18650 safety devices, fault diagnosis taxonomies, and early-warning reviews.
""", LIT_W, size=13, row_h=0.74, head_size=14, aligns=["c", "l", "l", "l"]); n += 1

    # 6. Literature Survey 2 (with Base Paper highlighted)
    table_slide(prs, n, "Literature Survey (contd.)", LIT_HEAD, LITERATURE_2, """
Part 2 covers online EV fault diagnostics, our Base Paper by Ojo et al. in IEEE TIE 2021,
model-based warning methods, online parameter identification, and cloud architectures.
Paper [7] is our designated Base Paper.
""", LIT_W, size=13, row_h=0.74, head_size=14, aligns=["c", "l", "l", "l"],
        legend=["* Designated Base Paper of this project (IEEE Trans. Ind. Electron., 2021)"]); n += 1

    # 7. Problem Analysis & Research Gap
    two_section_slide(prs, n,
        "Problem Analysis", [
            "Internal heat generation (I²R + Q_ab) drives thermal runaway inside the electrode assembly.",
            "Surface temperature lags core temperature by several minutes due to internal thermal resistance (R_core = 2.0 °C/W).",
            "Fixed threshold protection (55 °C) provides zero early-warning time; once exothermic reactions start, disconnecting current cannot quench runaway.",
            "Incipient internal micro-shorts generate very small heat powers (0.03 W to 0.29 W) that take tens of minutes to warm the cell, easily missed by short-window detectors.",
        ],
        "Research Gap", [
            "Need for a lightweight, physics-based thermal observer executable on a low-cost microcontroller (ESP32) at 5 Hz without GPU/cloud dependency.",
            "Need for abnormal heat (Q_ab) isolation in physical Watts to detect micro-faults even when the pack is at zero-current rest.",
            "Need for dual-layer safety: an independent, non-programmable hardware BMS backed by a predictive software supervisor with separate charge/load disconnects.",
        ], """
On this slide, we contrast the thermal physics with the research gaps identified in our survey.
The critical gap is the lack of an embedded, low-cost observer that isolates abnormal heat in Watts.
""", size=15); n += 1

    # 8. Objectives
    content_slide(prs, n, "Objectives of the Project", [
        "1. To formulate and validate a lumped-parameter two-node electro-thermal model capturing core and surface dynamics of 18650 Li-ion cells.",
        "2. To design an autonomous dual-layer safety architecture: an independent hardware BMS (Layer A) backed by an ESP32 supervisor (Layer B) with directional load and charge disconnects.",
        "3. To implement high-resolution analog front-end sensing: 16-bit individual cell voltages (ADS1115), pack current (ACS712 / INA226), and five NTC thermistors.",
        "4. To formulate and execute a real-time discrete Kalman filter at 5 Hz to estimate core temperature (T_core) and isolate abnormal fault heat (Q_ab) in Watts, latching trips in flash.",
        "5. To validate the system through KiCad 10 circuit simulations, automated safety testbenches, and prototype hardware bring-up.",
    ], """
Our five objectives map directly to the work executed for Stage-1. Objectives 1 and 2 established the
system architecture, while Objectives 3, 4, and 5 cover mathematical modeling, firmware,
hardware construction, and verification.
""", size=15); n += 1

    # 9. Methodology & Safety Algorithm Flowchart
    wide_image_slide(prs, n, "Methodology & Safety Algorithm Flowchart",
        "firmware_flow.png", [
            "Deterministic 5 Hz Safety Cycle: FreeRTOS safety task executes precisely every 200 ms.",
            "3-Stage Signal Conditioning: 5-sample median filter rejects spikes; 10 s LPF removes noise; 30 s regression computes dT/dt.",
            "Kalman State Observer: Estimates core temperature and isolates abnormal defect heat Q_ab in Watts.",
            "Graduated Safety Actuation: Normal -> Watch -> Warning (1 Hz buzzer) -> Latched Trip (relays open, logged to flash).",
        ], """
This flowchart shows the 5 Hz firmware safety loop. In each 200 ms step, raw sensor signals are
calibrated, median-filtered, fed into the Kalman observer, and evaluated against safety rules.
Wi-Fi telemetry runs strictly out-of-band and cannot block safety execution.
""", img_h=3.20, bullet_size=13, caption="Figure: FreeRTOS 5 Hz deterministic safety pipeline and graduated protection state machine",
        two_cols=True); n += 1

    # 10. System Architecture & Block Diagram
    image_and_text_slide(prs, n, "System Architecture & Block Diagram",
        "system_architecture.png", [
            "Welded 4S1P Cell Pack: Panasonic NCR18650GA (14.4 V nom, 16.8 V max, 3.3 Ah / 47.5 Wh) with cell NTC thermistors.",
            "Layer A (Hardware Safety BMS): Direct cell connection providing non-programmable OV (4.25 V), UV (2.70 V), OCD, SCD, and passive balancing.",
            "Primary Pack Fuse: 7.5 A fast blade fuse directly at positive exit terminal for ultimate short-circuit protection.",
            "Board A (Cell Taps): Conditions cell voltages via 330k/56k dividers and 10k/100nF RC filters into ADS1115 16-bit ADC.",
            "Board B (Supervisor): ESP32 running 5 Hz Kalman observer; monitors current via ACS712 / INA226 Kelvin shunt.",
            "Fail-Safe Contactor Disconnects: Normally-open K_LOAD and K_CHARGE relays in negative return (P-); hardware pull-ups ensure open on power loss.",
            "Isolated Auxiliary Power: LM2596 buck converter (5.0 V) tapped before current sensor so MCU draw is excluded from rest monitoring.",
        ], """
Here is our system block diagram. By tapping the LM2596 auxiliary supply before the current sensor,
we ensure the supervisor measures true battery rest current, which is critical for detecting self-discharge leakage.
Layer A acts as a hardware backstop, while Layer B provides predictive software supervision.
""", img_w_frac=0.54, bullet_size=13); n += 1

    # 11. Mathematical Formulation: Two-Node Thermal Model
    content_slide(prs, n, "Mathematical Formulation: Thermal Model", [
        "A lumped-parameter two-node electro-thermal circuit models core and surface dynamics:",
        "Core Node Differential Equation:",
        "    C_core · (d T_core / dt) = I² R_int + Q_ab − (T_core − T_surf) / R_core",
        "Surface Node Differential Equation:",
        "    C_surf · (d T_surf / dt) = (T_core − T_surf) / R_core − (T_surf − T_amb) / R_air",
        "Physical Model Parameters (for 18650 3.3 Ah cell):",
        "    • C_core = 40.0 J/°C,  C_surf = 5.0 J/°C  (Thermal capacities)",
        "    • R_core = 2.0 °C/W  (Internal conduction resistance from core to can)",
        "    • R_air = 30.0 °C/W  (Convection resistance from can surface to ambient air)",
        "    • I² R_int: Known electrical Joule heating (R_int ≈ 35 mΩ nominal)",
        "    • Q_ab: Unknown abnormal fault heat generation in Watts (internal micro-short, defect).",
        "Hierarchical Protection Action:",
        "    • Level 0 (Normal): Q_ab < 0.25 W  |  Level 1 (Watch): 0.25 W ≤ Q_ab < 0.38 W",
        "    • Level 2 (Warning): Q_ab ≥ 0.38 W for 30 s  |  Level 3 (Trip): Q_ab ≥ 0.75 W for 10 s or T_core > 60 °C",
    ], """
Here is our thermal model. Heat is generated in the core via known Joule heating I²R plus
any abnormal fault heat Q_ab. Heat conducts from the core to the surface across R_core,
and convects into ambient air across R_air.
""", size=14); n += 1

    # 12. KiCad Circuit Simulation Model
    image_and_text_slide(prs, n, "KiCad Circuit Simulation Model",
        "kicad_thermal_model.png", [
            "Thermal Model Mapped to KiCad Circuit Domain: 1 V = 1 °C, 1 A = 1 W, 1 F = 1 J/°C, 1 Ω = 1 °C/W.",
            "Core Thermal Capacitor: C_core = 40.0 F, representing internal heat capacity of cell jellyroll.",
            "Surface Thermal Capacitor: C_surf = 5.0 F, representing steel can thermal capacity.",
            "Conduction Resistor: R_core = 2.0 Ω, modeling internal core-to-surface heat conduction.",
            "Convection Resistor: R_air = 30.0 Ω, modeling natural convection from can to ambient air.",
            "Transient Stimulus: 1.0 W pulsed heat injection (current source I1) in cell core from t = 10 s.",
            "SPICE Simulation Setup: KiCad 10 / ngspice .tran 1 3600 analysis validates transient and steady-state thermal behavior.",
        ], """
In KiCad 10, we modeled the thermal equations as an equivalent electrical network.
Capacitors represent thermal masses and resistors represent thermal resistances.
The transient SPICE simulation confirms our thermal time constant of 22.5 minutes.
""", img_w_frac=0.55, bullet_size=13, caption="Figure: KiCad 10 schematic of the two-node electro-thermal equivalent circuit"); n += 1

    # 13. KiCad Transient Simulation Results
    image_and_text_slide(prs, n, "KiCad Transient Simulation Results",
        "sim_thermal.png", [
            "Transient Temperature Response: 1.0 W heat step injected at t = 0 with ambient temperature at 25.0 °C.",
            "Core Temperature Dynamics: Core temperature rises immediately to 27.0 °C due to internal thermal resistance R_core (2.0 °C/W).",
            "Surface Temperature Dynamics: Surface temperature lags by several minutes, governed by thermal conduction and convection delay.",
            "Steady-State Verification: Surface settles at ΔT = Q × R_air = 1 W × 30 °C/W = 30 °C above ambient (55.0 °C total).",
            "Core Steady-State: Core settles at ΔT = Q × (R_core + R_air) = 1 W × 32 °C/W = 32 °C above ambient (57.0 °C total).",
            "Thermal Time Constant: Measured τ = 1350 s (22.5 min), confirming theoretical lumped capacitance calculations.",
        ], """
This slide shows the transient simulation results from KiCad / ngspice. A 1 Watt heat input produces
an immediate core rise and a delayed surface rise settling at 30 °C above ambient.
This validates our state transition model used in firmware.
""", img_w_frac=0.55, bullet_size=13, caption="Figure: KiCad / ngspice transient thermal step response: Core (red) and Surface (green) waveforms"); n += 1

    # 14. Dynamic Defect Simulation & 5-Min Forecast
    wide_image_slide(prs, n, "Dynamic Defect Simulation & 5-Min Forecast",
        "defect-charts.png", [
            "Fault Injection Scenario: 3.0 A pack discharge combined with a 1.5 W internal defect injected into Cell 2.",
            "Core Divergence: Cell 2 core climbs rapidly to 31.8 °C while surface lags at 28.1 °C.",
            "Predictive Trip: Observer detects Q_ab crossing 0.75 W; triggers Level 3 Trip at t = 112 s (surface at only 28.1 °C).",
            "5-Minute Forecast Accuracy: RMS forecast error across cells 1–4 is 0.11 °C to 0.12 °C (well within < 0.5 °C qualification limit).",
        ], """
Here we inject an internal defect generating 1.5 W inside Cell 2 under 3 A load.
The observer detects the abnormal heat and opens both contactor relays at t = 112 seconds,
when the cell surface is only 28.1 °C. The 5-minute forecast predicts temperature within 0.12 °C RMS error.
""", img_h=3.20, bullet_size=13, caption="Figure: Defect simulation telemetry: Cell 2 core overheating, Q_ab rising to 1.5 W, and predictive contactor trip",
        two_cols=True); n += 1

    # 15. Performance Comparison: Predictive vs Fixed BMS
    wide_image_slide(prs, n, "Performance Comparison: Predictive vs Fixed BMS",
        "defect-compare.png", [
            "Intervention Timing: Predictive BMS trips contactors at 112 s vs 408 s (6.8 min) for conventional BMS (acts 5.0 min earlier!).",
            "Thermal Suppression: Hottest cell reaches only 28.1 °C under predictive protection vs 55.2 °C for conventional BMS (27.1 °C cooler!).",
            "Mechanism: Predictive observer acts on abnormal heat rate (Watts), whereas conventional BMS waits for outer can to reach 55 °C.",
            "Zero-Current Rest Advantage: Detects 1.0 W micro-short in 58 seconds even when current is zero (conventional BMS is completely blind).",
        ], """
This comparison is our most important performance result: our predictive BMS acts 5.0 minutes
earlier and keeps the cell 27.1 °C cooler than a conventional fixed-threshold BMS.
This prevents the cell from ever entering exothermic chemical decomposition.
""", img_h=3.20, bullet_size=13, caption="Figure: Side-by-side run comparison: Predictive BMS (trip at 112 s, 28.1 °C) vs Fixed-Limit BMS (trip at 408 s, 55.2 °C)",
        two_cols=True); n += 1

    # 16. Hardware: Board A
    image_and_text_slide(prs, n, "Hardware Implementation: Board A (Cell Taps)",
        "circuit_taps.png", [
            "Function: Conditions and filters four series cell tap voltages (B1, B2, B3, B+).",
            "Precision Resistor Dividers: Four 330 kΩ over 56 kΩ 1% metal-film networks attenuate 16.8 V pack to 2.44 V for ADC range.",
            "Low-Pass RC Filtering: 10 kΩ series resistor + 100 nF ceramic capacitor suppress switching noise (fc = 27.5 Hz).",
            "ADS1115 ADC: 16-bit delta-sigma converter over I2C (0x48) provides 125 µV LSB resolution for precision rest-leak tracking.",
            "Safety Grounding Isolation: J1 pin 1 (B-) left unconnected; prevents thin sense wire from carrying high pack load current.",
            "Assembly Status: Board A perfboard fully assembled, soldered, and bench verified across all 4 channels.",
        ], """
Turning to hardware: Board A conditions the four cell tap voltages. High-impedance 330k/56k
dividers scale 16.8 V down to 2.44 V, while 10k/100nF RC filters suppress noise. The ADS1115
gives 16-bit resolution, which is essential for tracking small self-discharge leaks.
""", img_w_frac=0.52, bullet_size=13, caption="Figure: Board A cell-tap conditioning schematic with 330k/56k dividers and ADS1115 ADC"); n += 1

    # 17. Hardware: Board B
    board_b_pics = get_board_b_pics()
    board_b_bullets = [
        "Microcontroller: ESP32-WROOM-32 DevKit running FreeRTOS with ADC1 dedicated to five NTC thermistors (10k B3950).",
        "Current Sensing Fallback: ACS712-5A Hall-effect module wired on ADC1_CH3 (GPIO39/VN); firmware auto-detects and runs telemetry.",
        "Seamless INA226 Revertibility: Plug-in I2C header J8 wired; firmware automatically prioritizes INA226 over I2C once installed.",
        "Relay Contactor Control: Two-channel 5 V relay module switching negative return lines (P-); hardware pull-ups ensure open fail-safe.",
        "Audio/Visual Alarm: Piezo buzzer and status LED on GPIO27 (pulsing at 1 Hz for Warning; steady on for latched Trip).",
        "Status & Work Done: Board B perfboard assembly & wiring actively in progress; firmware tested and verified live on ESP32.",
    ]
    board_b_note = """
Board B hosts the ESP32 supervisor, current sensing, relay controls, and thermistor conditioning.
To enable immediate prototype validation, we wired the ACS712 Hall-effect sensor on GPIO39.
The perfboard wiring is currently underway, and the firmware has been verified live on the ESP32.
"""
    if len(board_b_pics) >= 2:
        two_image_slide(prs, n, "Hardware Implementation: Board B (Supervisor Bring-Up)",
            board_b_pics[0], board_b_pics[1],
            "Board B Perfboard Construction (Work Done)", "Component Wiring & Subsystem Connections",
            board_b_note, bullets=board_b_bullets[:4], bullet_size=13)
    elif len(board_b_pics) == 1:
        image_and_text_slide(prs, n, "Hardware Implementation: Board B (Supervisor Bring-Up)",
            board_b_pics[0], board_b_bullets, board_b_note,
            caption="Figure: Board B perfboard assembly and wiring progress",
            img_w_frac=0.52, bullet_size=13)
    else:
        image_and_text_slide(prs, n, "Hardware Implementation: Board B (Supervisor Bring-Up)",
            "circuit_acs712.png", board_b_bullets, board_b_note,
            caption="Figure: Board B supervisor architecture with ACS712 current sensing fallback",
            img_w_frac=0.52, bullet_size=13)
    n += 1

    # 18. Live ESP32 Web Dashboard
    image_and_text_slide(prs, n, "Live ESP32 Web Dashboard & Telemetry",
        "esp32_dashboard_live.png", [
            "Embedded Web Server: ESP32 broadcasts Wi-Fi Access Point ('PredictiveBMS') and serves live HTML5 responsive dashboard.",
            "Fail-Safe Safety Banner: Red top status bar explicitly indicates: 'CURRENT / VOLTAGE IS NOT SENSED · BATTERY IS DISCONNECTED'.",
            "Relay Contactor Status: Visual contactor indicators render in OPEN state, guaranteeing fail-safe isolation during bring-up.",
            "Real-Time Telemetry: 4S individual cell voltage cards, pack current, ambient/cell temperatures, and estimated thermal power.",
            "Air-Gapped Telemetry: HTTP server runs in low-priority FreeRTOS task, completely decoupled from the 5 Hz safety loop.",
        ], """
Here is the live snapshot of our ESP32 web dashboard. The red banner clearly alerts that the battery
is disconnected and sensors are unattached during bring-up, while contactors remain fail-safe open.
This dashboard runs directly from the ESP32 over its own Wi-Fi Access Point.
""", img_w_frac=0.54, bullet_size=13, caption="Figure: Live ESP32 web dashboard snapshot showing active Wi-Fi telemetry and fail-safe disconnect banner"); n += 1

    # 19. Conclusion & Current Progress
    content_slide(prs, n, "Conclusion & Current Project Status", [
        "Stage-1 Milestones Successfully Achieved:",
        "    • Mathematical Formulation: Two-node lumped electro-thermal model and discrete Kalman observer formulated and validated.",
        "    • Simulation Verification: KiCad 10 / ngspice circuit simulations completed; 30-scenario automated testbench passed (100% pass).",
        "    • Predictive Advantage Proved: Acts 5.0 minutes earlier and keeps cells 27.1 °C cooler than conventional fixed-threshold BMS.",
        "    • Embedded Firmware: Production C++17 FreeRTOS firmware built, flashed to ESP32 hardware, and executing 5 Hz safety cycle.",
        "    • Live Web Dashboard: Operational over Wi-Fi AP with fail-safe status indicators and real-time telemetry.",
        "    • Board A (Cell Taps): 100% constructed, soldered, calibrated, and verified on bench.",
        "Current Work (In Progress):",
        "    • Board B (Supervisor): Perfboard wiring in progress with ACS712 current sensor fallback.",
        "Stage-2 Plan:",
        "    • Complete Board B wiring, connect 4S1P cell pack with Layer A hardware BMS, and conduct pack thermal chamber tests.",
    ], """
To conclude, Stage-1 has met all its core milestones: the mathematical formulation is proven,
circuit simulations and testbenches are verified, the firmware is live on ESP32, and Board A is fully constructed.
Board B assembly is currently underway for final Stage-2 pack testing.
""", size=14); n += 1

    # 20. Project Timeline
    table_slide(prs, n, "Project Timeline",
        ["Activity / Milestone", "Month 1", "Month 2", "Month 3", "Month 4", "Month 5"],
        [[{"b": "Milestone 1: ", "t": "Literature Survey & Base Paper Study"}, "✓", "✓", "", "", ""],
         [{"b": "Milestone 2: ", "t": "System Architecture & Dual-Layer Safety Design"}, "✗", "✓", "", "", ""],
         [{"b": "Milestone 3: ", "t": "Mathematical Modeling & KiCad Simulation"}, "✗", "✗", "✓", "", ""],
         [{"b": "Milestone 4: ", "t": "Hardware Prototype: Board A & Board B Bring-Up"}, "✗", "✗", "✓", "In Progress", ""],
         [{"b": "Milestone 5: ", "t": "4S Pack Testing, Enclosure & Final Viva"}, "✗", "✗", "", "", "Planned"]],
        """
Here is our project timeline. Milestones 1, 2, and 3 are fully completed. Milestone 4 is
currently in progress with Board A completed and Board B bring-up underway, and Milestone 5
is planned for Stage-2.
""", [3.80, 1.10, 1.10, 1.10, 1.10, 1.10], size=15, row_h=0.74,
        aligns=["l", "c", "c", "c", "c", "c"],
        legend=["✓ = Completed", "In Progress = Current Stage (Board A Done; Board B in Progress)", "Planned = Stage-2 Work"]); n += 1

    # 21. References 1
    content_slide(prs, n, "References", REFERENCES_1, """
Here are references 1 through 5, formatted according to IEEE standards.
""", size=13, numbered=True); n += 1

    # 22. References 2
    refs = content_slide(prs, n, "References (contd.)", REFERENCES_2, """
Here are references 6 through 11, completing our literature foundation and highlighting our base paper.
""", size=13, numbered=True)
    for i, p in enumerate([s for s in refs.shapes if s.has_text_frame][-1].text_frame.paragraphs):
        p.runs[0].text = "[%d]  " % (i + 6)
    n += 1

    # 23. Thank You
    closing_slide(prs, n); n += 1

    prs.save(PPTX_OUT)
    print("saved %s (%d slides)" % (os.path.basename(PPTX_OUT), len(prs.slides._sldIdLst)))
    if WARNINGS:
        print("\noverflow warnings:")
        for w in WARNINGS:
            print("   !!", w)
    else:
        print("no overflow warnings")

    # Export to PDF via LibreOffice
    print("exporting to PDF via LibreOffice...")
    cmd = [
        "libreoffice",
        "-env:UserInstallation=file:///tmp/libreoffice_user",
        "--headless",
        "--convert-to", "pdf",
        PPTX_OUT,
        "--outdir", HERE,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0 and os.path.exists(PDF_OUT):
        print("saved %s" % os.path.basename(PDF_OUT))
    else:
        print("LibreOffice export failed:", res.stderr)

    # Mirror to docs/build-guide/ if directory exists
    if os.path.exists(BUILD_GUIDE_DIR):
        for fname in ["Predictive_BMS_Stage1_Review2.pptx", "Predictive_BMS_Stage1_Review2.pdf"]:
            src = os.path.join(HERE, fname)
            dst = os.path.join(BUILD_GUIDE_DIR, fname)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                print("mirrored to %s" % dst)


if __name__ == "__main__":
    build()
