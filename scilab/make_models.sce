// Writes the two Xcos models in this folder:
//   cell_thermal_model.zcos       the two-node thermal model of one cell (section 9.1)
//   abnormal_heat_detection.zcos  the thermal model with the observer of section 9.2, and a
//                                 predictive trip compared with a fixed temperature limit
//
// The models are ready-made in this folder; this script is only needed after a change.
// Run it in Scilab from this folder:  exec("make_models.sce", -1)
//
// Coordinates are those of the Xcos page: x to the right, y downwards, in pixels.

loadXcosLibs();
loadScicos();
here = get_absolute_file_path("make_models.sce");

// --- Helpers ----------------------------------------------------------------------------

// A block from the palette, with its parameters (exprs), place, size and a label. Xcos keeps
// only one-word labels on a block, so the label is written as a note under the block.
function blk = place(gui, exprs, x, y, w, h, label)
    execstr("blk = " + gui + "(""define"");");
    if gui == "STEP_FUNCTION" then
        // The step's parameters sit in the STEP block inside this masked block.
        sb = blk.model.rpar;
        for i = 1:size(sb.objs)
            if typeof(sb.objs(i)) == "Block" then
                if sb.objs(i).gui == "STEP" then
                    s = sb.objs(i);
                    s.graphics.exprs = exprs;
                    sb.objs(i) = s;
                end
            end
        end
        blk.model.rpar = sb;
    elseif exprs <> [] then
        blk.graphics.exprs = exprs;
    end
    blk.graphics.orig = [x, y];
    blk.graphics.sz = [w, h];
    blk.graphics.id = label;   // shown when the mouse is over the block
endfunction

// A split point, where one signal goes to two places.
function blk = split(x, y)
    blk = SPLIT_f("define");
    blk.model.out = [-1; -1];
    blk.model.out2 = [-2; -2];
    blk.model.outtyp = [1; 1];
    blk.graphics.orig = [x, y];
    blk.graphics.sz = [1, 1];
endfunction

// Free text on the page.
function t = note(text, x, y, w, size_)
    t = TEXT_f("define");
    t.graphics.exprs = [text; "2"; string(size_)];
    t.graphics.orig = [x, y];
    t.graphics.sz = [6 * length(text), 20];   // Xcos centres text in its box
endfunction

// Port positions: inputs on the left, outputs on the right; Xcos puts port i of n at
// i/(n+1) of the block's height.
function p = port(blk, side, i, n)
    o = blk.graphics.orig; s = blk.graphics.sz;
    if blk.gui == "SPLIT_f" then
        p = o;
    elseif side == "in" then
        p = [o(1), o(2) + s(2) * i / (n + 1)];
    else
        p = [o(1) + s(1), o(2) + s(2) * i / (n + 1)];
    end
endfunction

// A data link from output `op` (of `nop`) of block a to input `ip` (of `nip`) of block b.
// It runs right, then up or down at x = xv, then right again. xv = [] puts the turn halfway.
function lnk = wire(objs, a, op, nop, b, ip, nip, xv)
    p1 = port(objs(a), "out", op, nop);
    p2 = port(objs(b), "in", ip, nip);
    if xv == [] then
        xv = (p1(1) + p2(1)) / 2;
    end
    if abs(p1(2) - p2(2)) < 0.5 then
        xx = [p1(1); p2(1)]; yy = [p1(2); p2(2)];
    else
        xx = [p1(1); xv; xv; p2(1)]; yy = [p1(2); p1(2); p2(2); p2(2)];
    end
    lnk = scicos_link(xx=xx, yy=yy, ct=[1, 1], from=[a, op, 0], to=[b, ip, 1]);
endfunction

// A data link from a split that first goes up or down to the height of the input, then right.
function lnk = branch(objs, a, op, b, ip, nip)
    p1 = port(objs(a), "out", op, 2);
    p2 = port(objs(b), "in", ip, nip);
    lnk = scicos_link(xx=[p1(1); p1(1); p2(1)], yy=[p1(2); p2(2); p2(2)], ..
                      ct=[1, 1], from=[a, op, 0], to=[b, ip, 1]);
endfunction

