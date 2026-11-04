"""Case orchestration: every sweep case is solved by a native Ansys product."""
import json
from pathlib import Path

from .config import Config, with_override
from .lumerical import export_lumerical, run_lumerical


def ensure_parameter_applied(c: Config, solver, parameter):
    """Prevent a sweep of a setting that the selected native model never receives."""
    if solver == "interconnect":
        quantities = {
            "source.wavelength_nm": {"source.frequency_Hz"},
            "source.input_power_mW": {"source.power_W"},
            "device.current_mA": {"device.current_A"},
            "device.length_um": {"device.length_m", "device.active_volume_m3"},
            "device.width_um": {"device.width_m", "device.active_volume_m3"},
            "device.active_thickness_um": {"device.active_thickness_m", "device.active_volume_m3"},
            "thermal.ambient_K": {"thermal.ambient_K"},
        }
        candidates = {parameter} if parameter.startswith("parameters.") else quantities.get(parameter, set())
        if not candidates.intersection(b.quantity for b in c.lumerical.interconnect.bindings):
            raise ValueError(f"{parameter} has no binding to the native INTERCONNECT model; configure it before sweeping")
        return
    common = {"device.width_um", "device.core_thickness_um", "mode.core_index", "mode.cladding_index"}
    supported = common | ({"source.wavelength_nm", "device.active_thickness_um", "mode.x_span_um", "mode.y_span_um"} if solver == "mode" else set())
    prefix = f"lumerical.{solver}."
    if parameter not in supported and not parameter.startswith(prefix):
        raise ValueError(f"{parameter} is not used by native {solver}; choose the appropriate solver or property binding")
    if parameter in {"mode.core_index", "mode.cladding_index"}:
        material = c.lumerical.core_material if parameter == "mode.core_index" else c.lumerical.cladding_material
        if material:
            raise ValueError(f"{parameter} is ignored when a native material name is configured")
    if parameter == prefix + "max_estimated_cells":
        raise ValueError("max_estimated_cells is a planning limit, not a simulated device parameter")


def run_sweep(c: Config, name: str, output: Path, *, api_path=None, config_directory=None,
              export_only=False, progress=print):
    matches = [s for s in c.sweeps if s.name == name]
    if not matches:
        raise ValueError(f"Unknown native sweep: {name}")
    sweep = matches[0]
    ensure_parameter_applied(c, sweep.solver, sweep.parameter)
    # Validate every case before launching anything.
    cases = [with_override(c, sweep.parameter, value) for value in sweep.values]
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    manifest = dict(name=name, solver=sweep.solver, parameter=sweep.parameter,
                    engine="Ansys Lumerical", status="starting", cases=[])
    path = output / "sweep_manifest.json"
    try:
        for index, (value, case) in enumerate(zip(sweep.values, cases)):
            directory = output / f"case_{index:03d}"
            entry = dict(value=value, directory=directory.name, status="starting")
            manifest["cases"].append(entry)
            path.write_text(json.dumps(manifest, indent=2) + "\n")
            progress(f"{sweep.solver}: {sweep.parameter}={value:g}")
            if export_only:
                export_lumerical(case, directory)
                entry["status"] = "exported_not_simulated"
            else:
                run_lumerical(case, sweep.solver, directory, api_path=api_path,
                              config_directory=config_directory)
                entry["status"] = "completed"
        manifest["status"] = "exported_not_simulated" if export_only else "completed"
    except Exception as error:
        if manifest["cases"]:
            manifest["cases"][-1]["status"] = "failed"
        manifest.update(status="failed", error=str(error))
        raise
    finally:
        path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
