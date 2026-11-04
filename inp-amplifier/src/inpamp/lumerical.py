"""Generate native LSF and automate licensed Ansys sessions through vendor lumapi.

MODE/FDTD projects are built from YAML. Active-gain INTERCONNECT runs use a
user-selected native SOA/CML template; no Python gain is substituted for it.
"""
from __future__ import annotations

import importlib
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

from .config import Config


def quote(value):
    """LSF string literal, with paths normalized by the caller when needed."""
    return json.dumps(str(value), ensure_ascii=True)


def number(value):
    return format(float(value), ".16g")


def setprop(prop, value):
    literal = quote(value) if isinstance(value, str) else number(value)
    return f"set({quote(prop)},{literal});"


def rectangle(name, spans, center, index, mesh_order, material=None):
    commands = ["addrect;", setprop("name", name)]
    for axis, span, position in zip("xyz", spans, center):
        commands.extend([setprop(axis, position), setprop(f"{axis} span", span)])
    commands.append(setprop("material", material or "<Object defined dielectric>"))
    if not material:
        commands.append(setprop("index", index))
    commands.extend([setprop("override mesh order from material database", 1), setprop("mesh order", mesh_order)])
    return "\n".join(commands)


def mode_script(c: Config):
    d, m = c.device, c.lumerical.mode
    width, thickness = d.width_um * 1e-6, d.core_thickness_um * 1e-6
    xs, ys = c.mode.x_span_um * 1e-6, c.mode.y_span_um * 1e-6
    mesh = m.mesh_step_nm * 1e-9
    return f'''# Generated from YAML. Open in Ansys Lumerical MODE and run in this folder.
# Effective passive InGaAsP/InP cross-section, propagation along z.
# No semiconductor gain/current is simulated by this MODE project.
# Select/verify the physical TE-like mode before using a production sweep.
switchtolayout;
deleteall;
{rectangle("InP_cladding", (xs * 1.1, ys * 1.1, 1e-6), (0, 0, 0), c.mode.cladding_index, 3, c.lumerical.cladding_material)}
{rectangle("effective_active_core", (width, thickness, 1e-6), (0, 0, 0), c.mode.core_index, 1, c.lumerical.core_material)}
addfde;
set("name","FDE");
set("solver type",3);
set("x",0); set("x span",{number(xs)});
set("y",0); set("y span",{number(ys)});
set("z",0);
setanalysis("wavelength",{number(c.source.wavelength_nm * 1e-9)});
setanalysis("number of trial modes",{m.trial_modes});
addmesh;
set("name","core_mesh");
set("x",0); set("x span",{number(width + 1e-6)});
set("y",0); set("y span",{number(thickness + 1e-6)});
set("z",0); set("z span",1e-6);
set("override x mesh",1); set("override y mesh",1);
set("dx",{number(mesh)}); set("dy",{number(mesh)});
save("inp_waveguide.lms");
nmodes=findmodes;
if (nmodes<1) {{ error("MODE found no modes. Check geometry, mesh and boundaries."); }}
x=getdata("mode1","x"); y=getdata("mode1","y");
Ex=getdata("mode1","Ex"); Ey=getdata("mode1","Ey"); Ez=getdata("mode1","Ez");
Hx=getdata("mode1","Hx"); Hy=getdata("mode1","Hy");
neff=getdata("mode1","neff");
matlabsave("mode_fields.mat",x,y,Ex,Ey,Ez,Hx,Hy,neff);
selectmode(1);
setanalysis("track selected mode",1);
setanalysis("detailed dispersion calculation",1);
setanalysis("start wavelength",{number(m.wavelength_start_nm * 1e-9)});
setanalysis("stop wavelength",{number(m.wavelength_stop_nm * 1e-9)});
setanalysis("number of points",{m.wavelength_points});
frequencysweep;
D=getdata("frequencysweep","D");
f_D=getdata("frequencysweep","f_D");
matlabsave("mode_dispersion.mat",D,f_D);
save("inp_waveguide.lms");
?"MODE finished. Inspect mode_fields.mat, mode_dispersion.mat and inp_waveguide.lms.";
'''


