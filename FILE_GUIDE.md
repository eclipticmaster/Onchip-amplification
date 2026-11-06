# Project file guide

This catalogue covers every project-owned source, configuration, documentation and test file, plus the generated file families repeated across result folders. Paths in the project tables start at `C:\Onchip-amplification`. Run-file tables use paths relative to an individual result folder. Python dependencies, version-control internals and caches are grouped by directory.

## Running commands and finding your results

From the repository root, repeat this command whenever you want a new MODE simulation:

```powershell
.\.venv\Scripts\python.exe -m inpamp run inp-amplifier/configs/lumerical.yaml --solver mode
```

The `run-lumerical` alias accepts the same arguments. Each invocation creates a separate folder such as:

```text
results/mode-2026-11-05_14-03-07-0800/
```

The name includes the operation/solver, the computer's local date and time, and its UTC offset. The example offset `-0800` means eight hours behind UTC. Calls within the same second receive suffixes such as `-02` and `-03`. The command prints the selected folder and returns its absolute path as `output_directory` in its JSON output.

`--output` remains available for a custom name. An available or empty custom folder is used directly. When that folder already contains files, the command creates a timestamped sibling, preserving the previous run:

```powershell
.\.venv\Scripts\python.exe -m inpamp run inp-amplifier/configs/lumerical.yaml --solver mode --output results/my-design
```

For example, the first run uses `results/my-design`; a subsequent run uses `results/my-design-2026-11-05_14-03-07-0800`. Exports, native sweeps and diagnostic plotting commands also accept an omitted output folder. Their defaults are:

| Command | Automatic output location |
| --- | --- |
| `run` / `run-lumerical` | `results/<solver>-<timestamp>/` |
| `export` / `export-lumerical` | `results/scripts-<timestamp>/` |
| `sweep --name NAME` | `results/sweep-NAME-<timestamp>/` |
| `plot DIRECTORY --solver SOLVER` | `DIRECTORY/SOLVER-graphs-<timestamp>/` |
| `plot-sweep DIRECTORY` | `DIRECTORY/sweep-graphs-<timestamp>/` |
| `figures DIRECTORY` | `DIRECTORY/figures/`, followed by timestamped siblings on subsequent calls |
| `figures DIRECTORY --replace` | Regenerates the selected existing figure package; its ownership and source data are checked |

`results/` is relative to the working directory where you invoke the command. A successful visible CLI run opens its native project and its figure gallery according to the `keep_open`, `make_figures` and `show_figures` settings. The graphs live inside that run's `figures/` folder.

## Renaming a completed run

After Lumerical finishes saving, rename the complete run folder in File Explorer. Keep the native data and its figure folders together. You can then open `inp_waveguide.lms` from the renamed folder, open `figures/index.html`, or regenerate its figures:

```powershell
.\.venv\Scripts\python.exe "results/My preferred experiment name/figures/regenerate.py"
```

The generated recipe locates data relative to its own folder. Figure manifests retain source hashes and support checking a relocated run. Older manifests can be recognized using matching native-file hashes. Absolute paths in historical metadata record the original creation location; relative artifact filenames and the regeneration recipe provide the portable working paths. External INTERCONNECT templates/CML files retain their configured dependency locations.

## Entry points and installation

| File | What it accomplishes |
| --- | --- |
| `README.md` | Introduces the repository, links the InP workflow and earlier erbium example, and gives initial commands. |
| `FILE_GUIDE.md` | Describes project files, output naming, renaming, generated artifacts and common editing tasks. |
| `inp-amplifier/README.md` | Main user guide for installation, YAML editing, native runs, figures, sweeps and schema migration. |
| `inp-amplifier/pyproject.toml` | Defines package metadata, Python/dependency requirements, editable installation, the `inpamp` executable and pytest settings. |
| `inp-amplifier/requirements.lock` | Pins the versions used for automation, native-data reading, plotting, building and tests. |
| `inp-amplifier/scripts/setup.sh` | Creates a virtual environment, installs pinned packages and the local project, checks dependencies and validates the example YAML. |
| `inp-amplifier/.gitignore` | Defines exclusions for environments, caches, build artifacts and local result folders. |
| `inp-amplifier/.vscode/settings.json` | Connects the YAML files under `configs/` to the simulation JSON schema for editor completion and validation. |

