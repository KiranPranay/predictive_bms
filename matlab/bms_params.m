function p = bms_params(source)
%BMS_PARAMS  Thermal model values and Kalman tuning of the supervisor.
%
%   p = bms_params()             the firmware's own values (types.h and config.h)
%   p = bms_params('simulator')  the values of the simulated pack; the simulator's scenarios
%                                load these as the fitted model (firmware/components/bms_sim/
%                                src/pack.cpp, Pack::Pack and Pack::fitted_params)
%
%   Every number here is a copy. The firmware holds the original: change it there first
%   (firmware/components/bms_core/include/bms/types.h and config.h), then here.

if nargin < 1
  source = 'firmware';
end

% Section 8, rules 1-3: the supervisor samples at 5 Hz.
p.sample_hz = 5;
p.dt = 1 / p.sample_hz;   % s

% Section 9.1: the two-state thermal model of one cell.
switch lower(source)
  case 'firmware'
    % Development values, replaced at Gate 9. The sum c_core + c_surf matches the 45 J/degC
    % estimate of section 9.1; the split and r_core are placeholders.
    p.c_core = 40;              % J/degC, heat capacity of the core
    p.c_surf = 5;               % J/degC, heat capacity of the surface layer
    p.r_core = 2;               % degC/W, core to surface
    p.r_air = [30 30 30 30];    % degC/W, surface to air, per cell (estimate)
    p.r_cell = [0.035 0.035 0.035 0.035];   % ohm, cell resistance, estimate until Gate 4
  case 'simulator'
    % The simulated pack (illustrative values, not measurements of the project's cells).
    % End cells cool better than middle cells.
    p.c_core = 40;
    p.c_surf = 5;
    p.r_core = 2;
    p.r_air = [28 31 31 28];
    p.r_cell = [NaN NaN NaN NaN];   % per seed; the supervisor's own estimate is in the CSV log
  otherwise
    error('bms_params: unknown source ''%s'' (use ''firmware'' or ''simulator'')', source);
end

% Kalman tuning (development values, confirmed at Gates 9 and 11), types.h KalmanTuning.
p.meas_sd_c = 0.05;    % degC, NTC noise after the median stage
p.core_sd_c = 0.005;   % degC per sample, model error of the core
p.surf_sd_c = 0.010;   % degC per sample, model error of the surface
p.heat_sd_w = 0.003;   % W per sample, random walk of the abnormal heat

% Section 9.2.
p.heat_current_clamp_a = 5.0;   % the Joule heat uses |I| clamped to 5 A
p.contact_heat_w = -0.4;        % abnormal heat below this under load: NTC contact fault

% Development value: no thermal verdict while the observer settles.
p.observer_warmup_s = 60;
end