// An activation link from the bottom of block a (output op) to the top of block b.
function lnk = event(objs, a, op, b)
    oa = objs(a).graphics.orig; sa = objs(a).graphics.sz;
    ob = objs(b).graphics.orig; sb = objs(b).graphics.sz;
    if objs(a).gui == "CLKSPLIT_f" then
        p1 = oa;
    else
        p1 = [oa(1) + sa(1) / 2, oa(2) + sa(2)];
    end
    p2 = [ob(1) + sb(1) / 2, ob(2)];
    lnk = scicos_link(xx=[p1(1); p1(1); p2(1); p2(1)], yy=[p1(2); (p1(2) + p2(2)) / 2; (p1(2) + p2(2)) / 2; p2(2)], ..
                      ct=[5, -1], from=[a, op, 0], to=[b, 1, 1]);
endfunction

// Evaluates every block's parameters with the context, as Xcos does before a simulation, so
// that each block has its final number of ports before the links are drawn.
function [scs_m, o] = evaluate(scs_m, o)
    [%scicos_context, ierr] = script2var(scs_m.props.context, struct());
    needcompile = 4;   // do_eval reads these two from its caller
    %cpr = list();
    [scs_m, %cpr, needcompile, ok] = do_eval(scs_m, %cpr, %scicos_context);
    if ~ok then
        error("the blocks could not be evaluated");
    end
    for k = 1:size(o)
        o(k) = scs_m.objs(k);
    end
endfunction

// Puts the blocks in the diagram, evaluates them, adds the links and the notes.
function scs_m = assemble(scs_m, o, links, notes)
    for k = 1:size(o)
        scs_m.objs(k) = o(k);
        // The label, centred under the block.
        if o(k).graphics.id <> "" then
            txt = o(k).graphics.id;
            org = o(k).graphics.orig; sz = o(k).graphics.sz;
            notes($+1) = note(txt, org(1) + sz(1) / 2 - 3 * length(txt), org(2) + sz(2) + 4, 0, 2);
        end
    end
    [scs_m, o] = evaluate(scs_m, o);
    L = links(o);
    n = size(o);
    for k = 1:size(L)
        scs_m.objs(n + k) = L(k);
    end
    n = size(scs_m.objs);
    for k = 1:size(notes)
        scs_m.objs(n + k) = notes(k);
    end

endfunction

// The context both models share. Values are the firmware's
// (firmware/components/bms_core/include/bms/types.h): development values, replaced by the
// Gate 9 fit.
thermal_context = [
    "// Thermal model of one cell (architecture section 9.1). Values from the firmware:"
    "// development values, replaced by the values fitted at Gate 9."
    "C_core = 40;   // J/degC, heat capacity of the cell core"
    "C_surf = 5;    // J/degC, heat capacity of the can surface (45 J/degC together)"
    "R_core = 2;    // degC/W, thermal resistance from core to surface"
    "R_air  = 30;   // degC/W, thermal resistance from surface to air"
    "T_amb  = 25;   // degC, air temperature"
    "// State x = [T_core; T_surf], input u = [heat in the core (W); T_amb]"
    "A_cell = [-1/(R_core*C_core), 1/(R_core*C_core); 1/(R_core*C_surf), -(1/R_core + 1/R_air)/C_surf];"
    "B_cell = [1/C_core, 0; 0, 1/(R_air*C_surf)];"
    "C_cell = eye(2, 2);"
    "D_cell = zeros(2, 2);"
    "x0_cell = [T_amb; T_amb];   // the cell starts at the air temperature"
];

// --- Model A: the thermal model of one cell ---------------------------------------------

scs_m = scicos_diagram();
scs_m.props.title = "cell_thermal_model";
scs_m.props.tf = 3620;
scs_m.props.context = [
    thermal_context
    "Q_step = 1;    // W, heat made in the core (for example a fault, or I^2 R)"
    "t_step = 10;   // s, when the heat starts"
];
o = list();
o(1) = place("STEP_FUNCTION", ["t_step"; "0"; "Q_step"], 60, 100, 40, 40, "Heat in the core: 1 W from t = 10 s");
o(2) = place("CONST_m", "T_amb", 50, 180, 60, 40, "Air: 25 °C");
o(3) = place("MUX", "2", 220, 40, 10, 240, "");
o(4) = place("CLSS", ["A_cell"; "B_cell"; "C_cell"; "D_cell"; "x0_cell"], 290, 120, 180, 80, ..
             "The cell: x = [T_core; T_surf]");
