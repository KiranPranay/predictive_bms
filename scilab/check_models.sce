// Simulates both Xcos models without opening any window and checks the results.
//
//   In Scilab, from this folder:   exec("check_models.sce", -1)
//   From a command line:           scilab-cli -nb -quit -f check_models.sce
//
// It writes results.json and the two time series (model_a.csv, model_b.csv) to
// build/scilab/ beside this folder, prints every check, and ends with exit code 1 when a
// check fails (when it is run from a command line).

loadXcosLibs();
loadScicos();
here = get_absolute_file_path("check_models.sce");
out = here + "../build/scilab/";
mkdir(here + "../build");
mkdir(out);
failed = 0;
checks = [];

function [failed, checks] = check(failed, checks, name, value, ok, limit)
    if ok then
        word = "PASS"; js = "true";
    else
        word = "FAIL"; js = "false";
        failed = failed + 1;
    end
    mprintf("%s  %s = %s (%s)\n", word, name, string(value), limit);
    checks($+1) = msprintf("{""check"": ""%s"", ""value"": %s, ""limit"": ""%s"", ""pass"": %s}", ..
                           name, string(value), limit, js);
endfunction

// --- Model A: the thermal model, 1 W step at t = 10 s -----------------------------------

importXcosDiagram(here + "cell_thermal_model.zcos");
Info = scicos_simulate(scs_m, list(), "nw");
t = xcos_thermal.time;
x = xcos_thermal.values;   // columns: T_core, T_surf
// The same model in KiCad/ngspice (kicad/sim/thermal-model) and in GNU Octave
// (matlab/thermal_step.m): 60, 300, 1200 and 3600 s after the step.
ref = [60, 26.3428, 26.0682; 300, 31.1053, 30.5625; 1200, 43.2515, 42.0252; 3600, 54.4588, 52.6018];
worst = 0;
for k = 1:size(ref, 1)
    i = find(abs(t - (ref(k, 1) + 10)) < 1e-6);
    worst = max(worst, max(abs(x(i, :) - ref(k, 2:3))));
end
[failed, checks] = check(failed, checks, "model A: largest difference from ngspice and Octave (degC)", ..
                         round(worst * 1e4) / 1e4, worst < 0.01, "< 0.01");
i60 = find(abs(t - 3610) < 1e-6);
[failed, checks] = check(failed, checks, "model A: core temperature 1 h after the step (degC)", ..
                         round(x(i60, 1) * 100) / 100, abs(x(i60, 1) - 54.4588) < 0.01, "54.46 in ngspice");
csvWrite([t, x], out + "model_a.csv", ",", ".", "%.5f");

// --- Model B: abnormal heat detection ----------------------------------------------------

importXcosDiagram(here + "abnormal_heat_detection.zcos");
Info = scicos_simulate(scs_m, list(), "nw");
t = xcos_temps.time;
temps = xcos_temps.values;   // true core, surface, estimated core
heat = xcos_heat.values;     // true abnormal heat, estimated abnormal heat
trips = xcos_trips.values;   // predictive trip, fixed-limit trip
t_fault = 600;
before = find(t < t_fault);
watch = max(heat(before, 2));
[failed, checks] = check(failed, checks, "model B: largest estimated abnormal heat before the fault (W)", ..
                         round(watch * 1000) / 1000, watch < 0.375, "< 0.375, the Warning level: no false alarm");
ip = find(trips(:, 1) > 0.5, 1);
ifx = find(trips(:, 2) > 0.5, 1);
if ip == [] then
    tp = %inf; ts_p = %nan;
else
    tp = t(ip); ts_p = temps(ip, 2);
end
if ifx == [] then
    tf = %inf; ts_f = %nan;
else
    tf = t(ifx); ts_f = temps(ifx, 2);
end
[failed, checks] = check(failed, checks, "model B: predictive trip, seconds after the fault starts", ..
                         tp - t_fault, tp > t_fault & tp < t_fault + 300, "within 5 minutes");
[failed, checks] = check(failed, checks, "model B: surface temperature at the predictive trip (degC)", ..
                         round(ts_p * 10) / 10, ts_p < 45, "below 45, the charge trip");
[failed, checks] = check(failed, checks, "model B: fixed-limit trip, seconds after the fault starts", ..
                         tf - t_fault, tf > tp, "later than the predictive trip");
q_end = heat($, 2);
[failed, checks] = check(failed, checks, "model B: estimated abnormal heat at the end (W)", ..
                         round(q_end * 1000) / 1000, abs(q_end - 1) < 0.05, "1 W was added");
csvWrite([t, temps, heat, trips], out + "model_b.csv", ",", ".", "%.5f");

summary = msprintf("{""predictive_trip_s"": %s, ""fixed_trip_s"": %s, ""surface_at_predictive_c"": %s, " + ..
                   """surface_at_fixed_c"": %s, ""fault_start_s"": %d, ""model_a_max_diff_c"": %s, ""checks"": [%s]}", ..
                   string(tp), string(tf), string(ts_p), string(ts_f), t_fault, string(worst), strcat(checks, ", "));
mputl(summary, out + "results.json");
mprintf("results: %s\n", out + "results.json");
if failed > 0 then
    mprintf("%d check(s) failed\n", failed);
else
    mprintf("all checks passed\n");
end
// From a command line, end Scilab with the result: 0 when every check passed, 1 otherwise.
if getscilabmode() <> "STD" then
    exit(bool2s(failed > 0));
end
