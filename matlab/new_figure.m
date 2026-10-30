function fig = new_figure()
%NEW_FIGURE  A figure that shows on the screen when the script runs in the Octave or MATLAB
%   window, and stays hidden in a batch run (octave-cli, octave --no-gui, matlab -batch).

if exist('OCTAVE_VERSION', 'builtin')
  show = isguirunning();
else
  show = usejava('desktop');
end
if show
  fig = figure('Position', [80 80 1200 675]);
else
  fig = figure('visible', 'off');
end
end