def fdtd_script(c: Config):
    f, d, m = c.lumerical.fdtd, c.device, c.lumerical.mode
    length, buffer = f.taper_length_um * 1e-6, f.buffer_um * 1e-6
    win, wout = c.layout.port_width_um * 1e-6, d.width_um * 1e-6
    thick = d.core_thickness_um * 1e-6
    ys, zs = f.transverse_span_um * 1e-6, f.vertical_span_um * 1e-6
    mesh = f.mesh_step_nm * 1e-9
    vertices = ";".join(f"{number(x)},{number(y)}" for x, y in [(-length / 2, -win / 2), (length / 2, -wout / 2), (length / 2, wout / 2), (-length / 2, win / 2)])
    return f'''# Open in Ansys Lumerical FDTD; run in this export folder.
# PASSIVE InP-platform taper coupon, propagation along x, vertical z.
# The current/gain rate equations and microcomb are NOT simulated by FDTD here.
# This coupon length is lumerical.fdtd.taper_length_um, not the full SOA length.
switchtolayout;
deleteall;
{rectangle("InP_cladding", (length + 2 * buffer + 2e-6, ys * 1.1, zs * 1.1), (0, 0, 0), c.mode.cladding_index, 3, c.lumerical.cladding_material)}
{rectangle("input_ridge", (buffer + 1e-6, win, thick), (-length / 2 - (buffer + 1e-6) / 2, 0, 0), c.mode.core_index, 1, c.lumerical.core_material)}
{rectangle("output_ridge", (buffer + 1e-6, wout, thick), (length / 2 + (buffer + 1e-6) / 2, 0, 0), c.mode.core_index, 1, c.lumerical.core_material)}
addpoly;
set("name","taper"); set("vertices",[{vertices}]);
set("z",0); set("z span",{number(thick)});
{setprop("material", c.lumerical.core_material or "<Object defined dielectric>")}
{setprop("index", c.mode.core_index) if not c.lumerical.core_material else "# Using native dispersive core material."}
set("override mesh order from material database",1); set("mesh order",1);
addfdtd;
set("name","FDTD"); set("dimension","3D");
set("x",0); set("x span",{number(length + 2 * buffer)});
set("y",0); set("y span",{number(ys)});
set("z",0); set("z span",{number(zs)});
set("mesh accuracy",2);
set("simulation time",{number(f.simulation_time_fs * 1e-15)});
set("x min bc","PML"); set("x max bc","PML");
set("y min bc","PML"); set("y max bc","PML");
set("z min bc","PML"); set("z max bc","PML");
addmesh; set("name","taper_mesh");
set("x",0); set("x span",{number(length + 2 * buffer)});
set("y",0); set("y span",{number(max(win, wout) + 1e-6)});
set("z",0); set("z span",{number(thick + 1e-6)});
set("override x mesh",1); set("override y mesh",1); set("override z mesh",1);
set("dx",{number(mesh)}); set("dy",{number(mesh)}); set("dz",{number(mesh)});
addmode;
set("name","pump"); set("injection axis","x-axis"); set("direction","Forward");
set("x",{number(-length / 2 - buffer / 2)});
set("y",0); set("y span",{number(ys * .8)});
set("z",0); set("z span",{number(zs * .8)});
set("mode selection","fundamental TE mode");
set("wavelength start",{number(m.wavelength_start_nm * 1e-9)});
set("wavelength stop",{number(m.wavelength_stop_nm * 1e-9)});
setglobalmonitor("frequency points",{f.wavelength_points});
addpower; set("name","T"); set("monitor type","2D X-normal");
set("x",{number(length / 2 + buffer / 2)});
set("y",0); set("y span",{number(ys * .9)}); set("z",0); set("z span",{number(zs * .9)});
addpower; set("name","R"); set("monitor type","2D X-normal");
set("x",{number(-length / 2 - buffer * .75)});
set("y",0); set("y span",{number(ys * .9)}); set("z",0); set("z span",{number(zs * .9)});
save("inp_taper.fsp");
run;
f=getdata("T","f");
T=transmission("T"); R=-transmission("R");
matlabsave("taper_transmission.mat",f,T,R);
save("inp_taper.fsp");
?"FDTD finished. These are total monitor fluxes, not a guided-mode S matrix.";
'''


def quantities(c):
    return {"source.frequency_Hz": 299792458 / (c.source.wavelength_nm * 1e-9),
            "source.power_W": c.source.input_power_mW * 1e-3,
            "device.current_A": c.device.current_mA * 1e-3,
            "device.length_m": c.device.length_um * 1e-6,
            "device.width_m": c.device.width_um * 1e-6,
            "device.active_thickness_m": c.device.active_thickness_um * 1e-6,
            "device.active_volume_m3": c.device.length_um * c.device.width_um * c.device.active_thickness_um * 1e-18,
            "thermal.ambient_K": c.thermal.ambient_K,
            "material.linewidth_enhancement_factor": c.material.linewidth_enhancement_factor}