## Python source

| File | What it accomplishes |
| --- | --- |
| `inp-amplifier/src/inpamp/__init__.py` | Introduces the package and exposes its version number. |
| `inp-amplifier/src/inpamp/__main__.py` | Starts the CLI when Python executes `python -m inpamp`. |
| `inp-amplifier/src/inpamp/cli.py` | Parses commands and aliases, validates inputs, selects output folders, dispatches native runs/exports/analysis, generates figures after successful CLI runs and prints results. |
| `inp-amplifier/src/inpamp/paths.py` | Allocates output folders using local date/time and UTC offset, handles collisions and preserves occupied destinations. |
| `inp-amplifier/src/inpamp/config.py` | Defines the schema-v2 models, physical-input checks, YAML inheritance, duplicate-key validation, CLI overrides and native-unit conversions. |
| `inp-amplifier/src/inpamp/lumerical.py` | Generates MODE/FDTD/INTERCONNECT scripts, loads vendor `lumapi`, launches native sessions, reports native errors, verifies saved results, serializes native metrics and reopens saved projects. |
| `inp-amplifier/src/inpamp/workflow.py` | Validates requested sweep parameters, dispatches one native run/export per case and records case/overall status. |
| `inp-amplifier/src/inpamp/results.py` | Reads native MAT/HDF5/JSON datasets, lists fields, selects numeric traces and produces diagnostic PNG/CSV plots and provenance manifests. |
| `inp-amplifier/src/inpamp/figures.py` | Generates manuscript-oriented figures, editable styles, vector/raster exports, plotted-data CSVs, an offline gallery, source hashes and portable regeneration recipes. It also supports explicit analyzer mappings and native MODE sweep summaries. |

## Editable simulation and figure settings

| File | What it accomplishes |
| --- | --- |
| `inp-amplifier/configs/inp_pump.yaml` | Baseline device dimensions, source/bias inputs, effective optical indices, native solver settings, GUI/figure preferences, circuit bindings and sweep definitions. |
| `inp-amplifier/configs/lumerical.yaml` | Main example entry point; inherits the baseline and supplies the overall native-workflow name. |
| `inp-amplifier/configs/high_current.yaml` | Inherits the baseline and changes the device bias to 350 mA for a comparison. |
| `inp-amplifier/configs/amplifier_only.yaml` | Names a native SOA characterization configuration for use with an SOA-only INTERCONNECT template. |
| `inp-amplifier/config.schema.json` | Machine-readable simulation schema for editors; regenerated by `python -m inpamp schema --output inp-amplifier/config.schema.json` from the repository root. |
| `inp-amplifier/styles/publication.yaml` | Starting presentation settings for figure size, fonts, colors, axes, colormaps and export formats. Copy/edit this file or a generated run's `figures.yaml`. |

Simulation YAML files control what is sent to Lumerical. Style YAML controls presentation of exported results. Native model-property bindings connect common or additional YAML values to specific elements inside an INTERCONNECT project.

## Detailed documentation

| File | What it accomplishes |
| --- | --- |
| `inp-amplifier/docs/lumerical.md` | Describes native execution, API configuration, optical geometry, circuit templates, bindings, sweeps, errors and result analysis. |
| `inp-amplifier/docs/figures.md` | Explains literature-motivated plots, physical interpretation, available native data, presentation controls, unit conversions and analyzer mappings. |
| `inp-amplifier/docs/physics.md` | Describes the physical scope, assumptions and native-model responsibilities of MODE, FDTD and INTERCONNECT. |
| `inp-amplifier/docs/calibration.md` | Lists the native-model, material, device-data and convergence work needed for a calibrated study. |
| `inp-amplifier/docs/references.md` | Records relevant literature, primary-source links and provenance of illustrative inputs. |

