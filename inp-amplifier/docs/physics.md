# Models, equations and conventions

All calculations are SI internally except the scalar mode mesh and concept layout, which use micrometres. YAML units are explicit in field names. Gains/losses are **power** coefficients in m⁻¹, not field coefficients. Optical interface losses are in dB. Reflectivities are power ratios.

## 1. Effective InP-platform cross-section

The initial structure is a rectangular effective InGaAsP optical core embedded in InP with an effective active stripe centered inside it. These are effective indices/dimensions, not a resolved separate-confinement heterostructure or quantum-well stack. An index contrast at 1550 nm does not imply that bulk InP provides the gain.

Solve the scalar Helmholtz eigenproblem:

`[∂x² + ∂y² + k0² n(x,y)²] E = beta² E`, `neff = beta/k0`.

A sparse second-order finite-difference operator has zero-field (Dirichlet) boundaries outside the interior grid. Fractional rectangular cell occupancy reduces grid staircasing. The largest guided eigenvalue gives a **single scalar** fundamental mode. It is not a full-vector TE/TM calculation, mode-count guarantee, loss calculation, or accurate overlap for a realistic multilayer stack.

`Gamma = integral_active |E|² dA / integral_all |E|² dA`

`Aeff = (integral |E|² dA)² / integral |E|⁴ dA`.

The scalar overlap lacks the vector energy weighting required in rigorous dispersive media. Monitor boundary energy and refine window/mesh independently. Imported `mode.confinement_factor` and `effective_area_um2` are used when `mode.enabled: false`.

## 2. Spatial CW semiconductor optical amplifier

With active area `Aa = width * active_thickness`, active volume `V = Aa * L`, uniform current injection, and carrier density `N(z)`:

`J = eta_inj * I / (q V)`

`R(N) = A N + B N² + C N³`

`g_mat(lambda,N,T) = a (N - Ntr(T)) exp[-4 ln(2) ((lambda-lambda_peak(T))/gain_fwhm)²]`

`g_k = Gamma * g_mat_k / [1 + epsilon_P * (Psignal + sum(Pase+ + Pase-))]`.

`g_k` is modal material gain, before internal loss. A single common carrier reservoir causes cross-saturation across signal and ASE bins. Negative gain represents absorption and contributes carrier generation in the algebraic balance. The Gaussian spectral envelope, fixed differential gain and power compression are phenomenological. This does not resolve band filling, QW carrier capture/escape, spatial hole burning within the transverse mode, carrier heating, spectral hole burning or a microscopic emission spectrum.

At each longitudinal cell:

`0 = J - R(N) - sum_k [g_k Ptotal_k / (h nu_k Aa)]`.

For fixed powers, the carrier balance is a monotonic cubic and is solved by bracketed vector bisection. The source photon energies differ across ASE bins. Passive propagation loss does **not** deplete carriers through stimulated emission.

Signal propagation and ASE in each frequency bin:

`dPsignal/dz = (g_signal - alpha_int) Psignal`

`+dPase+/dz = (g_k-alpha_int) Pase+ + S_k`

`-dPase-/dz = (g_k-alpha_int) Pase- + S_k`

`S_k = 2 n_sp h nu_k max(g_k,0) Delta_nu_k`.

The factor 2 denotes the total of two polarizations; one forward/backward power array is stored for each direction. This treats both polarizations as having the same effective gain/overlap. It is a simplified high-inversion ASE source with fixed `n_sp`, not a full spontaneous-emission model near/below transparency. It is not a reproduction of Connelly's full wideband band-structure model. A minimum spontaneous source independent of net gain is not modeled. ABC radiative recombination and ASE injection are phenomenological closures, not an exactly calibrated radiative-rate partition.

ASE has zero incoming boundary power at both ends. Frequency bins are uniform, spanning the configured wavelength interval around the reference gain peak. In each cell an exact constant-coefficient exponential update integrates gain/loss plus source. Under-relaxed iterations update the two traveling directions and temperature until both propagated-power and independent carrier-balance residuals pass. Failure to converge returns an error, not a success report. Interface losses act outside the gain region; signal and forward ASE both see the output loss.

### Output metrics

`G = Psignal_external_out / Psignal_external_in` includes both interface losses.

`OSNR = Psignal_external_out / [S_ASE_external(nu_signal) * Delta_nu_RBW]`, where `Delta_nu_RBW ≈ c Delta_lambda_RBW/lambda_signal²`. Both ASE polarizations are included and OSNR is an optical power ratio; it is not a predicted comb linewidth or RF SNR.

The optional high-gain noise-figure approximation is `F = 1/G + S_ASE_external/(G h nu_signal)`. This includes passive interface loss through `G` and the output PSD, but does not model input laser noise or detector bandwidth/noise. It is not available when ASE is disabled or the signal is outside the ASE integration band.

Feedback warning: `Rin Rout exp(2 integral(g_signal-alpha_int) dz) >= 1` indicates that a reflection-free traveling-wave model may lase and is invalid. Reflected waves and SOA–resonator coherent feedback are not solved.

## 3. Lumped thermal balance

