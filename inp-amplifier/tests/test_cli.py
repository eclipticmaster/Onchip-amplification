import ast
from pathlib import Path

import pytest

from inpamp.cli import main


def test_run_requires_native_solver_and_cannot_run_old_python_workflow():
    with pytest.raises(SystemExit) as error:
        main(["run", "configs/lumerical.yaml", "--output", "unused"])
    assert error.value.code == 2


def test_default_run_and_compatibility_alias_dispatch_native(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("inpamp.lumerical.run_lumerical", lambda c, solver, output, **kw: calls.append(solver) or {"test": "dispatch only"})
    config = Path(__file__).parents[1] / "configs/lumerical.yaml"
    for command in ["run", "run-lumerical"]:
        assert main([command, str(config), "--solver", "mode", "--output", str(tmp_path / command)]) == 0
    assert calls == ["mode", "mode"]


def test_completed_cli_runs_generate_figures_automatically(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("inpamp.lumerical.run_lumerical", lambda *a, **kw: {"status": "completed", "results_verified": True})
    monkeypatch.setattr("inpamp.figures.create_figures", lambda output, **kw: calls.append((output, kw)) or {"gallery": "fixture.html"})
    config = Path(__file__).parents[1] / "configs/lumerical.yaml"
    output = tmp_path / "native"
    assert main(["run", str(config), "--solver", "mode", "--output", str(output)]) == 0
    assert calls == [(output, {"style_path": None, "show": True})]
    calls.clear()
    assert main(["run", str(config), "--solver", "mode", "--output", str(output), "--set", "lumerical.make_figures=false"]) == 0
    assert not calls


@pytest.mark.parametrize("command", ["run", "run-lumerical"])
def test_repeated_native_commands_can_omit_output(tmp_path, monkeypatch, capsys, command):
    import json
    outputs = []
    def record(c, solver, output, **kwargs):
        outputs.append(output)
        (output / "preserved.txt").write_text("saved run")
        return {"status": "dispatch fixture"}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("inpamp.lumerical.run_lumerical", record)
    config = Path(__file__).parents[1] / "configs/lumerical.yaml"
    for _ in range(2):
        assert main([command, str(config), "--solver", "mode"]) == 0
        assert Path(json.loads(capsys.readouterr().out)["output_directory"]) == outputs[-1]
    assert outputs[0] != outputs[1]
    assert all(p.parent == tmp_path / "results" and p.name.startswith("mode-") for p in outputs)
    assert all((p / "preserved.txt").read_text() == "saved run" for p in outputs)


def test_existing_explicit_output_and_default_exports_are_reusable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = Path(__file__).parents[1] / "configs/lumerical.yaml"
    existing = tmp_path / "my-scripts"
    for _ in range(2):
        assert main(["export", str(config), "--output", str(existing)]) == 0
    assert len(list(tmp_path.glob("my-scripts*"))) == 2
    assert (existing / "mode.lsf").is_file()
    for _ in range(2):
        assert main(["export", str(config)]) == 0
    assert len(list((tmp_path / "results").glob("scripts-*"))) == 2


def test_repeated_figure_commands_choose_fresh_folders(tmp_path, monkeypatch):
    outputs = []
    def record(directory, output, **kwargs):
        outputs.append(output)
        (output / "index.html").write_text("gallery")
        return {"gallery": str(output / "index.html")}
    monkeypatch.setattr("inpamp.figures.create_figures", record)
    for _ in range(2):
        assert main(["figures", str(tmp_path)]) == 0
    assert outputs[0] == tmp_path / "figures"
    assert outputs[1] != outputs[0] and outputs[1].name.startswith("figures-")
    assert (outputs[0] / "index.html").read_text() == "gallery"


def test_package_has_no_retired_solver_modules_or_solver_imports():
    source = Path(__file__).parents[1] / "src/inpamp"
    for module in ["soa.py", "mode.py", "transient.py", "microcomb.py", "layout.py"]:
        assert not (source / module).exists()
    forbidden = {"scipy.optimize", "scipy.integrate", "scipy.sparse", "numpy.fft", "scipy.fft"}
    for file in source.glob("*.py"):
        tree = ast.parse(file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in forbidden
            elif isinstance(node, ast.Import):
                assert not any(alias.name in forbidden for alias in node.names)
