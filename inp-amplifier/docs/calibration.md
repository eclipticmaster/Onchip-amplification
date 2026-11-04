<<<<<<< HEAD
# Steps in order to accomplish calibration of the model

1. Specify the actual InP-platform epitaxy and active material (for example an InGaAsP or InAlGaAs multiple-quantum-well structure). Replace effective core dimensions, carrier volume, refractive indices, injection efficiency and overlap with foundry data or a vector-mode calculation.
2. Fit transparency, differential gain, spectral width/peak, internal loss and ABC recombination to measured gain–current and gain–wavelength curves. Fit gain compression against output-versus-input power at several currents. Many combinations are indistinguishable. Record data source, wavelength, temperature, polarization and reference planes.
3. Use measured input/output coupling losses and residual facet reflectivities. Compare saturated output and ASE spectra. Fit `n_sp` to ASE/noise data only over the range where its simplified source model applies. A fixed n_sp does not reproduce the full semiconductor spontaneous spectrum near transparency.
4. Fit thermal resistance and gain drift using I–V curves and temperature-dependent gain measurements. Replace the heat model with electrical/thermal FEM when local heating and device reliability matter.
5. Import the resonator's measured Q, coupling, dispersion and FSR, or obtain them from a vector eigenmode/coupler calculation. A drawn gap is not an inferred coupling Q. Measure the SOA-to-bus insertion loss.
6. Compare LLE predictions against calibrated pump power, detuning and thermal scanning conditions. Add measured laser/SOA amplitude and phase-noise spectra for noise-sensitive microcomb work; the current code deliberately does not equate its numerical perturbations with SOA noise. Model coherent reflections if the amplifier and ring interact through feedback.
7. Replace the concept GDS with a foundry PDK, contacts, isolation, cladding, alignment marks, optical transitions, electrical routing and real design rules before fabrication.

Save each fit as its own YAML and write the measured-data provenance in `calibration_notes`. Use `parameter_status: calibrated` only when you have a documented calibration. Keep the input data and raw outputs with the resolved configuration and metadata. No credentials, PDKs or measured data are bundled in this repository.
For basic geometry exploration, make a child config for each length/width/current and run with `--check`. Changing width/active thickness changes carrier density as well as optical confinement; holding current fixed does not hold current density fixed. The built-in current and input-power sweeps intentionally hold all other inputs fixed. A useful first design map is output power and OSNR versus current and active length, with a separate thermal/feedback constraint.
=======
# Calibrate and validate in Lumerical

1. Identify the real InP-platform epitaxy and active material (for example InGaAsP or InAlGaAs QWs). Build/import its vector geometry and dispersive materials in MODE. Replace the effective centered stripe analysis mask with the actual gain layers. Verify polarization, overlap and mesh/window convergence in MODE.
2. Select a native SOA element/CML in INTERCONNECT whose gain, carrier/saturation, ASE/noise and thermal capabilities match your study. Load measured/foundry gain data or a documented literature parameter set into that native model. Fit gain versus current, wavelength and input power there; Python does not implement or fit an alternative amplifier model.
3. Verify every native property name, expected unit and electrical port. Bind common YAML quantities and `parameters.*` to those exact properties. Record which coefficients are inferred versus measured and their reference planes. Geometry changes do not automatically recalibrate an unrelated CML.
4. Measure/simulate the actual coupling transition and passive link using native FDTD/ports. The included short taper is an effective passive coupon, not a validated InP-to-SiN transition or a full SOA.
5. Compare native power-meter and spectral/noise analyzer results against the input data, including interface losses and current/temperature conditions. Model thermal/electrical effects in appropriate native components/solvers if the selected SOA lacks them. No thermal balance is calculated in Python.
6. For full microcomb behavior, add a native nonlinear resonator model with the real Q/coupling, dispersion, Kerr response, pump scan and noise/feedback physics. A passive ring filter does not generate a comb. The prior Python LLE is removed, so this native model is a real prerequisite rather than a hidden fallback.
7. Run native grid/time-window/parameter convergence studies and retain native `.lms/.fsp/.icp` projects and analyzer exports. Plot those files later with Python. A graph or passing IO test is not evidence of native convergence or a stable soliton.

Save calibrated settings as a child YAML and document data/version/source in `calibration_notes`. Mark `parameter_status: calibrated` only with an actual documented calibration. No secrets, proprietary PDK or measured device data are bundled here.
>>>>>>> 06e41dcd3220de3304f4664c87f8723bb3a0fbd4
