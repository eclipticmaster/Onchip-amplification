"""Small hard-coded export fixtures verify plotting/IO, not simulation physics."""
import json

import h5py
import numpy as np
import pytest
from scipy.io import savemat

from inpamp.results import describe_results, plot_native, plot_sweep, read_results


def test_fdtd_offline_plot_preserves_exported_values(tmp_path, monkeypatch):
    import inpamp.lumerical as native
    monkeypatch.setattr(native, "load_api", lambda *a: pytest.fail("plotting must not load Ansys"))
    data = tmp_path / "native"
    data.mkdir()
    savemat(data / "taper_transmission.mat", {"f": [1.8e14, 1.9e14, 2e14], "T": [.7, .8, .9], "R": [.2, .1, .05]})
    result = plot_native(data, "fdtd", tmp_path / "graphs")
    assert result["simulation_performed"] is False
    csv = np.loadtxt(tmp_path / "graphs/taper.csv", delimiter=",", skiprows=1)
    np.testing.assert_array_equal(csv[:, 1], [.9, .8, .7])
    assert (tmp_path / "graphs/taper.png").stat().st_size > 1000


def test_mode_plot_reads_native_area_overlap_and_dispersion(tmp_path):
    data = tmp_path / "mode"
    data.mkdir()
    savemat(data / "mode_fields.mat", {"x": [-1e-6, 0, 1e-6], "y": [-1e-6, 1e-6], "E2": [[1., 2.], [3., 4.], [5., 6.]]})
    savemat(data / "mode_metrics.mat", {"neff": 3.2, "Gamma": .27, "Aeff": 1.4e-12})
    savemat(data / "mode_dispersion.mat", {"f_D": [1.8e14, 1.9e14, 2e14], "D": [-1e-5, -2e-5, -3e-5]})
    plot_native(data, "mode", tmp_path / "graphs")
    result = json.loads((tmp_path / "graphs/mode_metrics.json").read_text())
    assert result["active_power_overlap"] == .27
    assert result["scalar_field_area_um2"] == pytest.approx(1.4)
    assert result["calculated_by"] == "Lumerical mode.lsf"


def test_nested_mat_and_json_interconnect_traces(tmp_path):
    native = tmp_path / "native"
    native.mkdir()
    savemat(native / "spectrum.mat", {"output_spectrum": {"frequency": [1., 2., 3.], "power": [.2, .3, .4]}})
    fields = describe_results(native / "spectrum.mat")
    assert "output_spectrum.power" in {r["field"] for r in fields}
    plot_native(native, "interconnect", tmp_path / "graphs", result="spectrum.mat",
                x_field="output_spectrum.frequency", y_field="output_spectrum.power")
    (native / "spectrum.json").write_text(json.dumps({"frequency": [1., 2.], "power": {"real": [1., 2.], "imag": [.1, .2]}}))
    with pytest.raises(ValueError, match="complex"):
        plot_native(native, "interconnect", tmp_path / "bad", result="spectrum.json", x_field="frequency", y_field="power")
    plot_native(native, "interconnect", tmp_path / "complex", result="spectrum.json", x_field="frequency", y_field="power", component="abs")


def test_hdf5_matlab_arrays_read_with_correct_dimensions(tmp_path):
    path = tmp_path / "native-v73.mat"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("E2", data=np.array([[1., 2., 3.], [4., 5., 6.]]))
    data = read_results(path)
    np.testing.assert_array_equal(data["E2"], [[1., 4.], [2., 5.], [3., 6.]])


def test_missing_partial_and_failed_data_cannot_make_fake_graphs(tmp_path):
    data = tmp_path / "native"
    data.mkdir()
    with pytest.raises(ValueError, match="not found"):
        plot_native(data, "fdtd", tmp_path / "missing")
    (data / "run_status.json").write_text(json.dumps({"status": "failed", "results_verified": False}))
    with pytest.raises(ValueError, match="failed"):
        plot_native(data, "fdtd", tmp_path / "failed")


def test_native_sweep_plot_uses_one_exported_measurement_per_case(tmp_path):
    directory = tmp_path / "native"
    directory.mkdir()
    manifest = {"status": "completed", "name": "current", "solver": "interconnect", "parameter": "device.current_mA", "cases": []}
    for index, (current, power) in enumerate([(100., .01), (200., .03)]):
        case = directory / f"case_{index:03d}"
        case.mkdir()
        (case / "power.json").write_text(json.dumps({"power": power}))
        manifest["cases"].append({"directory": case.name, "value": current})
    (directory / "sweep_manifest.json").write_text(json.dumps(manifest))
    plot_sweep(directory, tmp_path / "graphs", result="power.json", field="power")
    csv = np.loadtxt(tmp_path / "graphs/sweep.csv", delimiter=",", skiprows=1)
    np.testing.assert_array_equal(csv, [[100., .01], [200., .03]])