## Checked-in native script examples

These examples can be opened in the corresponding Lumerical product. The CLI generates scripts from the current YAML into each output folder.

| File | What it accomplishes |
| --- | --- |
| `inp-amplifier/lumerical/generated/README.txt` | Instructions for running the example scripts and supplying a native SOA template. |
| `inp-amplifier/lumerical/generated/mode.lsf` | Builds the effective optical cross-section, solves native modes, integrates nominal-wavelength metrics, tracks dispersion and saves native MODE results. |
| `inp-amplifier/lumerical/generated/fdtd.lsf` | Builds the passive taper coupon, defines the source/mesh/monitors, runs FDTD and exports transmission/reflection. |
| `inp-amplifier/lumerical/generated/interconnect.lsf` | Loads `SOA_TEMPLATE.icp`, applies configured bindings, runs the native circuit and exports configured analyzer results. |
| `inp-amplifier/lumerical/generated/resolved_config.yaml` | Snapshot of the resolved settings associated with the checked-in export. |
| `inp-amplifier/lumerical/generated/simulation_plan.json` | Describes the prepared products/scripts, model requirements and FDTD planning estimate. |

## Tests

| File | What it accomplishes |
| --- | --- |
| `inp-amplifier/tests/test_cli.py` | Checks command parsing/aliases, native dispatch, automatic figures, optional/repeated outputs and package boundaries. |
| `inp-amplifier/tests/test_paths.py` | Checks timestamp format, UTC offsets, same-second collision suffixes and preservation of existing files. |
| `inp-amplifier/tests/test_config.py` | Checks example YAML, inheritance, unit conversion, invalid inputs and schema migration. |
| `inp-amplifier/tests/test_lumerical.py` | Checks script generation, tracked sweep setup, merge-marker detection, native API contracts, error reporting, result serialization and GUI launch behavior. |
| `inp-amplifier/tests/test_results.py` | Checks reading MAT/HDF5/JSON files, diagnostic plotting, scalar sweep analysis and failed/incomplete-run handling. |
| `inp-amplifier/tests/test_figures.py` | Checks figure formats, independent unit conversions, style editing, raw-data preservation, native trace mappings and regeneration after a run folder is renamed. |
| `inp-amplifier/tests/test_workflow.py` | Checks sweep dispatch, export-only cases, parameter binding and failure status. |

Run the suite from the repository root with `.\.venv\Scripts\python.exe -m pytest inp-amplifier/tests -q`.

## Files inside each native run/export folder

Each timestamped folder is self-contained for the generated scripts and exported data. A run for a selected solver also contains scripts for the other configured products, ready for inspection/export.

