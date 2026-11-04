"""Normalized mean-field LLE with physical SOA pump delivery.

tau=kappa*t/2; a=FFT(psi)/N. L_mu=-1-i*(alpha+2*Dint/kappa).
F^2=8*g*kappa_ex*P/(kappa^3*hbar*omega).
Uses symmetric exact linear/drive and nonlinear phase steps.
"""
import numpy as np
from scipy.constants import c as C0, hbar

from .config import Config


def integrate_lle(drive, dispersion, *, alpha_start, alpha_end, dt, scan_time, hold_time,
                  record_every=100, seed=7, field_noise_per_sqrt_tau=1e-5, kerr=True):
    n = len(dispersion)
    rng = np.random.default_rng(seed)
    psi = np.full(n, drive / (1 + 1j * alpha_start), dtype=complex)
    noise = field_noise_per_sqrt_tau
    psi += noise * (rng.normal(size=n) + 1j * rng.normal(size=n)) / np.sqrt(2)
    final_time = scan_time + hold_time
    requested_dt = dt
    # Exact linear steps alone do NOT guarantee split-step stability: rapid
    # dispersion can produce artificial high-frequency parametric growth.
    # Bound the maximum dispersion rotation per step, including unoccupied modes.
    max_dispersion = float(np.max(np.abs(dispersion)))
    if max_dispersion:
        dt = min(dt, 0.5 / max_dispersion)
    steps = int(np.ceil(final_time / dt))
    if steps > 2_000_000:
        raise RuntimeError("Dispersion-limited LLE needs >2 million steps. Reduce modes or scan/hold duration.")
    dt = final_time / steps
    traces, spectra = [], []

    def record(t, alpha):
        a = np.fft.fft(psi) / n
        total = np.sum(np.abs(a)**2)
        traces.append((t, alpha, total, np.abs(a[0])**2, total - np.abs(a[0])**2))
        spectra.append(np.abs(a)**2)

    record(0, alpha_start)
    max_nonlinear_step = 0.0
    for j in range(steps):
        t = (j + 0.5) * dt
        fraction = min(t / scan_time, 1.0) if scan_time else 1.0
        alpha = alpha_start + (alpha_end - alpha_start) * fraction
        operator = -1 - 1j * (alpha + dispersion)
        half = np.exp(operator * dt / 2)
        forcing = drive * np.expm1(operator[0] * dt / 2) / operator[0]
        a = np.fft.fft(psi) / n
        a *= half
        a[0] += forcing
        psi = np.fft.ifft(a) * n
        nonlinear_step = float(np.max(np.abs(psi)**2) * dt) if kerr else 0
        max_nonlinear_step = max(max_nonlinear_step, nonlinear_step)
        if nonlinear_step > 0.5:
            raise RuntimeError(f"LLE nonlinear phase per step is {nonlinear_step:.3g} rad; reduce microcomb.time_step.")
        if kerr:
            psi *= np.exp(1j * np.abs(psi)**2 * dt)
        a = np.fft.fft(psi) / n
        a *= half
        a[0] += forcing
        psi = np.fft.ifft(a) * n
        if noise:
            # Configurable numerical symmetry-breaking noise, NOT calibrated SOA ASE.
            psi += noise * np.sqrt(dt / 2) * (rng.normal(size=n) + 1j * rng.normal(size=n))
        if not np.all(np.isfinite(psi)):
            raise RuntimeError("LLE produced nonfinite fields; reduce time_step.")
        if (j + 1) % record_every == 0 or j == steps - 1:
            fraction_end = min((j + 1) * dt / scan_time, 1.0) if scan_time else 1.0
            record((j + 1) * dt, alpha_start + (alpha_end - alpha_start) * fraction_end)
    return dict(field=psi, spectrum=np.abs(np.fft.fft(psi) / n)**2,
                trace=np.asarray(traces), spectral_history=np.asarray(spectra),
                actual_time_step=dt, requested_time_step=requested_dt,
                max_dispersion_phase_per_step=max_dispersion * dt,
                max_nonlinear_phase_per_step=max_nonlinear_step)


