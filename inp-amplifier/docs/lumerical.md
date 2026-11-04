# Lumerical-only simulation workflow

Every physical simulation executes in **Ansys Lumerical MODE, FDTD or INTERCONNECT**. Python only manages YAML, native scripts/cases, file IO and analysis/graphs of native exports. The previous Python SOA, carrier/thermal, scalar-mode, CPA and Kerr/LLE simulators are removed.

## 1. Native scripts or vendor API

From `inp-amplifier`, with its virtual-environment Python:

```bash
python -m inpamp validate configs/lumerical.yaml
python -m inpamp export configs/lumerical.yaml --output results/native-scripts
```

The export includes `mode.lsf`, `fdtd.lsf`, `interconnect.lsf`, a resolved YAML and a simulation plan. It creates no native projects/results. Copy the export directory to your Lumerical machine, open a **new** project in the correct product, set the working directory to the export folder and run that product's script. MODE/FDTD scripts rebuild the geometry in the open project. All output filenames are relative so the export is portable between machines.

- MODE creates `inp_waveguide.lms`, `mode_fields.mat`, `mode_metrics.mat` and `mode_dispersion.mat`.
- FDTD creates `inp_taper.fsp` and `taper_transmission.mat`.
- INTERCONNECT loads your `SOA_TEMPLATE.icp`, applies verified property bindings, creates `inp_pump.icp` and saves the configured analyzer datasets.

Alternatively use `lumapi.py` shipped with the licensed Ansys installation. Set `LUMERICAL_API_PATH` to its `api/python` directory, or pass `--api-path`. Do not install an unrelated PyPI package named lumapi.

```powershell
$env:LUMERICAL_API_PATH = "C:\Program Files\Ansys Inc\vXXX\Lumerical\api\python"
python -m inpamp run configs/lumerical.yaml --solver mode --output results/native-mode
python -m inpamp run configs/lumerical.yaml --solver fdtd --output results/native-taper
python -m inpamp run configs/lumerical.yaml --solver interconnect --output results/native-soa
```

Replace the version/path with your installation. Linux uses the equivalent exported path. Configure your Ansys license through Ansys; no credentials belong in YAML. `run-lumerical` is an alias for `run`; both require the vendor API and use the native solver exclusively. An unavailable API, license, native property or result is an error with no Python replacement computation.

The runner records `run_status.json`, the configuration hash and expected native files. MODE metrics are integrated in `mode.lsf`; Python only serializes their native values. Ansys is not installed in this cloud machine, so native execution/compatibility still requires validation on your licensed installation.

## 2. Optical cross-section and transition

`mode.*` sets fallback effective indices and the native MODE window. `device.width_um`, `core_thickness_um` and the active-stripe mask feed the MODE geometry/analysis. `lumerical.mode.*` controls the native mesh/trial modes/dispersion sweep. Set exact `lumerical.core_material` and `cladding_material` names from your installation for real dispersive materials. No generic index choice is a substitute for your epitaxy.

FDTD uses `lumerical.fdtd.*`, including `input_width_um` and the short coupon length. It shares the output width/core thickness with `device`. It does not simulate a full millimetre-scale electrically pumped SOA. The planner estimates mesh size, but inspect the actual native mesh, memory, PML and decay time before interpreting results. Use a real hybrid transition geometry and native ports if you need an InP-to-SiN scattering matrix.

## 3. Active native SOA circuit

Create/select a native INTERCONNECT template using the actual SOA element or foundry CML available in your installed version. A typical initial circuit is:

```text
CW laser (pump_laser) -> native SOA (inp_soa) -> output analyzer (output_osa)
                                ^
                       bias source (bias_current)
```

Some SOA models use a direct current property instead of an electrical port; use the appropriate native connection. Add input/output power meters and native noise analyzers as needed. Calibrate the active material/gain and any carrier/thermal parameters inside the native model. An ideal amplifier or passive S matrix does not establish active semiconductor physics.

Save the configured circuit as `.icp`. Set `lumerical.interconnect.template_path` to it. Relative paths are resolved against the YAML selected on the command line. Keep external gain/CML data files and relative dependencies with the project. For manual GUI execution, place the template in the export directory as `SOA_TEMPLATE.icp`.

Inspect the native names before applying a property map:

```bash
python -m inpamp inspect-interconnect configs/lumerical.yaml --template /path/to/SOA_TEMPLATE.icp
```

The example conventions are `pump_laser.frequency` in Hz, `pump_laser.power` in W, `bias_current.amplitude` in A and the analyzer result `output_osa/spectrum`. They must match your selected model; they are not universal stock-model guarantees. Update `inspect_elements`, `bindings`, `fixed_properties` and `results` to the exact native names. Some analyzer results become available only after running; inspect in the GUI if needed. The runner verifies each target property through a native getter before applying changes.

Supported common unit-converted quantities are:

```text
source.frequency_Hz       source.power_W
 device.current_A         device.length_m
 device.width_m           device.active_thickness_m
 device.active_volume_m3  thermal.ambient_K
```

Extra coefficients are direct native values, explicitly mapped. For example, **only if your native model exposes the indicated property**, a child YAML can contain:

```yaml
extends: lumerical.yaml
parameters:
  alpha_H: 5.0
lumerical:
  interconnect:
    # This list replaces the inherited list; retain your verified pump/bias
    # bindings here as well. Use your model's actual property name.
    bindings:
      - element: inp_soa
        property: your_verified_linewidth_enhancement_property
        quantity: parameters.alpha_H
```

`parameters` does not run a Python gain model. Material/geometry changes in MODE do not automatically refit a circuit SOA/CML. Import/update the appropriate native model settings and record their source. To simulate full microcomb dynamics, extend the native template with a nonlinear resonator model; no Python LLE is provided.

## 4. Native sweeps and graphs

The YAML sweep list selects a native product, a parameter and values:

```yaml
sweeps:
  - name: current
    solver: interconnect
    parameter: device.current_mA
    values: [100.0, 200.0, 300.0]
```

```bash
python -m inpamp sweep configs/lumerical.yaml --name current --output results/current-sweep
python -m inpamp sweep configs/lumerical.yaml --name current --export-only --output results/current-scripts
```

Each case runs the selected Lumerical engine or exports a native script for the GUI. There is no Python sweep simulation. Irrelevant/unbound parameters fail before launch; failures stop the sweep and mark its manifest failed. Use separate output folders for convergence studies and preserve the exact YAML/data.

After native execution, plotting is offline and needs no Ansys installation:

```bash
python -m inpamp plot results/native-mode --solver mode --output results/mode-graphs
python -m inpamp plot results/native-taper --solver fdtd --output results/taper-graphs
python -m inpamp inspect-results results/native-soa/output_spectrum.mat
```

Use the exact native dataset paths listed by `inspect-results` with `plot --solver interconnect --result ... --x ... --y ...`. Multi-trace arrays require explicit field/index selection; complex traces require a component selection. To plot a sweep, configure/export a scalar native measurement in every case, then use `plot-sweep --result FILE --field PATH`. The [README](../README.md) contains full command examples. Missing result files are errors, never replaced with analytic curves.

See [scope](physics.md), [native calibration](calibration.md) and [references](references.md). Orchestration/IO tests do not execute Ansys or validate your physical model.
