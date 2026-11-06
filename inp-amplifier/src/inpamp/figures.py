"""Publication figure exports from existing native data; no simulation models."""
from __future__ import annotations

import hashlib
import html
import json
import os
import platform
import re
import webbrowser
from pathlib import Path
from typing import Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
import yaml

from .config import UniqueLoader
from .results import _check_status, numeric, read_results, select, vector, write_csv

C0 = 299792458.0


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    title: str | None = None
    xlabel: str | None = None
    ylabel: str | None = None
    xlim: tuple[float | None, float | None] | None = None
    ylim: tuple[float | None, float | None] | None = None
    xscale: Literal["linear", "log", "symlog"] = "linear"
    yscale: Literal["linear", "log", "symlog"] = "linear"
    colors: list[str] | None = None
    cmap: str = "magma"
    clim: tuple[float, float] | None = None
    field_scale: Literal["linear", "dB"] = "linear"
    field_floor_db: float = -40.0
    linewidth: float = Field(default=1.6, gt=0)
    marker: str = ""
    grid: bool = False
    legend: bool = True
    zero_line: bool = False
    enabled: bool = True


class Trace(BaseModel):
    """Explicit native data mapping; no guesses about analyzer names or units."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    figure: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    label: str = "Native data"
    file: str
    x: str | None = None  # None means use the parameter in sweep_manifest.json.
    y: str
    denominator: str | None = None  # Same native file, scalar or matching vector.
    x_transform: Literal["identity", "frequency_to_wavelength_nm", "W_to_dBm"] = "identity"
    y_transform: Literal["identity", "W_to_dBm", "ratio_to_dB", "loss_dB"] = "identity"
    x_factor: float = 1.0
    y_factor: float = 1.0
    x_offset: float = 0.0
    y_offset: float = 0.0
    component: Literal["real", "imag", "abs"] | None = None


class Style(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    width_mm: float = Field(default=89.0, gt=0)
    height_mm: float = Field(default=66.0, gt=0)
    font_family: str = "DejaVu Sans"
    font_size: float = Field(default=9.0, gt=0)
    dpi: int = Field(default=600, ge=72, le=2400)
    formats: list[Literal["png", "pdf", "svg"]] = Field(default_factory=lambda: ["png", "pdf", "svg"])
    palette: list[str] = Field(default_factory=lambda: ["#0072B2", "#D55E00", "#009E73", "#CC79A7"])
    figures: dict[str, Options] = Field(default_factory=dict)
    traces: list[Trace] = Field(default_factory=list)
    rcparams: dict = Field(default_factory=dict)


def load_style(path=None):
    data = {} if path is None else yaml.load(Path(path).read_text(encoding="utf-8"), Loader=UniqueLoader)
    style = Style.model_validate(data or {})
    if not style.palette or not style.formats:
        raise ValueError("Figure palette and formats must not be empty")
    if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) for name in style.figures):
        raise ValueError("Figure names must be ASCII identifiers")
    return style


def _transform(value, operation):
    a = np.asarray(value, dtype=float)
    if operation == "identity":
        return a
    if operation == "frequency_to_wavelength_nm":
        if np.any(a <= 0):
            raise ValueError("Frequency-to-wavelength conversion requires positive frequencies")
        return C0 / a * 1e9
    # Zero/negative power has no finite logarithmic value: omit, never floor data.
    result = np.full(a.shape, np.nan)
    positive = a > 0
    result[positive] = 10 * np.log10(a[positive])
    if operation == "W_to_dBm":
        result[positive] += 30
    elif operation == "loss_dB":
        result = -result
    return result


class Figures:
    def __init__(self, directory, output, style):
        self.directory, self.output, self.style = directory, output, style
        self.sources, self.artifacts, self.cards = set(), [], []
        self.metrics, self.missing = {}, []
        self.config = {}
        config_path = directory / "resolved_config.yaml"
        if config_path.is_file():
            self.config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            self.sources.add(config_path)

    def read(self, filename):
        path = self.directory / filename
        self.sources.add(path)
        return read_results(path)

    def options(self, name):
        return self.style.figures.setdefault(name, Options())

    def axes(self, name, title, xlabel, ylabel):
        opt = self.options(name)
        fig, ax = plt.subplots(figsize=(self.style.width_mm / 25.4, self.style.height_mm / 25.4), layout="constrained")
        ax.set(title=title if opt.title is None else opt.title,
               xlabel=xlabel if opt.xlabel is None else opt.xlabel,
               ylabel=ylabel if opt.ylabel is None else opt.ylabel,
               xscale=opt.xscale, yscale=opt.yscale)
        if opt.xlim:
            ax.set_xlim(*opt.xlim)
        if opt.ylim:
            ax.set_ylim(*opt.ylim)
        if opt.grid:
            ax.grid(True, alpha=.2)
        else:
            ax.grid(False)
        if opt.zero_line and opt.yscale != "log":
            ax.axhline(0, color="0.6", linewidth=.6, linestyle="--", zorder=0)
        return fig, ax, opt

    def save(self, name, fig, caption, columns):
        paths = {}
        try:
            for extension in dict.fromkeys(["png", *self.style.formats]):
                path = self.output / f"{name}.{extension}"
                fig.savefig(path, dpi=self.style.dpi, metadata={"Creator": "inpamp native-result figures"} if extension == "pdf" else None)
                self.artifacts.append(path.name)
                paths[extension] = path.name
        finally:
            plt.close(fig)
        csv = self.output / f"{name}.csv"
        write_csv(csv, columns)
        self.artifacts.append(csv.name)
        self.cards.append(dict(id=name, files=paths, csv=csv.name, caption=caption))

    def lines(self, name, title, xlabel, ylabel, curves, caption, x_name="x", y_names=None):
        if not self.options(name).enabled:
            return
        fig, ax, opt = self.axes(name, title, xlabel, ylabel)
        colors = opt.colors or self.style.palette
        columns = {}
        for index, (label, x, y) in enumerate(curves):
            x, y = np.asarray(x), np.asarray(y)
            if len(x) != len(y) or not np.any(np.isfinite(x) & np.isfinite(y)):
                plt.close(fig)
                raise ValueError(f"{name}: no finite paired samples for {label}")
            order = np.argsort(x, kind="stable")
            x, y = x[order], y[order]
            ax.plot(x, y, label=label, color=colors[index % len(colors)], linewidth=opt.linewidth, marker=opt.marker)
            key = (y_names[index] if y_names else re.sub(r"\W+", "_", label).strip("_")) or f"trace_{index}"
            if key in columns:
                key += f"_{index}"
            columns[f"{x_name}_{index}"] = x
            columns[key] = y
        # Different traces may have different sample counts; pad CSV with NaN.
        length = max(len(a) for a in columns.values())
        columns = {k: np.pad(np.asarray(v, float), (0, length - len(v)), constant_values=np.nan) for k, v in columns.items()}
        if len(curves) > 1 and opt.legend:
            ax.legend(frameon=False)
        self.save(name, fig, caption, columns)

    def mode(self):
        fields = self.read("mode_fields.mat")
        metrics = self.read("mode_metrics.mat")
        dispersion = self.read("mode_dispersion.mat")
        x, y = vector(fields["x"], "x"), vector(fields["y"], "y")
        e2 = numeric(fields["E2"], "native |E| squared")
        if e2.shape != (len(x), len(y)) or np.any(e2 < 0) or e2.max() <= 0:
            raise ValueError("Native E2 must be a positive field map with shape (len(x), len(y))")
        norm = e2 / e2.max()
        neff = np.asarray(metrics["neff"]).squeeze()
        gamma, area = numeric(metrics["Gamma"], "Gamma"), numeric(metrics["Aeff"], "Aeff")
        if neff.size != 1 or not np.isfinite(neff) or gamma.size != 1 or area.size != 1:
            raise ValueError("MODE metrics must be finite scalars")
        self.metrics.update(neff_real=float(neff.real), neff_imag=float(neff.imag),
                            active_power_overlap=float(gamma.item()), effective_area_um2=float(area.item()) * 1e12)
        name = "mode_intensity"
        if self.options(name).enabled:
            fig, ax, opt = self.axes(name, "Mode intensity", r"$x$ ($\mu$m)", r"$y$ ($\mu$m)")
            displayed = norm
            color_label = r"$|E|^2\,/\,\max(|E|^2)$"
            if opt.field_scale == "dB":
                if opt.field_floor_db >= 0:
                    raise ValueError("field_floor_db must be negative")
                displayed = 10 * np.log10(np.maximum(norm, 10 ** (opt.field_floor_db / 10)))
                color_label = r"Normalized $|E|^2$ (dB)"
            clim = opt.clim or ((opt.field_floor_db, 0) if opt.field_scale == "dB" else (0, 1))
            image = ax.pcolormesh(x * 1e6, y * 1e6, displayed.T, cmap=opt.cmap, vmin=clim[0], vmax=clim[1], shading="auto", rasterized=True)
            ax.set_aspect("equal")
            device = self.config.get("device", {})
            if {"width_um", "core_thickness_um"} <= device.keys():
                w, h = device["width_um"], device["core_thickness_um"]
                ax.add_patch(Rectangle((-w / 2, -h / 2), w, h, fill=False, edgecolor="white", linewidth=.7))
                if "active_thickness_um" in device:
                    a = device["active_thickness_um"]
                    ax.add_patch(Rectangle((-w / 2, -a / 2), w, a, fill=False, edgecolor="#56B4E9", linewidth=.8, linestyle="--"))
            fig.colorbar(image, ax=ax, label=color_label, shrink=.8)
            xx, yy = np.meshgrid(x * 1e6, y * 1e6, indexing="ij")
            self.save(name, fig, "Native MODE intensity, normalized to its peak. White: effective core; dashed blue: configured active stripe when geometry metadata is available. Display normalization does not change the exported field. A scalar intensity map alone does not establish polarization or single-mode operation.",
                      {"x_um": xx.ravel(), "y_um": yy.ravel(), "E2_native": e2.ravel(), "E2_normalized": norm.ravel()})
        ix, iy = np.argmin(abs(x)), np.argmin(abs(y))
        self.lines("mode_profiles", "Mode cross-sections", r"Coordinate ($\mu$m)", "Normalized intensity",
                   [(f"Lateral (y={y[iy] * 1e6:.3g} µm)", x * 1e6, norm[:, iy]),
                    (f"Vertical (x={x[ix] * 1e6:.3g} µm)", y * 1e6, norm[ix, :])],
                   "Slices through the grid points nearest x=0 and y=0, sharing the same global peak normalization. These are intensity profiles, not integrated power fractions.", x_name="coordinate_um")
        f, d = vector(dispersion["f_D"], "f_D"), vector(dispersion["D"], "D")
        if len(f) != len(d) or np.any(f <= 0):
            raise ValueError("Native dispersion and positive frequency arrays must have equal lengths")
        wavelength = C0 / f * 1e9
        self.lines("waveguide_dispersion", "Waveguide dispersion", "Wavelength (nm)", r"$D$ (ps nm$^{-1}$ km$^{-1}$)",
                   [("D", wavelength, d * 1e6)],
                   "Native tracked-mode dispersion D. This is the straight effective SOA waveguide, not the SiN resonator integrated dispersion. Fixed-index materials include waveguide dispersion but omit physical material dispersion.", x_name="wavelength_nm", y_names=["D_ps_nm_km"])
        beta2 = -(C0 / f) ** 2 * d / (2 * np.pi * C0) * 1e27
        self.lines("waveguide_beta2", "Group-velocity dispersion", "Wavelength (nm)", r"$\beta_2$ (fs$^2$ mm$^{-1}$)",
                   [("beta2", wavelength, beta2)],
                   "Algebraic conversion of exported D: beta2 = -lambda² D / (2πc). Positive beta2 is normal dispersion; negative beta2 is anomalous. This conversion supplies no resonator frequencies or soliton prediction.", x_name="wavelength_nm", y_names=["beta2_fs2_mm"])
        self.missing.extend(["Confinement/area versus geometry requires a completed native MODE parameter sweep.",
                             "SOA output power, saturation, gain bandwidth, ASE and noise figure require a configured native SOA circuit and analyzer exports.",
                             "Comb spectra, integrated resonator dispersion, detuning scans and RF/RIN spectra require the corresponding resonator/dynamics/noise data."])

    def fdtd(self):
        data = self.read("taper_transmission.mat")
        f, t, r = [vector(data[k], k) for k in ["f", "T", "R"]]
        if not len(f) == len(t) == len(r) or np.any(f <= 0):
            raise ValueError("FDTD arrays must have equal lengths and positive frequency")
        wl = C0 / f * 1e9
        for name, title, y, label in [("taper_transmission", "Passive taper transmission", t, "T"),
                                      ("taper_reflection", "Passive taper reflection", r, "R")]:
            self.lines(name, title, "Wavelength (nm)", "Power fraction", [(label, wl, y)],
                       "Total native monitor flux normalized to source power; this is not a guided-mode S parameter.", "wavelength_nm", [label])
        for name, title, value, operation, ylabel in [
            ("taper_insertion_loss", "Passive taper insertion loss", t, "loss_dB", r"$-10\log_{10}T$ (dB)"),
            ("taper_reflection_db", "Passive taper reflection", r, "ratio_to_dB", r"$10\log_{10}R$ (dB)")]:
            if np.any(value > 0):
                self.lines(name, title, "Wavelength (nm)", ylabel, [(name, wl, _transform(value, operation))],
                           "Converted from total monitor flux. Nonpositive values have no finite logarithm and are omitted, not replaced by a numerical floor. Reflection is signed dB, not positive return loss. Guided-mode insertion loss requires native mode-expansion/port data.", "wavelength_nm", [name + "_dB"])
        self.lines("taper_power_balance", "Monitor power balance", "Wavelength (nm)", "Power fraction",
                   [("T + R", wl, t + r), ("1 − T − R", wl, 1 - t - r)],
                   "The residual can include radiation, absorption, uncollected flux and numerical error. It is not independently measured absorption; no clipping or passivity correction has been applied.", "wavelength_nm", ["T_plus_R", "uncollected_residual"])
        self.missing.append("Total monitor flux does not identify the transmitted guided mode; add native ports/mode expansion for modal coupling efficiency.")

    def sweep(self, manifest):
        if manifest.get("status") != "completed" or not manifest.get("cases"):
            raise ValueError("Publication plots require a completed, nonempty native sweep")
        if manifest.get("solver") != "mode":
            self.missing.append("Map your native sweep measurements using traces in figures.yaml (x: null uses the swept parameter).")
            return
        x, neff, gamma, area = [], [], [], []
        for case in manifest["cases"]:
            folder = self.directory / case["directory"]
            _check_status(folder)
            data = self.read(str(Path(case["directory"]) / "mode_metrics.mat"))
            values = [np.asarray(data[k]).squeeze() for k in ["neff", "Gamma", "Aeff"]]
            if any(v.size != 1 or not np.isfinite(v) for v in values):
                raise ValueError("MODE sweep metrics must be finite scalars")
            x.append(case["value"])
            neff.append(float(values[0].real))
            gamma.append(float(values[1].real))
            area.append(float(values[2].real) * 1e12)
        parameter = manifest["parameter"]
        for name, title, values, ylabel in [
            ("sweep_neff", "Effective index", neff, r"Re($n_\mathrm{eff}$)"),
            ("sweep_overlap", "Active-region overlap", gamma, r"$\Gamma$"),
            ("sweep_area", "Effective mode area", area, r"$A_\mathrm{eff}$ ($\mu$m$^2$)")]:
            self.lines(name, title, parameter, ylabel, [(name, x, values)],
                       "Native MODE metrics from each completed case. Increased confinement is not by itself evidence of increased saturation power or improved SOA performance.", "parameter", [name])

    def custom(self, sweep=None):
        grouped = {}
        for trace in self.style.traces:
            if trace.x is None:
                if not sweep or sweep.get("status") != "completed":
                    raise ValueError(f"{trace.figure}: x: null requires a completed sweep")
                xs, ys = [], []
                for case in sweep["cases"]:
                    _check_status(self.directory / case["directory"])
                    data = self.read(str(Path(case["directory"]) / trace.file))
                    value = numeric(select(data, trace.y), trace.y, component=trace.component)
                    if value.size != 1:
                        raise ValueError("Sweep traces require one explicitly selected scalar per case")
                    if trace.denominator:
                        denominator = numeric(select(data, trace.denominator), trace.denominator)
                        if denominator.size != 1 or denominator.item() <= 0:
                            raise ValueError("Sweep denominator must be a positive scalar")
                        value = value / denominator
                    xs.append(case["value"])
                    ys.append(value.item())
                x, y = np.asarray(xs), np.asarray(ys)
            else:
                data = self.read(trace.file)
                x = vector(select(data, trace.x), trace.x)
                y = vector(select(data, trace.y), trace.y, component=trace.component)
                if trace.denominator:
                    denominator = numeric(select(data, trace.denominator), trace.denominator)
                    if denominator.size not in (1, y.size) or np.any(denominator <= 0):
                        raise ValueError("Trace denominator must be positive and scalar or match y")
                    y = y / denominator
            x = _transform(x, trace.x_transform) * trace.x_factor + trace.x_offset
            y = _transform(y, trace.y_transform) * trace.y_factor + trace.y_offset
            grouped.setdefault(trace.figure, []).append((trace.label, x, y))
        for name, curves in grouped.items():
            if name in {card["id"] for card in self.cards}:
                raise ValueError(f"Custom figure name conflicts with built-in figure: {name}")
            self.lines(name, name.replace("_", " ").capitalize(), "Native x (configure xlabel)", "Native y (configure ylabel)", curves,
                       "Explicit native dataset mapping from figures.yaml. Verify source units, calibration, signal/noise separation and reference planes. Display scaling does not establish these conventions.")


def _relative_path(path, start):
    try:
        return Path(os.path.relpath(path, start)).as_posix()
    except ValueError:  # Paths on separate Windows drives retain absolute provenance.
        return None


def _same_source(old, directory, output):
    """Recognize a renamed run through relative paths and native-file hashes."""
    if old.get("operation") != "publication_figures":
        return False
    if old.get("source_directory") == str(directory):
        return True
    relative = old.get("source_directory_relative")
    if relative is not None:
        if (output / relative).resolve() != directory:
            return False
        fingerprints = old.get("source_files_relative", {})
    else:
        # Upgrade galleries created before relative provenance was recorded.
        original = Path(old.get("source_directory", ""))
        fingerprints = {str(Path(path).relative_to(original)): digest
                        for path, digest in old.get("sources", {}).items()
                        if Path(path).is_relative_to(original)}
    return bool(fingerprints) and all(
        (directory / name).is_file() and hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
        for name, digest in fingerprints.items()
    )


def create_figures(directory, output=None, *, solver="auto", style_path=None, show=False, replace=False):
    directory = Path(directory).resolve()
    output = Path(output).resolve() if output else directory / "figures"
    status = _check_status(directory) if not (directory / "sweep_manifest.json").is_file() else "Native parameter sweep"
    sweep = json.loads((directory / "sweep_manifest.json").read_text()) if (directory / "sweep_manifest.json").is_file() else None
    old_path = output / "figure_manifest.json"
    if output.exists() and any(output.iterdir()):
        if not replace or not old_path.is_file():
            raise ValueError("Figure directory exists; use --replace only for a previously generated figure directory")
        old = json.loads(old_path.read_text())
        if not _same_source(old, directory, output):
            raise ValueError("Refusing to overwrite a directory not generated for these native results")
    if output == directory:
        raise ValueError("Figure output must be separate from native result files")
    if style_path is None and (output / "figures.yaml").is_file():
        style_path = output / "figures.yaml"
    style = load_style(style_path)
    rc = {"font.family": style.font_family, "font.size": style.font_size, "axes.labelsize": style.font_size,
          "axes.titlesize": style.font_size, "xtick.labelsize": style.font_size - 1, "ytick.labelsize": style.font_size - 1,
          "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42,
          "svg.fonttype": "none", "savefig.facecolor": "white", **style.rcparams}
    # Validate rcParams and all configured colors before creating artifacts.
    for color in [*style.palette, *[c for o in style.figures.values() for c in (o.colors or [])]]:
        matplotlib.colors.to_rgba(color)
    output.mkdir(parents=True, exist_ok=True)
    figures = Figures(directory, output, style)
    if solver == "auto" and not sweep:
        run_status = directory / "run_status.json"
        if run_status.is_file():
            solver = json.loads(run_status.read_text())["solver"]
        else:
            solver = "mode" if (directory / "mode_fields.mat").is_file() else "fdtd" if (directory / "taper_transmission.mat").is_file() else "interconnect"
    with plt.rc_context(rc):
        if sweep:
            figures.sources.add(directory / "sweep_manifest.json")
            figures.sweep(sweep)
        elif solver == "mode":
            figures.mode()
        elif solver == "fdtd":
            figures.fdtd()
        elif solver == "interconnect":
            figures.missing.append("Configure traces in figures.yaml using actual analyzer fields; inspect-results lists the available paths. Gain, noise and spectral units are never guessed.")
        else:
            raise ValueError(f"Unknown solver: {solver}")
        figures.custom(sweep)
    if (directory / "run_status.json").is_file():
        figures.sources.add(directory / "run_status.json")
    style_file = output / "figures.yaml"
    style_file.write_text(yaml.safe_dump(style.model_dump(mode="json"), sort_keys=False, allow_unicode=True), encoding="utf-8")
    recipe = output / "regenerate.py"
    relative = _relative_path(directory, output)
    source_expression = f'(Path(__file__).resolve().parent / {relative!r}).resolve()' if relative is not None else f'Path({str(directory)!r})'
    recipe.write_text(
        '# Edit figures.yaml, then run this file using the project virtual-environment Python.\n'
        'from pathlib import Path\nfrom inpamp.figures import create_figures\n'
        f'create_figures({source_expression}, Path(__file__).resolve().parent, solver={solver!r},\n'
        '               style_path=Path(__file__).with_name("figures.yaml"), replace=True, show=True)\n', encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps(figures.metrics, indent=2, allow_nan=False) + "\n")
    _gallery(figures, status)
    figures.artifacts.extend(["figures.yaml", "regenerate.py", "metrics.json", "index.html"])
    manifest = dict(operation="publication_figures", source_directory=str(directory), simulation_performed=False,
                    source_directory_relative=relative,
                    source_files_relative={name: hashlib.sha256(p.read_bytes()).hexdigest()
                                           for p in sorted(figures.sources)
                                           if (name := _relative_path(p.resolve(), directory)) is not None},
                    source_status=status, sources={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(figures.sources)},
                    renderer=dict(python=platform.python_version(), matplotlib=matplotlib.__version__, numpy=np.__version__),
                    style=style.model_dump(mode="json"), figures=figures.cards, unavailable=figures.missing,
                    artifacts=figures.artifacts)
    old_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    if show:
        webbrowser.open((output / "index.html").as_uri())
    return {"gallery": str(output / "index.html"), "figures": [c["id"] for c in figures.cards],
            "style": str(style_file), "manifest": str(old_path), "unavailable": figures.missing}


def _gallery(figures, status):
    esc = html.escape
    cards = []
    for card in figures.cards:
        links = " · ".join(f'<a href="{esc(path)}">{esc(ext.upper())}</a>' for ext, path in card["files"].items())
        cards.append(f'<article><h2>{esc(card["id"].replace("_", " ").capitalize())}</h2>'
                     f'<a href="{esc(card["files"]["png"])}"><img src="{esc(card["files"]["png"])}"></a>'
                     f'<p>{esc(card["caption"])}</p><p>{links} · <a href="{esc(card["csv"])}">CSV</a></p></article>')
    rows = "".join(f'<tr><th>{esc(k)}</th><td>{v:.7g}</td></tr>' for k, v in figures.metrics.items())
    missing = "".join(f'<li>{esc(s)}</li>' for s in figures.missing)
    parameter_status = figures.config.get("parameter_status", "not provided")
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Native Lumerical figures</title><style>
body{{font:16px/1.6 system-ui,sans-serif;color:#1b2836;background:#f3f5f7;margin:0}}
main{{max-width:1150px;margin:auto;padding:32px}}h1{{margin-bottom:8px}}h2{{font-size:20px}}a{{color:#005b91}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:24px}}article,.info{{background:white;padding:24px;border:1px solid #dce2e8;border-radius:8px;margin:20px 0}}img{{width:100%;height:auto}}
th{{text-align:left;padding-right:30px}}code{{background:#e9eef2;padding:2px 5px}}p{{margin:10px 0}}article p{{font-size:14px}}
</style><main><h1>Native Lumerical figures</h1><p>{esc(status)} · Parameter status: <strong>{esc(str(parameter_status))}</strong></p>
<p>Figure formatting is ready for manuscript preparation. Physical calibration, convergence and interpretation remain part of the study.</p>
<div class="info"><h2>Edit and regenerate</h2><p>Edit <a href="figures.yaml">figures.yaml</a> for titles, labels, limits, scales, colors, markers, fonts and export sizes. Run <code>regenerate.py</code> with the project Python, or rerun <code>inpamp figures ... --replace --show</code>. Replotting uses existing data and needs no Ansys license.</p>
<p>PDF and SVG preserve vector lines/text; field maps are embedded rasters at the selected DPI. CSV contains plotted samples. Every figure has a caption explaining its scope.</p><table>{rows}</table></div>
<div class="grid">{''.join(cards)}</div><div class="info"><h2>Further measurements</h2><ul>{missing}</ul>
<p>Read <a href="https://doi.org/10.1109/JSTQE.2016.2593103">Davenport et al. (2016)</a> for SOA confinement/saturation trade-offs and <a href="https://doi.org/10.1038/s41467-019-08498-2">Raja et al. (2019)</a> for integrated soliton microcomb characterization.</p></div></main></html>'''
    (figures.output / "index.html").write_text(page, encoding="utf-8")
