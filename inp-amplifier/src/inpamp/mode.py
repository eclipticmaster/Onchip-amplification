"""Scalar 2-D finite-difference eigenmode; all computational lengths in um."""
from dataclasses import dataclass

import numpy as np
from scipy.sparse import diags, eye, kron
from scipy.sparse.linalg import eigsh

from .config import Config


@dataclass
class ModeResult:
    confinement: float
    area_um2: float
    neff: float | None = None
    x: np.ndarray | None = None
    y: np.ndarray | None = None
    intensity: np.ndarray | None = None
    index: np.ndarray | None = None
    boundary_fraction: float | None = None


def solve_mode(c: Config) -> ModeResult:
    m, d = c.mode, c.device
    if not m.enabled:
        return ModeResult(m.confinement_factor, m.effective_area_um2)
    x = np.linspace(-m.x_span_um / 2, m.x_span_um / 2, m.nx + 2)[1:-1]
    y = np.linspace(-m.y_span_um / 2, m.y_span_um / 2, m.ny + 2)[1:-1]
    dx, dy = x[1] - x[0], y[1] - y[0]
    xx, yy = np.meshgrid(x, y, indexing="ij")
    # Fractional cell occupancy reduces staircasing as a YAML width is varied.
    fx = np.clip((d.width_um / 2 - np.abs(x)) / dx + 0.5, 0, 1)
    fy = np.clip((d.core_thickness_um / 2 - np.abs(y)) / dy + 0.5, 0, 1)
    fa = np.clip((d.active_thickness_um / 2 - np.abs(y)) / dy + 0.5, 0, 1)
    core = fx[:, None] * fy[None, :]
    active = fx[:, None] * fa[None, :]
    n2 = m.cladding_index**2 + (m.core_index**2 - m.cladding_index**2) * core
    k0 = 2 * np.pi / (c.source.wavelength_nm * 1e-3)
    dxx = diags([np.ones(m.nx - 1), -2 * np.ones(m.nx), np.ones(m.nx - 1)], [-1, 0, 1]) / dx**2
    dyy = diags([np.ones(m.ny - 1), -2 * np.ones(m.ny), np.ones(m.ny - 1)], [-1, 0, 1]) / dy**2
    operator = kron(dxx, eye(m.ny)) + kron(eye(m.nx), dyy) + diags((k0**2 * n2).ravel())
    values, vectors = eigsh(operator.tocsc(), k=1, sigma=(k0 * m.core_index)**2, which="LM", v0=np.ones(m.nx * m.ny), tol=1e-10)
    neff = np.sqrt(values[0]) / k0
    if not m.cladding_index < neff < m.core_index:
        raise RuntimeError("No guided scalar mode found. Increase window/resolution or change core geometry.")
    intensity = np.abs(vectors[:, 0].reshape(m.nx, m.ny))**2
    intensity /= np.sum(intensity) * dx * dy
    area = 1 / (np.sum(intensity**2) * dx * dy)
    gamma = np.sum(intensity * active) * dx * dy
    edge = (np.abs(xx) > m.x_span_um * 0.4) | (np.abs(yy) > m.y_span_um * 0.4)
    return ModeResult(float(gamma), float(area), float(neff), x, y, intensity, np.sqrt(n2), float(np.sum(intensity[edge]) * dx * dy))
