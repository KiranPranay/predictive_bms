function save_figure(fig, path)
%SAVE_FIGURE  Save a figure as a 1600 x 900 pixel PNG (150 dpi). A hidden figure is closed
%   after saving; a figure on the screen stays open to be looked at.
%
%   Some batch runs cannot draw a hidden figure (octave-cli on Windows has only the FLTK
%   toolkit, which needs a figure on the screen). The figure is then not saved, a note says so,
%   and the script goes on: the numbers do not depend on the figure. In the Octave or MATLAB
%   window the figure is always shown and saved.

w = 1600 / 150;
h = 900 / 150;
set(fig, 'PaperUnits', 'inches', 'PaperPosition', [0 0 w h], 'PaperSize', [w h]);
folder = fileparts(path);
if ~isempty(folder) && ~exist(folder, 'dir')
  mkdir(folder);
end
try
  print(fig, '-dpng', '-r150', path);
  fprintf('Figure saved: %s\n', path);
catch err
  fprintf('Figure not saved (%s). Run the script in the Octave window to see and save it.\n', ...
          err.message);
end
if strcmp(get(fig, 'Visible'), 'off')
  close(fig);
end
end
