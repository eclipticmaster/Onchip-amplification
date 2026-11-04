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
