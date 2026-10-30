function obs = thermal_observer(action, varargin)
%THERMAL_OBSERVER  Section 9.2: Kalman observer of [T_c; T_s; Q_ab] for one cell.
%
%   A line-by-line copy of the firmware's CellObserver
%   (firmware/components/bms_core/src/thermal.cpp). It works in single precision, like the
%   firmware, so the two give the same numbers from the same inputs.
%
%   obs = thermal_observer('configure', p, cell)   p from bms_params, cell 1 to 4
%   obs = thermal_observer('reset', obs, t_surface_c)
%   obs = thermal_observer('step', obs, p_joule_w, t_amb_c, t_meas_c)
%   obs = thermal_observer('predict', obs, p_joule_w, t_amb_c)
%
%   After 'step', obs.x(1) is the core temperature (degC), obs.x(2) the surface temperature
%   (degC) and obs.x(3) the abnormal heat (W).
%
%   The inputs of 'step' and 'predict' are those of the last interval: the Joule heat
%   I^2 R and the ambient temperature of the previous sample. 'step' predicts over that
%   interval, then corrects with the new surface reading. 'predict' is used when the reading
%   is not valid.

switch action
  case 'configure'
    obs = configure(varargin{:});
  case 'reset'
    obs = reset_state(varargin{:});
  case 'step'
    obs = step(varargin{:});
  case 'predict'
    obs = predict(varargin{:});
  otherwise
    error('thermal_observer: unknown action ''%s''', action);
end
end

function obs = configure(p, cell)
[obs.phi, obs.gam] = thermal_discretise(p, cell, p.dt);
obs.q = single([p.core_sd_c ^ 2; p.surf_sd_c ^ 2; p.heat_sd_w ^ 2]);
obs.r = single(p.meas_sd_c ^ 2);
obs.x = single(zeros(3, 1));
obs.P = single(zeros(3, 3));
obs.ready = false;
end

function obs = reset_state(obs, t_surface_c)
obs.x = single([t_surface_c; t_surface_c; 0]);
obs.P = single(zeros(3, 3));
obs.P(1, 1) = 1;       % the core may be warmer than the surface at start
obs.P(2, 2) = obs.r;
obs.P(3, 3) = 0.1;     % W^2
obs.ready = true;
end

function obs = predict(obs, p_joule_w, t_amb_c)
u = single([p_joule_w; t_amb_c]);
obs.x = obs.phi * obs.x + obs.gam * u;
obs.P = obs.phi * obs.P * obs.phi' + diag(obs.q);
end

function obs = step(obs, p_joule_w, t_amb_c, t_meas_c)
obs = predict(obs, p_joule_w, t_amb_c);
% Only T_s is measured: H = [0 1 0].
s = obs.P(2, 2) + obs.r;
k = obs.P(:, 2) / s;
innov = single(t_meas_c) - obs.x(2);
obs.x = obs.x + k * innov;
obs.P = obs.P - k * obs.P(2, :);
% Keep P symmetric, as the firmware does after each correction.
obs.P = (obs.P + obs.P') / 2;
end