o(5) = split(520, 160);
o(6) = place("CSCOPE", ["5 2 3 4 6 7 9 13"; "-1"; "[]"; "[800;500]"; "20"; "60"; "3610"; "200"; "0"; ..
                        "Cell temperatures (degC): core red, surface blue"], 580, 110, 60, 60, "");
o(7) = place("TOWS_c", ["4000"; "xcos_thermal"; "0"], 700, 250, 100, 40, "Results for check_models.sce");
o(8) = place("SampleCLK", ["1"; "0"], 690, -20, 40, 40, "");
o(9) = place("CLKSPLIT_f", [], 710, 50, 1, 1, "");
function L = links_a(o)
    L = list();
    L($+1) = wire(o, 1, 1, 1, 3, 1, 2, 170);
    L($+1) = wire(o, 2, 1, 1, 3, 2, 2, 170);
    L($+1) = wire(o, 3, 1, 1, 4, 1, 1, []);
    L($+1) = wire(o, 4, 1, 1, 5, 1, 1, []);
    L($+1) = branch(o, 5, 1, 6, 1, 1);
    L($+1) = branch(o, 5, 2, 7, 1, 1);
    L($+1) = event(o, 8, 1, 9);
    L($+1) = event(o, 9, 1, 6);
    L($+1) = event(o, 9, 2, 7);
endfunction
notes = list();
notes(1) = note("Thermal model of one cell (architecture section 9.1)", 30, -40, 500, 4);
notes(2) = note("Double-click the page (or Simulation > Set Context) to see the values. Start: the black triangle.", 30, -5, 600, 2);
scs_m = assemble(scs_m, o, links_a, notes);
xcosDiagramToScilab(here + "cell_thermal_model.zcos", scs_m);
mprintf("wrote cell_thermal_model.zcos\n");

// --- Model B: abnormal heat detection ---------------------------------------------------

scs_m = scicos_diagram();
scs_m.props.title = "abnormal_heat_detection";
scs_m.props.tf = 3600;
scs_m.props.context = [
    thermal_context
    "R_cell = 0.035; // Ohm, cell resistance (architecture 9.6: about 35 mOhm for an 18650)"
    "I_load = 3;     // A, load current; its heat I^2 R is known to the supervisor"
    "Q_fault = 1;    // W, abnormal heat the supervisor does not know about (a fault)"
    "t_fault = 600;  // s, when the abnormal heat starts (10 minutes)"
    "Q_trip = 0.75;  // W, trip level: 1.0 degC/min x 45 J/degC (architecture 9.8)"
    "T_fixed = 55;   // degC, a fixed limit: 55 degC disables the load (architecture section 8)"
    "dt = 0.2;       // s, the firmware samples 5 times a second"
    "// The observer (section 9.2) adds the abnormal heat Q_ab as a third state."
    "A3 = [A_cell, [1/C_core; 0]; 0, 0, 0];"
    "B3 = [B_cell; 0, 0];"
    "M = expm([A3, B3; zeros(2, 5)] * dt);   // exact step of 0.2 s, as in the firmware"
    "Phi = M(1:3, 1:3); Gam = M(1:3, 4:5);"
    "H = [0, 1, 0];                          // only the surface temperature is measured"
    "Qn = diag([0.005^2, 0.010^2, 0.003^2]); // the Kalman tuning of the firmware"
    "Rn = 0.05^2;                            // NTC noise, degC^2"
    "P = eye(3, 3);"
    "for k = 1:20000"
    "  Pm = Phi*P*Phi'' + Qn; K = Pm*H''/(H*Pm*H'' + Rn); P = Pm - K*H*Pm;"
    "end"
    "// K is the gain that the Kalman filter of the firmware settles to. Inputs:"
    "// [I^2 R; T_amb; measured T_surf]; outputs: [estimated T_core; estimated Q_ab]."
    "A_obs = Phi*(eye(3, 3) - K*H);"
    "B_obs = [Gam, Phi*K];"
    "C_obs = [1, 0, 0; 0, 0, 1]*(eye(3, 3) - K*H);"
    "D_obs = [0, 0, K(1); 0, 0, K(3)];"
    "x0_obs = [T_amb; T_amb; 0];"
];
o = list();
// 1. Heat sources.
o(1) = place("CONST_m", "I_load", 20, 60, 60, 40, "Load current: 3 A");
o(2) = place("POWBLK_f", "2", 120, 60, 40, 40, "I^2");
o(3) = place("GAINBLK", "R_cell", 200, 60, 40, 40, "x R = Joule heat");
o(4) = split(280, 80);
o(5) = place("STEP_FUNCTION", ["t_fault"; "0"; "Q_fault"], 30, 150, 40, 40, "Abnormal heat: 1 W from 10 min");
o(6) = split(280, 170);
o(7) = place("SUMMATION", "[1;1]", 330, 85, 40, 100, "Total heat (W)");
o(8) = place("CONST_m", "T_amb", 20, 260, 60, 40, "Air: 25 °C");
o(9) = split(280, 280);
o(10) = place("GOTO", ["Q_joule"; "1"], 300, 15, 80, 30, "");
o(11) = place("GOTO", ["Q_fault"; "1"], 300, 210, 80, 30, "");
o(12) = place("GOTO", ["T_amb"; "1"], 300, 320, 80, 30, "");
// 2. The cell.
o(13) = place("MUX", "2", 440, 110, 10, 200, "");
o(14) = place("CLSS", ["A_cell"; "B_cell"; "C_cell"; "D_cell"; "x0_cell"], 500, 170, 180, 80, ..
              "The cell: true temperatures");
