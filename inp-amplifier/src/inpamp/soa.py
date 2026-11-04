"""CW traveling-wave SOA with local ABC carriers and bidirectional ASE.

Powers are W, carrier densities m^-3, gain/loss m^-1, z m.
Material gain describes an effective InGaAsP active region on an InP host.
"""
from dataclasses import dataclass

import numpy as np
from scipy.constants import c as C0, h as H, e as Q
from scipy.optimize import brentq

from .config import Config
from .mode import ModeResult


def recombination(n, material):
    return (material.recombination_A_per_s * n + material.recombination_B_m3_per_s * n**2
            + material.recombination_C_m6_per_s * n**3)


def transparency(c: Config, temperature_K):
    return c.material.transparency_density_m3 * np.exp(
        (temperature_K - c.material.reference_temperature_K) / c.material.transparency_temperature_scale_K)


def gain_shape(c: Config, wavelengths_nm, temperature_K):
    peak = c.material.gain_peak_nm + c.material.gain_peak_shift_nm_per_K * (temperature_K - c.material.reference_temperature_K)
    return np.exp(-4 * np.log(2) * ((np.asarray(wavelengths_nm) - peak) / c.material.gain_fwhm_nm)**2)


def propagate(power, coefficient, source, dz):
    """Exact constant-coefficient dP/dz = coefficient*P + source."""
    exponent = coefficient * dz
    if np.max(exponent) > 100:
        raise RuntimeError("Excessive gain per cell. Increase numerics.z_cells or reduce drive/gain.")
    # expm1(x)/x has a removable singularity; avoid computing the bad branch.
    factor = np.ones_like(exponent)
    np.divide(np.expm1(exponent), exponent, out=factor, where=np.abs(exponent) > 1e-12)
    return power * np.exp(exponent) + source * dz * factor


@dataclass
class SOAResult:
    summary: dict
    z_m: np.ndarray
    carriers_m3: np.ndarray
    signal_W: np.ndarray
    modal_gain_per_m: np.ndarray
    ase_wavelength_nm: np.ndarray
    ase_bin_width_Hz: np.ndarray
    ase_forward_W: np.ndarray
    ase_backward_W: np.ndarray
    warnings: list[str]


