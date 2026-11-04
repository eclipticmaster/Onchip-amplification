import json

import gdstk
import pytest

from inpamp.config import Config
from inpamp.workflow import change, run


def test_amplifier_workflow_writes_consistent_artifacts(tmp_path):
    c = change(Config(), "sweeps", enabled=False)
    c = change(c, "transient", enabled=False)
    c = change(c, "microcomb", enabled=False)
    output = tmp_path / "study"
    result = run(c, output, progress=lambda _: None)
    summary = json.loads((output / "summary.json").read_text())
    assert summary["amplifier"] == result["amplifier"]
    assert (output / "report.html").stat().st_size > 10000
    assert (output / "longitudinal.csv").stat().st_size > 1000
    assert (output / "resolved_config.yaml").exists()
    assert (output / "metadata.json").exists()
    lib = gdstk.read_gds(str(output / "design.gds"))
    assert lib.top_level()[0].bounding_box()[1][0] > c.device.length_um
    ports = json.loads((output / "ports.json").read_text())
    assert ports["amplifier_output"]["center"][0] == c.device.length_um + 2 * c.layout.taper_length_um
    # Reruns cannot silently combine new data with old figures.
    with pytest.raises(ValueError, match="not empty"):
        run(c, output, progress=lambda _: None)