o(15) = place("DEMUX", "2", 730, 150, 10, 120, "");
o(16) = place("GOTO", ["T_core"; "1"], 780, 175, 80, 30, "");
o(17) = place("GOTO", ["T_surf"; "1"], 780, 215, 80, 30, "");
// 3. The predictive layer.
o(18) = place("FROM", "Q_joule", 440, 437.5, 80, 30, "");
o(19) = place("FROM", "T_amb", 440, 475, 80, 30, "");
o(20) = place("FROM", "T_surf", 440, 512.5, 80, 30, "");
o(21) = place("MUX", "3", 570, 415, 10, 150, "");
o(22) = place("DLSS", ["A_obs"; "B_obs"; "C_obs"; "D_obs"; "x0_obs"], 630, 450, 200, 80, ..
              "Observer: the Kalman filter of section 9.2");
o(23) = place("SampleCLK", ["dt"; "0"], 850, 370, 40, 40, "");
o(24) = place("DEMUX", "2", 880, 450, 10, 80, "");
o(25) = place("GOTO", ["T_core_est"; "1"], 930, 440, 100, 30, "");
o(26) = split(920, 450 + 160 / 3);
o(27) = place("HYSTHERESIS", ["Q_trip"; "Q_trip - 0.01"; "1"; "0"; "1"], 990, 450 + 160 / 3 - 20, 60, 40, ..
              "Predictive trip: Q_ab ≥ 0.75 W");
o(28) = place("GOTO", ["Q_est"; "1"], 990, 560, 80, 30, "");
o(29) = place("GOTO", ["Trip_pred"; "1"], 1090, 450 + 160 / 3 - 15, 90, 30, "");
o(30) = place("FROM", "T_surf", 880, 640, 80, 30, "");
o(31) = place("HYSTHERESIS", ["T_fixed"; "T_fixed - 0.1"; "1"; "0"; "1"], 990, 635, 60, 40, ..
              "Fixed limit: T_surf ≥ 55 °C");
