# InP amplifier simulations in Ansys Lumerical

**All physics simulations run in Lumerical.** Python reads YAML, generates native scripts, launches Ansys through its vendor API, and plots existing exported results. There are no Python gain/carrier, thermal, eigenmode, pulse or Kerr/LLE solvers, and no simulation fallback when Ansys is unavailable.

The intended system is CW laser → InGaAsP/InP semiconductor optical amplifier → microcomb pump link. MODE handles vector modes/overlap/dispersion; FDTD handles passive taper transmission/reflection; INTERCONNECT runs the active native SOA/CML circuit. Gain, ASE, carrier dynamics, heating and nonlinear resonator physics must be provided by the selected native model. Having a passive ring component alone does not simulate microcomb generation.

## Install the automation and plotting tools

<<<<<<< HEAD
Use your virtual-environment Python. The prepared cloud Python is `/workspace/.venvs/inp-amplifier/bin/python`. A checked-in [native script export](lumerical/generated/README.txt) is provided so you can copy it straight to Lumerical without Python on that machine. Open a **new** MODE/FDTD project, set its working directory to the export folder and run its script; the geometry script rebuilds the objects in that project.

| Product | Native work prepared |
| --- | --- |
| MODE | Vector FDE modes, tracked dispersion, field export, active-stripe power overlap |
| FDTD | Passive 3-D taper coupon with total transmission/reflection spectra |
| INTERCONNECT | Native SOA/CML template automation; YAML-to-model bindings and analyzer export |

