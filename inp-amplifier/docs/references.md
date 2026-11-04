# References and input provenance

This workflow uses native **Ansys Lumerical MODE, FDTD and INTERCONNECT**. It does not implement Python semiconductor or Kerr physics. The starting device dimensions/effective indices are illustrative; no single publication's parameter table has been fitted or reproduced as a validated device.

## Native workflow references

- Ansys [Python API installation guide](https://optics.ansys.com/hc/en-us/articles/39744901602707-Installation-and-Getting-Started-Python-API): use the vendor `lumapi.py` and your installed version's script/element documentation. Native script compatibility and model/property names must be tested on the licensed installation.
- The user's [GDSLayout example](https://github.com/Liu-Wenzheng/gdslayout) motivated the editable YAML workflow. It is not the semiconductor model used here. Inspected revision: `736ee58db68f3242196283930d9dd8a28aa88b9d`.

## Physics literature for choosing/calibrating a native model

1. M. J. Connelly, “Wideband semiconductor optical amplifier steady-state numerical model,” *IEEE Journal of Quantum Electronics* **37**, 439–447 (2001). [DOI: 10.1109/3.910455](https://doi.org/10.1109/3.910455). Background for gain/carrier/ASE capabilities to look for in the native SOA model; this repository does not implement that model in Python.
2. G. P. Agrawal and N. A. Olsson, “Self-phase modulation and spectral broadening of optical pulses in semiconductor laser amplifiers,” *IEEE Journal of Quantum Electronics* **25**, 2297–2306 (1989). Background for native gain/phase dynamics and linewidth-enhancement parameterization.
3. H. Coen, H. G. Randle, T. Sylvestre and M. Erkintalo, “Modeling of octave-spanning Kerr frequency combs using a generalized mean-field Lugiato–Lefever model,” *Optics Letters* **38**, 37–39 (2013). [DOI: 10.1364/OL.38.000037](https://doi.org/10.1364/OL.38.000037). Background for nonlinear resonator requirements; no Python LLE solver remains in this project.

Publisher/arXiv full-text access was blocked by the cloud network policy during the initial work. These are model-family references, not a claim of a fresh full-text literature survey or literature-calibrated numeric coefficients. Consult the primary articles and foundry/native model documentation before selecting an actual stack.

## Illustrative inputs that remain

| Input | Status/use |
| --- | --- |
| 1550 nm, 1 mW input, 250 mA bias | Telecom-band scenario; applied to native source/bias only when bound |
| 1 mm length, 2 um width, 0.4 um core, 0.12 um active stripe | Effective initial geometry; not an epitaxial recipe or qualified SOA design |
| Core/cladding indices 3.4/3.17 | Effective fallback for passive MODE/FDTD; replace with native dispersive materials |
| 20 um taper, 0.8 um input width | Passive diagnostic coupon; not validated hybrid insertion loss |
| Gain/recombination/ASE/thermal/Kerr coefficients | No surrogate defaults are solved in Python; configure/calibrate the actual native SOA/resonator model |

`requirements.lock` pins only automation, IO/plotting and test/build tools. Resolved YAML, native execution status, exported datasets and graph source hashes distinguish script generation from real solver results. Previously reported Python-model powers/spectra are historical and are not native Lumerical predictions.