def simulate_microcomb(c: Config, pump_output_mW):
    r = c.microcomb
    omega = 2 * np.pi * C0 / (c.source.wavelength_nm * 1e-9)
    k0, kex = omega / r.intrinsic_Q, omega / r.coupling_Q
    kappa = k0 + kex
    circumference = 2 * np.pi * r.radius_um * 1e-6
    fsr = C0 / (r.group_index * circumference)
    volume = circumference * r.effective_area_um2 * 1e-12
    g = hbar * omega**2 * C0 * r.n2_m2_per_W / (r.effective_index**2 * volume)
    delivered = pump_output_mW * 1e-3 * 10**(-r.link_loss_dB / 10)
    reference = kappa**3 * hbar * omega / (8 * g * kex)
    drive = np.sqrt(delivered / reference)
    mu = np.fft.fftfreq(r.modes, d=1 / r.modes)
    dint = 2 * np.pi * (0.5 * r.D2_MHz * 1e6 * mu**2 + r.D3_kHz * 1e3 * mu**3 / 6)
    result = integrate_lle(drive, 2 * dint / kappa, alpha_start=r.detuning_start, alpha_end=r.detuning_end,
                           dt=r.time_step, scan_time=r.scan_time, hold_time=r.hold_time,
                           record_every=r.record_every, seed=r.seed, field_noise_per_sqrt_tau=r.field_noise_per_sqrt_tau)
    photons_per_normalized_power = kappa / (2 * g)
    output_scale = kex * hbar * omega * photons_per_normalized_power
    # Resonator leakage, not through-port power: through port needs coherent interference.
    leakage_W = result["spectrum"] * output_scale
    edge = np.abs(mu) >= r.modes * 0.4
    history = result["spectral_history"]
    edge_fraction = float(np.max(history[:, edge].sum(axis=1) / np.maximum(history.sum(axis=1), 1e-30)))
    warnings = []
    if edge_fraction > 1e-4:
        warnings.append("LLE has appreciable power near the spectral grid edge; increase microcomb.modes and rerun.")
    if delivered / reference < 1:
        warnings.append("Delivered pump is below the ideal F^2=1 drive scale; this run need not generate comb sidebands.")
    if np.max(np.abs(dint)) > 2 * np.pi * fsr / 2:
        warnings.append("Truncated resonator dispersion approaches an FSR; check validity of the D2/D3 expansion.")
    side = leakage_W.copy()
    side[0] = 0
    pump_leak = max(leakage_W[0], 1e-30)
    active = int(np.count_nonzero(side > pump_leak * 1e-6))
    summary = dict(delivered_pump_mW=float(delivered * 1e3), F_squared=float(delivered / reference),
                   ideal_F_squared_one_power_mW=float(reference * 1e3), loaded_Q=float(omega / kappa),
                   loaded_linewidth_MHz=float(kappa / (2 * np.pi) * 1e-6), FSR_GHz=float(fsr * 1e-9),
                   single_photon_kerr_rad_per_s=float(g), sideband_leakage_mW=float(side.sum() * 1e3),
                   sidebands_above_minus60dBc=active, max_spectral_edge_fraction=edge_fraction,
                   max_nonlinear_phase_per_step=result["max_nonlinear_phase_per_step"],
                   max_dispersion_phase_per_step=result["max_dispersion_phase_per_step"],
                   requested_time_step=result["requested_time_step"],
                   time_step=result["actual_time_step"], simulated_time_ns=float((r.scan_time + r.hold_time) * 2 / kappa * 1e9),
                   state_classification="Unclassified LLE trajectory; not a demonstrated stable soliton")
    frequencies = omega / (2 * np.pi) + fsr * mu + dint / (2 * np.pi)
    if np.min(frequencies) <= 0:
        raise RuntimeError("LLE grid contains nonpositive optical frequencies; reduce modes or increase radius.")
    return dict(summary=summary, warnings=warnings, mu=mu, wavelength_nm=C0 / frequencies * 1e9,
                leakage_mW=leakage_W * 1e3, field=result["field"], trace=result["trace"],
                spectral_history=history, intracavity_scale_W=photons_per_normalized_power * hbar * omega * fsr)
