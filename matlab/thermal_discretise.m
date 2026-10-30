function [phi, gam, A] = thermal_discretise(p, cell, h)
%THERMAL_DISCRETISE  Section 9.1 model of one cell over a time step h, in seconds.
%
%   x(k+1) = phi * x(k) + gam * u(k),   x = [T_c; T_s; Q_ab],   u = [I^2 R; T_amb]
%
%   The step is exact: the matrix exponential of the augmented matrix [A B; 0 0] gives phi and
%   gam in one go, as in the firmware (thermal.cpp, discretise). A is the continuous-time matrix
%   of the three states. phi and gam are single precision, like the firmware's floats.

cc = p.c_core;
cs = p.c_surf;
rc = p.r_core;
ru = p.r_air(cell);
a1 = 1 / (rc * cc);
b1 = 1 / (rc * cs);
b2 = 1 / (ru * cs);

% Rows: dT_c/dt, dT_s/dt, dQ_ab/dt. Columns: T_c, T_s, Q_ab, I^2 R, T_amb.
M = zeros(5, 5);
M(1, :) = [-a1, a1, 1 / cc, 1 / cc, 0];
M(2, :) = [b1, -(b1 + b2), 0, 0, b2];
A = M(1:3, 1:3);

E = expm(M * h);
phi = single(E(1:3, 1:3));
gam = single(E(1:3, 4:5));
end