| Relative filename | What it accomplishes / main contents |
| --- | --- |
| `README.txt` | Run/export instructions and template requirements. |
| `resolved_config.yaml` | Full settings after inheritance and overrides, recorded for reproducibility. |
| `simulation_plan.json` | Describes scripts, native products, expected projects and estimated FDTD cell count. |
| `mode.lsf` | Exact generated MODE script for this configuration. |
| `fdtd.lsf` | Exact generated FDTD script for this configuration. |
| `interconnect.lsf` | Exact generated circuit script; API execution resolves its configured template path. |
| `run_status.json` | Native solver, completed/failed status, result verification, configuration hash, vendor API location, expected artifact names and GUI information. |
| `inp_waveguide.lms` | Native MODE project containing geometry, solver settings and saved mode/dispersion results. |
| `mode_fields.mat` | Nominal-wavelength `x`, `y`, native intensity `E2`, complex `Ex`, `Ey`, `Ez`, `Hx`, `Hy` and effective index `neff`. Coordinates use metres. |
| `mode_metrics.mat` | Native scalar `neff`, active power overlap `Gamma` and scalar-field effective area `Aeff` in square metres. |
| `mode_metrics.json` | Readable serialization of native mode metrics; the native-run area field is `scalar_field_area_m2`. |
| `mode_dispersion.mat` | Tracked native dispersion `D` in s/m² and its frequency axis `f_D` in Hz. |
| `inp_taper.fsp` | Native FDTD project containing taper geometry, source, mesh, monitors and saved results. |
| `taper_transmission.mat` | Native frequency `f` in Hz and dimensionless monitor power fractions `T`, `R`. |
| `taper_transmission.csv` | The same spectra displayed on a wavelength axis in nm; columns identify total-flux transmission/reflection. |
| `inp_taper_p0.log` and other solver `.log` files | Native engine initialization, meshing, progress, termination and timing diagnostics. Names can vary with product and process count. |
| `inp_pump.icp` | Native INTERCONNECT project containing the configured active circuit and its saved results. |
| `<result_label>.mat` | Native analyzer dataset requested by a `lumerical.interconnect.results` entry. |
| `<result_label>.json` | JSON representation of that analyzer result, preserving structured and complex-valued data. |
| `SOA_TEMPLATE.icp` | Optional user-supplied native SOA/CML circuit for running an exported script manually. Its models and data dependencies accompany the template. |
| `validation.json` | Optional record created during a manual/native verification exercise, such as checked sweep endpoints or finite-data checks. |
| Additional native `.bak`, autosave or support files | Recovery copies or supporting artifacts produced by the installed Lumerical version. |

## Publication figures inside a run

The first figure package uses `figures/`. Repeated CLI `figures` commands choose timestamped siblings. Each package uses the same filenames below.

| Relative filename inside the figure package | What it accomplishes |
| --- | --- |
| `index.html` | Offline gallery with previews, export links, captions, metrics and further-measurement guidance. |
| `figures.yaml` | Editable settings for titles, axes, limits, scales, colors, fonts, colormaps, line styles and native trace mappings. |
| `regenerate.py` | Recreates the package from its local style and native data, locating the source through a relative path where supported. |
| `figure_manifest.json` | Source-file hashes, original/current source location, relative source references, renderer versions, exact style, figure captions and artifact list. |
| `metrics.json` | Figure-facing summary of native mode metrics; `effective_area_um2` uses square micrometres. |
| `mode_intensity.png`, `mode_intensity.pdf`, `mode_intensity.svg`, `mode_intensity.csv` | Peak-normalized native intensity map; the CSV also retains the original intensity and x/y coordinates. |
| `mode_profiles.png`, `mode_profiles.pdf`, `mode_profiles.svg`, `mode_profiles.csv` | Lateral and vertical slices through grid points nearest the origin, using the shared peak normalization. |
| `waveguide_dispersion.png`, `waveguide_dispersion.pdf`, `waveguide_dispersion.svg`, `waveguide_dispersion.csv` | Native D versus wavelength, displayed in ps/(nm km). |
| `waveguide_beta2.png`, `waveguide_beta2.pdf`, `waveguide_beta2.svg`, `waveguide_beta2.csv` | Algebraic conversion of native D to beta2, displayed in fs²/mm. |
| `taper_transmission.*` | Total native transmitted monitor fraction versus wavelength. Each enabled format and a CSV are produced. |
| `taper_reflection.*` | Total native reflected monitor fraction versus wavelength. |
| `taper_insertion_loss.*` | Transmission converted to `-10 log10(T)` in dB. |
| `taper_reflection_db.*` | Reflection converted to `10 log10(R)` in dB. |
| `taper_power_balance.*` | `T+R` and residual `1-T-R` versus wavelength. |
| `sweep_neff.*`, `sweep_overlap.*`, `sweep_area.*` | Native MODE metrics versus the parameter in a completed sweep. |
| `<custom_figure_name>.*` | Explicitly mapped analyzer traces, including power, gain, noise, spectra or time-domain exports selected in the style YAML. |

For `.*` figure families, `.png` is the gallery preview, `.pdf` and `.svg` provide the enabled manuscript/vector exports, and `.csv` stores plotted samples. Enabled export formats follow `figures.yaml`. PDF/SVG field maps include embedded raster meshes; curves and text retain vector formatting.

