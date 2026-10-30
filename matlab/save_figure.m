function save_figure(fig, path)
%SAVE_FIGURE  Save a figure as a 1600 x 900 pixel PNG (150 dpi). A hidden figure is closed
%   after saving; a figure on the screen stays open to be looked at.

w = 1600 / 150;
h = 900 / 150;
set(fig, 'PaperUnits', 'inches', 'PaperPosition', [0 0 w h], 'PaperSize', [w h]);
folder = fileparts(path);
if ~isempty(folder) && ~exist(folder, 'dir')
  mkdir(folder);
end
print(fig, '-dpng', '-r150', path);
fprintf('Figure saved: %s\n', path);
if strcmp(get(fig, 'Visible'), 'off')
  close(fig);
end
end
