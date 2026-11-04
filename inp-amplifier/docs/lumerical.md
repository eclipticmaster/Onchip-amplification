# Primary workflow: Ansys Lumerical

The target tools are **MODE + FDTD + INTERCONNECT**, using YAML as the design input and vendor `lumapi` for automation. Exporting scripts does not require Ansys. Executing native simulations requires your licensed installation; Ansys is not installed in the cloud machine used to develop this code. Native `.lms`, `.fsp`, `.icp` projects and their results are produced only by Lumerical.

## Products and physics

| Tool | Included automation | What this does not calculate |
| --- | --- | --- |
| MODE | Effective InGaAsP/InP cross-section; vector FDE modes; tracked-mode dispersion; native field export and power-flux overlap | Quantum-well band structure, electrical injection or gain saturation |
| FDTD | 3-D passive taper coupon; TE mode source; wavelength-resolved total transmission/reflection | Electrically pumped SOA gain or a Kerr microcomb; no material gain is faked with a negative index |
| INTERCONNECT | Load your native SOA/CML circuit; map YAML pump/current/device settings onto verified native properties; run and export configured analyzer data | An unprovided epitaxial/semiconductor gain model; automatically determining version-specific model parameters/ports |

The optional Python SOA/LLE scripts are independent reference calculations. Their output is **not a Lumerical result**. The LLE microcomb solver is not exported as a native INTERCONNECT nonlinear resonator. The native workflow initially characterizes the amplifier/pump delivery; demonstrating the full comb in Lumerical requires a suitable nonlinear resonator compact model and data, which are not bundled here.

## 1. Export scripts from YAML

From `inp-amplifier`, using your virtual-environment Python:

```bash
python -m inpamp validate configs/lumerical.yaml
python -m inpamp export-lumerical configs/lumerical.yaml --output results/lumerical-export
```

The export contains:

- `mode.lsf`: creates/saves `inp_waveguide.lms`, solves modes/dispersion and writes `mode_fields.mat` and `mode_dispersion.mat` when run in MODE.
- `fdtd.lsf`: creates/saves `inp_taper.fsp` and writes `taper_transmission.mat` when run in FDTD.
- `interconnect.lsf`: loads `SOA_TEMPLATE.icp`, applies your configured bindings, saves `inp_pump.icp` and exports configured native results. It requires the template described below.
- `resolved_config.yaml` and `simulation_plan.json`, which explicitly mark export-only status and estimate FDTD mesh size.

Copy the export directory to your Lumerical machine. In each product, set the working directory to that folder, open the corresponding `.lsf` in the script editor, and run it. The scripts use relative filenames so the export can move between cloud/Linux and Windows. The generated scripts and projects are editable inside Lumerical; change YAML and re-export to reproduce a geometry change.

The default cross-section uses effective constant indices. For a physical study, set `lumerical.core_material` and `cladding_material` to exact dispersive material-database names available in your installation, or replace the effective geometry with your actual layered stack. MODE must calculate confinement for the correct gain-layer stack/polarization. Constant-index MODE results contain waveguide dispersion only, not a calibrated material-dispersion prediction.

## 2. Run through lumapi on the licensed machine

Do **not** install a random PyPI package named lumapi. Use the `lumapi.py` shipped with Ansys, normally in `<Lumerical installation>/api/python`. Set `LUMERICAL_API_PATH` to that directory or pass `--api-path`.

```powershell
$env:LUMERICAL_API_PATH = "C:\Program Files\Ansys Inc\vXXX\Lumerical\api\python"
python -m inpamp run-lumerical configs/lumerical.yaml --solver mode --output results/native-mode
python -m inpamp run-lumerical configs/lumerical.yaml --solver fdtd --output results/native-taper
```

Replace the version/path with your installation. On Linux, export the equivalent path and use the same commands. Configure your Ansys license normally; no license tokens are stored in YAML. Set `lumerical.hide_gui: true` only if your installation supports that execution mode.

The runner saves a `run_status.json` with completed/failed state and verifies expected native files. MODE also writes `mode_metrics.json` using **native vector Poynting flux** to estimate active-stripe overlap. FDTD writes a CSV of total monitor flux. Any API, license, property or result error is a failed native run, not a fallback to Python calculations.

MODE exports fields and overlap metrics at `source.wavelength_nm`. It then solves at `lumerical.mode.wavelength_start_nm`, selects the mode with the best overlap with the nominal mode, and tracks that mode through `wavelength_stop_nm`. In a tracked sweep, Lumerical fixes the start wavelength to the initial mode's wavelength; setting `start wavelength` after enabling tracking is invalid. The final `.lms` contains the sweep, while `mode_fields.mat` and `mode_metrics.json` describe the nominal source wavelength. The built-in FDE/FDTD solver names are read-only and are left at their native defaults.

