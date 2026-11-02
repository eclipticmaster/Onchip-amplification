# Simulation roadmap

This is a sequence of experiments, not an implementation claim.

| Stage | Question | Proposed method | Output to save |
|---|---|---|---|
| 1 | Where does the signal mode live? | Lumerical MODE/FDE at ~1550 nm | field profile, `Aeff`, `Gamma_Er`, `neff` |
| 2 | Does the pump overlap the signal? | MODE/FDE at ~980 nm | pump/signal fields and overlap |
| 3 | Can a compact taper move the mode adiabatically? | Lumerical EME, length sweep | conversion loss vs taper length |
| 4 | What gain is possible with a chosen Er film? | coupled rate / power equations with measured spectra | gain vs pump / signal / length |
| 5 | Can pulses be stretched on-chip over the Er gain bandwidth? | dispersion sweeps, grating or dispersive waveguide | GDD, TOD, insertion loss vs wavelength |
| 6 | Does CPA improve pulse energy without unacceptable nonlinear phase? | gain-modified NLSE / split-step propagation | pulse/spectral phase, B-integral, energy, duration |
| 7 | Can the pulsed output synchronously drive a Kerr resonator? | resonator mean-field model (LLE), with measured pump spectrum | soliton operating region, required seed power, comb efficiency |

## Separate system choices

**CW microcomb:** an Er amplifier can boost a coherent CW seed without CPA.

**Pulse-pumped microcomb:** a pulsed seed + optional CPA may help, but waveform, repetition rate and phase must suit the target ring. Don't select an arbitrary 100-fs output just because compression is possible.

## First paper-relevant benchmarks

Compare against a commercial EDFA or semiconductor-gain-assisted approach under matched resonator conditions: external seed power, on-chip pump power, comb efficiency, soliton access stability, optical noise and repetition-rate phase noise. Do not report a reduced **intrinsic cavity threshold** merely because the on-chip amplifier increases delivered pump power.
