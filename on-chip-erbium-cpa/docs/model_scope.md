# What these simulations do (and do not do)

## Stage 1: cross-section and modes

**Solver:** Ansys Lumerical MODE/FDE (2-D transverse eigenmode solve), controlled through `lumapi`.

**Geometry:** buried SiN rail, SiO₂ spacer, Er:Al₂O₃ film.

**Outputs:** `neff`, scalar-intensity effective area, estimated fraction of forward Poynting flux inside the gain-layer bounds, SiN-width sweep, and a nominal dispersion sweep.

**Not yet verified:** mode-order tracking (the script uses `mode1` as a starting guess), TE/TM identity, leaky modes, physical rail/top-layer coupling, substrate, actual fabricated thicknesses, convergence of the FDE grid/boundaries, and measured material dispersion. Verify the TE-like mode visually at every critical sweep point. A power-overlap fraction is a useful first proxy, not a full microscopic gain-weighting model.

## Stage 2: idealized chirped-pulse calculation

**Inputs:** transform-limited Gaussian FWHM, initial pulse energy, repetition rate, stretcher GDD, assumed energy gain in dB, effective area and assumed Kerr coefficient.

**Outputs:** stretched duration, ideal amplified pulse energy, peak/average powers, an illustrative B-integral and ideally recompressed output.

**Not included:** field-resolved pulse propagation, erbium emission/absorption cross sections, population inversion, pump depletion, gain saturation, finite gain bandwidth, ASE, Er–Er upconversion, temperature dependence, higher-order dispersion or microcomb dynamics. It is **not** a predictive CPA model.

**Important:** a 20-dB gain setting is an illustration, not a measured achievable gain. At 1 GHz, 10 pJ input pulses amplified by 20 dB would imply 1 W optical average output, far above what should be assumed for this geometry without a validated pumped-gain model and thermal budget.

## Physics to validate before interpreting a result

1. Run a mesh and domain-size convergence study. Confirm the desired mode, not just `mode1`.
2. Use dispersive refractive index data for SiN, SiO₂, and the actual Er:Al₂O₃ film.
3. Solve at **both** Er pump (~980 nm) and signal (~1550 nm) wavelengths; evaluate spatial pump/signal overlap.
4. Add actual Er concentration, measured emission/absorption cross-section spectra, lifetimes, pump loss and upconversion.
5. Solve pump/signal propagation and rate equations along the gain length; include saturation and ASE.
6. Add a time-domain pulse propagator with gain spectrum, GDD/TOD and SPM, then characterize compression quality.
7. Only after these steps, couple to a microresonator model with pulse train repetition-rate vs FSR and pump-noise sensitivity.