o(32) = place("GOTO", ["Trip_fixed"; "1"], 1090, 640, 90, 30, "");
// 4. Displays.
o(33) = place("FROM", "T_core", 1260, 52.5, 90, 30, "");
o(34) = place("FROM", "T_surf", 1260, 90, 90, 30, "");
o(35) = place("FROM", "T_core_est", 1260, 127.5, 90, 30, "");
o(36) = place("MUX", "3", 1390, 30, 10, 150, "");
o(37) = place("FROM", "Q_fault", 1260, 235, 90, 30, "");
o(38) = place("FROM", "Q_est", 1260, 275, 90, 30, "");
o(39) = place("MUX", "2", 1390, 210, 10, 120, "");
o(40) = place("FROM", "Trip_pred", 1260, 385, 90, 30, "");
o(41) = place("FROM", "Trip_fixed", 1260, 425, 90, 30, "");
o(42) = place("MUX", "2", 1390, 360, 10, 120, "");
o(43) = place("CMSCOPE", ["3 2 2"; "5 2 1 3 5 1 3"; "-1"; "[]"; "[900;750]"; "20 0 -0.1"; "70 1.5 1.2"; ..
                          "3600 3600 3600"; "200"; "0"; "Abnormal heat detection"], ..
              1480, 140, 60, 240, "");