def solve_soa(c: Config, mode: ModeResult) -> SOAResult:
    d, m, num = c.device, c.material, c.numerics
    nz, nb = num.z_cells, num.ase_bins
    length = d.length_um * 1e-6
    area = d.width_um * d.active_thickness_um * 1e-12
    volume = area * length
    dz = length / nz
    injection = d.injection_efficiency * d.current_mA * 1e-3 / (Q * volume)
    # Work in units of 1e24 m^-3 for well-scaled scalar roots.
    hi = 1.0
    while recombination(hi * 1e24, m) < injection:
        hi *= 2
        if hi > 1e6:
            raise RuntimeError("Unphysical injection density; check current and active volume.")
    unsaturated = brentq(lambda u: (recombination(u * 1e24, m) - injection) / 1e33, 0, hi) * 1e24
    nu_signal = C0 / (c.source.wavelength_nm * 1e-9)
    half = num.ase_bandwidth_nm / 2
    edges = np.linspace(C0 / ((m.gain_peak_nm + half) * 1e-9), C0 / ((m.gain_peak_nm - half) * 1e-9), nb + 1)
    nu_ase, widths = (edges[1:] + edges[:-1]) / 2, np.diff(edges)
    wavelengths = C0 / nu_ase * 1e9
    nus = np.r_[nu_signal, nu_ase]
    lambdas = np.r_[c.source.wavelength_nm, wavelengths]
    input_W = c.source.input_power_mW * 1e-3
    injected_W = input_W * 10**(-d.input_loss_dB / 10)
    transmission = 10**(-d.output_loss_dB / 10)
    signal = np.full(nz + 1, injected_W)
    af = np.zeros((nz + 1, nb))
    ab = np.zeros_like(af)
    temperature = c.thermal.ambient_K
    residual = np.inf
    rates_residual = np.inf
    for iteration in range(1, num.max_iterations + 1):
        local_power = np.column_stack(((signal[1:] + signal[:-1]) / 2,
                                      (af[1:] + af[:-1] + ab[1:] + ab[:-1]) / 2))
        total = local_power.sum(axis=1)
        slope = mode.confinement * m.differential_gain_m2 * gain_shape(c, lambdas, temperature)[None, :] / (1 + m.gain_compression_per_W * total[:, None])
        ntr = transparency(c, temperature)
        stim_coefficient = np.sum(slope * local_power / (H * nus[None, :] * area), axis=1)
        # R(N) + K(N-Ntr) = J is monotonic, bracketed by 0 and max(Ntr,N0).
        low = np.zeros(nz)
        high = np.full(nz, max(ntr, unsaturated) * (1 + 1e-10))
        for _ in range(55):
            mid = (low + high) / 2
            positive = recombination(mid, m) + stim_coefficient * (mid - ntr) > injection
            high = np.where(positive, mid, high)
            low = np.where(positive, low, mid)
        carriers = (low + high) / 2
        gain = slope * (carriers[:, None] - ntr)
        net = gain - d.internal_loss_per_m
        # Total of two polarizations in each directional ASE bin.
        spontaneous = 2 * m.spontaneous_emission_factor * H * nu_ase * widths * np.maximum(gain[:, 1:], 0) if num.include_ase else np.zeros((nz, nb))
        new_signal = np.empty_like(signal)
        new_af, new_ab = np.zeros_like(af), np.zeros_like(ab)
        new_signal[0] = injected_W
        for j in range(nz):
            new_signal[j + 1] = propagate(new_signal[j], net[j, 0], 0, dz)
            new_af[j + 1] = propagate(new_af[j], net[j, 1:], spontaneous[j], dz)
        for j in range(nz - 1, -1, -1):
            new_ab[j] = propagate(new_ab[j + 1], net[j, 1:], spontaneous[j], dz)
        optical_extraction = new_signal[-1] - injected_W + new_af[-1].sum() + new_ab[0].sum()
        electrical_W = d.current_mA * 1e-3 * c.thermal.junction_voltage_V
        heat_W = max(electrical_W - optical_extraction, 0)
        target_temperature = c.thermal.ambient_K + (c.thermal.resistance_K_per_W * heat_W if c.thermal.enabled else 0)
        if target_temperature > 700:
            raise RuntimeError("Junction temperature exceeds model range (700 K); check thermal design/current.")
        power_scale = max(injected_W, np.max(new_signal), np.max(new_af.sum(axis=1)), np.max(new_ab.sum(axis=1)), 1e-12)
        residual = max(np.max(np.abs(new_signal - signal)), np.max(np.abs(new_af - af)), np.max(np.abs(new_ab - ab))) / power_scale
        temperature_residual = abs(target_temperature - temperature)
        # Independent carrier-balance residual evaluated with the newly propagated powers.
        new_local = np.column_stack(((new_signal[1:] + new_signal[:-1]) / 2,
                                    (new_af[1:] + new_af[:-1] + new_ab[1:] + new_ab[:-1]) / 2))
        new_slope = mode.confinement * m.differential_gain_m2 * gain_shape(c, lambdas, target_temperature)[None, :] / (1 + m.gain_compression_per_W * new_local.sum(axis=1)[:, None])
        stimulated = np.sum(new_slope * (carriers[:, None] - transparency(c, target_temperature)) * new_local / (H * nus[None, :] * area), axis=1)
        rates_residual = np.max(np.abs(injection - recombination(carriers, m) - stimulated)) / max(injection, 1e25)
        if residual < num.relative_tolerance and temperature_residual < 1e-4 and rates_residual < 10 * num.relative_tolerance:
            signal, af, ab = new_signal, new_af, new_ab
            break
        mix = num.relaxation
        signal += mix * (new_signal - signal)
        af += mix * (new_af - af)
        ab += mix * (new_ab - ab)
        temperature += mix * (target_temperature - temperature)
    else:
        raise RuntimeError(f"SOA did not converge in {num.max_iterations} iterations (power residual {residual:.3g}, carrier residual {rates_residual:.3g}). Reduce relaxation or increase max_iterations.")
    gain_linear = signal[-1] * transmission / input_W
    psd = af[-1] * transmission / widths
    signal_psd = float(np.interp(nu_signal, nu_ase, psd))
    rbw = C0 * num.osnr_bandwidth_nm * 1e-9 / (c.source.wavelength_nm * 1e-9)**2
    osnr = 10 * np.log10(signal[-1] * transmission / (signal_psd * rbw)) if signal_psd > 0 else None
    nf = 10 * np.log10(1 / gain_linear + signal_psd / (gain_linear * H * nu_signal)) if num.include_ase else None
    roundtrip_log = (np.log(d.input_reflectivity * d.output_reflectivity)
                     + 2 * np.sum(net[:, 0]) * dz) if d.input_reflectivity * d.output_reflectivity > 0 else -np.inf
    roundtrip = float(np.exp(min(roundtrip_log, 700)))
    warnings = []
    if roundtrip >= 1:
        warnings.append("Facet round-trip power gain >= 1: feedback/lasing invalidates the reflection-free SOA approximation.")
    if target_temperature > 360:
        warnings.append("Junction temperature > 360 K: extrapolated material parameters need calibration.")
    if optical_extraction > electrical_W + 1e-9:
        warnings.append("Optical extraction exceeds electrical input; illustrative gain parameters violate energy budget.")
    band_edge = (af[-1, 0] + af[-1, -1]) / max(af[-1].sum(), 1e-30)
    if band_edge > 0.01:
        warnings.append("ASE at spectral boundaries is significant; increase ase_bandwidth_nm and check spectral convergence.")
    if nu_signal < edges[0] or nu_signal > edges[-1]:
        warnings.append("Pump is outside ASE integration band: OSNR/noise figure are unavailable.")
        osnr, nf = None, None
    summary = dict(input_power_mW=c.source.input_power_mW, output_power_mW=float(signal[-1] * transmission * 1e3),
                   on_chip_output_mW=float(signal[-1] * 1e3), gain_dB=float(10 * np.log10(gain_linear)),
                   forward_ase_mW=float(af[-1].sum() * transmission * 1e3), backward_ase_mW=float(ab[0].sum() * 1e3),
                   osnr_dB=None if osnr is None else float(osnr), osnr_bandwidth_nm=num.osnr_bandwidth_nm,
                   approximate_noise_figure_dB=None if nf is None else float(nf),
                   junction_temperature_K=float(target_temperature), electrical_power_mW=float(electrical_W * 1e3),
                   heat_mW=float(heat_W * 1e3), optical_extraction_mW=float(optical_extraction * 1e3),
                   facet_roundtrip_power_gain=roundtrip, iterations=iteration,
                   power_fixed_point_residual=float(residual), carrier_balance_relative_residual=float(rates_residual))
    return SOAResult(summary, np.linspace(0, length, nz + 1), carriers, signal, gain[:, 0], wavelengths, widths, af, ab, warnings)
