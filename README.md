# On-chip amplifier simulations in Lumerical

The [InP amplifier workflow](inp-amplifier/README.md) uses **Ansys Lumerical for every physics simulation**. Python is limited to YAML/configuration, native solver orchestration and graphs/analysis of exported native results.

- [Edit the native YAML settings](inp-amplifier/configs/lumerical.yaml) and inherited [device settings](inp-amplifier/configs/inp_pump.yaml).
- [Use the native workflow guide](inp-amplifier/docs/lumerical.md): MODE for vector modes/overlap/dispersion, FDTD for passive taper transmission/reflection, and INTERCONNECT for the native active SOA/CML circuit.
- [Copy the generated `.lsf` scripts](inp-amplifier/lumerical/generated/README.txt) to your licensed machine or launch through vendor `lumapi`.
- [Plot native data later in Python](inp-amplifier/README.md#plot-and-analyze-the-native-results-later). No Python physical model supplies the plotted simulation results.

```bash
cd inp-amplifier
bash scripts/setup.sh
.venv/bin/python -m inpamp export configs/lumerical.yaml --output results/native-scripts
# On the licensed Ansys machine, configure LUMERICAL_API_PATH first:
.venv/bin/python -m inpamp run configs/lumerical.yaml --solver mode --output results/native-mode
.venv/bin/python -m inpamp plot results/native-mode --solver mode --output results/mode-graphs
```

Active amplification requires a selected native INTERCONNECT SOA/CML template and calibrated gain data. A full microcomb requires a native nonlinear resonator model in that circuit; none is replaced with a Python LLE. Ansys is not installed in this cloud instance, so native compatibility/performance remain to be checked on the licensed installation.

The earlier [Er:Al₂O₃ MODE wrapper](on-chip-erbium-cpa/README.md) still launches Lumerical and plots its outputs. The standalone Python CPA simulator and the InP Python physics solvers have been removed.
