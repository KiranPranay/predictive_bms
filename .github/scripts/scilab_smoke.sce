// Checks that Scilab for Windows can write, read and simulate an Xcos diagram without a
// window: a constant into a "to workspace" block, run for 10 s.
//     Scilex.exe -nw -nb -quit -f .github/scripts/scilab_smoke.sce

loadXcosLibs();
loadScicos();
disp(getversion());

// The blocks keep their default settings: the constant is 1, and "to workspace" writes the
// variable A.
scs_m = scicos_diagram();
scs_m.props.tf = 10;
c = CONST_m("define");
c.graphics.sz = [40 40];
c.graphics.orig = [0 0];
w = TOWS_c("define");
w.graphics.sz = [40 40];
w.graphics.orig = [100 0];
k = CLOCK_c("define");
k.graphics.sz = [40 40];
k.graphics.orig = [100 100];
scs_m.objs(1) = c;
scs_m.objs(2) = w;
scs_m.objs(3) = k;
scs_m.objs(4) = scicos_link(xx=[44; 96], yy=[20; 20], from=[1 1 0], to=[2 1 1]);
scs_m.objs(5) = scicos_link(xx=[120; 120], yy=[96; 44], ct=[5 -1], from=[3 1 0], to=[2 1 1]);

f = TMPDIR + "/smoke.zcos";
xcosDiagramToScilab(f, scs_m);
clear scs_m;
if ~importXcosDiagram(f) then
    mprintf("could not read %s\n", f);
    exit(1);
end
scicos_simulate(scs_m, list(), "nw");
mprintf("Xcos: wrote, read and simulated %s; last value %g\n", f, A.values($));
if abs(A.values($) - 1) > 1e-9 then
    exit(1);
end
exit(0);