def interconnect_script(c: Config):
    circuit = c.lumerical.interconnect
    values = quantities(c)
    lines = ["# Native INTERCONNECT SOA/CML template workflow.",
             "# Supply SOA_TEMPLATE.icp with the named components/properties from YAML.",
             "# Verify bindings with inspect-interconnect first; model names vary by version.",
             "# The template must contain the active SOA physics/current connection.",
             "# No scalar/Python gain is injected into this native model.",
             'load("SOA_TEMPLATE.icp");', "switchtodesign;"]
    for binding in circuit.bindings:
        lines.append(f"setnamed({quote(binding.element)},{quote(binding.property)},{number(values[binding.quantity])});")
    for fixed in circuit.fixed_properties:
        value = quote(fixed.value) if isinstance(fixed.value, str) else number(fixed.value)
        lines.append(f"setnamed({quote(fixed.element)},{quote(fixed.property)},{value});")
    lines += ['save("inp_pump.icp");', "run;"]
    for result in circuit.results:
        lines.append(f"{result.label}=getresult({quote(result.element)},{quote(result.result)});")
        lines.append(f"matlabsave({quote(result.label + '.mat')},{result.label});")
    lines += ['save("inp_pump.icp");', '?"INTERCONNECT finished. Verify active SOA calibration and analyzer reference planes.";']
    return "\n".join(lines) + "\n"


