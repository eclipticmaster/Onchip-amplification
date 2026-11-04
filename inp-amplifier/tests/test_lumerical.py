import json

import numpy as np
import pytest

from inpamp.config import Config
from inpamp.lumerical import _save_mode_metrics, export_lumerical, fdtd_script, interconnect_script, load_api, mode_script, quantities
from inpamp.workflow import change


def test_native_scripts_use_yaml_geometry_and_si_units():
    c = change(Config(), "device", width_um=2.6, core_thickness_um=0.5, current_mA=325.0)
    mode = mode_script(c)
    assert 'set("x span",2.6e-06);' in mode
    assert 'set("y span",5e-07);' in mode
    assert "findmodes" in mode and "frequencysweep" in mode
    assert "matlabsave" in mode
    fdtd = fdtd_script(c)
    assert 'set("injection axis","x-axis")' in fdtd
    assert 'set("monitor type","2D X-normal")' in fdtd
    assert 'R=-transmission("R")' in fdtd
    assert quantities(c)["device.current_A"] == pytest.approx(0.325)
    assert quantities(c)["device.active_volume_m3"] == pytest.approx(1000 * 2.6 * .12 * 1e-18)
    assert 'setnamed("bias_current","amplitude",0.325)' in interconnect_script(c)


def test_material_names_are_native_overrides():
    c = change(Config(), "lumerical", core_material="my_calibrated_core")
    script = mode_script(c)
    assert 'set("material","my_calibrated_core")' in script
    core_section = script.split('set("name","effective_active_core")')[1].split("addfde;")[0]
    assert 'set("index"' not in core_section


def test_export_is_not_a_native_simulation(tmp_path):
    p = tmp_path / "export"
    plan = export_lumerical(Config(), p)
    assert plan["status"] == "scripts_generated_not_simulated"
    assert not plan["interconnect"]["template_configured"]
    assert plan["fdtd"]["estimated_uniform_mesh_cells"] > 100000
    assert sorted(q.suffix for q in p.glob("*.lsf")) == [".lsf"] * 3
    assert not list(p.glob("*.lms"))
    assert not list(p.glob("*.fsp"))
    assert not list(p.glob("*.icp"))
    assert "native" in (p / "interconnect.lsf").read_text().lower()
    with pytest.raises(ValueError, match="not empty"):
        export_lumerical(Config(), p)


def test_vendor_api_path_must_point_to_vendor_module(tmp_path):
    with pytest.raises(ValueError, match="vendor lumapi.py"):
        load_api(tmp_path)


def test_native_vector_field_postprocessing_with_analytic_flux(tmp_path):
    # An independent synthetic constant field checks the math only, not Ansys.
    x = np.linspace(-2e-6, 2e-6, 101)
    y = np.linspace(-1e-6, 1e-6, 101)
    shape = (len(x), len(y))
    arrays = dict(x=x, y=y, Ex=np.ones(shape, dtype=complex), Hy=np.ones(shape, dtype=complex),
                  Ey=np.zeros(shape), Ez=np.zeros(shape), Hx=np.zeros(shape), neff=np.array(3.25 + 0j))

    class FieldsOnly:
        def getv(self, name):
            return arrays[name]

    _save_mode_metrics(FieldsOnly(), Config(), tmp_path)
    metrics = json.loads((tmp_path / "mode_metrics.json").read_text())
    assert metrics["neff_real"] == 3.25
    assert metrics["scalar_field_area_um2"] == pytest.approx(8)
    expected_fraction = 2.0 * 0.12 / 8
    assert metrics["active_power_overlap"] == pytest.approx(expected_fraction, rel=0.02)


def test_native_launch_failure_cannot_be_reported_as_success(tmp_path, monkeypatch):
    import inpamp.lumerical as native

    def fail_session(**kwargs):
        raise RuntimeError("test license launch failure")

    class FailingAPI:
        MODE = staticmethod(fail_session)
        FDTD = staticmethod(fail_session)
        INTERCONNECT = staticmethod(fail_session)

    monkeypatch.setattr(native, "load_api", lambda path: FailingAPI)
    output = tmp_path / "native"
    with pytest.raises(RuntimeError, match="license launch failure"):
        native.run_lumerical(Config(), "mode", output)
    status = json.loads((output / "run_status.json").read_text())
    assert status["status"] == "failed"
    assert status["results_verified"] is False
    assert not list(output.glob("*.lms"))
