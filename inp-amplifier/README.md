# YAML-driven InP amplifier simulations for Lumerical

The primary workflow targets **Ansys Lumerical MODE, FDTD and INTERCONNECT** for a CW laser → InP-platform semiconductor optical amplifier → microcomb pump link. Edit YAML to generate native `.lsf` scripts and automate your licensed Lumerical installation through `lumapi`.

Start with [configs/lumerical.yaml](configs/lumerical.yaml), which inherits the editable device/material/source settings in [configs/inp_pump.yaml](configs/inp_pump.yaml). Follow the [Lumerical guide](docs/lumerical.md) for the native run, project files, model selection and active-gain calibration.

```bash
# In this directory, after installing with bash scripts/setup.sh:
python -m inpamp export-lumerical configs/lumerical.yaml --output results/lumerical-export
# On the licensed Ansys machine, with its LUMERICAL_API_PATH set:
python -m inpamp run-lumerical configs/lumerical.yaml --solver mode --output results/native-mode
python -m inpamp run-lumerical configs/lumerical.yaml --solver fdtd --output results/native-taper
```

Use your virtual-environment Python. The prepared cloud Python is `/workspace/.venvs/inp-amplifier/bin/python`. A checked-in [native script export](lumerical/generated/README.txt) is provided so you can copy it straight to Lumerical without Python on that machine. Open a **new** MODE/FDTD project, set its working directory to the export folder and run its script; the geometry script rebuilds the objects in that project.

| Product | Native work prepared |
| --- | --- |
| MODE | Vector FDE modes, tracked dispersion, field export, active-stripe power overlap |
| FDTD | Passive 3-D taper coupon with total transmission/reflection spectra |
| INTERCONNECT | Native SOA/CML template automation; YAML-to-model bindings and analyzer export |

