function results = crosscheck(scenarios, sim)
%CROSSCHECK  The observer in this folder against the firmware's, on the simulator's logs.
%
%   crosscheck
%   crosscheck({'load_defect', 'soft_short'})
%   crosscheck({'load_defect'}, 'C:\path\to\bms_sim.exe')   another simulator build
%
%   For each scenario, the PC simulator (build/host/bms_sim) runs the firmware's supervisor on
%   the simulated pack and writes a CSV log. This function reads the log, gives the same
%   measured inputs (current, surface temperatures, ambient temperature and the supervisor's
%   cell resistance) to thermal_observer.m, and compares its core temperature and abnormal
%   heat with the values the firmware logged.
%
%   With one log row per sample (5 Hz) the replay is exact: the two must agree to the
%   rounding of the CSV file. With one row per second the replay fills the missing samples by
%   interpolation, starts from the firmware's state and skips the 60 s warm-up; the agreement
%   is then only as close as the missing samples allow.
%
%   Results: crosscheck.json and the logs; the figures and a copy of crosscheck.json beside
%   them (see result_folders). The figures show on the screen when it runs in the Octave or
%   MATLAB window. In the Windows package the simulator, bms_sim.exe, is in this folder.

if nargin < 1 || isempty(scenarios)
  scenarios = {'discharge_steps', 'heat_no_current', 'load_defect', 'soft_short'};
end
root = fileparts(fileparts(mfilename('fullpath')));
if nargin < 2
  sim = find_simulator(root);
end
[out_dir, fig_dir] = result_folders();
p = bms_params('simulator');

% Agreement limits for the exact replay. The CSV keeps 3 decimals of a temperature and 4 of a
% power and a current. The rounded surface readings (up to 0.0005 C) pass through the
% observer's gain, which is large in the first seconds while the observer is still uncertain:
% the rounding alone gives differences up to about 0.007 C and 0.0014 W there, and under
% 0.001 C and 0.0005 W after the first minute. With a log written to 7 decimals the two agree
% to 0.0001 C and 0.0001 W, which is the single-precision arithmetic.
tol_tc = 0.01;     % degC
tol_q = 0.002;     % W

fprintf('%-16s %-7s %7s %12s %12s %12s %12s  %s\n', 'scenario', 'replay', 'rows', ...
        'max dTc (C)', 'rms dTc (C)', 'max dQ (W)', 'rms dQ (W)', 'result');
results = struct([]);
for s = 1:numel(scenarios)
  name = scenarios{s};
  csv = fullfile(out_dir, [name '.csv']);
  make_log(sim, name, csv);
  d = read_log(csv);
  r = replay(d, p);

  ok = all(isfinite(r.dtc(r.use, :)), 2) & all(isfinite(r.dq(r.use, :)), 2);
  dtc = abs(r.dtc(r.use(ok), :));
  dq = abs(r.dq(r.use(ok), :));
  res.scenario = name;
  res.replay = r.mode;
  res.rows_compared = sum(ok);
  res.max_dtc_c = max(dtc(:));
  res.rms_dtc_c = sqrt(mean(dtc(:) .^ 2));
  res.max_dq_w = max(dq(:));
  res.rms_dq_w = sqrt(mean(dq(:) .^ 2));
  res.max_abs_q_w = max(max(abs([d.q1_w d.q2_w d.q3_w d.q4_w])));
  res.max_dtc_per_cell_c = max(dtc, [], 1);
  res.max_dq_per_cell_w = max(dq, [], 1);
  if strcmp(r.mode, 'exact')
    res.pass = res.max_dtc_c <= tol_tc && res.max_dq_w <= tol_q;
    verdict = 'agree';
    if ~res.pass
      verdict = 'DIFFER';
    end
  else
    res.pass = [];
    verdict = 'approximate (one row per second)';
  end
  fprintf('%-16s %-7s %7d %12.5f %12.5f %12.5f %12.5f  %s\n', name, r.mode, ...
          res.rows_compared, res.max_dtc_c, res.rms_dtc_c, res.max_dq_w, res.rms_dq_w, verdict);
  if isempty(results)
    results = res;
  else
    results(end + 1) = res;
  end

  if any(strcmp(name, {'load_defect', 'heat_no_current'}))
    plot_check(d, r, name, fullfile(fig_dir, ['crosscheck_' name '.png']));
  end
end

