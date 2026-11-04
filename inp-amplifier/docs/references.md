# References and parameter provenance

The equations use established SOA and Kerr-resonator model families. **No single publication's parameter table has been reproduced or fitted here.** All YAML device coefficients are editable, unmeasured starting assumptions. They must not be attributed to a real commercial/foundry amplifier or treated as a demonstrated performance target.

## Model references

1. M. J. Connelly, “Wideband semiconductor optical amplifier steady-state numerical model,” *IEEE Journal of Quantum Electronics* **37**, 439–447 (2001). [DOI: 10.1109/3.910455](https://doi.org/10.1109/3.910455). Reference for coupling traveling signals, ASE and carriers in SOAs. Our implementation is substantially simpler: Gaussian effective gain, ABC recombination and fixed spontaneous-emission factor replace the full material/spectral treatment.
2. G. P. Agrawal and N. A. Olsson, “Self-phase modulation and spectral broadening of optical pulses in semiconductor laser amplifiers,” *IEEE Journal of Quantum Electronics* **25**, 2297–2306 (1989). Reference for carrier-induced gain/phase coupling and the linewidth-enhancement factor. Our transient is a lumped current-step approximation, not that paper's complete pulse-propagation model.
3. H. Coen, H. G. Randle, T. Sylvestre and M. Erkintalo, “Modeling of octave-spanning Kerr frequency combs using a generalized mean-field Lugiato–Lefever model,” *Optics Letters* **38**, 37–39 (2013). [DOI: 10.1364/OL.38.000037](https://doi.org/10.1364/OL.38.000037). Reference for the mean-field Kerr-resonator approach; our baseline retains only Kerr and D2/D3 dispersion.
4. G. Moille, Q. Li, X. Lu and K. Srinivasan, “pyLLE: a Fast and User Friendly Lugiato–Lefever Equation Solver,” *Journal of Research of NIST* **124**, 124012 (2019). [DOI: 10.6028/jres.124.012](https://doi.org/10.6028/jres.124.012). The authors' [public repository](https://github.com/gregmoille/pyLLE), including its solver and documented resonator/dispersion workflow, was inspected as an implementation reference. This project implements its own small normalized Python solver; it does not bundle, execute or validate against pyLLE. The upstream README currently says the package is no longer maintained.
5. The user's [GDSLayout example](https://github.com/Liu-Wenzheng/gdslayout) was inspected for its YAML-per-device and configurable layout workflow. This project uses independent gdstk geometry instead of its larger GDSFactory-based layout dependency stack. GDSLayout itself is not an InP SOA solver.

Publisher/arXiv requests were blocked by this environment's outbound domain policy during implementation. The primary references above identify the standard model families, rather than implying new retrieval of their full text or a fresh literature survey. Accessible GDSLayout and pyLLE documentation/source were consulted directly. Before committing to a physical stack, consult the full primary articles and your foundry's data; there is no claim here of literature-validated numerical coefficients or current state-of-the-art InP amplifier performance.

## Why these starting values?

| YAML group | Initial choice and status |
| --- | --- |
| Platform/wavelength | 1550 nm effective InGaAsP/InP SOA and a SiN resonator: a telecom-band design scenario, not a specific epitaxy |
| Active geometry | 1 mm × 2 um × 0.12 um pumped region; 0.4 um effective optical core: illustrative geometry; not extracted from a paper |
| Indices | Core 3.4, cladding 3.17: approximate effective values to demonstrate guiding; no wavelength/temperature dispersion fit |
| Injection/recombination | 250 mA, eta=0.7, A=1e8 s⁻¹, B=1e-16 m³/s, C=3e-41 m⁶/s: illustrative III–V rate-equation scales, not measured coefficients |
| Material gain | a=2.5e-20 m², Ntr=1.5e24 m⁻³, 70 nm Gaussian width, 1500 m⁻¹ internal loss: jointly uncalibrated example assumptions |
| Saturation/noise | epsilon=5 W⁻¹, n_sp=2, alpha_H=5: phenomenological example values; not a measured saturation power/noise figure |
| Heating/interfaces | 30 K/W, 1.3 V, two 1.5 dB SOA interfaces and 2 dB to the ring: packaging/link assumptions |
| Resonator | 100 um radius, Q_i=Q_c=2e6, n_g=n_eff=1.9, A_eff=0.8 um²: editable illustrative high-Q SiN scenario |
| Kerr/dispersion | n2=2.4e-19 m²/W is a conventional order-of-magnitude SiN modeling choice; D2/(2pi)=2 MHz is an assumed anomalous-dispersion example, not calculated from ring width |
| Detuning/noise | Scan alpha=-2 to 3, seeded numerical field noise: numerical experiment settings, not an experimentally verified soliton-access protocol |
| Layout | Arbitrary layers and dimensions for visualization/export; no foundry rules or transition design |

The scalar-mode overlap is calculated from the example cross-section. The saturated gain and output power are solver results, not preselected target gains. This allows current, geometry and optical power changes to have coupled consequences while keeping calibration responsibilities visible.

## Reproducibility of consulted source

- GDSLayout inspection: commit `736ee58db68f3242196283930d9dd8a28aa88b9d`.
- pyLLE inspection: commit `37adc0113312529b187484e8b9255a706654debc`.
- Runtime dependencies: pinned in `requirements.lock`.
- Each simulation report records the input hash, source-code hash, git state and actual dependency versions in `metadata.json`.