If a script fails, the CLI and `run_status.json` include the native script filename, line number and error message captured with Lumerical's [try/catch](https://optics.ansys.com/hc/en-us/articles/360034928513-try-Script-command) and [feval](https://optics.ansys.com/hc/en-us/articles/360034405934-feval-Script-command) commands. Inspect that line in the exported `.lsf`. After correcting YAML or updating the code, rerun with a **new output directory**: existing results are never overwritten or resumed. Old exported scripts must be regenerated to pick up code fixes.

## 3. Prepare the active SOA circuit in INTERCONNECT

The correct native SOA element/CML, gain data, electrical connection, property names and port names depend on your installed version and device model. They are deliberately not guessed or replaced with an ideal constant-gain amplifier. Create a small native circuit **once** in INTERCONNECT using your available native SOA model or foundry CML:

```text
CW laser (pump_laser) -> native SOA (inp_soa) -> output analyzer (output_osa)
                                ^
                       bias current (bias_current)
```

Connect the electrical source only if your chosen SOA exposes an electrical bias port; some models expose current as a direct parameter. Use a native spectral analyzer, and add input/output power meters and a noise analyzer as appropriate. Ensure the SOA's traveling-wave/carrier/gain model and parameterization are configured for your InP-platform active material. A native ideal optical amplifier or an S-parameter block does not establish active semiconductor gain physics.

Save as `SOA_TEMPLATE.icp`. Put the file alongside your child YAML, or configure an absolute `lumerical.interconnect.template_path`. If the template has external data/CML dependencies, retain those files and their relative paths. You can use an existing vendor application example as this template instead of assembling a new circuit.

Inspect its actual property/result names:

```bash
python -m inpamp inspect-interconnect configs/lumerical.yaml --template /path/to/SOA_TEMPLATE.icp
```

The example YAML bindings assume `pump_laser.frequency` in Hz, `pump_laser.power` in W, and `bias_current.amplitude` in A. These are **template conventions to verify**, not a claim that every SOA/version has those properties. The configured analyzer result `output_osa/spectrum` must also match your native analyzer. Inspect the template in the GUI if results are unavailable until after a run.

Set `bindings` to the exact native names/units. The runner uses native getters to verify each target property before setting anything. For a SOA with current as a direct parameter, replace the `bias_current` binding with the SOA's actual current property. To control length, volume, width or thermal settings, bind them only if the native model exposes the corresponding quantity. Supported SI quantities are:

```text
source.frequency_Hz       source.power_W
device.current_A          device.length_m
device.width_m            device.active_thickness_m
device.active_volume_m3   thermal.ambient_K
material.linewidth_enhancement_factor
```

For additional model-specific coefficients, use `fixed_properties` with verified property names and native units:

```yaml
lumerical:
  interconnect:
    template_path: SOA_TEMPLATE.icp
    # Preserve/replace the bindings/results sections as required by your model.
    fixed_properties: []  # Entries: {element: <name>, property: <native name>, value: <SI value>}
```

Then run:

```bash
python -m inpamp run-lumerical configs/lumerical.yaml --solver interconnect --output results/native-soa
```

The native project and configured result datasets are saved as `.icp`, `.mat` and JSON. No synthetic SOA gain from the reference Python solver is substituted. For a YAML current sweep, rerun `run-lumerical` with `--set device.current_mA=...` and a separate output directory; the same property map applies. Geometry/overlap changes do not automatically refit an external CML's material model. Record which MODE/FDTD results were used to update that model and which coefficients remain independent.

## 4. Validation on your installation

First run MODE at the nominal wavelength, inspect mode1's polarization and confinement, then check the tracked dispersion for mode crossings. Refine mesh and window. The overlap uses an effective centered active stripe; replace that mask with your real gain layers when available.

For FDTD, inspect source-mode identity, actual mesh/memory, PML distance, simulation decay, passivity and convergence. Default FDTD is a **20 um transition coupon**, not the 150 um concept taper or full 1 mm SOA. The distinction limits computational cost; set the coupon length to the intended transition when validating it. Monitor flux is total transmitted/reflected power; a guided-mode scattering matrix requires mode-expansion/port measurements and de-embedding. Do not automatically equate `1-T` with hybrid InP–SiN insertion loss: the coupon is an effective InP-platform taper, not a validated heterogeneous transition.

For INTERCONNECT, compare gain versus current, input power and wavelength with the native SOA reference example or measured/literature data. Check ASE/noise definitions and reference planes. Add the intended resonator/coupler CML and measured dispersion only after amplifier/pump delivery is calibrated. There is no claim that having a native project file alone proves soliton generation.

The default MODE and FDTD workflows have been exercised on Windows with Lumerical 2026 R1 (v261). The saved MODE project was reopened and its 21 finite dispersion values verified across 1500–1600 nm. FDTD created its native project and 21 finite transmission/reflection samples over the same range. These runs establish execution for this configuration and installation; they do not establish mesh convergence or device calibration. INTERCONNECT's template-specific bindings still require validation with your active circuit. The Python tests verify generation, unit conversions, field postprocessing and failure reporting without simulating Ansys. Model equations and optional reference-code assumptions remain in [physics.md](physics.md), with provenance in [references.md](references.md).
