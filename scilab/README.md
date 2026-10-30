# Xcos models in Scilab

Xcos is the block-diagram tool of Scilab. It does the same job as Simulink in MATLAB. Scilab is
free and open source. These two models show the predictive layer as block diagrams.

| File | What it shows |
| --- | --- |
| `cell_thermal_model.zcos` | The thermal model of one cell (architecture section 9.1). 1 W of heat starts in the core at t = 10 s. The scope shows the core and surface temperatures for one hour. |
| `abnormal_heat_detection.zcos` | A cell carries 3 A, so it makes Joule heat (I² R), which the supervisor knows. At 10 minutes, 1 W of extra heat starts: a fault the supervisor does not know about. An observer (the Kalman filter of section 9.2) estimates this abnormal heat from the surface temperature. A predictive trip happens when the estimate reaches 0.75 W. A fixed-limit trip happens when the surface reaches 55 °C. |

The values are in the model's context: in Xcos, **Simulation → Set Context**. The thermal values
are the firmware's development values; Gate 9 replaces them with values measured on the real
cells.

## Install Scilab

Download Scilab 2027.0.0 from <https://www.scilab.org/download> and install it with the default
choices. On Windows this is `scilab-2027.0.0.bin.x64.exe`.

## Run a model

1. Double-click the `.zcos` file. Xcos opens with the diagram. (Or start Scilab, then
   **Applications → Xcos**, then **File → Open**.)
2. Click **Start**, the black triangle ▶ in the toolbar, or **Simulation → Start**.
3. A scope window opens and draws the results. The model simulates one hour; this takes a few
   seconds.

In `abnormal_heat_detection.zcos` the scope has three graphs:

- top: the true core temperature (red), the surface temperature (blue) and the core
  temperature that the observer estimates (black);
- middle: the true abnormal heat (green) and the estimate (red);
- bottom: the predictive trip (black) and the fixed-limit trip (green). 1 means tripped.

## Results

These are simulation results with the development values.

- `cell_thermal_model.zcos`: one hour after the heat starts, the core is at 54.46 °C and the
  surface at 52.60 °C. KiCad's simulator (ngspice) and GNU Octave give the same numbers, within
  0.004 °C.
- `abnormal_heat_detection.zcos`: the predictive trip comes 117 s after the fault starts, with the
  surface at 30.9 °C. The fixed 55 °C limit trips 1918 s (32 minutes) after the fault starts.
  The estimate settles at 1.00 W, the true value, and stays at zero before the fault: no false
  alarm.

The model has no sensor noise, and the firmware also waits 10 s before it trips (section 9.8).
The project's own simulator (section 15 of the build guide) runs the complete firmware, with
noise and every other check.

## For the developer: make, check and draw

From this folder, in Scilab:

- `exec("make_models.sce", -1)` writes both `.zcos` files.
- `exec("check_models.sce", -1)` simulates both without a window and checks the results. From a
  command line: `scilab-cli -nb -quit -f check_models.sce` (exit code 1 when a check fails). It
  writes `../build/scilab/`.
- `exec("render_pictures.sce", -1)` draws both diagrams for the build guide. It opens Xcos for a
  few seconds.
- `python3 make_charts.py` (from a terminal) draws the charts for the build guide from
  `../build/scilab/`.