def export_lumerical(c: Config, output: Path):
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    f = c.lumerical.fdtd
    # Deliberately conservative uniform-mesh estimate; actual mesher/PML differ.
    cells = int(np.prod(np.ceil(np.array([f.taper_length_um + 2 * f.buffer_um,
                                        f.transverse_span_um, f.vertical_span_um]) / (f.mesh_step_nm * 1e-3))))
    plan = {"status": "scripts_generated_not_simulated", "units": "SI in native LSF",
            "mode": {"product": "MODE", "script": "mode.lsf", "project_created_when_run": "inp_waveguide.lms",
                     "physics": "passive vector FDE modes and native tracked-mode dispersion; effective index cross-section"},
            "fdtd": {"product": "FDTD", "script": "fdtd.lsf", "project_created_when_run": "inp_taper.fsp",
                     "physics": "passive 3-D taper transmission/reflection, not active SOA gain",
                     "estimated_uniform_mesh_cells": cells, "cell_limit": f.max_estimated_cells,
                     "estimate_note": "Only a planning estimate; inspect actual mesh, memory and run time in Lumerical."},
            "interconnect": {"product": "INTERCONNECT", "script": "interconnect.lsf",
                             "requires": "A native SOA/CML template with verified bindings and semiconductor gain data",
                             "template_configured": bool(c.lumerical.interconnect.template_path),
                             "project_created_when_run": "inp_pump.icp"},
            "microcomb": {"status": "no_native_kerr_comb_solver_exported",
                          "note": "The included Python LLE is an optional separate reference model, not a Lumerical result."},
            "scope": "No licensed Lumerical simulation is implied by a successful export."}
    for name, text in [("mode.lsf", mode_script(c)), ("fdtd.lsf", fdtd_script(c)),
                       ("interconnect.lsf", interconnect_script(c))]:
        (output / name).write_text(text, encoding="utf-8")
    (output / "simulation_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    import yaml
    (output / "resolved_config.yaml").write_text(yaml.safe_dump(c.model_dump(), sort_keys=False))
    (output / "README.txt").write_text(
        "Generated Lumerical scripts; no simulation has run yet.\n"
        "In MODE/FDTD: set the working directory to this folder, open the corresponding .lsf and run.\n"
        "Native .lms/.fsp/.icp and .mat results are created by Lumerical, not by script export.\n"
        "Active SOA: create/copy a calibrated native SOA/CML circuit as SOA_TEMPLATE.icp; inspect names/properties/results and update YAML bindings.\n"
        "See the project docs/lumerical.md for products, calibration and run commands.\n")
    return plan


def load_api(path=None):
    configured = path or os.getenv("LUMERICAL_API_PATH")
    if configured:
        folder = Path(configured).expanduser().resolve()
        if not (folder / "lumapi.py").is_file():
            raise ValueError(f"LUMERICAL_API_PATH must contain the vendor lumapi.py: {folder}")
        sys.path.insert(0, str(folder))
    try:
        return importlib.import_module("lumapi")
    except ImportError as error:
        raise RuntimeError("Ansys lumapi is unavailable. Install licensed Lumerical and set LUMERICAL_API_PATH to its api/python folder, or run the exported .lsf scripts in the Lumerical GUI. Do not pip-install an unrelated lumapi package.") from error


def _json_result(data):
    if isinstance(data, dict):
        return {str(k): _json_result(v) for k, v in data.items()}
    if isinstance(data, np.ndarray):
        if np.iscomplexobj(data):
            return {"real": data.real.tolist(), "imag": data.imag.tolist()}
        return data.tolist()
    if isinstance(data, (np.floating, np.integer)):
        return data.item()
    if isinstance(data, (complex, np.complexfloating)):
        return {"real": float(data.real), "imag": float(data.imag)}
    if isinstance(data, np.bool_):
        return bool(data)
    return data


def inspect_interconnect(c: Config, *, template: Path, api_path=None):
    if not template.is_file():
        raise ValueError(f"Native INTERCONNECT template not found: {template}")
    api = load_api(api_path)
    output = {}
    with api.INTERCONNECT(hide=c.lumerical.hide_gui) as session:
        session.load(str(template.resolve()))
        elements = sorted({b.element for b in c.lumerical.interconnect.bindings} | {r.element for r in c.lumerical.interconnect.results}
                          | {b.element for b in c.lumerical.interconnect.fixed_properties}
                          | set(c.lumerical.interconnect.inspect_elements))
        for name in elements:
            entry = {}
            try:
                entry["properties"] = session.getnamed(name)
            except Exception as error:
                entry["properties_error"] = str(error)
            try:
                entry["results"] = session.getresult(name)
            except Exception as error:
                entry["results_error"] = str(error)
            output[name] = _json_result(entry)
    return output


def run_lumerical(c: Config, solver: str, output: Path, *, api_path=None, config_directory=None):
    # Fail early on missing vendor runtime; never mark export as a solver success.
    api = load_api(api_path)
    template = None
    if solver == "interconnect":
        value = c.lumerical.interconnect.template_path
        if not value:
            raise ValueError("Active SOA run requires lumerical.interconnect.template_path and verified template-specific bindings. See docs/lumerical.md.")
        template = Path(value).expanduser()
        if not template.is_absolute():
            template = Path(config_directory or Path.cwd()) / template
        template = template.resolve()
        if not template.is_file():
            raise ValueError(f"SOA template not found: {template}")
        if not c.lumerical.interconnect.results:
            raise ValueError("Configure at least one native INTERCONNECT result to verify the active run.")
    plan = export_lumerical(c, output)
    output = output.resolve()
    if solver == "fdtd" and plan["fdtd"]["estimated_uniform_mesh_cells"] > c.lumerical.fdtd.max_estimated_cells:
        raise ValueError("FDTD estimate exceeds max_estimated_cells. Review domain/mesh/resources and adjust YAML deliberately; no solver was launched.")
    status = {"solver": solver, "status": "starting", "results_verified": False,
              "config_sha256": hashlib.sha256(json.dumps(c.model_dump(), sort_keys=True).encode()).hexdigest(),
              "api_module_path": getattr(api, "__file__", None)}
    status_path = output / "run_status.json"
    status_path.write_text(json.dumps(status, indent=2) + "\n")
    try:
        constructor = {"mode": api.MODE, "fdtd": api.FDTD, "interconnect": api.INTERCONNECT}[solver]
        with constructor(hide=c.lumerical.hide_gui) as session:
            session.eval(f"cd({quote(output.as_posix())});")
            script = (output / f"{solver}.lsf").read_text()
            if template:
                # Bindings are verified by native getters before applying any changes.
                session.load(str(template))
                for b in c.lumerical.interconnect.bindings:
                    session.getnamed(b.element, b.property)
                for b in c.lumerical.interconnect.fixed_properties:
                    session.getnamed(b.element, b.property)
                script = script.replace('load("SOA_TEMPLATE.icp");', f"load({quote(template.as_posix())});")
            session.eval(script)
            if solver == "mode":
                _save_mode_metrics(session, c, output)
                required = ["inp_waveguide.lms", "mode_fields.mat", "mode_dispersion.mat", "mode_metrics.json"]
            elif solver == "fdtd":
                from .artifacts import csv
                freq, t, r = [np.asarray(session.getv(key)).reshape(-1) for key in ["f", "T", "R"]]
                if not (len(freq) == len(t) == len(r) and len(freq) >= 3 and np.all(np.isfinite(t)) and np.all(np.isfinite(r))):
                    raise RuntimeError("FDTD did not return finite transmission/reflection spectra")
                csv(output / "taper_transmission.csv", {"wavelength_nm": 299792458 / freq * 1e9, "T_total_flux": t, "R_total_flux": r})
                required = ["inp_taper.fsp", "taper_transmission.mat", "taper_transmission.csv"]
            else:
                for r in c.lumerical.interconnect.results:
                    data = session.getresult(r.element, r.result)
                    if data is None or (isinstance(data, dict) and not data):
                        raise RuntimeError(f"Native analyzer returned no data: {r.element}/{r.result}")
                    (output / f"{r.label}.json").write_text(json.dumps(_json_result(data), indent=2, allow_nan=False) + "\n")
                required = ["inp_pump.icp", *[r.label + ".mat" for r in c.lumerical.interconnect.results]]
        for name in required:
            if not (output / name).is_file() or (output / name).stat().st_size == 0:
                raise RuntimeError(f"Native simulation did not create the expected artifact: {name}")
        status.update(status="completed", results_verified=True, artifacts=required,
                      note="Native solver execution verified; device calibration/convergence remain separate requirements.")
    except Exception as error:
        status.update(status="failed", error=str(error))
        raise RuntimeError(f"Lumerical {solver} failed: {error}. Check the installed version, license and generated script/template.") from error
    finally:
        status_path.write_text(json.dumps(status, indent=2) + "\n")
    return status


def _save_mode_metrics(session, c, output):
    # Native vector fields. This uses power flux for active-region overlap.
    x, y = [np.asarray(session.getv(key)).reshape(-1) for key in ["x", "y"]]
    nx, ny = len(x), len(y)

    def field(key):
        array = np.asarray(session.getv(key)).squeeze()
        if array.shape == (nx, ny):
            return array
        if array.shape == (ny, nx):
            return array.T
        raise RuntimeError(f"Unexpected MODE field shape {array.shape}")

    ex, ey, ez, hx, hy = [field(key) for key in ["Ex", "Ey", "Ez", "Hx", "Hy"]]
    intensity = np.abs(ex)**2 + np.abs(ey)**2 + np.abs(ez)**2
    flux = 0.5 * np.real(ex * np.conj(hy) - ey * np.conj(hx))
    xx, yy = np.meshgrid(x, y, indexing="ij")
    # Cell-average mask avoids silently missing a very thin active stripe.
    dx, dy = np.gradient(x), np.gradient(y)
    fx = np.clip((c.device.width_um * 0.5e-6 - np.abs(x)) / dx + 0.5, 0, 1)
    fy = np.clip((c.device.active_thickness_um * 0.5e-6 - np.abs(y)) / dy + 0.5, 0, 1)
    mask = fx[:, None] * fy[None, :]
    trap = getattr(np, "trapezoid", None) or np.trapz

    def integrate(a):
        return trap(trap(a, x=y, axis=1), x=x, axis=0)

    total_flux = float(integrate(flux))
    if not np.isfinite(total_flux) or abs(total_flux) < np.finfo(float).tiny:
        raise RuntimeError("MODE returned no finite propagating modal power")
    gamma = float(integrate(flux * mask) / total_flux)
    area = float(integrate(intensity)**2 / integrate(intensity**2))
    neff = np.asarray(session.getv("neff")).squeeze()
    metrics = dict(engine="Ansys Lumerical MODE vector FDE", mode="mode1 (verify TE-like identity in GUI)",
                   neff_real=float(np.real(neff)), neff_imag=float(np.imag(neff)),
                   active_power_overlap=gamma, scalar_field_area_um2=area * 1e12,
                   note="Overlap is from native vector Poynting flux; area is the scalar |E| definition. Effective passive index geometry is not a resolved QW gain calculation.")
    if not np.isfinite(area) or area <= 0 or not -0.01 <= gamma <= 1.01:
        raise RuntimeError("Unphysical native-mode overlap/area; inspect mode identity and field coordinates")
    (output / "mode_metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n")
