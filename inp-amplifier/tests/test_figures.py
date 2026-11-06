"""Figure IO and independent unit-conversion checks; no surrogate simulations."""
import hashlib
import json

import numpy as np
import pytest
from scipy.io import savemat
import yaml

from inpamp.figures import C0, create_figures


def fixture_mode(path):
    path.mkdir()
    savemat(path / "mode_fields.mat", {"x": [-1e-6, 0., 1e-6], "y": [-.5e-6, .5e-6], "E2": [[1., 2.], [2., 4.], [1., 2.]]})
    savemat(path / "mode_metrics.mat", {"neff": 3.2 + .001j, "Gamma": .24, "Aeff": 1.3e-12})
    savemat(path / "mode_dispersion.mat", {"f_D": C0 / np.array([1500e-9, 1550e-9, 1600e-9]), "D": [-2e-5, -3e-5, -4e-5]})
    (path / "run_status.json").write_text(json.dumps({"solver": "mode", "status": "completed", "results_verified": True}))
    return path


def quick_style(path, **kwargs):
    path.write_text(yaml.safe_dump({"dpi": 72, "formats": ["png", "pdf", "svg"], **kwargs}))
    return path


def test_mode_figures_preserve_native_data_and_have_correct_units(tmp_path, monkeypatch):
    monkeypatch.setattr("inpamp.lumerical.load_api", lambda *a: pytest.fail("No native session when plotting"))
    source = fixture_mode(tmp_path / "mode")
    original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
    result = create_figures(source, style_path=quick_style(tmp_path / "style.yaml"))
    output = source / "figures"
    assert len(result["figures"]) == 4
    data = np.genfromtxt(output / "waveguide_dispersion.csv", delimiter=",", names=True)
    np.testing.assert_allclose(data["wavelength_nm_0"], [1500., 1550., 1600.])
    np.testing.assert_allclose(data["D_ps_nm_km"], [-20., -30., -40.])
    beta2 = np.genfromtxt(output / "waveguide_beta2.csv", delimiter=",", names=True)
    # Independent SI conversion: beta2 [s²/m] = -D [s/m²] * lambda² / (2πc).
    expected = np.array([2e-5, 3e-5, 4e-5]) * (np.array([1500., 1550., 1600.]) * 1e-9) ** 2 / (2 * np.pi * C0) * 1e27
    np.testing.assert_allclose(beta2["beta2_fs2_mm"], expected)
    assert (output / "waveguide_dispersion.pdf").read_bytes().startswith(b"%PDF")
    assert "<svg" in (output / "waveguide_dispersion.svg").read_text()
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in original.items())
    assert json.loads((output / "metrics.json").read_text())["active_power_overlap"] == .24


def test_custom_style_and_regeneration_do_not_modify_samples(tmp_path):
    source = fixture_mode(tmp_path / "mode")
    style = quick_style(tmp_path / "style.yaml", figures={"waveguide_dispersion": {"title": "Edited title", "xlabel": "Edited axis", "colors": ["#aabbcc"], "xlim": [1520, 1580]}})
    result = create_figures(source, style_path=style)
    output = source / "figures"
    svg = (output / "waveguide_dispersion.svg").read_text()
    assert "Edited title" in svg and "Edited axis" in svg and "#aabbcc" in svg
    with pytest.raises(ValueError, match="exists"):
        create_figures(source)
    saved = yaml.safe_load((output / "figures.yaml").read_text())
    saved["figures"]["waveguide_dispersion"]["title"] = "Another title"
    (output / "figures.yaml").write_text(yaml.safe_dump(saved))
    create_figures(source, replace=True)
    assert "Another title" in (output / "waveguide_dispersion.svg").read_text()
    assert len(np.genfromtxt(output / "waveguide_dispersion.csv", delimiter=",", names=True)) == 3
    assert result["gallery"].endswith("index.html")