o(44) = place("SampleCLK", ["1"; "0"], 1490, 40, 40, 40, "");
// 5. Results for the check script (not needed to run the model).
o(45) = place("FROM", "T_core", 1260, 612.5, 90, 30, "");
o(46) = place("FROM", "T_surf", 1260, 650, 90, 30, "");
o(47) = place("FROM", "T_core_est", 1260, 687.5, 90, 30, "");
o(48) = place("MUX", "3", 1390, 590, 10, 150, "");
o(49) = place("TOWS_c", ["4000"; "xcos_temps"; "0"], 1450, 645, 100, 40, "");
o(50) = place("FROM", "Q_fault", 1260, 795, 90, 30, "");
o(51) = place("FROM", "Q_est", 1260, 835, 90, 30, "");
o(52) = place("MUX", "2", 1390, 770, 10, 120, "");
o(53) = place("TOWS_c", ["4000"; "xcos_heat"; "0"], 1450, 810, 100, 40, "");
o(54) = place("FROM", "Trip_pred", 1260, 945, 90, 30, "");
o(55) = place("FROM", "Trip_fixed", 1260, 985, 90, 30, "");
o(56) = place("MUX", "2", 1390, 920, 10, 120, "");
o(57) = place("TOWS_c", ["4000"; "xcos_trips"; "0"], 1450, 960, 100, 40, "");
o(58) = place("SampleCLK", ["1"; "0"], 1630, 560, 40, 40, "");
o(59) = place("CLKSPLIT_f", [], 1650, 625, 1, 1, "");
o(60) = place("CLKSPLIT_f", [], 1650, 790, 1, 1, "");
function L = links_b(o)
    L = list();
    // Heat sources.
    L($+1) = wire(o, 1, 1, 1, 2, 1, 1, []);
    L($+1) = wire(o, 2, 1, 1, 3, 1, 1, []);
    L($+1) = wire(o, 3, 1, 1, 4, 1, 1, []);
    L($+1) = wire(o, 4, 1, 2, 7, 1, 2, 310);       // Joule heat into the total
    L($+1) = branch(o, 4, 2, 10, 1, 1);             // and to the observer, by tag
    L($+1) = wire(o, 5, 1, 1, 6, 1, 1, []);
    L($+1) = wire(o, 6, 1, 2, 7, 2, 2, 310);       // abnormal heat into the total
    L($+1) = branch(o, 6, 2, 11, 1, 1);             // and to the scope, by tag
    L($+1) = wire(o, 8, 1, 1, 9, 1, 1, []);
    L($+1) = wire(o, 9, 1, 2, 13, 2, 2, 410);      // air temperature into the cell
    L($+1) = branch(o, 9, 2, 12, 1, 1);             // and to the observer, by tag
    // The cell.
    L($+1) = wire(o, 7, 1, 1, 13, 1, 2, 410);
    L($+1) = wire(o, 13, 1, 1, 14, 1, 1, []);
    L($+1) = wire(o, 14, 1, 1, 15, 1, 1, []);
    L($+1) = wire(o, 15, 1, 2, 16, 1, 1, 760);
    L($+1) = wire(o, 15, 2, 2, 17, 1, 1, 760);
    // The predictive layer.
    L($+1) = wire(o, 18, 1, 1, 21, 1, 3, 545);
    L($+1) = wire(o, 19, 1, 1, 21, 2, 3, 545);
    L($+1) = wire(o, 20, 1, 1, 21, 3, 3, 545);
    L($+1) = wire(o, 21, 1, 1, 22, 1, 1, []);
    L($+1) = event(o, 23, 1, 22);
    L($+1) = wire(o, 22, 1, 1, 24, 1, 1, []);
    L($+1) = wire(o, 24, 1, 2, 25, 1, 1, 910);
    L($+1) = wire(o, 24, 2, 2, 26, 1, 1, []);
    L($+1) = wire(o, 26, 1, 2, 27, 1, 1, 950);
    L($+1) = branch(o, 26, 2, 28, 1, 1);
    L($+1) = wire(o, 27, 1, 1, 29, 1, 1, []);
    L($+1) = wire(o, 30, 1, 1, 31, 1, 1, []);
    L($+1) = wire(o, 31, 1, 1, 32, 1, 1, []);
    // Displays.
    L($+1) = wire(o, 33, 1, 1, 36, 1, 3, 1370);
    L($+1) = wire(o, 34, 1, 1, 36, 2, 3, 1370);
    L($+1) = wire(o, 35, 1, 1, 36, 3, 3, 1370);
    L($+1) = wire(o, 37, 1, 1, 39, 1, 2, 1370);
    L($+1) = wire(o, 38, 1, 1, 39, 2, 2, 1370);
    L($+1) = wire(o, 40, 1, 1, 42, 1, 2, 1370);
    L($+1) = wire(o, 41, 1, 1, 42, 2, 2, 1370);
    L($+1) = wire(o, 36, 1, 1, 43, 1, 3, 1440);
    L($+1) = wire(o, 39, 1, 1, 43, 2, 3, 1440);
    L($+1) = wire(o, 42, 1, 1, 43, 3, 3, 1440);
    L($+1) = event(o, 44, 1, 43);
    // Results for the check script.
    L($+1) = wire(o, 45, 1, 1, 48, 1, 3, 1370);
    L($+1) = wire(o, 46, 1, 1, 48, 2, 3, 1370);
    L($+1) = wire(o, 47, 1, 1, 48, 3, 3, 1370);
    L($+1) = wire(o, 48, 1, 1, 49, 1, 1, []);
    L($+1) = wire(o, 50, 1, 1, 52, 1, 2, 1370);
    L($+1) = wire(o, 51, 1, 1, 52, 2, 2, 1370);
    L($+1) = wire(o, 52, 1, 1, 53, 1, 1, []);
    L($+1) = wire(o, 54, 1, 1, 56, 1, 2, 1370);
    L($+1) = wire(o, 55, 1, 1, 56, 2, 2, 1370);
    L($+1) = wire(o, 56, 1, 1, 57, 1, 1, []);
    L($+1) = event(o, 58, 1, 59);
    L($+1) = event(o, 59, 1, 49);
    L($+1) = event(o, 59, 2, 60);
    L($+1) = event(o, 60, 1, 53);
    L($+1) = event(o, 60, 2, 57);
endfunction
notes = list();
notes(1) = note("Abnormal heat detection: the predictive layer against a fixed temperature limit", 20, -60, 900, 4);
notes(2) = note("Double-click the page (or Simulation > Set Context) to see the values. Start: the black triangle.", 20, -25, 900, 2);
notes(3) = note("1. Heat in the cell", 20, 25, 200, 3);
notes(4) = note("2. The cell", 500, 120, 200, 3);
notes(5) = note("3. The predictive layer (it knows I^2 R, not the fault)", 440, 390, 500, 3);
notes(6) = note("4. Decisions", 990, 605, 200, 3);
notes(9) = note("Every 0.2 s (5 Hz)", 900, 380, 0, 2);
notes(7) = note("5. Scope: temperatures, abnormal heat, trips", 1260, 0, 400, 3);
notes(8) = note("Results for check_models.sce (not needed to run the model)", 1260, 565, 400, 2);
scs_m = assemble(scs_m, o, links_b, notes);
xcosDiagramToScilab(here + "abnormal_heat_detection.zcos", scs_m);
mprintf("wrote abnormal_heat_detection.zcos\n");
