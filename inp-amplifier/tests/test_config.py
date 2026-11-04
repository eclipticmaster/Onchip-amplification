from pathlib import Path

import pytest
from pydantic import ValidationError

from inpamp.config import Config, load_config

CONFIGS = Path(__file__).parents[1] / "configs"


@pytest.mark.parametrize("path", sorted(CONFIGS.glob("*.yaml")))
def test_examples_validate(path):
    assert load_config(path).source.wavelength_nm == 1550


def test_inheritance_and_override():
    c = load_config(CONFIGS / "high_current.yaml", ["device.length_um=1500.0"])
    assert c.device.current_mA == 350
    assert c.device.length_um == 1500
    assert c.material.differential_gain_m2 == 2.5e-20


@pytest.mark.parametrize("override", ["device.curent_mA=150.0", "source.input_power_mW=-1", "device.length_um=.nan", "device.current_mA=true", "mode.nx=12", "microcomb.modes=100"])
def test_invalid_physics_and_typos_are_rejected(override):
    with pytest.raises((ValueError, ValidationError)):
        load_config(CONFIGS / "inp_pump.yaml", [override])


def test_duplicate_keys_rejected(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("device:\n  current_mA: 100.0\n  current_mA: 200.0\n")
    with pytest.raises(ValueError, match="Duplicate"):
        load_config(p)


def test_cyclic_inheritance_rejected(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("extends: bad.yaml\n")
    with pytest.raises(ValueError, match="Cyclic"):
        load_config(p)


def test_active_region_must_fit_core():
    with pytest.raises(ValidationError):
        Config.model_validate({"device": {"active_thickness_um": 0.8}})
