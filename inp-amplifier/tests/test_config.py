from pathlib import Path

import pytest

from inpamp.config import Config, load_config, quantities, with_override

CONFIGS = Path(__file__).parents[1] / "configs"


@pytest.mark.parametrize("path", sorted(CONFIGS.glob("*.yaml")))
def test_native_examples_validate(path):
    assert load_config(path).schema_version == 2


def test_inheritance_and_si_conversion():
    c = load_config(CONFIGS / "high_current.yaml", ["device.length_um=1500.0"])
    assert quantities(c)["device.current_A"] == pytest.approx(.35)
    assert quantities(c)["device.length_m"] == pytest.approx(.0015)
    assert quantities(c)["source.power_W"] == pytest.approx(.001)


@pytest.mark.parametrize("override", ["device.curent_mA=150.0", "source.input_power_mW=-1", "device.length_um=.nan", "device.current_mA=true", "microcomb.modes=256", "numerics.z_cells=64", "mode.nx=100"])
def test_invalid_or_retired_inputs_fail(override):
    with pytest.raises(ValueError):
        load_config(CONFIGS / "inp_pump.yaml", [override])


def test_v1_has_migration_error(tmp_path):
    path = tmp_path / "old.yaml"
    path.write_text("schema_version: 1\n")
    with pytest.raises(ValueError, match="retired Python"):
        load_config(path)


def test_duplicate_keys_and_cyclic_inheritance(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("device:\n  current_mA: 100.0\n  current_mA: 200.0\n")
    with pytest.raises(ValueError, match="Duplicate"):
        load_config(path)
    path.write_text("extends: bad.yaml\n")
    with pytest.raises(ValueError, match="Cyclic"):
        load_config(path)


def test_explicit_native_parameter_binding():
    c = Config.model_validate({"parameters": {"alpha_H": 5.0}, "lumerical": {"interconnect": {"bindings": [
        {"element": "inp_soa", "property": "model-specific alpha", "quantity": "parameters.alpha_H"}
    ]}}})
    assert quantities(c)["parameters.alpha_H"] == 5
    assert quantities(with_override(c, "parameters.alpha_H", 6.0))["parameters.alpha_H"] == 6
    with pytest.raises(ValueError, match="Unknown native binding"):
        Config.model_validate({"lumerical": {"interconnect": {"bindings": [
            {"element": "inp_soa", "property": "alpha", "quantity": "parameters.missing"}
        ]}}})
