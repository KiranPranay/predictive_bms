function [out_dir, fig_dir] = result_folders()
%RESULT_FOLDERS  Where thermal_step and crosscheck write their results and figures.
%
%   In the repository (this folder sits beside host/ and docs/): the results go to build/matlab/
%   and the figures to docs/build-guide/matlab/. In the Windows package, where this folder
%   stands alone with bms_sim.exe, both go to a "results" folder beside the scripts.

here = fileparts(mfilename('fullpath'));
root = fileparts(here);
if exist(fullfile(root, 'host'), 'dir')
  out_dir = fullfile(root, 'build', 'matlab');
  fig_dir = fullfile(root, 'docs', 'build-guide', 'matlab');
else
  out_dir = fullfile(here, 'results');
  fig_dir = out_dir;
end
for d = {out_dir, fig_dir}
  if ~exist(d{1}, 'dir')
    mkdir(d{1});
  end
end
end
