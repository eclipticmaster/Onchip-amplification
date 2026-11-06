# Figures for an InP SOA driving a microcomb

The present experiment is a CW pump link: source → InP-platform SOA → passive transition → resonator. Its central questions are usable pump power, noise/coherence and access to the desired comb state. A MODE field picture is useful design evidence, but does not by itself answer these system questions.

## What the literature plots, and what it means

| Figure | Purpose and interpretation | Required native data |
| --- | --- | --- |
| Mode intensity with geometry; confinement Γ and area versus width/thickness | Locate the field in the active layer and compare candidate geometries. Confinement competes with saturation power and parasitic loss; the maximum Γ is not automatically the best amplifier. | MODE fields, native overlap/area and a geometry sweep |
| Signal output power and gain versus signal input power, at fixed bias/wavelength | Identify small-signal gain and compression. A 3 dB compression point is where gain has fallen 3 dB from an established unsaturated plateau; distinguish input and output saturation powers. | Calibrated native SOA signal power at both reference planes, input-power sweep |
| Signal output power and gain versus bias current | Choose an operating bias and look for limited benefit or thermal rollover. Hold wavelength, input power and temperature conditions fixed. | Native SOA current sweep and signal power exports |
| Gain versus wavelength for multiple currents/input powers | Determine useful gain bandwidth and wavelength-dependent saturation or ripple. | Native SOA wavelength sweeps |
| Transmission, reflection and insertion loss versus wavelength | Determine how much useful power the passive link delivers and how much is reflected. Total flux does not identify the guided output mode. | FDTD monitors; ports/mode expansion for modal coupling |
| ASE spectrum, noise figure, OSNR and polarization-dependent gain | Evaluate signal quality alongside gain. Noise figure, OSNR and RIN are different quantities and cannot be interchanged. | Appropriate native signal/noise analyzers and polarization runs |
| Resonance lineshape/Q, integrated resonator dispersion, comb spectrum, detuning scan and RF/heterodyne noise | Establish resonator suitability and distinguish noisy, breathing and stable comb states. | Native resonator frequencies/lineshapes, nonlinear dynamics and noise measurements |

Specific reading examples:

