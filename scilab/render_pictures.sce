// Draws both models as PNG pictures, as Xcos shows them, for the build guide:
// ../docs/build-guide/scilab/cell_thermal_model.png and abnormal_heat_detection.png.
// It opens Xcos for a few seconds, because the drawing needs a running Xcos.
// Run it in Scilab from this folder:  exec("render_pictures.sce", -1)

loadXcosLibs();
loadScicos();
here = get_absolute_file_path("render_pictures.sce");
out = here + "../docs/build-guide/scilab/";
mkdir(out);
names = ["cell_thermal_model", "abnormal_heat_detection"];
xcos(here + names(1) + ".zcos");
sleep(4000);
jimport org.scilab.modules.xcos.utils.XcosDelegates;
jimport java.io.File;
for n = names
    src = here + n + ".zcos";
    XcosDelegates.convertToPNG(src, src, File.new(out + n + ".png"), n);
    mprintf("wrote %s\n", out + n + ".png");
end