For active gain, select/configure a native SOA or foundry CML circuit in INTERCONNECT once, inspect its actual property names, and set `lumerical.interconnect.template_path` and bindings. Then run `--solver interconnect`. This keeps gain/carrier physics in the native SOA model; it does not substitute a Python gain curve or an ideal amplifier. The [guide](docs/lumerical.md#3-prepare-the-active-soa-circuit-in-interconnect) gives the circuit structure and commands.

**Current validation:** The default YAML has been run through native MODE and FDTD on Windows with Ansys Lumerical 2026 R1 (v261). MODE produced nominal-wavelength fields/overlap metrics and 21 finite dispersion points spanning 1500–1600 nm; FDTD produced a saved taper project and 21 finite transmission/reflection samples over that range. Compatibility with other versions, convergence and SOA template calibration require separate checks. INTERCONNECT still requires your configured native SOA/CML template and has not been validated with an active circuit here. `.lms/.fsp/.icp` files are created by licensed native runs, not fabricated during export. Full native Kerr-comb simulation is not bundled; the included LLE is an optional separate Python reference model.

The starting effective InGaAsP/InP geometry and coefficients are illustrative, not a foundry stack or a literature-calibrated device. See [references and provenance](docs/references.md) and [calibration](docs/calibration.md). The earlier Er:Al₂O₃ scripts are retained separately.

---

The remainder documents the **optional Python reference calculations**, conceptual GDS export and their verification. These help check trends and pump budgets, and are never presented as Lumerical results.

## Optional Python reference workflow

From this `inp-amplifier` directory on Linux/macOS:
=======
From this directory:
>>>>>>> 06e41dcd3220de3304f4664c87f8723bb3a0fbd4

```bash
bash scripts/setup.sh
```

Use `.venv/bin/python` for the following commands, or activate the environment. In the prepared cloud machine the Python is `/workspace/.venvs/inp-amplifier/bin/python`.

On Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
$env:LUMERICAL_API_PATH = "C:\Program Files\Ansys Inc\vXXX\Lumerical\api\python"
```

Use the actual installed version/path. `lumapi` comes with Ansys; do not install an unrelated PyPI package with that name. Plotting exported data does not require Ansys or a license.

## Edit YAML and run native simulations

Start with [configs/lumerical.yaml](configs/lumerical.yaml), which inherits [configs/inp_pump.yaml](configs/inp_pump.yaml). All dimensional keys state their units. The native SOA template/model property map must match your installed version and CML; see [the Lumerical guide](docs/lumerical.md).

```bash
python -m inpamp validate inp-amplifier/configs/lumerical.yaml
python -m inpamp export inp-amplifier/configs/lumerical.yaml --output results/native-scripts
python -m inpamp run inp-amplifier/configs/lumerical.yaml --solver mode --output results/native-mode
python -m inpamp run inp-amplifier/configs/lumerical.yaml --solver fdtd --output results/native-taper
python -m inpamp run inp-amplifier/configs/lumerical.yaml --solver interconnect --output results/native-soa
```

`export` only writes scripts/settings. Copy the [checked-in scripts](lumerical/generated/README.txt) to Lumerical and run them in its GUI if you prefer; no Python is needed for that. Open a new project, set its working directory to the script folder, then run the `.lsf`. Native projects/results are created only by Ansys. `run` requires `--solver` and has no Python simulation mode. The older `export-lumerical`/`run-lumerical` names remain aliases for these same native operations.

For active SOA runs, set `lumerical.interconnect.template_path` to your native `.icp` project and verify its bindings first:

```bash
python -m inpamp inspect-interconnect configs/lumerical.yaml --template /path/to/SOA_TEMPLATE.icp
```

Ansys is not installed in this cloud machine. Export/unit/IO tests can run here; native solver execution and version-specific compatibility must be checked on your licensed installation. Parameters are illustrative until calibrated to the actual stack/device. No native full-comb model is bundled: add a suitable nonlinear resonator model to your INTERCONNECT template if comb dynamics are required. No Python comb solver is retained.

## Plot and analyze the native results later

These commands only read data; they never launch Ansys or calculate replacement spectra.

```bash
python -m inpamp plot results/native-mode --solver mode --output results/mode-graphs
python -m inpamp plot results/native-taper --solver fdtd --output results/taper-graphs
python -m inpamp inspect-results results/native-soa/output_spectrum.mat
```

For INTERCONNECT, select the exact fields shown by `inspect-results`. For example, **if your native result has `output_spectrum.frequency` and `output_spectrum.power`**:

```bash
python -m inpamp plot results/native-soa --solver interconnect \
  --result output_spectrum.mat --x output_spectrum.frequency --y output_spectrum.power \
  --xlabel "Frequency (Hz)" --ylabel "Power (native units)" --output results/soa-graphs
```

Native MATLAB/HDF5 MAT files and the runner's JSON datasets are supported. Multiple traces are not silently averaged: select a field/index explicitly. Complex data require `--component real`, `imag` or `abs`. MODE overlap/area and dispersion are calculated in the native script; Python only displays their exported values and converts display units. Each graph directory contains PNG/CSV files and `analysis_manifest.json` with source-file hashes and `simulation_performed: false`. Failed/partial runner results are rejected. GUI-exported files can be analyzed without a runner status file and are identified as such.

## Sweep parameters in Lumerical

The YAML defines current, input-power and width sweeps. Each case gets a fresh native project/result directory:

```bash
python -m inpamp sweep configs/lumerical.yaml --name current --output results/current-sweep
python -m inpamp sweep configs/lumerical.yaml --name width --output results/width-sweep
# Alternatively export every case and run the scripts in Lumerical's GUI:
python -m inpamp sweep configs/lumerical.yaml --name current --export-only --output results/current-scripts
```

INTERCONNECT sweeps require a property binding for the varied quantity; unsupported sweeps fail before launching anything. To graph a scalar power-meter measurement exported in every case, use its actual filename/field:

```bash
python -m inpamp plot-sweep results/current-sweep --result output_power.json \
  --field power --ylabel "Measured output power (W)" --output results/current-graphs
```

Configure that result in YAML first. A spectral array is not a scalar power-meter result. For native grid convergence, define a sweep of `lumerical.mode.mesh_step_nm` or `lumerical.fdtd.mesh_step_nm`; this reruns the actual native solver rather than solving an approximation in Python.

## Reproducibility and migration

Each export contains the resolved YAML and a simulation plan. Native runs record status and expected result files. Existing output directories must be empty; there is no silent merging with stale results. Use a child YAML with `extends` or `--set device.current_mA=300.0` for a variant.

Schema v2 removes the old Python-only `material`, `numerics`, `transient`, `microcomb` and `layout` sections and scalar-mode grid settings. Old v1 YAML is rejected with migration guidance. Put extra native model coefficients under `parameters` and explicitly bind them to verified native properties; they are never consumed by a Python model. See [scope](docs/physics.md), [calibration](docs/calibration.md), and [references](docs/references.md).

```bash
python -m pytest -q
python -m inpamp schema --output config.schema.json
```

Tests verify configuration, native-script generation, native dispatch/failure handling and reading/plotting test result fixtures. They do not claim to run Ansys or establish physical device performance.
