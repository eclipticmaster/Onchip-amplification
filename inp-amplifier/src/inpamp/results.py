"""Read and plot native result files. No field propagation or device models."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat


def read_results(path: Path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Native result file not found: {path}. Run/export from Lumerical first.")
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text())
    if path.suffix.lower() != ".mat":
        raise ValueError("Read a native .mat export or the runner's .json dataset")
    try:
        return {k: v for k, v in loadmat(path, simplify_cells=True).items() if not k.startswith("__")}
    except (NotImplementedError, ValueError) as error:
        import h5py
        if not h5py.is_hdf5(path):
            raise ValueError(f"Unreadable native MAT export: {path}") from error
        with h5py.File(path, "r") as handle:
            return {key: _hdf5_value(handle, value) for key, value in handle.items() if not key.startswith("#")}


def _hdf5_value(handle, node, chain=()):
    import h5py
    if node.name in chain:
        raise ValueError("Cyclic MATLAB object references in result file")
    chain = (*chain, node.name)
    if isinstance(node, h5py.Group):
        result = {key: _hdf5_value(handle, value, chain) for key, value in node.items()}
        if set(result) == {"real", "imag"}:
            return result["real"] + 1j * result["imag"]
        return result
    array = node[()]
    if h5py.check_dtype(ref=node.dtype) is not None:
        values = [_hdf5_value(handle, handle[ref], chain) if ref else None for ref in array.flat]
        return values[0] if len(values) == 1 else values
    if array.dtype.names and {"real", "imag"}.issubset(array.dtype.names):
        array = array["real"] + 1j * array["imag"]
    # MATLAB HDF5 numeric datasets store the dimensions in reverse order.
    return array.transpose() if array.ndim > 1 else array


def select(data, field):
    value = data
    for part in field.split("."):
        try:
            value = value[part] if isinstance(value, dict) else value[int(part)]
        except (KeyError, ValueError, TypeError, IndexError) as error:
            raise ValueError(f"Result field not found: {field}. Use inspect-results to list paths.") from error
    # The JSON runner preserves complex arrays explicitly, not as strings.
    if isinstance(value, dict) and set(value) == {"real", "imag"}:
        return np.asarray(value["real"]) + 1j * np.asarray(value["imag"])
    return value


def describe_results(path):
    entries = []

    def walk(value, prefix):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{prefix}.{key}" if prefix else str(key))
        else:
            try:
                array = np.asarray(value)
                entries.append({"field": prefix, "shape": list(array.shape), "dtype": str(array.dtype)})
            except (TypeError, ValueError):
                if isinstance(value, list):
                    for index, child in enumerate(value):
                        walk(child, f"{prefix}.{index}")
    walk(read_results(path), "")
    return entries


def numeric(value, label, *, component=None):
    array = np.asarray(value).squeeze()
    if array.dtype.kind not in "iufc" or not np.all(np.isfinite(array)) or array.size == 0:
        raise ValueError(f"{label} must contain finite, nonempty numeric data exported by Lumerical")
    if component == "real":
        array = np.real(array)
    elif component == "imag":
        array = np.imag(array)
    elif component == "abs":
        array = np.abs(array)
    elif np.iscomplexobj(array):
        if np.any(array.imag != 0):
            raise ValueError(f"{label} is complex; select --component real, imag or abs")
        array = array.real
    return array


def vector(value, label, **kwargs):
    array = numeric(value, label, **kwargs)
    if array.ndim != 1 or array.size < 2:
        raise ValueError(f"{label} must be a vector with at least two samples; select a trace explicitly")
    return array


def write_csv(path, columns):
    arrays = [np.asarray(value).reshape(-1) for value in columns.values()]
    if not arrays or len({len(a) for a in arrays}) != 1:
        raise ValueError("CSV columns must have equal lengths")
    np.savetxt(path, np.column_stack(arrays), delimiter=",", header=",".join(columns), comments="")


def _new_output(output):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Analysis directory is not empty: {output}; choose a new --output directory")
    output.mkdir(parents=True, exist_ok=True)
    return output


def _check_status(directory):
    path = directory / "run_status.json"
    if not path.exists():
        return "GUI/native exports; execution not verified by this Python runner"
    status = json.loads(path.read_text())
    if status.get("status") != "completed" or status.get("results_verified") is not True:
        raise ValueError("Native run is not completed/verified; refusing to plot partial or failed run data")
    return "Native run completed and files verified by the runner"


def _record(output, sources, artifacts, note):
    manifest = dict(operation="plot_existing_Lumerical_results", simulation_performed=False,
                    source_status=note, source_files={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                    artifacts=artifacts)
    (output / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def _save(fig, path):
    try:
        fig.tight_layout()
        fig.savefig(path, dpi=180)
    finally:
        plt.close(fig)


def plot_native(directory: Path, solver, output: Path, *, result=None, x_field=None,
                y_field=None, x_label=None, y_label=None, component=None):
    directory = Path(directory).resolve()
    status_note = _check_status(directory)
    sources, artifacts = [], []
    if solver == "mode":
        sources = [directory / name for name in ["mode_fields.mat", "mode_metrics.mat", "mode_dispersion.mat"]]
        fields, metrics, dispersion = [read_results(p) for p in sources]
        x, y = vector(fields["x"], "x"), vector(fields["y"], "y")
        intensity = numeric(fields["E2"], "native E2")
        if intensity.shape != (len(x), len(y)):
            raise ValueError(f"Native E2 shape {intensity.shape} must match (len(x), len(y))")
        freq, d = vector(dispersion["f_D"], "f_D"), vector(dispersion["D"], "D")
        if len(freq) != len(d) or np.any(freq <= 0):
            raise ValueError("MODE dispersion arrays must have equal lengths and positive frequencies")
        # Display-only axis/unit conversion; dispersion/area/overlap are native.
        wavelength, d_units = 299792458 / freq * 1e9, d * 1e6
        order = np.argsort(wavelength)
        neff = np.asarray(metrics["neff"]).squeeze()
        gamma, area = numeric(metrics["Gamma"], "native Gamma"), numeric(metrics["Aeff"], "native Aeff")
        if neff.size != 1 or gamma.size != 1 or area.size != 1:
            raise ValueError("Native MODE metrics must be scalar")
        output = _new_output(output)
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        image = axes[0].pcolormesh(x * 1e6, y * 1e6, intensity.T, shading="auto")
        axes[0].set(xlabel="x (um)", ylabel="y (um)", title="Lumerical MODE: exported |E|²")
        fig.colorbar(image, ax=axes[0])
        axes[1].plot(wavelength[order], d_units[order])
        axes[1].set(xlabel="Wavelength (nm)", ylabel="D (ps/nm/km)", title="Lumerical MODE: native dispersion")
        _save(fig, output / "mode.png")
        write_csv(output / "dispersion.csv", {"wavelength_nm": wavelength[order], "D_ps_per_nm_per_km": d_units[order]})
        values = {"neff_real": float(np.real(neff)), "neff_imag": float(np.imag(neff)),
                  "active_power_overlap": float(gamma), "scalar_field_area_um2": float(area) * 1e12,
                  "calculated_by": "Lumerical mode.lsf"}
        (output / "mode_metrics.json").write_text(json.dumps(values, indent=2, allow_nan=False) + "\n")
        artifacts = ["mode.png", "dispersion.csv", "mode_metrics.json"]
    elif solver == "fdtd":
        sources = [directory / "taper_transmission.mat"]
        data = read_results(sources[0])
        f, t, r = [vector(data[key], key) for key in ["f", "T", "R"]]
        if not (len(f) == len(t) == len(r)) or np.any(f <= 0):
            raise ValueError("FDTD arrays must have equal lengths and positive frequencies")
        wavelength = 299792458 / f * 1e9
        order = np.argsort(wavelength)
        output = _new_output(output)
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(wavelength[order], t[order], label="Transmission")
        ax.plot(wavelength[order], r[order], label="Reflection")
        ax.set(xlabel="Wavelength (nm)", ylabel="Total monitor power fraction", title="Lumerical FDTD: passive taper")
        ax.legend()
        _save(fig, output / "taper.png")
        write_csv(output / "taper.csv", {"wavelength_nm": wavelength[order], "T_total_flux": t[order], "R_total_flux": r[order]})
        artifacts = ["taper.png", "taper.csv"]
    elif solver == "interconnect":
        if not result or not x_field or not y_field:
            raise ValueError("INTERCONNECT plotting needs --result FILE --x FIELD --y FIELD; use inspect-results for exact native dataset names")
        sources = [directory / result]
        data = read_results(sources[0])
        x = vector(select(data, x_field), x_field)
        y = vector(select(data, y_field), y_field, component=component)
        if len(x) != len(y):
            raise ValueError("Selected native x/y traces must have equal lengths")
        output = _new_output(output)
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(x, y)
        ax.set(xlabel=x_label or x_field, ylabel=y_label or y_field, title="Lumerical INTERCONNECT: exported trace")
        _save(fig, output / "interconnect.png")
        write_csv(output / "interconnect.csv", {"x_native_units": x, "y_native_units": y})
        artifacts = ["interconnect.png", "interconnect.csv"]
    else:
        raise ValueError(f"Unknown native solver: {solver}")
    return _record(output, sources, artifacts, status_note)


def plot_sweep(directory: Path, output: Path, *, result, field, y_label=None):
    directory = Path(directory).resolve()
    manifest_path = directory / "sweep_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("status") == "failed" or not manifest.get("cases"):
        raise ValueError("Cannot analyze a failed or empty sweep")
    x, y, sources = [], [], [manifest_path]
    for case in manifest["cases"]:
        case_dir = directory / case["directory"]
        _check_status(case_dir)
        path = case_dir / result
        value = numeric(select(read_results(path), field), field)
        if value.size != 1:
            raise ValueError("Sweep graph requires one measured scalar per case; select an explicit field/index")
        x.append(case["value"])
        y.append(value.item())
        sources.append(path)
    output = _new_output(output)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x, y, "o-")
    ax.set(xlabel=manifest["parameter"], ylabel=y_label or field, title=f"Lumerical {manifest['solver']}: {manifest['name']}")
    _save(fig, output / "sweep.png")
    write_csv(output / "sweep.csv", {"parameter_value": x, "native_measured_value": y})
    return _record(output, sources, ["sweep.png", "sweep.csv"], "Existing exported native sweep measurements")
