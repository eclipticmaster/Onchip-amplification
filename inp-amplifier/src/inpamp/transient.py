"""Lumped carrier/current-step model, no ASE or thermal dynamics."""
import numpy as np
from scipy.constants import c as C0, h as H, e as Q
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from .config import Config
from .mode import ModeResult
from .soa import gain_shape, recombination, transparency


def simulate_transient(c: Config, mode: ModeResult, temperature_K):
    d, m, tr = c.device, c.material, c.transient
    length = d.length_um * 1e-6
    volume = length * d.width_um * d.active_thickness_um * 1e-12
    pin = c.source.input_power_mW * 1e-3 * 10**(-d.input_loss_dB / 10)
    energy = H * C0 / (c.source.wavelength_nm * 1e-9)
    ntr = transparency(c, temperature_K)
    slope = mode.confinement * m.differential_gain_m2 * float(gain_shape(c, c.source.wavelength_nm, temperature_K))

    def optical(n):
        g0 = slope * (n - ntr)

        def residual(pout):
            loggain = (g0 / (1 + m.gain_compression_per_W * (pin + pout) / 2) - d.internal_loss_per_m) * length
            return pout - pin * np.exp(np.clip(loggain, -700, 100))

        upper = max(pin, 1e-9)
        while residual(upper) < 0:
            upper *= 2
            if upper > 1e6:
                raise RuntimeError("Lumped transient optical power is outside the model range.")
        pout = brentq(residual, 0, upper, xtol=1e-14)
        mean = (pin + pout) / 2
        gain = g0 / (1 + m.gain_compression_per_W * mean)
        return pout, mean, gain

    def derivative(n24, current_mA):
        n = float(n24) * 1e24
        _, mean, gain = optical(n)
        injection = d.injection_efficiency * current_mA * 1e-3 / (Q * volume)
        stimulated = gain * length * mean / (energy * volume)
        return (injection - recombination(n, m) - stimulated) / 1e33  # dn24 / d(ns)

    hi = 10.0
    while derivative(hi, tr.initial_current_mA) > 0:
        hi *= 2
    initial = brentq(lambda n: derivative(n, tr.initial_current_mA), 0, hi)
    # Split at the discontinuity; the integrator never steps over the current jump.
    times = np.linspace(0, tr.duration_ns, tr.samples)
    before = times <= tr.step_time_ns
    density = np.full(tr.samples, initial)
    tail_times = times[~before]
    if len(tail_times):
        solution = solve_ivp(lambda t, y: [derivative(y[0], d.current_mA)],
                             (tr.step_time_ns, tr.duration_ns), [initial], t_eval=tail_times,
                             method="RK45", rtol=1e-8, atol=1e-10, max_step=0.02)
        if not solution.success:
            raise RuntimeError(f"Carrier transient failed: {solution.message}")
        density[~before] = solution.y[0]
    output = np.array([optical(n * 1e24) for n in density])
    phase = -m.linewidth_enhancement_factor * length * (output[:, 2] - output[0, 2]) / 2
    chirp_GHz = np.gradient(phase, times) / (2 * np.pi)  # rad/ns -> GHz
    return dict(time_ns=times, current_mA=np.where(before, tr.initial_current_mA, d.current_mA),
                carriers_m3=density * 1e24, output_power_mW=output[:, 0] * 10**(-d.output_loss_dB / 10) * 1e3,
                phase_rad=phase, chirp_GHz=chirp_GHz)