## Sweep folders and diagnostic plotting

| File or path | What it accomplishes |
| --- | --- |
| `<sweep>/sweep_manifest.json` | Sweep name, native solver, parameter, values, case directories and individual/overall status. |
| `<sweep>/case_000/`, `case_001/`, … | Separate native run/export folders for each parameter value. Their files follow the native-run table. |
| `<sweep>/figures/` | Summary figure package for completed native sweep data. |
| `<analysis>/analysis_manifest.json` | Source hashes, artifact names and provenance for a diagnostic `plot` or `plot-sweep` operation. |
| `<analysis>/mode.png` | Diagnostic two-panel MODE field/dispersion image. |
| `<analysis>/dispersion.csv` | Diagnostic wavelength/D data with display units. |
| `<analysis>/mode_metrics.json` | Diagnostic metric summary with `scalar_field_area_um2` in square micrometres. |
| `<analysis>/taper.png`, `<analysis>/taper.csv` | Diagnostic FDTD transmission/reflection plot and samples. |
| `<analysis>/interconnect.png`, `<analysis>/interconnect.csv` | Explicitly selected native circuit trace and samples. |
| `<analysis>/sweep.png`, `<analysis>/sweep.csv` | One selected native scalar measurement per sweep case, plotted against the parameter. |

## Earlier Er:Al2O3 / SiN project

| File | What it accomplishes |
| --- | --- |
| `on-chip-erbium-cpa/README.md` | Explains the retained large-mode-area erbium/SiN MODE example, installation path and execution command. |
| `on-chip-erbium-cpa/requirements.txt` | Lists Python dependencies used by that wrapper. |
| `on-chip-erbium-cpa/.gitignore` | Defines exclusions for environments, native outputs, caches and private fabrication/model data. |
| `on-chip-erbium-cpa/results/.gitkeep` | Keeps the example's empty result directory present in version control. |
| `on-chip-erbium-cpa/simulations/mode/er_al2o3_sin_lma_mode.py` | Builds its effective Er:Al2O3/SiN structure, launches native MODE, sweeps rail width, obtains dispersion, postprocesses native fields and saves plots. Its editable import block identifies the installed vendor API. |

That wrapper writes under `on-chip-erbium-cpa/results/mode/`:

| Filename | What it accomplishes |
| --- | --- |
| `mode_1550nm.png` | Native nominal-wavelength mode visualization. |
| `width_sweep.csv` | Native width-sweep results and derived field metrics. |
| `Aeff_vs_width.png` | Effective area versus SiN rail width. |
| `overlap_vs_width.png` | Active-layer overlap versus rail width. |
| `neff_vs_width.png` | Effective index versus rail width. |
| `dispersion.csv`, `dispersion.png` | Native dispersion samples and their plot. |
| `er_al2o3_sin_lma_mode.lms` | Saved native MODE project for the earlier geometry. |

## Local environment and generated support files

| Directory / filename family | What it accomplishes |
| --- | --- |
| `.venv/` or `inp-amplifier/.venv/` | Local Python executable, activation scripts and installed dependency files. Project-owned installation requirements are listed in `pyproject.toml` and `requirements.lock`. |
| `.git/` | Repository commits, branches, object data and local Git bookkeeping. |
| `**/__pycache__/`, `*.pyc` | Interpreter-generated bytecode caches. |
| `**/.pytest_cache/` | Cached test discovery and result information. |
| `**/*.egg-info/` | Installed/editable package metadata generated from `pyproject.toml`. |
| `build/`, `dist/` | Build intermediates and packaged distributions when packaging tools are run. |
| `<Ansys installation>/api/python/lumapi.py` | Vendor API module loaded by the runner to control the installed native applications. |

Update this guide when adding a project file or a new output family. For day-to-day edits, start with simulation YAML for device/model changes, `figures.yaml` for presentation changes, and `docs/calibration.md` for the physical validation plan.
