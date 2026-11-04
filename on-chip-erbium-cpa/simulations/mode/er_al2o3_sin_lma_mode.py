"""
er_al2o3_sin_lma_mode.py

Python/lumapi version of the MODE/FDE starter model for a large-mode-area
Er:Al2O3 / SiN hybrid amplifier.

What this script does
---------------------
1. Opens Ansys Lumerical MODE through the Python API (lumapi).
2. Builds:
       Er:Al2O3 active top layer
       SiO2 spacer/background
       narrow buried SiN rail
3. Finds the fundamental hybrid mode near 1550 nm.
4. Calculates in Python:
       effective index neff
       effective mode area Aeff
       approximate power overlap with Er:Al2O3
5. Sweeps SiN rail width.
6. Runs Lumerical's detailed dispersion sweep.
7. Saves plots and the .lms project.

Important
---------
The refractive indices below are intentionally simple placeholders.
For publication-quality dispersion, replace them with wavelength-dependent
material data measured for your actual deposited films.

The script requires:
    numpy
    matplotlib
    lumapi (installed with Lumerical)

Ansys documents two convenient ways to make lumapi importable:
1. Run this file from Lumerical's built-in Python environment, or
2. Set LUMERICAL_API_PATH to the folder containing lumapi.py.

Example Windows PowerShell:
    $env:LUMERICAL_API_PATH="C:\\Program Files\\Ansys Inc\\vXXX\\Lumerical\\api\\python"
    python er_al2o3_sin_lma_mode.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------
# 0. Import lumapi
# ---------------------------------------------------------------------
import importlib.util

spec = importlib.util.spec_from_file_location(
    "lumapi",
    "C:/Program Files/Ansys Inc/v261/Lumerical/api/python/lumapi.py",
)
lumapi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lumapi)


# ---------------------------------------------------------------------
# 1. User-editable physical parameters
# ---------------------------------------------------------------------
C0 = 299_792_458.0
LAMBDA0 = 1550e-9

# Placeholder refractive indices near 1550 nm.
N_SIO2 = 1.444
N_SIN = 1.996
N_ER_AL2O3 = 1.65

# Geometry.
W_SIN = 0.28e-6
H_SIN = 0.80e-6
T_SPACER = 0.31e-6
T_GAIN = 1.50e-6
W_GAIN = 10.0e-6

# Simulation region.
X_SPAN_SIM = 12e-6
Y_SPAN_SIM = 8e-6
Z_SPAN_GEOM = 1e-6

# Mesh.
DX = 20e-9
DY = 20e-9

# Width sweep.
WIDTHS = np.linspace(0.16e-6, 0.80e-6, 17)

# Dispersion sweep.
LAMBDA_START = 1500e-9
LAMBDA_STOP = 1600e-9
N_LAMBDA = 51

# Results location.
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "results" / "mode"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# 2. Small numerical helpers
# ---------------------------------------------------------------------
def squeeze_vector(a) -> np.ndarray:
    """Convert Lumerical coordinate data into a 1-D NumPy array."""
    return np.asarray(a).squeeze().astype(float)


def align_field(a, nx: int, ny: int) -> np.ndarray:
    """
    Convert a Lumerical field array to shape (nx, ny).

    Lumerical datasets often arrive as (nx, ny, 1, ...). This helper
    removes singleton dimensions and transposes if required.
    """
    arr = np.asarray(a).squeeze()

    if arr.shape == (nx, ny):
        return arr
    if arr.shape == (ny, nx):
        return arr.T

    raise ValueError(
        f"Unexpected field shape {arr.shape}; expected {(nx, ny)} "
        f"or {(ny, nx)}."
    )


def trapz(y, x, axis):
    """Compatibility wrapper for NumPy versions with/without trapezoid()."""
    if hasattr(np, "trapezoid"):
        return np.trapezoid(y, x=x, axis=axis)
    return np.trapz(y, x=x, axis=axis)


def integrate_xy(field: np.ndarray, x: np.ndarray, y: np.ndarray):
    """Integrate a field whose array shape is (len(x), len(y))."""
    integral_y = trapz(field, y, axis=1)
    return trapz(integral_y, x, axis=0)


# ---------------------------------------------------------------------
# 3. Extract modal quantities from a calculated D-CARD
# ---------------------------------------------------------------------
def extract_mode_quantities(mode, mode_name: str, gain_bounds):
    """
    Return neff, Aeff, active-layer power overlap, coordinates and |E|^2.

    Aeff uses the common scalar-field definition:
        Aeff = (integral |E|^2 dA)^2 / integral |E|^4 dA

    The active-layer overlap is estimated from longitudinal Poynting flux.
    """
    x = squeeze_vector(mode.getdata(mode_name, "x"))
    y = squeeze_vector(mode.getdata(mode_name, "y"))
    nx, ny = len(x), len(y)

    ex = align_field(mode.getdata(mode_name, "Ex"), nx, ny)
    ey = align_field(mode.getdata(mode_name, "Ey"), nx, ny)
    ez = align_field(mode.getdata(mode_name, "Ez"), nx, ny)
    hx = align_field(mode.getdata(mode_name, "Hx"), nx, ny)
    hy = align_field(mode.getdata(mode_name, "Hy"), nx, ny)

    e2 = np.abs(ex) ** 2 + np.abs(ey) ** 2 + np.abs(ez) ** 2

    int_e2 = integrate_xy(e2, x, y)
    int_e4 = integrate_xy(e2**2, x, y)
    aeff = np.real(int_e2**2 / int_e4)

    # Propagation is along z for an XY FDE cross-section.
    sz = 0.5 * np.real(ex * np.conj(hy) - ey * np.conj(hx))

    xg_min, xg_max, yg_min, yg_max = gain_bounds
    xx, yy = np.meshgrid(x, y, indexing="ij")
    gain_mask = (
        (xx >= xg_min)
        & (xx <= xg_max)
        & (yy >= yg_min)
        & (yy <= yg_max)
    )

    p_total = integrate_xy(sz, x, y)
    p_gain = integrate_xy(sz * gain_mask, x, y)

    if np.isclose(p_total, 0):
        gamma_gain = np.nan
    else:
        gamma_gain = np.real(p_gain / p_total)

    neff = np.asarray(mode.getdata(mode_name, "neff")).squeeze()
    neff = float(np.real(neff))

    return {
        "neff": neff,
        "Aeff": aeff,
        "Gamma_gain": gamma_gain,
        "x": x,
        "y": y,
        "E2": e2,
    }


# ---------------------------------------------------------------------
# 4. Build the Lumerical MODE project
# ---------------------------------------------------------------------
def build_geometry(mode):
    y_sin = 0.0
    gain_ymin = H_SIN / 2 + T_SPACER
    gain_ymax = gain_ymin + T_GAIN
    gain_y = 0.5 * (gain_ymin + gain_ymax)

    mode.switchtolayout()
    mode.deleteall()

    # SiO2 background.
    sio2 = mode.addrect()
    sio2["name"] = "SiO2 background"
    sio2["x"] = 0.0
    sio2["x span"] = X_SPAN_SIM
    sio2["y"] = 0.5e-6
    sio2["y span"] = Y_SPAN_SIM
    sio2["z"] = 0.0
    sio2["z span"] = Z_SPAN_GEOM
    sio2["material"] = "<Object defined dielectric>"
    sio2["index"] = N_SIO2

    # Er:Al2O3 active top layer.
    gain = mode.addrect()
    gain["name"] = "ErAl2O3 gain"
    gain["x"] = 0.0
    gain["x span"] = W_GAIN
    gain["y"] = gain_y
    gain["y span"] = T_GAIN
    gain["z"] = 0.0
    gain["z span"] = Z_SPAN_GEOM
    gain["material"] = "<Object defined dielectric>"
    gain["index"] = N_ER_AL2O3
    gain["override mesh order from material database"] = 1
    gain["mesh order"] = 2

    # SiN rail.
    sin = mode.addrect()
    sin["name"] = "SiN rail"
    sin["x"] = 0.0
    sin["x span"] = W_SIN
    sin["y"] = y_sin
    sin["y span"] = H_SIN
    sin["z"] = 0.0
    sin["z span"] = Z_SPAN_GEOM
    sin["material"] = "<Object defined dielectric>"
    sin["index"] = N_SIN
    sin["override mesh order from material database"] = 1
    sin["mesh order"] = 1

    # Fine mesh around the hybrid mode region.
    mesh = mode.addmesh()
    mesh["name"] = "fine mesh"
    mesh["x"] = 0.0
    mesh["x span"] = 4e-6
    mesh["y"] = gain_y / 2
    mesh["y span"] = 4.5e-6
    mesh["z"] = 0.0
    mesh["z span"] = Z_SPAN_GEOM
    mesh["dx"] = DX
    mesh["dy"] = DY

    # FDE region: XY cross-section, propagation in z.
    fde = mode.addfde()
    fde["solver type"] = 3
    fde["x"] = 0.0
    fde["x span"] = X_SPAN_SIM
    fde["y"] = 0.5e-6
    fde["y span"] = Y_SPAN_SIM
    fde["z"] = 0.0

    mode.setanalysis("wavelength", LAMBDA0)
    mode.setanalysis("number of trial modes", 6)

    gain_bounds = (
        -W_GAIN / 2,
        W_GAIN / 2,
        gain_ymin,
        gain_ymax,
    )

    return gain_bounds


# ---------------------------------------------------------------------
# 5. Main simulation
# ---------------------------------------------------------------------
def main():
    print("Launching Lumerical MODE...")

    # hide=False is intentional for learning: you can watch the model being built.
    with lumapi.MODE(hide=False) as mode:
        gain_bounds = build_geometry(mode)

        # -------------------------------------------------------------
        # Nominal 1550-nm mode
        # -------------------------------------------------------------
        nmodes = int(mode.findmodes())
        print(f"Number of modes found: {nmodes}")

        if nmodes < 1:
            raise RuntimeError("MODE found no guided modes.")

        # IMPORTANT: visually verify that mode1 is the TE-like mode you want.
        mode_name = "mode1"
        result = extract_mode_quantities(mode, mode_name, gain_bounds)

        print("\nNominal 1550-nm hybrid mode")
        print("--------------------------------")
        print(f"neff              = {result['neff']:.6f}")
        print(f"Aeff              = {result['Aeff'] * 1e12:.3f} um^2")
        print(
            "Er:Al2O3 overlap = "
            f"{100 * result['Gamma_gain']:.2f} %"
        )

        # Plot |E|^2.
        fig = plt.figure(figsize=(7, 5))
        plt.pcolormesh(
            result["x"] * 1e6,
            result["y"] * 1e6,
            result["E2"].T,
            shading="auto",
        )
        plt.xlabel("x (um)")
        plt.ylabel("y (um)")
        plt.title("Hybrid fundamental-mode |E|² at 1550 nm")
        plt.colorbar(label="|E|² (arb.)")
        plt.tight_layout()
        fig.savefig(OUTPUT_DIR / "mode_1550nm.png", dpi=200)
        plt.show(block=False)

        # -------------------------------------------------------------
        # SiN rail-width sweep
        # -------------------------------------------------------------
        neff_vs_w = []
        aeff_vs_w = []
        gamma_vs_w = []

        print("\nSweeping SiN rail width...")

        for width in WIDTHS:
            mode.switchtolayout()
            mode.setnamed("SiN rail", "x span", float(width))
            mode.setanalysis("wavelength", LAMBDA0)

            nm = int(mode.findmodes())
            if nm < 1:
                neff_vs_w.append(np.nan)
                aeff_vs_w.append(np.nan)
                gamma_vs_w.append(np.nan)
                continue

            r = extract_mode_quantities(mode, "mode1", gain_bounds)

            neff_vs_w.append(r["neff"])
            aeff_vs_w.append(r["Aeff"])
            gamma_vs_w.append(r["Gamma_gain"])

            print(
                f"w = {width*1e9:6.1f} nm | "
                f"Aeff = {r['Aeff']*1e12:7.3f} um^2 | "
                f"Gamma_Er = {100*r['Gamma_gain']:6.2f} %"
            )

        neff_vs_w = np.asarray(neff_vs_w)
        aeff_vs_w = np.asarray(aeff_vs_w)
        gamma_vs_w = np.asarray(gamma_vs_w)

        # Save numerical sweep.
        np.savetxt(
            OUTPUT_DIR / "width_sweep.csv",
            np.column_stack(
                [
                    WIDTHS * 1e9,
                    neff_vs_w,
                    aeff_vs_w * 1e12,
                    100 * gamma_vs_w,
                ]
            ),
            delimiter=",",
            header="SiN_width_nm,neff,Aeff_um2,ErAl2O3_overlap_percent",
            comments="",
        )

        fig = plt.figure(figsize=(7, 5))
        plt.plot(WIDTHS * 1e9, aeff_vs_w * 1e12, "o-")
        plt.xlabel("SiN rail width (nm)")
        plt.ylabel(r"$A_{\mathrm{eff}}$ ($\mu$m$^2$)")
        plt.title("Mode area versus SiN rail width")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        fig.savefig(OUTPUT_DIR / "Aeff_vs_width.png", dpi=200)
        plt.show(block=False)

        fig = plt.figure(figsize=(7, 5))
        plt.plot(WIDTHS * 1e9, 100 * gamma_vs_w, "o-")
        plt.xlabel("SiN rail width (nm)")
        plt.ylabel("Er:Al2O3 power overlap (%)")
        plt.title("Active-layer overlap versus SiN rail width")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        fig.savefig(OUTPUT_DIR / "overlap_vs_width.png", dpi=200)
        plt.show(block=False)

        fig = plt.figure(figsize=(7, 5))
        plt.plot(WIDTHS * 1e9, neff_vs_w, "o-")
        plt.xlabel("SiN rail width (nm)")
        plt.ylabel(r"$n_{\mathrm{eff}}$")
        plt.title("Effective index versus SiN rail width")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        fig.savefig(OUTPUT_DIR / "neff_vs_width.png", dpi=200)
        plt.show(block=False)

        # -------------------------------------------------------------
        # Restore nominal geometry and run dispersion sweep
        # -------------------------------------------------------------
        mode.switchtolayout()
        mode.setnamed("SiN rail", "x span", W_SIN)
        mode.setanalysis("wavelength", LAMBDA0)
        mode.findmodes()
        mode.selectmode(1)

        mode.setanalysis("track selected mode", 1)
        mode.setanalysis("detailed dispersion calculation", 1)
        for prop in ("start wavelength", "start frequency"):
            try:
                print(f"{prop}: {mode.getanalysis(prop)}")
            except lumapi.LumApiError as exc:
                print(f"{prop} unavailable: {exc}")
        mode.setanalysis("start wavelength", LAMBDA_START)
        mode.setanalysis("stop wavelength", LAMBDA_STOP)
        mode.setanalysis("number of points", N_LAMBDA)

        print("\nRunning detailed dispersion sweep...")
        mode.frequencysweep()

        dispersion = np.asarray(
            mode.getdata("frequencysweep", "D")
        ).squeeze()
        f_d = np.asarray(
            mode.getdata("frequencysweep", "f_D")
        ).squeeze()

        wavelength_nm = C0 / f_d * 1e9

        # Lumerical D data are converted as in Ansys's MODE example.
        dispersion_ps_nm_km = dispersion * 1e6

        order = np.argsort(wavelength_nm)
        wavelength_nm = wavelength_nm[order]
        dispersion_ps_nm_km = dispersion_ps_nm_km[order]

        np.savetxt(
            OUTPUT_DIR / "dispersion.csv",
            np.column_stack([wavelength_nm, dispersion_ps_nm_km]),
            delimiter=",",
            header="wavelength_nm,D_ps_per_nm_per_km",
            comments="",
        )

        fig = plt.figure(figsize=(7, 5))
        plt.plot(wavelength_nm, dispersion_ps_nm_km)
        plt.xlabel("Wavelength (nm)")
        plt.ylabel("Dispersion D (ps/nm/km)")
        plt.title("Hybrid-waveguide dispersion")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        fig.savefig(OUTPUT_DIR / "dispersion.png", dpi=200)
        plt.show(block=False)

        project_file = OUTPUT_DIR / "er_al2o3_sin_lma_mode.lms"
        mode.save(str(project_file))

        print("\nFinished.")
        print(f"Results saved in: {OUTPUT_DIR}")
        print("\nNext physics step:")
        print("  1. Replace placeholder indices with measured dispersive data.")
        print("  2. Solve the same structure at 980 nm.")
        print("  3. Calculate pump/signal spatial overlap.")
        print("  4. Then introduce Er population/gain equations.")

        plt.show()


if __name__ == "__main__":
    main()
