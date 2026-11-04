# Physics belongs to the native Lumerical models

The Python package has no physical solver. It does not solve eigenmodes, carrier rate equations, optical gain/ASE, temperature, pulse propagation or a Kerr/LLE equation. There is no idealized-model fallback when Ansys is missing or a native run fails.

## MODE

`mode.lsf` builds the effective InGaAsP/InP cross-section and uses native FDE `findmodes` and tracked `frequencysweep`. Native vector fields, intensity, effective index, scalar-field effective area and gain-stripe power overlap are exported. The overlap and area integrations execute in **Lumerical script**, not Python. Python serializes those numbers and plots the exported field/dispersion.

The initial cross-section uses effective indices and a centered active-stripe mask, not a resolved multiple-quantum-well stack. Set native material names or build the real layered geometry before drawing physical conclusions. Fixed indices contain geometric waveguide dispersion only. Inspect mode identity/polarization, active-mask sampling, mesh/window convergence and mode crossings. The area definition uses |E|; a rigorous nonlinear effective area in dispersive media may need a different native analysis expression.

## FDTD

`fdtd.lsf` simulates a short passive 3-D taper with a TE-like mode source, PML boundaries and total-power transmission/reflection monitors. The default coupon is 20 um long; it is not a full 1 mm active amplifier. Source normalization, loss, radiation and reflection are calculated by **FDTD**. Python converts exported frequency to wavelength for display and plots the monitor values without fitting an ideal curve.

Refine native mesh, PML distances and simulation decay time; inspect actual memory/runtime. Total flux is not a guided-mode S matrix or a calibrated InP-to-SiN transition loss. Native ports/mode-expansion measurements and the actual heterogeneous stack are needed for that study. No negative-index substitute is used to invent active gain.

## INTERCONNECT

The active SOA physics is supplied by your selected native SOA element or foundry CML inside a real `.icp` template. That model must include the gain/carrier/saturation/ASE behavior needed by your study. Electrical bias, material coefficients and thermal behavior only affect the simulation if they are part of that model and explicitly bound/configured. The Python runner only sets properties, runs INTERCONNECT and saves its analyzer results.

`parameters` is a map of extra native model inputs, not an implemented Python rate-equation model. The exact native property names and units must be verified. For example a material coefficient under `parameters.alpha_H` does nothing unless a `bindings` entry sends it to the correct native element property; a sweep without an applicable binding is rejected.

For full microcomb dynamics, the INTERCONNECT template must also contain a suitable native nonlinear resonator model with calibrated dispersion, coupling and Kerr response. A passive ring transfer function alone is insufficient. This repository does not bundle that model or calculate a comb in Python. Calibration/native-model availability remains a prerequisite; the code does not fabricate results for missing physics.

## Graphs and analysis

`plot` and `plot-sweep` read existing native `.mat`/JSON exports and write PNG/CSV graphs. They may reshape arrays, select traces/components and convert axis/display units; they do not propagate fields or predict missing device data. The graph manifest records source hashes and `simulation_performed: false`. Native datasets from a failed/incomplete runner invocation are rejected. GUI exports are supported and marked as not verified by the runner.

Only native Ansys result files establish a native result. Generating a `.lsf`, passing orchestration/plotting tests or opening a project file does not establish a physical simulation's correctness. Check the installed Ansys version, native model calibration and convergence on your licensed machine.