% The build guide reads the copy beside the figures.
text = jsonencode(struct('tolerance_tc_c', tol_tc, 'tolerance_q_w', tol_q, 'results', results));
for dest = {out_dir, fig_dir}
  fid = fopen(fullfile(dest{1}, 'crosscheck.json'), 'w');
  fprintf(fid, '%s\n', text);
  fclose(fid);
end
fprintf('Results: %s\n', fullfile(out_dir, 'crosscheck.json'));
end

% -------------------------------------------------------------------------------------------

function sim = find_simulator(root)
% The simulator beside this file (the Windows package), or the PC build in the repository:
% cmake -S host -B build/host && cmake --build build/host
here = fileparts(mfilename('fullpath'));
paths = {fullfile(here, 'bms_sim.exe'), fullfile(here, 'bms_sim'), ...
         fullfile(root, 'build', 'host', 'bms_sim'), fullfile(root, 'build', 'host', 'bms_sim.exe'), ...
         fullfile(root, 'build', 'host', 'Release', 'bms_sim.exe'), ...
         fullfile(root, 'build', 'host', 'Debug', 'bms_sim.exe')};
for i = 1:numel(paths)
  sim = paths{i};
  if exist(sim, 'file')
    return;
  end
end
if ~exist(fullfile(root, 'host'), 'dir')
  error('crosscheck:nosim', 'bms_sim.exe is missing from this folder. Extract the whole zip again.');
end
error('crosscheck:nosim', ['The simulator is not built. In the repository folder run:\n', ...
       '  cmake -S host -B build/host\n  cmake --build build/host']);
end

function make_log(sim, name, csv)
% A log of every sample if the simulator can write one (--csv-all), otherwise one row per
% second (--csv). A scenario that fails its own checks still writes its log, so the exit status
% of the run is not used; only an unknown option sends the simulator back to its usage text.
base = sprintf('"%s" run %s --csv "%s" --quiet', sim, name, csv);
out = run_command([base ' --csv-all']);
if ~isempty(strfind(out, 'usage:'))
  out = run_command(base);
end
info = dir(csv);
if isempty(info) || info.bytes == 0
  error('crosscheck:nolog', 'The simulator wrote no log for %s:\n%s', name, out);
end
end

function out = run_command(cmd)
if exist(csv_target(cmd), 'file')
  delete(csv_target(cmd));   % never compare with an old log
end
cmd = [cmd ' 2>&1'];
if ispc && ~exist('OCTAVE_VERSION', 'builtin')
  % cmd.exe removes the outer pair of quotes. MATLAB passes the line as it is, so it needs one
  % more pair; Octave for Windows adds that pair itself.
  cmd = ['"' cmd '"'];
end
[~, out] = system(cmd);
end

function path = csv_target(cmd)
% The file named after --csv in a command line.
tok = regexp(cmd, '--csv "([^"]*)"', 'tokens', 'once');
path = tok{1};
end

function d = read_log(path)
% The firmware's CSV format (telemetry.cpp, write_csv_header); an empty field is NaN.
fid = fopen(path, 'r');
header = fgetl(fid);
names = strsplit(strtrim(header), ',');
fmt = repmat({'%f'}, 1, numel(names));
fmt{strcmp(names, 'mode')} = '%s';
cols = textscan(fid, [fmt{:}], 'Delimiter', ',', 'EmptyValue', NaN);
fclose(fid);
for i = 1:numel(names)
  d.(names{i}) = cols{i};
end
end

function r = replay(d, p)
% Runs one observer per cell on the logged inputs, as the supervisor does (supervisor.cpp,
% run_thermal): the observer starts from the surface reading when the thermal layer starts,
% and each step uses the Joule heat and ambient temperature of the previous sample.
ts = [d.ts1 d.ts2 d.ts3 d.ts4];
tc_fw = [d.tc1 d.tc2 d.tc3 d.tc4];
q_fw = [d.q1_w d.q2_w d.q3_w d.q4_w];
r_ohm = [d.r1_mohm d.r2_mohm d.r3_mohm d.r4_mohm] / 1000;
cur = d.current_a;
tamb = d.t_amb;
t = d.t_s;
n = numel(t);
dt_log = median(diff(t));
exact = abs(dt_log - p.dt) < 1e-3;

tc = nan(n, 4);
q = nan(n, 4);
obs = cell(1, 4);
for c = 1:4
  obs{c} = thermal_observer('configure', p, c);
end
running = false;
prev_pj = single(zeros(1, 4));
prev_tamb = single(0);
t_start = NaN;

