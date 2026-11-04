import numpy as np
import pytest
from scipy.constants import e
from scipy.optimize import brentq

from inpamp.config import Config
from inpamp.microcomb import integrate_lle
from inpamp.mode import ModeResult, solve_mode
from inpamp.soa import gain_shape, propagate, recombination, solve_soa, transparency
from inpamp.transient import simulate_transient
from inpamp.workflow import change


@pytest.fixture(scope="module")
def mode():
    return solve_mode(Config())


def test_propagation_matches_analytic_limits():
    coefficient = np.array([0.0, 12.0, -9.0, 1e-14])
    power, source, dz = 0.2, 0.01, 0.1
    actual = propagate(power, coefficient, source, dz)
    expected = np.array([power + source * dz,
                         power * np.exp(1.2) + source / 12 * np.expm1(1.2),
                         power * np.exp(-0.9) + source / -9 * np.expm1(-0.9),
                         power + source * dz])
    np.testing.assert_allclose(actual, expected, rtol=1e-12)


def test_mode_is_guided_and_normalized(mode):
    assert 3.17 < mode.neff < 3.4
    assert 0 < mode.confinement < 1
    dx, dy = mode.x[1] - mode.x[0], mode.y[1] - mode.y[0]
    assert np.sum(mode.intensity) * dx * dy == pytest.approx(1)
    assert mode.boundary_fraction < 1e-3


def test_passive_limit_is_exact_at_zero_injection():
    c = change(Config(), "device", current_mA=0.0)
    r = solve_soa(c, ModeResult(0.0, 1.0))
    expected_gain = np.exp(-c.device.internal_loss_per_m * c.device.length_um * 1e-6) * 10**(-(c.device.input_loss_dB + c.device.output_loss_dB) / 10)
    assert r.summary["output_power_mW"] == pytest.approx(c.source.input_power_mW * expected_gain, rel=1e-12)
    assert np.max(r.carriers_m3) < 1e10
    assert r.summary["forward_ase_mW"] == 0


def test_small_signal_matches_unsaturated_analytic_gain(mode):
    c = change(Config(), "thermal", enabled=False)
    c = change(c, "numerics", include_ase=False)
    # Unsaturated gain is ~60 dB with ASE disabled; keep even the amplified
    # power negligible compared with the stimulated-depletion scale.
    c = change(c, "source", input_power_mW=1e-13)
    c = change(c, "material", gain_compression_per_W=0.0)
    d = c.device
    volume = d.length_um * d.width_um * d.active_thickness_um * 1e-18
    injection = d.injection_efficiency * d.current_mA * 1e-3 / (e * volume)
    n0 = brentq(lambda n24: (recombination(n24 * 1e24, c.material) - injection) / 1e33, 0, 100) * 1e24
    g = mode.confinement * c.material.differential_gain_m2 * (n0 - transparency(c, 300)) * gain_shape(c, c.source.wavelength_nm, 300)
    analytic = 10 / np.log(10) * (g - d.internal_loss_per_m) * d.length_um * 1e-6 - d.input_loss_dB - d.output_loss_dB
    r = solve_soa(c, mode)
    assert r.summary["gain_dB"] == pytest.approx(analytic, abs=1e-5)
    assert np.max(np.abs(r.carriers_m3 / n0 - 1)) < 1e-6


def test_saturation_carrier_balance_and_electrical_budget(mode):
    c = Config()
    low = solve_soa(change(c, "source", input_power_mW=0.1), mode)
    high = solve_soa(change(c, "source", input_power_mW=10.0), mode)
    assert high.summary["gain_dB"] < low.summary["gain_dB"]
    assert high.summary["output_power_mW"] > low.summary["output_power_mW"]
    for r in [low, high]:
        assert r.summary["carrier_balance_relative_residual"] < 1e-5
        assert r.summary["optical_extraction_mW"] < r.summary["electrical_power_mW"]
        assert r.summary["junction_temperature_K"] >= c.thermal.ambient_K
        assert r.summary["forward_ase_mW"] > 0
        assert np.min(r.ase_forward_W) >= 0
        assert np.min(r.ase_backward_W) >= 0
        assert np.all(r.ase_forward_W[0] == 0)
        assert np.all(r.ase_backward_W[-1] == 0)


def test_no_current_step_remains_at_equilibrium(mode):
    c = change(Config(), "transient", initial_current_mA=250.0)
    r = simulate_transient(c, mode, 300)
    np.testing.assert_allclose(r["carriers_m3"], r["carriers_m3"][0], rtol=1e-7)
    np.testing.assert_allclose(r["chirp_GHz"], 0, atol=1e-6)


def test_linear_lle_matches_driven_cavity_solution():
    # Exact steady state and a time-varying integration implemented independently.
    r = integrate_lle(1.2, np.zeros(32), alpha_start=2.0, alpha_end=2.0, dt=0.02,
                      scan_time=0, hold_time=4, field_noise_per_sqrt_tau=0, kerr=False)
    np.testing.assert_allclose(r["field"], 1.2 / (1 + 2j), atol=1e-12)
    assert np.sum(r["spectrum"][1:]) < 1e-25


def test_nonlinear_lle_homogeneous_fixed_point_and_dt_refinement():
    # For |psi|^2=1, alpha=1, F=1, the continuous LLE has psi=1.
    # Starting off that branch, compare integration errors as dt is halved.
    args = dict(drive=1.0, dispersion=np.zeros(32), alpha_start=1.0, alpha_end=1.0,
                scan_time=0, hold_time=60, field_noise_per_sqrt_tau=0)
    coarse = integrate_lle(**args, dt=0.02)["field"][0]
    fine = integrate_lle(**args, dt=0.01)["field"][0]
    assert abs(fine - 1) < abs(coarse - 1)
    assert abs(fine - 1) < 2e-4


def test_lle_restricts_fast_dispersion_steps():
    r = integrate_lle(1, np.arange(32) * 20, alpha_start=1, alpha_end=1, dt=.02,
                      scan_time=0, hold_time=.1, field_noise_per_sqrt_tau=0, kerr=False)
    assert r["actual_time_step"] < .02
    assert r["max_dispersion_phase_per_step"] <= .5
