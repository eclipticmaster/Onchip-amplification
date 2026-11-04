# On-chip amplifier simulations

## InP amplifier for a microcomb pump

The [InP amplifier project](inp-amplifier/README.md) prepares editable YAML and native Ansys Lumerical scripts for a CW pump laser amplified by an Indium Phosphide (InP) semiconductor optical amplifier using a method of Chirped Pulse Amplification before a microcomb.

- [Edit the Lumerical YAML](inp-amplifier/configs/lumerical.yaml) and inherited [device settings](inp-amplifier/configs/inp_pump.yaml).
- [Follow the Lumerical guide](inp-amplifier/docs/lumerical.md): MODE vector modes/dispersion, FDTD passive taper transmission/reflection and INTERCONNECT native SOA/CML circuit automation.
- [Copy the generated native scripts](inp-amplifier/lumerical/generated/README.txt) to your licensed installation, or run through the vendor `lumapi`.
- Optional separate Python reference models cover carriers, gain/ASE, heating, transients, sweeps and a Kerr LLE. Their results are not Lumerical simulations.

```bash
cd inp-amplifier
bash scripts/setup.sh
.venv/bin/python -m inpamp export-lumerical configs/lumerical.yaml --output results/lumerical-export
```

Ansys is not installed in this cloud environment. Native execution requires your licensed MODE/FDTD/INTERCONNECT installation and a configured native SOA/CML template for active gain. Starting parameters and layouts are illustrative; see [scope](inp-amplifier/docs/lumerical.md) and [references](inp-amplifier/docs/references.md).

## Earlier Er:Al₂O₃ / SiN CPA starter

The original scripts remain in [on-chip-erbium-cpa](on-chip-erbium-cpa/README.md). The standalone educational CPA model uses NumPy/Matplotlib; its separate mode script requires Ansys Lumerical MODE. The original README is preserved there in UTF-8.
