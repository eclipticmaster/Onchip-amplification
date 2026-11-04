"""CSV/plots plus a portable HTML report with embedded figures."""
import base64
import html
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def csv(path, columns):
    np.savetxt(path, np.column_stack(list(columns.values())), delimiter=",", header=",".join(columns), comments="")


def savefig(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_mode(output, c, m):
    if m.intensity is None:
        return
    xx, yy = np.meshgrid(m.x, m.y, indexing="ij")
    csv(output / "mode.csv", dict(x_um=xx.ravel(), y_um=yy.ravel(), intensity_per_um2=m.intensity.ravel(), index=m.index.ravel()))
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, a, title in zip(axes, [m.index, m.intensity], ["Scalar index model", "Fundamental scalar mode |E|²"]):
        image = ax.pcolormesh(m.x, m.y, a.T, shading="auto")
        ax.axhline(c.device.active_thickness_um / 2, color="white", lw=0.6, ls="--")
        ax.axhline(-c.device.active_thickness_um / 2, color="white", lw=0.6, ls="--")
        ax.set(xlabel="x (um)", ylabel="y (um)", title=title)
        fig.colorbar(image, ax=ax)
    savefig(fig, output / "mode.png")


def write_soa(output, c, r):
    centers = (r.z_m[:-1] + r.z_m[1:]) / 2
    csv(output / "longitudinal.csv", dict(z_um=centers * 1e6, carriers_m3=r.carriers_m3,
                                         signal_mW=(r.signal_W[:-1] + r.signal_W[1:]) * 500,
                                         modal_gain_per_m=r.modal_gain_per_m,
                                         forward_ase_mW=(r.ase_forward_W[:-1] + r.ase_forward_W[1:]).sum(axis=1) * 500,
                                         backward_ase_mW=(r.ase_backward_W[:-1] + r.ase_backward_W[1:]).sum(axis=1) * 500))
    psd = r.ase_forward_W[-1] * 10**(-c.device.output_loss_dB / 10) / r.ase_bin_width_Hz
    rbw = 299792458 * c.numerics.osnr_bandwidth_nm * 1e-9 / (r.ase_wavelength_nm * 1e-9)**2
    order = np.argsort(r.ase_wavelength_nm)
    csv(output / "ase_spectrum.csv", dict(wavelength_nm=r.ase_wavelength_nm[order],
                                         output_ase_W_per_Hz=psd[order], output_ase_dBm_per_RBW=10 * np.log10(np.maximum(psd[order] * rbw[order] * 1e3, 1e-30))))
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    axes[0].plot(r.z_m * 1e6, r.signal_W * 1e3, label="Signal")
    axes[0].plot(r.z_m * 1e6, r.ase_forward_W.sum(axis=1) * 1e3, label="ASE +")
    axes[0].plot(r.z_m * 1e6, r.ase_backward_W.sum(axis=1) * 1e3, label="ASE -")
    axes[0].set(xlabel="z (um)", ylabel="Internal power (mW)", title="Traveling-wave propagation")
    axes[0].legend()
    axes[1].plot(centers * 1e6, r.carriers_m3 / 1e24)
    axes[1].set(xlabel="z (um)", ylabel="N (10²⁴ m⁻³)", title="Carrier depletion")
    axes[2].plot(r.ase_wavelength_nm[order], 10 * np.log10(np.maximum(psd[order] * rbw[order] * 1e3, 1e-30)))
    axes[2].axvline(c.source.wavelength_nm, color="black", ls="--", label="Pump wavelength")
    axes[2].set(xlabel="Wavelength (nm)", ylabel=f"ASE (dBm / {c.numerics.osnr_bandwidth_nm:g} nm)", title="Output ASE, two polarizations")
    for ax in axes:
        ax.grid(alpha=0.2)
    savefig(fig, output / "amplifier.png")


def write_sweeps(output, sweeps):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for name, rows in sweeps.items():
        # Null noise metrics remain NaN in numeric CSV; JSON report uses null.
        csv(output / f"sweep_{name}.csv", {k: np.array([row[k] if row[k] is not None else np.nan for row in rows]) for k in rows[0]})
    current, power = sweeps["current"], sweeps["input_power"]
    axes[0].plot([r["current_mA"] for r in current], [r["output_power_mW"] for r in current], "o-")
    axes[0].set(xlabel="Current (mA)", ylabel="Output signal (mW)", title="Current sweep")
    axes[1].semilogx([r["input_power_mW"] for r in power], [r["gain_dB"] for r in power], "o-")
    axes[1].set(xlabel="Input signal (mW)", ylabel="Gain (dB)", title="Gain saturation")
    axes[2].plot([r["current_mA"] for r in current], [r["junction_temperature_K"] for r in current], "o-")
    axes[2].set(xlabel="Current (mA)", ylabel="Junction temperature (K)", title="Lumped thermal estimate")
    for ax in axes:
        ax.grid(alpha=0.2)
    savefig(fig, output / "sweeps.png")


def write_transient(output, t):
    csv(output / "transient.csv", t)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, key, label in zip(axes, ["current_mA", "output_power_mW", "chirp_GHz"], ["Injection current (mA)", "Output signal (mW)", "Transient chirp (GHz)"]):
        ax.plot(t["time_ns"], t[key])
        ax.set(xlabel="Time (ns)", ylabel=label)
        ax.grid(alpha=0.2)
    fig.suptitle("Lumped carrier transient (ASE omitted, temperature held fixed)")
    savefig(fig, output / "transient.png")


def write_microcomb(output, c, r):
    order = np.argsort(r["mu"])
    csv(output / "microcomb_spectrum.csv", dict(mode_number=r["mu"][order], wavelength_nm=r["wavelength_nm"][order],
                                               resonator_leakage_mW=r["leakage_mW"][order]))
    tr = r["trace"]
    csv(output / "microcomb_trace.csv", dict(normalized_time=tr[:, 0], normalized_detuning=tr[:, 1], intracavity_normalized_power=tr[:, 2],
                                            pump_normalized_power=tr[:, 3], sideband_normalized_power=tr[:, 4]))
    theta = np.arange(c.microcomb.modes) * 2 * np.pi / c.microcomb.modes
    csv(output / "microcomb_waveform.csv", dict(azimuth_rad=theta, intracavity_circulating_power_W=np.abs(r["field"])**2 * r["intracavity_scale_W"]))
    np.savez_compressed(output / "microcomb_fields.npz", azimuth_rad=theta, normalized_field=r["field"],
                        mode_number=r["mu"], spectral_history=r["spectral_history"], trace=tr)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes[0, 0].plot(r["mu"][order], 10 * np.log10(np.maximum(r["leakage_mW"][order], 1e-12)))
    axes[0, 0].set(xlabel="Mode number", ylabel="Resonator leakage (dBm)", title="Final LLE spectrum (not through-port power)")
    axes[0, 1].plot(theta, np.abs(r["field"])**2 * r["intracavity_scale_W"])
    axes[0, 1].set(xlabel="Azimuth (rad)", ylabel="Circulating power (W)", title="Final intracavity waveform")
    axes[1, 0].plot(tr[:, 0], tr[:, 2], label="Total")
    axes[1, 0].plot(tr[:, 0], tr[:, 4], label="Sidebands")
    axes[1, 0].set(xlabel="Normalized time (κt/2)", ylabel="Normalized power", title="Scan + hold evolution")
    axes[1, 0].legend()
    hist = 10 * np.log10(np.maximum(r["spectral_history"][:, order], 1e-10))
    im = axes[1, 1].pcolormesh(r["mu"][order], tr[:, 0], hist, shading="auto", vmin=-70)
    axes[1, 1].set(xlabel="Mode number", ylabel="Normalized time", title="Spectral evolution (dB, normalized)")
    fig.colorbar(im, ax=axes[1, 1])
    savefig(fig, output / "microcomb.png")


def write_report(output: Path, summary):
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    esc = html.escape
    sections = []
    for section in ["mode", "amplifier", "microcomb", "numerical_checks"]:
        if section not in summary:
            continue
        rows = "".join(f"<tr><td>{esc(key)}</td><td>{esc(f'{value:.7g}' if isinstance(value, float) else str(value))}</td></tr>" for key, value in summary[section].items())
        sections.append(f"<h2>{esc(section.replace('_', ' ').title())}</h2><table>{rows}</table>")
    figures = []
    for name in ["layout", "mode", "amplifier", "sweeps", "transient", "microcomb"]:
        path = output / f"{name}.png"
        if path.exists():
            encoded = base64.b64encode(path.read_bytes()).decode()
            figures.append(f'<h2>{name.title()}</h2><img alt="{name}" src="data:image/png;base64,{encoded}">')
    warnings = "".join(f"<li>{esc(w)}</li>" for w in summary["warnings"])
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>InP amplifier / microcomb study</title><style>body{{font:16px system-ui;max-width:1160px;margin:40px auto;padding:0 24px;color:#162338;background:#f6f8fa}}h1,h2{{color:#174a7e}}img{{width:100%;background:white;border-radius:8px}}table{{border-collapse:collapse;background:white;width:100%}}td{{padding:7px 12px;border-bottom:1px solid #ddd}}.note{{padding:16px;background:#fff3cd;border-radius:8px}}code{{overflow-wrap:anywhere}}</style>
<h1>{esc(summary['name'])}</h1><p class="note">Parameter status: <b>{esc(summary['parameter_status'])}</b>. This report is a reduced-order research simulation. It is not a measured InP amplifier prediction, a fabrication-qualified design, or proof of a stable soliton.</p>
<p>{esc(summary['calibration_notes'])}</p><p>Workflow: CW pump → InP-platform SOA → link loss → Kerr resonator. The ASE calculation and LLE are coupled through average signal power only; no calibrated noise or optical feedback is transferred.</p>
<p>Run ID: <code>{esc(summary['run_id'])}</code> · Configuration SHA256: <code>{esc(summary['config_sha256'])}</code></p>
<h2>Model notes / warnings</h2><ul>{warnings}</ul>{''.join(sections)}{''.join(figures)}
<p>Numerical data, resolved_config.yaml, metadata.json, and design.gds are stored beside this report. See the project documentation for equations, convergence checks and references.</p></html>'''
    (output / "report.html").write_text(page, encoding="utf-8")