- [Davenport et al., *Heterogeneous Silicon/III–V Semiconductor Optical Amplifiers*, JSTQE 22 (2016)](https://siliconphotonics.ece.ucsb.edu/sites/default/files/2017-02/Davenport%20Heterogeneous%20Silicon%20III%E2%80%93V%20Semiconductor%20Optical%20Amplifiers_0.pdf): Figs. 3–7 compare simulated gain, confinement, field profiles and loss contributions against geometry. Figs. 13–14 show measured saturation curves and the gain/saturation trade-off; Fig. 15 shows gain bandwidth. This is a different heterogeneous stack, so its numbers are not specifications for our effective InP cross-section. Fig. 16 concerns lasing before AR coating, and should not be treated as a single-pass SOA power–current curve.
- [Feyisa et al., *Low Polarization Sensitive O-band SOA on InP Membrane for Advanced Photonic Integration* (2024)](https://pure.tue.nl/ws/files/334531562/Low_Polarization_Sensitive_O-Band_SOA_on_InP_Membrane_for_Advanced_Photonic_Integration.pdf): separates design predictions from measured TE/TM gain, polarization dependence and noise characterization. It illustrates why wavelength/polarization/noise must be reported together; its O-band device is not a C-band calibration for this project.
- [Raja et al., *Electrically pumped photonic integrated soliton microcomb*, Nature Communications 10, 680 (2019)](https://doi.org/10.1038/s41467-019-08498-2): Fig. 3 combines optical spectra with RF spectra to distinguish noisy, breathing and stable states. Fig. 4 adds resonator dispersion, linewidths and heterodyne coherence evidence. It uses self-injection locking, whereas our present script characterizes the SOA waveguide; the architecture and required resonator data differ.

For this project, start with field/overlap, geometry sweeps and passive link loss. The decisive next amplifier figures are signal power/gain versus input and current, followed by gain bandwidth and noise. Full microcomb claims require the resonator and dynamics evidence above.

## Automatically generated figures

After a successful CLI `run` or `run-lumerical`, publication figures are written into `<run>/figures` and its offline gallery opens in your browser for visible runs. The native Lumerical window behavior is independent.

```yaml
lumerical:
  make_figures: true
  show_figures: true
  figure_style: null  # Or ../styles/publication.yaml, relative to the selected YAML.
```

`hide_gui: true` suppresses automatically opening the browser. `make_figures: false` disables automatic rendering. Plotting failure is reported as `figures_error` in CLI output without changing a successful native simulation into a failed one.

Generate/replot an existing run without rerunning Lumerical:

```powershell
# From C:\Onchip-amplification:
.\.venv\Scripts\python.exe -m inpamp figures results/native-mode --show
# After editing results/native-mode/figures/figures.yaml:
.\.venv\Scripts\python.exe -m inpamp figures results/native-mode --replace --show
# Or use the generated regeneration recipe:
.\.venv\Scripts\python.exe results/native-mode/figures/regenerate.py
```

Repeating the CLI `figures` command creates a timestamped sibling when its requested folder already contains a package. This also applies to repeated `--output` values. The `--replace` option instead regenerates the chosen owned package from its native data. A completed run folder can be renamed together with its figures; the generated recipe uses a relative source path and manifests verify relocation through native-file hashes. The [file guide](../../FILE_GUIDE.md) describes every file and the naming rules. The older `plot` commands remain available for simple diagnostic graphs.

MODE automatically produces `mode_intensity`, `mode_profiles`, `waveguide_dispersion` and `waveguide_beta2`, plus a metrics table. FDTD produces transmission, reflection, insertion loss, reflection in dB, and monitor power balance. MODE sweep directories produce native effective-index, overlap and area curves versus the swept parameter. Current/active-power sweeps use explicit native field mappings described below.

The current straight-waveguide D is not the SiN ring's integrated dispersion. Its beta2 plot is only the algebraic conversion

```text
beta2 [s²/m] = -lambda² [m²] × D [s/m²] / (2πc [m/s])
D [ps/(nm km)] = D [s/m²] × 10^6
beta2 [fs²/mm] = beta2 [s²/m] × 10^27
```

Negative beta2 is anomalous; positive beta2 is normal. The fixed-index example includes waveguide dispersion, but not calibrated material dispersion. No cavity Dint, threshold or soliton state is inferred from it.

## Edit the presentation

Each generated `figures.yaml` lists the available figure names and options. Set `title: ''` to remove a title; `null` uses the default. Change labels, limits, scales, colors, colormaps, line width, markers, grid and font settings. For example:

```yaml
width_mm: 89.0
height_mm: 66.0
font_size: 9.0
dpi: 600
formats: [png, pdf, svg]
figures:
  mode_intensity:
    title: ''
    xlim: [-2.0, 2.0]
    ylim: [-0.8, 0.8]
    cmap: viridis
    field_scale: dB
    field_floor_db: -40.0
  waveguide_dispersion:
    title: My waveguide
    xlabel: Wavelength (nm)
    xlim: [1520.0, 1580.0]
    colors: ['#D55E00']
    marker: o
    linewidth: 1.5
    grid: false
```

Use `--style inp-amplifier/styles/publication.yaml` for the supplied starting style. Replotting preserves edited values in the output style. The PNG preview is always generated for the gallery. PDF/SVG preserve vector curves and text; field maps are rasterized to avoid huge vector meshes. Default dimensions are 89 × 66 mm, with embedded PDF fonts and 600 dpi PNG. Adjust these to the target journal's requirements.

Every curve has a CSV of displayed samples. Axis cropping does not crop its CSV. Separate traces may have different sample counts; empty padded cells are NaN. Field-map CSV contains coordinates, original native intensity and normalized intensity. The map's optional dB floor is explicitly a display limit; power curves never replace nonpositive values with a fake positive floor.

`figure_manifest.json` records source-file SHA-256 hashes, exact style and plotting-library versions. `metrics.json` contains values read from native exports. Captions and the gallery state limitations and show the configuration's `parameter_status`. Formatting alone does not establish publication-quality physical validation: include mesh convergence, a calibrated stack/model and justified error/uncertainty estimates in the study. No uncertainty bands or fitted curves are invented.

## Map active-circuit and noise data explicitly

First list the real analyzer field names:

```powershell
.\.venv\Scripts\python.exe -m inpamp inspect-results results/native-soa/output_spectrum.mat
```

Add `traces` to the style YAML. The following is a **data-contract example**, not a claim about stock Lumerical analyzer names: replace the filename and keys with your actual exports. Suppose a native export has matching vectors `input_signal_power_W`, `output_signal_power_W` and `noise_figure_dB`:

```yaml
figures:
  soa_transfer:
    xlabel: Input signal power (dBm)
    ylabel: Output signal power (dBm)
  soa_gain:
    xlabel: Input signal power (dBm)
    ylabel: Signal gain (dB)
  soa_nf:
    xlabel: Input signal power (dBm)
    ylabel: Noise figure (dB)
traces:
  - figure: soa_transfer
    file: native_powers.mat
    x: input_signal_power_W
    y: output_signal_power_W
    x_transform: W_to_dBm
    y_transform: W_to_dBm
  - figure: soa_gain
    file: native_powers.mat
    x: input_signal_power_W
    y: output_signal_power_W
    denominator: input_signal_power_W
    x_transform: W_to_dBm
    y_transform: ratio_to_dB
  - figure: soa_nf
    file: native_powers.mat
    x: input_signal_power_W
    y: noise_figure_dB
    x_transform: W_to_dBm
```

Gain is `10 log10(Pout_signal/Pin_signal)` at explicitly defined reference planes. Exclude ASE from signal power. Do not convert a PSD to dBm/nm by merely applying `W_to_dBm`: power-per-bin, W/Hz and W/nm need their own bin widths/Jacobian and labels. Report OSA resolution/noise bandwidth for spectra/OSNR. Native noise-figure values already in dB need no additional logarithm.

Several entries with the same `figure` overlay traces for comparing currents, polarization, meshes or operating states. `label` controls their legend; `component` selects real/imag/abs for complex values. `x_factor`, `y_factor`, `x_offset` and `y_offset` apply after the named unit transformation. `frequency_to_wavelength_nm` converts a positive native optical frequency axis. Existing native resonance Dint, time traces and RIN can use identity/scaling transformations with explicit units. No peak fitting, FFT noise estimation, or new physical simulation is performed.

For a completed sweep, use `x: null`: x comes from `sweep_manifest.json` and `file` is read in each case directory. `y` must select one scalar per case; a denominator, if used, must also be scalar. This supports native output power/gain versus current/input power. For an input-power parameter stored in mW, set `x_factor: 0.001` for watts without a logarithmic transform, or keep the mW axis and label it accordingly.
