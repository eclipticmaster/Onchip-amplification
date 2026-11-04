import json
from pathlib import Path

import pytest

from inpamp.config import Config
from inpamp.workflow import ensure_parameter_applied, run_sweep


def config():
    return Config.model_validate({"sweeps": [{"name": "current", "solver": "interconnect", "parameter": "device.current_mA", "values": [100., 200.]}]})


def test_sweep_dispatches_every_case_to_native_runner(tmp_path, monkeypatch):
    calls = []
    def record(c, solver, output, **kwargs):
        calls.append((c.device.current_mA, solver, output.name))
    monkeypatch.setattr("inpamp.workflow.run_lumerical", record)
    result = run_sweep(config(), "current", tmp_path / "sweep", progress=lambda _: None)
    assert calls == [(100., "interconnect", "case_000"), (200., "interconnect", "case_001")]
    assert result["engine"] == "Ansys Lumerical" and result["status"] == "completed"


def test_sweep_export_does_not_claim_simulation(tmp_path):
    result = run_sweep(config(), "current", tmp_path / "sweep", export_only=True, progress=lambda _: None)
    assert result["status"] == "exported_not_simulated"
    assert not list((tmp_path / "sweep").rglob("*.icp"))
    assert 'setnamed("bias_current","amplitude",0.1)' in (tmp_path / "sweep/case_000/interconnect.lsf").read_text()


def test_unbound_or_irrelevant_parameter_is_rejected():
    with pytest.raises(ValueError, match="no binding"):
        ensure_parameter_applied(Config(), "interconnect", "device.length_um")
    with pytest.raises(ValueError, match="not used"):
        ensure_parameter_applied(Config(), "mode", "device.current_mA")


def test_native_sweep_failure_stops_without_python_fallback(tmp_path, monkeypatch):
    calls = []
    def fail(c, *args, **kwargs):
        calls.append(c.device.current_mA)
        raise RuntimeError("native launch failed")
    monkeypatch.setattr("inpamp.workflow.run_lumerical", fail)
    with pytest.raises(RuntimeError, match="native launch failed"):
        run_sweep(config(), "current", tmp_path / "sweep", progress=lambda _: None)
    assert calls == [100.]
    manifest = json.loads((tmp_path / "sweep/sweep_manifest.json").read_text())
    assert manifest["status"] == "failed" and manifest["cases"][0]["status"] == "failed"
