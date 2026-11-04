from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml

from . import __version__
from .artifacts import write_microcomb, write_mode, write_report, write_soa, write_sweeps, write_transient
from .config import Config
from .layout import export_layout
from .microcomb import simulate_microcomb
from .mode import ModeResult, solve_mode
from .soa import solve_soa
from .transient import simulate_transient


def change(c: Config, section, **values):
    data = c.model_dump()
    data[section].update(values)
    return Config.model_validate(data)


def convergence_checks(c: Config, mode=None, baseline=None):
    mode = mode or solve_mode(c)
    baseline = baseline or solve_soa(c, mode)
    reference = baseline.summary["output_power_mW"]
    if c.numerics.z_cells * 2 > 1000 or c.numerics.ase_bins * 2 - 1 > 501:
        raise ValueError("Convergence check requires room to double the longitudinal and ASE grids")
    z_result = solve_soa(change(c, "numerics", z_cells=c.numerics.z_cells * 2), mode)
    ase_result = solve_soa(change(c, "numerics", ase_bins=c.numerics.ase_bins * 2 - 1), mode)
    result = dict(z_grid_output_relative_change=abs(z_result.summary["output_power_mW"] / reference - 1),
                  ase_grid_output_relative_change=abs(ase_result.summary["output_power_mW"] / reference - 1))
    if c.mode.enabled:
        if c.mode.nx * 2 - 1 > 501 or c.mode.ny * 2 - 1 > 501:
            raise ValueError("Convergence check requires room to double the mode grid")
        refined_mode = solve_mode(change(c, "mode", nx=c.mode.nx * 2 - 1, ny=c.mode.ny * 2 - 1))
        result["mode_confinement_relative_change"] = abs(refined_mode.confinement / mode.confinement - 1)
        result["mode_area_relative_change"] = abs(refined_mode.area_um2 / mode.area_um2 - 1)
        result["mode_neff_relative_change"] = abs(refined_mode.neff / mode.neff - 1)
    result["passed"] = all(v < 0.02 for v in result.values())
    result["scope"] = "2% refinement screen for SOA output and scalar-mode quantities; not an LLE stability certification"
    return result


def run(c: Config, output: Path, *, check=False, progress=print):
    output = output.resolve()
    # Use an empty results directory; a failed run must not inherit older artifacts.
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output directory is not empty: {output}. Choose a new --output directory.")
    output.mkdir(parents=True, exist_ok=True)
    data = c.model_dump()
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    (output / "resolved_config.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    progress("Solving transverse scalar mode...")
    mode = solve_mode(c)
    write_mode(output, c, mode)
    progress("Solving CW carriers, signal, bidirectional ASE and thermal balance...")
    amplifier = solve_soa(c, mode)
    write_soa(output, c, amplifier)
    warnings = list(amplifier.warnings)
    warnings.append("Scalar mode, effective material gain and lumped heating require calibration to the actual epitaxial stack.")
    if mode.boundary_fraction and mode.boundary_fraction > 1e-3:
        warnings.append("Mode energy near the window boundary exceeds 0.1%; enlarge mode spans and repeat the convergence check.")
    summary = dict(name=c.name, parameter_status=c.parameter_status, calibration_notes=c.calibration_notes,
                   run_id=str(uuid4()), config_sha256=digest,
                   mode=dict(confinement_factor=mode.confinement, effective_area_um2=mode.area_um2,
                             effective_index=mode.neff, boundary_energy_fraction=mode.boundary_fraction),
                   amplifier=amplifier.summary, warnings=warnings)
    if c.sweeps.enabled:
        sweeps = {}
        for name, section, parameter, values in [
            ("current", "device", "current_mA", c.sweeps.current_mA),
            ("input_power", "source", "input_power_mW", c.sweeps.input_power_mW),
        ]:
            rows = []
            for value in values:
                progress(f"Sweep {parameter}={value:g}...")
                varied = change(c, section, **{parameter: value})
                result = solve_soa(varied, mode)
                rows.append({"current_mA": varied.device.current_mA, **result.summary})
                warnings.extend(f"Sweep {parameter}={value:g}: {w}" for w in result.warnings)
            sweeps[name] = rows
        if all(sweeps.values()):
            write_sweeps(output, sweeps)
        summary["sweeps"] = sweeps
    if c.transient.enabled:
        progress("Solving lumped current-step transient...")
        write_transient(output, simulate_transient(c, mode, amplifier.summary["junction_temperature_K"]))
        warnings.append("Transient uses a lumped single-pass model without ASE; its steady output can differ from the spatial CW solution.")
    if c.microcomb.enabled:
        progress("Propagating Kerr resonator scan and hold (LLE)...")
        comb = simulate_microcomb(c, amplifier.summary["output_power_mW"])
        write_microcomb(output, c, comb)
        summary["microcomb"] = comb["summary"]
        warnings.extend(comb["warnings"])
        warnings.append("LLE uses mean delivered signal power and configurable numerical field noise; no SOA ASE/RIN transfer, thermal detuning, back-reflections or soliton stability classification.")
    if c.layout.enabled:
        progress("Exporting conceptual GDS and checking read-back...")
        export_layout(c, output)
        warnings.append("GDS is a conceptual hybrid placement with arbitrary layers, not a foundry mask or a verified optical transition.")
    if check:
        progress("Checking doubled SOA, ASE and scalar-mode grids...")
        summary["numerical_checks"] = convergence_checks(c, mode, amplifier)
        if not summary["numerical_checks"]["passed"]:
            warnings.append("Numerical grid refinement exceeded the 2% screen; refine grids before interpreting results.")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=Path(__file__).parent, text=True))
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, dirty = None, None
    source_hash = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        source_hash.update(path.name.encode())
        source_hash.update(path.read_bytes())
    metadata = dict(run_id=summary["run_id"], created_at_utc=datetime.now(timezone.utc).isoformat(),
                    inpamp_version=__version__, python=platform.python_version(),
                    platform=platform.platform(), git_commit=commit, git_dirty=dirty,
                    source_sha256=source_hash.hexdigest(), config_sha256=digest,
                    dependencies={name: importlib.metadata.version(name) for name in ["numpy", "scipy", "matplotlib", "PyYAML", "pydantic", "gdstk"]})
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    write_report(output, summary)
    progress(f"Complete. Report: {output / 'report.html'}")
    return summary
