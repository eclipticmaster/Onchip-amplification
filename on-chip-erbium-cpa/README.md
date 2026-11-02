# On-chip Er:Al₂O₃ / SiN amplifier — simulation starter

A small Python research repository for studying a **large-mode-area Er³⁺:Al₂O₃ optical amplifier** built above a narrow SiN rail embedded in SiO₂, and exploring **chirped-pulse amplification (CPA)** at ~1550 nm.

> **Status: educational, first-order models — not a fabricated design or validated optical amplifier.**
> The mode solver uses approximate, constant refractive indices. The CPA calculation uses an assumed optical gain rather than measured erbium rate equations. Results must **not** be described as verified device performance.

## Architecture

```text
  top:   Er³⁺:Al₂O₃ active layer
         ─────────────────────────
           SiO₂ spacer
                 ▌  narrow SiN rail
                 ▌
         SiO₂ background / cladding
```

At the system level, the long-term concept is:

`pulse source → stretcher → Er:Al₂O₃/SiN LMA amplifier → compressor/pulse shaper → SiN microresonator`

CPA is for pulsed operation; **CW-pumped microcomb generation does not require CPA**. Synchronous pulse pumping also requires repetition-rate/FSR and phase matching, which this repository does not yet simulate.

## Files

| Path | Purpose |
| --- | --- |
| `simulations/mode/er_al2o3_sin_lma_mode.py` | Opens Lumerical MODE through `lumapi`; builds the cross-section; solves modes and sweeps SiN width; plots approximate Er-layer overlap and dispersion. |
| `simulations/cpa/er_al2o3_cpa_first_order.py` | Pure Python/NumPy first-order Gaussian-pulse stretcher, ideal gain, ideal compressor, intensity and nonlinear-phase estimate. |
| `docs/model_scope.md` | Assumptions, what is missing, and the most important quantities to validate. |
| `docs/research_roadmap.md` | Next simulations needed for a physical amplifier and pulsed microcomb. |
| `data/README.md` | Where measured Er:Al₂O₃ material properties can be added later. |
| `results/` | Generated figures/CSVs, locally ignored by Git. |

## Start in VS Code (Windows)

1. Install [Python](https://www.python.org/downloads/), [Git](https://git-scm.com/downloads), and [VS Code](https://code.visualstudio.com/). Install the **Python** extension in VS Code.
2. Open this **entire repository folder** with `File → Open Folder`.
3. Open a new terminal (`Terminal → New Terminal`) and create an environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

   If PowerShell activation is blocked, use `.venv\Scripts\python.exe` instead of `python`; no policy change is required.

4. Run the **standalone CPA calculation** (does not need Lumerical):

   ```powershell
   python simulations/cpa/er_al2o3_cpa_first_order.py
   ```

5. For the **waveguide eigenmode solver**, install/activate your licensed **Ansys Lumerical MODE** and identify the folder containing `lumapi.py`. In PowerShell, for example:

   ```powershell
   $env:LUMERICAL_API_PATH = "C:\Program Files\Ansys Inc\vXXX\Lumerical\api\python"
   python simulations/mode/er_al2o3_sin_lma_mode.py
   ```

   Replace `vXXX` with the version on your machine. Some standalone Lumerical installations use `C:\Program Files\Lumerical\vXXX\api\python` instead.

6. Inspect files under `results/mode/` and `results/cpa/`. The original scripts are deliberately simple and contain user-editable parameters near the top.

See Ansys's [Python API guide](https://optics.ansys.com/hc/en-us/articles/39744901602707-Installation-and-Getting-Started-Python-API) for alternative import methods.

## First experiments

- **Mode area:** sweep SiN width and see how the transverse mode expands into the active top layer.
- **Active-layer overlap:** compare large `Aeff` with the fraction of optical power in Er:Al₂O₃; both matter.
- **Dispersion:** calculate `D(λ)` for the hybrid geometry, but replace constant indices with measured **dispersive** material models before drawing conclusions.
- **Pulse shaping:** adjust the Gaussian pulse width, GDD and *assumed* gain to learn the CPA scaling.

## Upload to your GitHub account with VS Code

1. Open the unzipped project folder in VS Code.
2. Click **Source Control** (branch icon) → **Initialize Repository**.
3. Stage the source/documentation files, enter `Initial Er:Al2O3/SiN amplifier simulation scaffold`, and click **Commit**.
4. Open `Ctrl+Shift+P` → **Publish to GitHub** (or Source Control's Publish Branch / Publish to GitHub button).
5. Sign in to your existing GitHub account if prompted, choose **Private repository**, and publish.
6. Going forward: save → stage → commit → **Sync Changes** (or Push) to update GitHub.

Basic GitHub publishing works in VS Code without any additional GitHub extension. [Official VS Code guidance](https://code.visualstudio.com/docs/sourcecontrol/repos-remotes).

## Research/ownership precautions

Start with a **private** repository. Check the lab's rules before uploading proprietary foundry PDKs, licensed material data, partner files, unpublished results, or fabrication designs. Avoid adding large `.lms`/`.fsp` simulation outputs. Only publish source material you own or are allowed to share.

This repository contains **no external PDK** or third-party confidential materials.
