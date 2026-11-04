#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
venv_dir="${VENV_DIR:-$project_dir/.venv}"
python3 -m venv "$venv_dir"
"$venv_dir/bin/python" -m pip install -r requirements.lock
"$venv_dir/bin/python" -m pip install --no-build-isolation --no-deps -e .
"$venv_dir/bin/python" -m pip check
"$venv_dir/bin/python" -m inpamp validate configs/lumerical.yaml
