"""
er_al2o3_cpa_first_order.py

Pure-Python first-order chirped-pulse-amplifier sanity model.

This is intentionally NOT a full Er:Al2O3 amplifier solver. It is the
mathematical layer you can use before building the full rate-equation model.

Included:
    Gaussian pulse stretching by GDD
    idealized energy gain
    ideal second-order compression
    peak power / average power
    peak intensity
    nonlinear coefficient gamma
    approximate B-integral

Not included yet:
    Er population rate equations
    pump depletion
    gain saturation
    ASE
    cooperative upconversion
    wavelength-dependent gain
    gain narrowing
    beta3 / higher-order phase
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "results" / "cpa"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# 1. Constants and input pulse
# ---------------------------------------------------------------------
C0 = 299_792_458.0

lambda0 = 1550e-9
tau0 = 100e-15          # transform-limited intensity FWHM
E_in = 10e-12           # 10 pJ
f_rep = 1e9             # 1 GHz repetition rate

# ---------------------------------------------------------------------
# 2. Stretcher
# ---------------------------------------------------------------------
# +0.36 ps^2
Phi2_stretch = 0.36e-24

stretch_factor = np.sqrt(
    1.0 + (4.0 * np.log(2.0) * Phi2_stretch / tau0**2) ** 2
)

tau_stretched = tau0 * stretch_factor

# For Gaussian intensity:
# E = P_peak * tau_FWHM * sqrt(pi)/(2 sqrt(ln2))
shape_factor = np.sqrt(np.pi) / (2.0 * np.sqrt(np.log(2.0)))

Ppk_in = E_in / (shape_factor * tau0)
Ppk_stretched = E_in / (shape_factor * tau_stretched)

# ---------------------------------------------------------------------
# 3. First-order amplifier
# ---------------------------------------------------------------------
Aeff = 30e-12            # 30 um^2
Gamma_Er = 0.80

L_gain = 0.08            # 8 cm
G_dB = 20.0              # idealized energy gain

G_linear = 10.0 ** (G_dB / 10.0)

E_amp = E_in * G_linear
Ppk_amp_stretched = E_amp / (shape_factor * tau_stretched)

# ---------------------------------------------------------------------
# 4. Nonlinear phase estimate
# ---------------------------------------------------------------------
# Placeholder hybrid-mode effective nonlinear index.
n2_eff = 1.0e-19         # m^2/W

omega0 = 2.0 * np.pi * C0 / lambda0

gamma = n2_eff * omega0 / (C0 * Aeff)

# Very simple first-order B-integral estimate.
Ppk_average = 0.5 * (Ppk_stretched + Ppk_amp_stretched)
B_integral = gamma * Ppk_average * L_gain

# ---------------------------------------------------------------------
# 5. Ideal compressor
# ---------------------------------------------------------------------
# Later replace this with the GDD extracted from the actual amplifier.
Phi2_amp = 0.0

Phi2_comp = -(Phi2_stretch + Phi2_amp)
Phi2_total = Phi2_stretch + Phi2_amp + Phi2_comp

tau_out = tau0 * np.sqrt(
    1.0 + (4.0 * np.log(2.0) * Phi2_total / tau0**2) ** 2
)

Ppk_out_ideal = E_amp / (shape_factor * tau_out)

# ---------------------------------------------------------------------
# 6. Intensities and average powers
# ---------------------------------------------------------------------
Ipk_in = Ppk_in / Aeff
Ipk_stretched = Ppk_stretched / Aeff
Ipk_amp_stretched = Ppk_amp_stretched / Aeff
Ipk_out = Ppk_out_ideal / Aeff

Pavg_in = E_in * f_rep
Pavg_out = E_amp * f_rep

# ---------------------------------------------------------------------
# 7. Print results
# ---------------------------------------------------------------------
print("=" * 64)
print("FIRST-ORDER Er:Al2O3 ON-CHIP CPA CHECK")
print("=" * 64)
print(f"Input pulse FWHM             : {tau0*1e15:10.3f} fs")
print(f"Stretched pulse FWHM         : {tau_stretched*1e12:10.3f} ps")
print(f"Stretch factor               : {stretch_factor:10.3f}")
print()
print(f"Input pulse energy           : {E_in*1e12:10.3f} pJ")
print(f"Amplified pulse energy       : {E_amp*1e12:10.3f} pJ")
print(f"Input peak power             : {Ppk_in:10.3f} W")
print(f"Stretched input peak power   : {Ppk_stretched:10.3f} W")
print(f"Stretched amplified Ppeak    : {Ppk_amp_stretched:10.3f} W")
print(f"Ideal compressed peak power  : {Ppk_out_ideal:10.3f} W")
print()
print(f"Aeff                         : {Aeff*1e12:10.3f} um^2")
print(f"Er overlap Gamma             : {100*Gamma_Er:10.3f} %")
print(f"Nonlinear gamma              : {gamma:10.5g} 1/(W m)")
print(f"Approximate B-integral       : {B_integral:10.5g} rad")
print()
print(f"Average input power          : {Pavg_in*1e3:10.3f} mW")
print(f"Average output power         : {Pavg_out*1e3:10.3f} mW")
print()
print(f"Ipeak before stretch         : {Ipk_in/1e12:10.3f} W/um^2")
print(f"Ipeak stretched input        : {Ipk_stretched/1e12:10.3f} W/um^2")
print(f"Ipeak stretched output       : {Ipk_amp_stretched/1e12:10.3f} W/um^2")
print(f"Ipeak after compression      : {Ipk_out/1e12:10.3f} W/um^2")
print("=" * 64)

# ---------------------------------------------------------------------
# 8. Plot normalized pulse envelopes for intuition
# ---------------------------------------------------------------------
def gaussian_intensity(t, fwhm, peak):
    return peak * np.exp(-4.0 * np.log(2.0) * (t / fwhm) ** 2)


# Use separate time axes because the stretched pulse is much longer.
t_short = np.linspace(-5*tau0, 5*tau0, 2000)
t_long = np.linspace(-4*tau_stretched, 4*tau_stretched, 2000)

plt.figure(figsize=(7, 5))
plt.plot(t_short * 1e15, gaussian_intensity(t_short, tau0, Ppk_in))
plt.xlabel("Time (fs)")
plt.ylabel("Instantaneous power (W)")
plt.title("Input transform-limited pulse")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "input_pulse.png", dpi=200)

plt.figure(figsize=(7, 5))
plt.plot(
    t_long * 1e12,
    gaussian_intensity(t_long, tau_stretched, Ppk_stretched),
    label="Before gain",
)
plt.plot(
    t_long * 1e12,
    gaussian_intensity(t_long, tau_stretched, Ppk_amp_stretched),
    label="After idealized gain",
)
plt.xlabel("Time (ps)")
plt.ylabel("Instantaneous power (W)")
plt.title("Chirped pulse inside the amplifier")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "stretched_pulse.png", dpi=200)

plt.figure(figsize=(7, 5))
plt.plot(
    t_short * 1e15,
    gaussian_intensity(t_short, tau_out, Ppk_out_ideal),
)
plt.xlabel("Time (fs)")
plt.ylabel("Instantaneous power (W)")
plt.title("Ideally recompressed amplified pulse")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "compressed_pulse.png", dpi=200)

print(f"Pulse figures saved to {OUTPUT_DIR}")
plt.show()
