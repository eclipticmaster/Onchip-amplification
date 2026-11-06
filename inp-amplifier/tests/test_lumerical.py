"""API protocol tests and fixture values; these do not execute Ansys physics."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from inpamp.config import Config, with_override
import inpamp.lumerical as native


@pytest.mark.parametrize("generate", [native.mode_script, native.fdtd_script, native.interconnect_script])
def test_native_scripts_have_no_merge_conflicts(generate):
    script = generate(Config())
    assert not any(line.startswith(("<<<<<<<", "=======", ">>>>>>>")) for line in script.splitlines())


def test_nominal_metrics_are_exported_before_seeding_tracked_sweep():
    script = native.mode_script(Config())
    metrics, sweep = script.split('copydcard("mode1","inpamp_nominal_mode");')
    assert 'matlabsave("mode_metrics.mat",neff,Gamma,Aeff);' in metrics
    assert 'setanalysis("wavelength",1.5e-06);' in sweep
    assert sweep.index("findmodes;") < sweep.index('setanalysis("track selected mode",1);')
    assert 'selectmode(bestoverlap("inpamp_nominal_mode"));' in sweep
    assert 'setanalysis("start wavelength"' not in sweep


def test_native_scripts_encode_geometry_and_native_metrics():
    c = with_override(Config(), "device.width_um", 2.6)
    script = native.mode_script(c)
    assert 'set("x span",2.6e-06)' in script
    assert "findmodes" in script and "frequencysweep" in script
    assert "Gamma=real(integrate2" in script and "Aeff=real(integrate2" in script
    assert 'matlabsave("mode_metrics.mat",neff,Gamma,Aeff)' in script
    assert 'set("injection axis","x-axis")' in native.fdtd_script(c)
    assert 'R=-transmission("R")' in native.fdtd_script(c)


def test_export_is_not_a_simulation(tmp_path):
    output = tmp_path / "export"
    plan = native.export_lumerical(Config(), output)
    assert plan["status"] == "scripts_generated_not_simulated"
    assert len(list(output.glob("*.lsf"))) == 3
    assert not list(output.glob("*.lms"))
    assert not list(output.glob("*.fsp"))
    assert not list(output.glob("*.icp"))
    with pytest.raises(ValueError, match="not empty"):
        native.export_lumerical(Config(), output)


def test_native_material_and_string_binding_are_preserved():
    c = Config.model_validate({"parameters": {"material_name": "custom core"}, "lumerical": {
        "core_material": "measured core", "interconnect": {"bindings": [
            {"element": "soa", "property": "material", "quantity": "parameters.material_name"}]}}})
    assert 'set("material","measured core")' in native.mode_script(c)
    assert 'setnamed("soa","material","custom core")' in native.interconnect_script(c)


def test_native_failure_has_no_fallback(tmp_path, monkeypatch):
    def unavailable(**kwargs):
        raise RuntimeError("test native license failure")
    monkeypatch.setattr(native, "load_api", lambda _: SimpleNamespace(MODE=unavailable))
    output = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="native license failure"):
        native.run_lumerical(Config(), "mode", output)
    status = json.loads((output / "run_status.json").read_text())
    assert status["status"] == "failed" and status["results_verified"] is False
    assert not list(output.glob("*.mat"))


def test_mode_serialization_uses_native_metric_values_only(tmp_path):
    fixture = {"neff": 3.25 + .01j, "Gamma": .23, "Aeff": 1.2e-12}
    class ExportedValues:
        def getv(self, key):
            return fixture[key]
    native._export_mode_data(ExportedValues(), tmp_path)
    result = json.loads((tmp_path / "mode_metrics.json").read_text())
    assert result["active_power_overlap"] == .23
    assert result["scalar_field_area_m2"] == 1.2e-12


def test_mode_run_dispatches_native_script_and_requires_native_artifacts(tmp_path, monkeypatch):
    # This records the API contract; it never computes a field or mode.
    calls = []
    class Session:
        def __init__(self, **kwargs):
            calls.append("open_MODE")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def eval(self, script):
            calls.append(script)
        def getv(self, key):
            return {"inpamp_script_error": "", "neff": 3.25, "Gamma": .23, "Aeff": 1.2e-12}[key]
    monkeypatch.setattr(native, "load_api", lambda _: SimpleNamespace(MODE=Session))
    with pytest.raises(RuntimeError, match="expected artifact"):
        native.run_lumerical(Config(), "mode", tmp_path / "native")
    assert calls[0] == "open_MODE"
    assert "feval(" in calls[2]
    assert "findmodes" in (tmp_path / "native" / "mode.lsf").read_text()


def test_empty_native_datasets_and_bad_api_path_rejected(tmp_path):
    assert not native._has_numeric_data({"Lumerical_dataset": {"id": 1}, "power": []})
    assert not native._has_numeric_data({"power": np.array([np.nan])})
    assert native._has_numeric_data({"power": np.array([0.0, 1.0])})
    with pytest.raises(ValueError, match="vendor lumapi.py"):
        native.load_api(tmp_path)


def test_native_script_error_is_reported_and_stops_postprocessing(tmp_path, monkeypatch):
    import inpamp.lumerical as native

    message = "Error: mode.lsf line 32: in set, the requested property 'name' is inactive"

    class FailedScriptSession:
        def __init__(self, **kwargs):
            self.commands = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def eval(self, script):
            self.commands.append(script)

        def getv(self, name):
            assert name == "inpamp_script_error", "Postprocessing must not run after a native failure"
            return message

    session = FailedScriptSession()

    class ScriptAPI:
        MODE = FDTD = INTERCONNECT = staticmethod(lambda **kwargs: session)

    monkeypatch.setattr(native, "load_api", lambda path: ScriptAPI)
    output = tmp_path / "native with spaces"
    with pytest.raises(RuntimeError, match="mode.lsf line 32"):
        native.run_lumerical(Config(), "mode", output)
    status = json.loads((output / "run_status.json").read_text())
    assert status["status"] == "failed"
    assert status["results_verified"] is False
    assert message in status["error"]
    assert len(session.commands) == 2  # cd and one execution, with no retry
    assert 'try { feval(' in session.commands[-1]
    assert (output / "mode.lsf").resolve().as_posix() in session.commands[-1]


@pytest.mark.parametrize("hide,keep_open,expected", [(False, True, True), (True, True, False), (False, False, False)])
def test_gui_reopens_only_after_successful_visible_runs(tmp_path, monkeypatch, hide, keep_open, expected):
    output = tmp_path / "run"
    opened = []

    class Session:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def fixture_exports(session, script):
        for name in ["inp_waveguide.lms", "mode_fields.mat", "mode_dispersion.mat", "mode_metrics.mat"]:
            (output / name).write_text("IO fixture, not simulation data")

    Session.eval = lambda self, script: None
    monkeypatch.setattr(native, "load_api", lambda _: SimpleNamespace(MODE=Session))
    monkeypatch.setattr(native, "_run_native_script", fixture_exports)
    monkeypatch.setattr(native, "_export_mode_data", lambda s, p: (p / "mode_metrics.json").write_text("{}"))
    monkeypatch.setattr(native, "_open_project_gui", lambda api, solver, path: opened.append(path))
    c = Config.model_validate({"lumerical": {"hide_gui": hide, "keep_open": keep_open}})
    status = native.run_lumerical(c, "mode", output)
    assert status["status"] == "completed" and status["results_verified"]
    assert opened == ([output / "inp_waveguide.lms"] if expected else [])


def test_gui_launch_uses_vendor_installation_and_separate_path_arguments(tmp_path, monkeypatch):
    installation = tmp_path / "Ansys with spaces"
    api_path = installation / "api" / "python" / "lumapi.py"
    executable = installation / "bin" / ("mode-solutions.exe" if native.os.name == "nt" else "mode-solutions")
    executable.parent.mkdir(parents=True)
    executable.touch()
    project = tmp_path / "results with spaces" / "inp_waveguide.lms"
    calls = []
    monkeypatch.setattr(native.subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)))
    native._open_project_gui(SimpleNamespace(__file__=str(api_path)), "mode", project)
    assert calls == [([str(executable), str(project.resolve())], {"cwd": str(project.parent.resolve())})]