for k = 1:n
  fw_running = all(isfinite(tc_fw(k, :)));
  if ~fw_running
    running = false;   % the thermal layer is off, or not started yet
    continue;
  end
  if ~running
    % The thermal layer starts here.
    for c = 1:4
      obs{c} = thermal_observer('reset', obs{c}, ts(k, c));
      if ~exact
        % Part-way into a 1 Hz log: start from the firmware's own state.
        obs{c}.x = single([tc_fw(k, c); ts(k, c); q_fw(k, c)]);
      end
    end
    running = true;
    t_start = t(k);
  elseif exact
    for c = 1:4
      if isfinite(ts(k, c))
        obs{c} = thermal_observer('step', obs{c}, prev_pj(c), prev_tamb, ts(k, c));
      else
        obs{c} = thermal_observer('predict', obs{c}, prev_pj(c), prev_tamb);
      end
    end
  else
    % One row per second: the samples in between are missing. Hold the Joule heat and the
    % ambient temperature, and interpolate the surface readings.
    m = round((t(k) - t(k - 1)) / p.dt);
    for j = 1:m
      w = j / m;
      for c = 1:4
        meas = (1 - w) * ts(k - 1, c) + w * ts(k, c);
        obs{c} = thermal_observer('step', obs{c}, prev_pj(c), prev_tamb, meas);
      end
    end
  end
  for c = 1:4
    tc(k, c) = obs{c}.x(1);
    q(k, c) = obs{c}.x(3);
  end
  if isfinite(cur(k)) && isfinite(tamb(k))
    i_heat = min(single(abs(cur(k))), single(p.heat_current_clamp_a));
    prev_pj = i_heat * i_heat * single(r_ohm(k, :));
    prev_tamb = single(tamb(k));
  end
end

r.mode = 'exact';
if ~exact
  r.mode = 'approx';
end
r.t = t;
r.tc = tc;
r.q = q;
r.dtc = tc - tc_fw;
r.dq = q - q_fw;
if exact
  r.use = find(isfinite(tc(:, 1)));
else
  r.use = find(isfinite(tc(:, 1)) & t - t_start >= p.observer_warmup_s);
end
end

function plot_check(d, r, name, path)
colors = [0.165 0.471 0.839; 0.922 0.408 0.204; 0.106 0.686 0.478; 0.929 0.631 0];
tmin = r.t / 60;
tc_fw = [d.tc1 d.tc2 d.tc3 d.tc4];
q_fw = [d.q1_w d.q2_w d.q3_w d.q4_w];
fig = new_figure();

panels = {r.tc, tc_fw, 'Core temperature T_c (\circC)', 1; ...
          r.q, q_fw, 'Abnormal heat Q_{ab} (W)', 1; ...
          r.dtc, [], 'T_c, Octave minus firmware (m\circC)', 1000; ...
          r.dq, [], 'Q_{ab}, Octave minus firmware (mW)', 1000};
% Panel positions: two rows of two, below a two-line title.
pos = {[0.08 0.55 0.38 0.33], [0.58 0.55 0.38 0.33], ...
       [0.08 0.08 0.38 0.33], [0.58 0.08 0.38 0.33]};
for i = 1:4
  axes('Position', pos{i});
  hold on;
  h = zeros(1, 4);
  for c = 1:4
    h(c) = plot(tmin, panels{i, 1}(:, c) * panels{i, 4}, '-', 'Color', colors(c, :), ...
                'LineWidth', 1.5);
    if ~isempty(panels{i, 2})
      plot(tmin, panels{i, 2}(:, c), '--', 'Color', colors(c, :) * 0.6, 'LineWidth', 1.5);
    end
  end
  hold off;
  grid on;
  box on;
  set(gca, 'FontSize', 11);
  xlabel('Time (min)');
  ylabel(panels{i, 3});
  xlim([tmin(1) tmin(end)]);
  if i == 3
    legend(h, {'Cell 1', 'Cell 2', 'Cell 3', 'Cell 4'}, 'Location', 'northeast');
  end
end
replay_note = 'every sample replayed';
if ~strcmp(r.mode, 'exact')
  replay_note = 'one row per second, approximate';
end
txt = {sprintf('Octave observer against the firmware, simulator scenario "%s"', name), ...
       sprintf('Solid: Octave. Dashed: firmware log. %s.', [upper(replay_note(1)) replay_note(2:end)])};
axes('Position', [0 0.92 1 0.08], 'Visible', 'off');
text(0.5, 0.5, txt, 'Units', 'normalized', 'HorizontalAlignment', 'center', ...
     'VerticalAlignment', 'middle', 'FontSize', 13, 'Interpreter', 'none');
save_figure(fig, path);
end