`Pheat = max(Vjunction I - [Psignal_gain_region_out - Psignal_gain_region_in + Pase_forward_out + Pase_backward_out], 0)`

`Tjunction = Tambient + Rthermal Pheat`

`Ntr(T) = Ntr_ref exp[(T-Tref)/Tscale]`

`lambda_peak(T) = lambda_peak_ref + shift * (T-Tref)`.

The solver warns if extracted optical power exceeds electrical input rather than silently treating that as a valid parameter fit. This is a package-level effective thermal closure: spontaneous radiation escaping unguided modes, detailed electrical transport, contact losses, local absorption heat, interfaces, temperature gradients and time-dependent heat diffusion are not resolved. `thermal.enabled: false` holds material parameters at `ambient_K`.

## 4. Lumped current-step transient

A separate one-reservoir model integrates `dN/dt = J(t) - R(N) - g(N) L Pmean/(h nu V)` with `Pmean = (Pin+Pout)/2`. The implicit gain-compressed single-pass output is solved from `Pout = Pin exp[(g(N,Pmean)-alpha_int)L]`. The integrator begins at the initial-current equilibrium and restarts at the specified step. Carrier density and output power are calculated; `phi(t) = -alpha_H L [g(t)-g(0)]/2`, and chirp is `dphi/dt/(2pi)`.

This is a learning model for current-driven gain/phase response. It omits ASE, propagation delays, spatial carrier profiles and thermal dynamics; temperature is held at the CW result. Its final output need not equal the spatial CW solver. It does not calculate a pump RIN/phase-noise spectrum or ultrashort-pulse propagation.

## 5. Kerr resonator and LLE

The ring is an illustrative SiN resonator reached through `microcomb.link_loss_dB` after the SOA's output loss. Its gap/width drawing does not calculate Q or dispersion.

`omega0 = 2 pi c/lambda_pump`

`kappa0 = omega0/Qintrinsic`, `kappa_ex = omega0/Qcoupling`, `kappa = kappa0+kappa_ex`

`FSR = c/(ng 2 pi R)`, `Veff = 2 pi R Aeff`

`g0 = hbar omega0² c n2 / (neff² Veff)` (single-photon Kerr shift)

`Dint(mu) = D2 mu²/2 + D3 mu³/6`.

YAML `D2_MHz` means `D2/(2pi)` in MHz; positive D2 is anomalous in this convention. `D3_kHz` has the corresponding angular-frequency conversion. This finite polynomial is not a calculated material/geometric dispersion spectrum; avoid extrapolating it outside its validity.

Use `tau = kappa t/2`, `alpha = 2(omega_cold-omega_pump)/kappa`, `psi = sqrt(2g0/kappa) A`, where modal `A_mu` is in sqrt(photons), and `a_mu = FFT(psi)/Ngrid`:

`dpsi/dtau = -(1+i alpha) psi + i |psi|² psi - i FFT^-1[(2Dint/kappa) FFT(psi)] + F`

`F² = 8 g0 kappa_ex Pdelivered / (kappa³ hbar omega0)`.

The reported `ideal_F_squared_one_power_mW` is a **normalization/reference drive scale**, not a guarantee of oscillation or a soliton threshold. Mode instability also depends on detuning, dispersion, available mode numbers, scanning, seed and perturbations.

Linear loss, detuning, dispersion and constant pump are integrated exactly in Fourier space, symmetrically around an exact local Kerr phase step. The time-dependent scan uses midpoint detuning, then holds the final detuning. The seeded numerical complex field perturbations have magnitude `field_noise_per_sqrt_tau`, added with sqrt(time-step) scaling; these are explicitly **not calibrated quantum noise, SOA ASE or pump RIN**. Set to zero for deterministic analytic-limit tests. The requested `time_step` is an upper bound: the solver shortens it to keep the maximum dispersion phase per step at most 0.5 rad, avoiding artificial high-mode growth observed with a larger unbounded step. It refuses more than two million internal steps. A separate nonlinear phase-step guard and spectral-edge monitor flag under-resolution; none of these proves convergence alone. There is no automatic anti-alias filter or dispersion beyond D3. Increase modes and reduce time step for confirmation. Different grid sizes/seeds can select different multistable trajectories; do not expect identical pulse positions/counts from independently seeded scans.

`resonator_leakage_mW = kappa_ex hbar omega0 |A_mu|²` is the field leaking from the resonator into the bus. It is **not the through-port pump power**, which needs interference with the input field. The exported waveform is intracavity circulating power, not a free-space compressed pulse. Reported sideband counts use a -60 dBc cutoff against the final leaking pump and are descriptive only.

This unidirectional coupling transfers SOA average CW **signal power** into the LLE. It omits calibrated laser/SOA noise transfer, resonance thermal shifts, feedback, Raman response, self-steepening, avoided crossings, multimode coupling, and a stability proof or automatic soliton classification. The low initial noise can leave a CW trajectory; a spectrum with sidebands is not necessarily a soliton. Sweep detuning and hold time, test seeds, mesh/time-step convergence and analyze stability before making a physical claim.
