# Edit figures.yaml, then run this file using the project virtual-environment Python.
from pathlib import Path
from inpamp.figures import create_figures
create_figures((Path(__file__).resolve().parent / '..').resolve(), Path(__file__).resolve().parent, solver='mode',
               style_path=Path(__file__).with_name("figures.yaml"), replace=True, show=True)