def test_fdtd_logarithms_do_not_floor_or_invent_power(tmp_path):
    source = tmp_path / "fdtd"
    source.mkdir()
    savemat(source / "taper_transmission.mat", {"f": [C0 / 1500e-9, C0 / 1550e-9, C0 / 1600e-9], "T": [1., .5, .1], "R": [0., .01, .1]})
    create_figures(source, solver="fdtd", style_path=quick_style(tmp_path / "style.yaml"))
    output = source / "figures"
    loss = np.genfromtxt(output / "taper_insertion_loss.csv", delimiter=",", names=True)
    np.testing.assert_allclose(loss["taper_insertion_loss_dB"], [0., 3.01029995664, 10.], atol=1e-10)
    reflected = np.genfromtxt(output / "taper_reflection_db.csv", delimiter=",", names=True)
    assert np.isnan(reflected["taper_reflection_db_dB"][0])
    np.testing.assert_allclose(reflected["taper_reflection_db_dB"][1:], [-20., -10.])


def test_gain_trace_uses_explicit_signal_power_ratio(tmp_path):
    source = tmp_path / "native"
    source.mkdir()
    (source / "gain.json").write_text(json.dumps({"Pin_W": [.001, .01, .1], "Pout_W": [.01, .05, .2]}))
    style = quick_style(tmp_path / "style.yaml", traces=[{"figure": "soa_gain", "file": "gain.json", "x": "Pin_W", "y": "Pout_W", "denominator": "Pin_W", "x_transform": "W_to_dBm", "y_transform": "ratio_to_dB"}])
    create_figures(source, solver="interconnect", style_path=style)
    data = np.genfromtxt(source / "figures/soa_gain.csv", delimiter=",", names=True)
    np.testing.assert_allclose(data["x_0"], [0., 10., 20.])
    np.testing.assert_allclose(data["Native_data"], [10., 10 * np.log10(5), 10 * np.log10(2)])


def test_failed_runs_and_unowned_directories_are_rejected(tmp_path):
    source = fixture_mode(tmp_path / "mode")
    output = tmp_path / "valuable data"
    output.mkdir()
    (output / "keep.txt").write_text("preserve")
    with pytest.raises(ValueError, match="previously generated"):
        create_figures(source, output, replace=True)
    assert (output / "keep.txt").read_text() == "preserve"
    (source / "run_status.json").write_text(json.dumps({"status": "failed"}))
    with pytest.raises(ValueError, match="failed"):
        create_figures(source)


def test_mode_sweep_plots_native_metrics_per_case(tmp_path):
    directory = tmp_path / "sweep"
    directory.mkdir()
    cases = []
    for i, value in enumerate([1., 2.]):
        case = fixture_mode(directory / f"case_{i}")
        savemat(case / "mode_metrics.mat", {"neff": 3.1 + i * .1, "Gamma": .2 + i * .1, "Aeff": (1 + i) * 1e-12})
        cases.append({"directory": case.name, "value": value})
    (directory / "sweep_manifest.json").write_text(json.dumps({"status": "completed", "solver": "mode", "parameter": "device.width_um", "cases": cases}))
    result = create_figures(directory, style_path=quick_style(tmp_path / "style.yaml"))
    assert result["figures"] == ["sweep_neff", "sweep_overlap", "sweep_area"]
    data = np.genfromtxt(directory / "figures/sweep_overlap.csv", delimiter=",", names=True)
    np.testing.assert_allclose(data["sweep_overlap"], [.2, .3])


@pytest.mark.parametrize("legacy_manifest", [False, True])
def test_complete_run_can_be_renamed_and_its_recipe_regenerated(tmp_path, monkeypatch, legacy_manifest):
    import runpy
    monkeypatch.setattr("webbrowser.open", lambda *args: True)
    source = fixture_mode(tmp_path / "original-run")
    create_figures(source, style_path=quick_style(tmp_path / "style.yaml"))
    if legacy_manifest:
        manifest_path = source / "figures/figure_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        del manifest["source_directory_relative"]
        del manifest["source_files_relative"]
        manifest_path.write_text(json.dumps(manifest))
    renamed = tmp_path / "my chosen experiment name"
    assert source.parent == renamed.parent == tmp_path
    source.rename(renamed)
    runpy.run_path(str(renamed / "figures/regenerate.py"), run_name="__main__")
    manifest = json.loads((renamed / "figures/figure_manifest.json").read_text())
    assert manifest["source_directory"] == str(renamed)
    assert manifest["source_directory_relative"] == ".."
    assert "waveguide_dispersion.pdf" in manifest["artifacts"]