For active gain, select/configure a native SOA or foundry CML circuit in INTERCONNECT once, inspect its actual property names, and set `lumerical.interconnect.template_path` and bindings. Then run `--solver interconnect`. This keeps gain/carrier physics in the native SOA model; it does not substitute a Python gain curve or an ideal amplifier. The [guide](docs/lumerical.md#3-prepare-the-active-soa-circuit-in-interconnect) gives the circuit structure and commands.

**Current validation:** Ansys is not installed in this cloud machine. Native scripts are generated and their generation/unit conversions tested; actual Lumerical solver execution, exact installed-version compatibility and SOA template calibration remain to be checked on your installation. `.lms/.fsp/.icp` files are created by licensed native runs, not fabricated during export. Full native Kerr-comb simulation is not bundled; the included LLE is an optional separate Python reference model.

The starting effective InGaAsP/InP geometry and coefficients are illustrative, not a foundry stack or a literature-calibrated device. See [references and provenance](docs/references.md) and [calibration](docs/calibration.md). The earlier Er:Al₂O₃ scripts are retained separately.

---

The remainder documents the **optional Python reference calculations**, conceptual GDS export and their verification. These help check trends and pump budgets, and are never presented as Lumerical results.

## Optional Python reference workflow

From this `inp-amplifier` directory on Linux/macOS:

```bash
bash scripts/setup.sh
.venv/bin/python -m inpamp validate configs/inp_pump.yaml
.venv/bin/python -m inpamp run configs/inp_pump.yaml --check
```

The setup script creates a local virtual environment, installs the pinned dependencies, installs this project, and checks dependency consistency. It is safe to run again. In the prepared cloud machine, use `/workspace/.venvs/inp-amplifier/bin/python` instead of `.venv/bin/python`; it is already installed.

Windows PowerShell equivalent:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
.\.venv\Scripts\python.exe -m inpamp run configs/inp_pump.yaml --check
```

Each run creates a new timestamped directory under `results/` and prints its path. Open `report.html` in a browser; it embeds all figures and works offline. Results also include CSVs, `summary.json`, the exact `resolved_config.yaml`, code/configuration hashes, package versions, and `design.gds`. GDS can be opened in KLayout. `layout.png` provides an immediate preview.

## Edit your amplifier

Start with [configs/inp_pump.yaml](configs/inp_pump.yaml). The comments identify units and which settings affect each model. Keep a copy of this baseline and create small variants:

```yaml
extends: inp_pump.yaml
name: My longer amplifier
device:
  length_um: 1500.0
  current_mA: 300.0
source:
  input_power_mW: 2.0
microcomb:
  link_loss_dB: 1.0
```

Save it beside the other configs, then run `python -m inpamp run configs/my_amplifier.yaml --check` with your environment's Python. Parent paths resolve relative to the child YAML. Unknown fields, duplicate keys, nonfinite values, invalid dimensions and inheritance cycles fail with an error. The included JSON schema supports YAML editor completion; regenerate it with `python -m inpamp schema --output config.schema.json` after changing the schema code. Schema defaults describe the baseline; run-time inherited values are recorded in `resolved_config.yaml`.

For one-off changes:

```bash
python -m inpamp run configs/inp_pump.yaml \
  --set device.current_mA=300.0 \
  --set device.length_um=1500.0
python -m inpamp run configs/amplifier_only.yaml
python -m inpamp run configs/high_current.yaml
python -m inpamp run configs/quick.yaml
```

Use the virtual-environment Python in those commands. `--output results/my-study` selects an explicit directory; it must be empty so stale results cannot be mistaken for a successful new run. An error returns a nonzero exit status and leaves any partial artifacts for diagnosis, without writing a success report.

| Change in YAML | What it changes |
| --- | --- |
| `source.wavelength_nm`, `input_power_mW` | Pump, gain detuning and saturation |
| `device.length_um`, `width_um`, `active_thickness_um` | Injected carrier density, gain length, active volume and matching concept geometry |
| `device.current_mA`, `injection_efficiency` | Electrical carrier injection |
| `material.*` | Gain, recombination, gain compression, ASE and thermal sensitivity |
| `mode.*` | Scalar-mode grid/index model or imported confinement/area |
| `thermal.*`, coupling losses | Junction temperature and usable output power |
| `sweeps.current_mA`, `input_power_mW` | Current and input-power sweep samples |
| `microcomb.*` | Delivered pump, Q, FSR, dispersion, detuning scan, numerical resolution |
| `layout.*` | Concept tapers, pad, bus and ring drawing |

**Important separation:** `layout.ring_gap_um` does not calculate `microcomb.coupling_Q`; ring width does not calculate dispersion. Those need electromagnetic simulations or measured data. The mode's confinement feeds the SOA; its effective area is reported, while carrier depletion uses the physical active area and empirical gain compression uses local power. With `mode.enabled: false`, you can enter a confinement factor and area from a trusted vector solver.

## What runs

1. A scalar 2-D finite-difference mode solver estimates the fundamental effective index, mode area and gain-region overlap.
2. A spatial steady-state SOA solver couples ABC carrier recombination, stimulated depletion, gain saturation, spectral gain, bidirectional ASE and a lumped thermal balance. It reports output power, gain, OSNR, an approximate noise figure and a facet-feedback diagnostic.
3. Current/input-power sweeps and a separate lumped current-step transient expose saturation, heating, recovery and linewidth-enhancement-induced phase/chirp.
4. Delivered SOA signal power drives a split-step mean-field Lugiato–Lefever equation (LLE). Outputs show the spectrum, intracavity waveform and scan/hold evolution. A trajectory is **not automatically a stable soliton**. ASE and phase noise are not calibrated or propagated into the resonator.
5. Matching concept geometry exports to GDS, ports JSON and a PNG preview. Arbitrary layers, effective cross-sections and the drawn hybrid connection are **not foundry-qualified masks, coupling designs or design-rule checks**.

Equations, signs, noise conventions and omissions are documented in [physics.md](docs/physics.md). Sources and parameter provenance are in [references.md](docs/references.md).

## Verification and numerical checks

```bash
python -m pytest -q
python -m inpamp check configs/inp_pump.yaml
```

`check` doubles the SOA longitudinal and ASE spectral grids and refines the scalar-mode grid. It returns nonzero if output power or the checked mode quantities change by more than 2%. `run --check` adds these results to the report. This is an initial refinement screen, not a universal convergence certificate.

Before trusting a particular study, increase the mode **window** as well as its mesh; widen the ASE **band** as well as its bins; halve LLE `time_step`; double `modes`; extend the hold; and compare multiple noise seeds. Nonlinear/chaotic LLE trajectories need statistical and stability analysis rather than pointwise agreement. The tests cover analytic propagation/passive/small-signal limits, carrier/energy bookkeeping, gain saturation, transient equilibrium, a driven linear cavity, nonlinear homogeneous LLE time-step refinement, input rejection and GDS/report artifacts. See [calibration.md](docs/calibration.md) for turning the baseline into a device study.

The published environment configuration has not been modified or republished by this addition. Local installation is reproducible from `scripts/setup.sh` and `requirements.lock`.
