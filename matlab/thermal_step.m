function res = thermal_step()
%THERMAL_STEP  Section 9.1 model of one healthy cell: response to a 1 W heat step.
%
%   1 W of heat starts in the core at t = 0. The cell and the air are at 25 degC. The model
%   runs for one hour with the firmware's development values (bms_params). It prints the core
%   and surface temperatures at 60, 300, 1200 and 3600 s and the two time constants, saves
%   build/matlab/thermal_step.csv (t, tc, ts) and the figure
%   docs/build-guide/matlab/thermal_step.png.
%
%   The same model is a circuit: heat flow is a current, temperature a voltage, a heat
%   capacity a capacitor to ground and a thermal resistance a resistor. The ngspice run of
%   that circuit must give the same numbers.

root = fileparts(fileparts(mfilename('fullpath')));
p = bms_params('firmware');
cell = 1;
heat_w = 1;
t_amb = 25;
t_end = 3600;

% Exact solution in double precision, one second at a time.
[~, ~, A] = thermal_discretise(p, cell, 1);
cc = p.c_core;
cs = p.c_surf;
b2 = 1 / (p.r_air(cell) * cs);
M = zeros(4, 4);   % states T_c, T_s; inputs: heat into the core, T_amb
M(1:2, 1:2) = A(1:2, 1:2);
M(1, 3) = 1 / cc;
M(2, 4) = b2;
E = expm(M);

t = (0:t_end)';
x = zeros(numel(t), 2);
z = [t_amb; t_amb; heat_w; t_amb];
x(1, :) = z(1:2)';
for k = 2:numel(t)
  z = E * z;
  x(k, :) = z(1:2)';
end

lambda = eig(A(1:2, 1:2));
tau = sort(-1 ./ lambda);   % fast, slow
t_ss_surf = t_amb + heat_w * p.r_air(cell);
t_ss_core = t_ss_surf + heat_w * p.r_core;

fprintf('Two-state model, 1 W into the core, ambient %.1f C\n', t_amb);
fprintf('  C_core %.1f J/C, C_surf %.1f J/C, R_core %.1f C/W, R_air %.1f C/W\n', ...
        cc, cs, p.r_core, p.r_air(cell));
fprintf('  time constants: fast %.4f s, slow %.4f s\n', tau(1), tau(2));
fprintf('  %8s %12s %12s\n', 't (s)', 'T_core (C)', 'T_surf (C)');
marks = [60 300 1200 3600];
for m = marks
  k = find(t == m, 1);
  fprintf('  %8d %12.4f %12.4f\n', m, x(k, 1), x(k, 2));
end
fprintf('  steady state: T_core %.4f C, T_surf %.4f C\n', t_ss_core, t_ss_surf);

out_dir = fullfile(root, 'build', 'matlab');
if ~exist(out_dir, 'dir')
  mkdir(out_dir);
end
fid = fopen(fullfile(out_dir, 'thermal_step.csv'), 'w');
fprintf(fid, 't,tc,ts\n');
fprintf(fid, '%d,%.6f,%.6f\n', [t, x]');
fclose(fid);

fig = figure('visible', 'off');
plot(t / 60, x(:, 1), '-', 'Color', [0.922 0.408 0.204], 'LineWidth', 2);
hold on;
plot(t / 60, x(:, 2), '-', 'Color', [0.165 0.471 0.839], 'LineWidth', 2);
plot([0 t_end / 60], [t_ss_core t_ss_core], ':', 'Color', [0.45 0.45 0.45], 'LineWidth', 1);
plot([0 t_end / 60], [t_ss_surf t_ss_surf], ':', 'Color', [0.45 0.45 0.45], 'LineWidth', 1);
hold off;
grid on;
set(gca, 'FontSize', 12);
xlabel('Time (min)');
ylabel('Temperature (\circC)');
title(sprintf(['Two-state cell model: 1 W into the core, ambient %g \\circC ', ...
               '(time constants %.1f s and %.0f s)'], t_amb, tau(1), tau(2)));
legend({'Core T_c', 'Surface T_s', 'Steady state'}, 'Location', 'southeast');
xlim([0 t_end / 60]);
save_figure(fig, fullfile(root, 'docs', 'build-guide', 'matlab', 'thermal_step.png'));
close(fig);

res.t = t;
res.tc = x(:, 1);
res.ts = x(:, 2);
res.tau_s = tau';
res.marks_s = marks;
res.tc_marks = x(marks + 1, 1)';
res.ts_marks = x(marks + 1, 2)';
end
