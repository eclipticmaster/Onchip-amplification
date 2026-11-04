# Earlier Er:Al₂O₃ / SiN MODE automation

The retained `simulations/mode/er_al2o3_sin_lma_mode.py` builds geometry and launches **licensed Ansys Lumerical MODE** through vendor `lumapi`. MODE solves the modes and dispersion. Python reads the native fields for postprocessing/plots; it does not contain an electromagnetic solver.

The former standalone Python CPA calculator has been removed to keep all physical simulation in Lumerical. CPA/pulse amplification needs a suitable native INTERCONNECT project; no Python replacement is provided.

For the new InP pump amplifier, use the [native YAML workflow](../inp-amplifier/README.md).

The current legacy wrapper loads `lumapi.py` from `C:/Program Files/Ansys Inc/v261/Lumerical/api/python/lumapi.py`, as configured in its import block. Keep that path for the matching installation or edit the import block for another installed version. The new InP workflow supports `LUMERICAL_API_PATH` and `--api-path` instead.

From this directory on the matching licensed machine:

```powershell
python -m pip install -r requirements.txt
python simulations/mode/er_al2o3_sin_lma_mode.py
```

`lumapi` is supplied by Ansys, not pip. The original effective refractive indices/geometry remain educational placeholders; calibrate to the real material stack before interpreting native results. Outputs are written under `results/mode/`.
