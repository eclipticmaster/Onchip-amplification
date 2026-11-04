"""Concept geometry sharing amplifier length/width and resonator radius with physics.

Layer numbers are illustrative and carry no foundry/process meaning.
"""
import json
from pathlib import Path

import gdstk
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

from .config import Config


LAYERS = {"InP ridge": 1, "top contact / pad": 2, "passive bus": 3,
          "resonator": 4, "annotation": 99, "outline": 100}


def export_layout(c: Config, output: Path):
    d, l, r = c.device, c.layout, c.microcomb
    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    cell = lib.new_cell("INP_PUMP_CONCEPT")
    length, width, taper = d.length_um, d.width_um, l.taper_length_um
    y0 = 0.0
    x0, x1 = taper, taper + length
    cell.add(gdstk.rectangle((x0, -width / 2), (x1, width / 2), layer=1))
    cell.add(gdstk.Polygon([(0, -l.port_width_um / 2), (x0, -width / 2), (x0, width / 2), (0, l.port_width_um / 2)], layer=1))
    cell.add(gdstk.Polygon([(x1, -width / 2), (x1 + taper, -l.port_width_um / 2), (x1 + taper, l.port_width_um / 2), (x1, width / 2)], layer=1))
    # One schematic top contact; backside return contact is not a layout mask.
    cell.add(gdstk.rectangle((x0 + length * 0.1, -width * 0.25), (x1 - length * 0.1, width * 0.25), layer=2))
    pad_x = x0 + length / 2
    pad_y = -l.pad_offset_um
    cell.add(gdstk.rectangle((pad_x - l.pad_size_um / 2, pad_y - l.pad_size_um / 2),
                            (pad_x + l.pad_size_um / 2, pad_y + l.pad_size_um / 2), layer=2))
    cell.add(gdstk.rectangle((pad_x - 5, pad_y), (pad_x + 5, 0), layer=2))
    amplifier_out = x1 + taper
    x_end = amplifier_out
    if r.enabled:
        ring_x = amplifier_out + 2 * r.radius_um + 100
        ring_y = r.radius_um + l.ring_width_um / 2 + l.ring_gap_um + l.bus_width_um / 2
        x_end = ring_x + 2 * r.radius_um + 100
        cell.add(gdstk.rectangle((amplifier_out, -l.bus_width_um / 2), (x_end, l.bus_width_um / 2), layer=3))
        cell.add(gdstk.ellipse((ring_x, ring_y), r.radius_um + l.ring_width_um / 2,
                              inner_radius=r.radius_um - l.ring_width_um / 2, tolerance=0.01, layer=4))
    top = (2 * r.radius_um + 80) if r.enabled else 100
    bottom = -l.pad_offset_um - l.pad_size_um / 2 - 80
    # Outline is a thin frame rather than a filled rectangle covering the device.
    outer = gdstk.rectangle((-80, bottom), (x_end + 80, top))
    inner = gdstk.rectangle((-78, bottom + 2), (x_end + 78, top - 2))
    cell.add(*gdstk.boolean(outer, inner, "not", layer=100))
    cell.add(gdstk.Label("CONCEPT ONLY - NO PDK / DRC", (0, top - 25), layer=99))
    cell.add(gdstk.Label("InP SOA; active length %.1f um" % length, (x0, 35), layer=99))
    if r.enabled:
        cell.add(gdstk.Label("Hybrid interface: supplied link loss", (amplifier_out + 10, -40), layer=99))
    gds = output / "design.gds"
    lib.write_gds(str(gds))
    ports = {"units": "um", "status": "concept_only_not_fabrication_ready",
             "input": {"center": [0, y0], "width": l.port_width_um, "orientation_deg": 180},
             "amplifier_output": {"center": [amplifier_out, y0], "width": l.port_width_um, "orientation_deg": 0},
             "bus_output": {"center": [x_end, y0], "width": l.bus_width_um, "orientation_deg": 0},
             "layers": LAYERS, "backside_contact": "not modeled"}
    (output / "ports.json").write_text(json.dumps(ports, indent=2) + "\n")
    colors = {1: "#0969da", 2: "#bf8700", 3: "#1a7f37", 4: "#8250df", 100: "#7d8590"}
    fig = plt.figure(figsize=(13, 7))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.4, 1])
    ax = fig.add_subplot(grid[0, :])
    taper_ax = fig.add_subplot(grid[1, 0])
    zoom_ax = fig.add_subplot(grid[1, 1])
    names = {v: k for k, v in LAYERS.items()}
    for target in [ax, taper_ax, zoom_ax]:
        used = set()
        for p in cell.polygons:
            target.add_patch(Polygon(p.points, facecolor=colors.get(p.layer, "gray"), alpha=0.8,
                                     label=names[p.layer] if p.layer not in used else None))
            used.add(p.layer)
        target.set(xlabel="x (um)", ylabel="y (um)")
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.set_title("Concept layout - InP SOA and hybrid resonator interface (no PDK / DRC)")
    ax.legend(loc="upper left", fontsize=8, ncol=3)
    ax.annotate("", xy=(x0, 40), xytext=(x1, 40), arrowprops=dict(arrowstyle="|-|", color="#0969da"))
    ax.text((x0 + x1) / 2, 55, f"Pumped length {length:g} um; ridge width {width:g} um", ha="center", fontsize=9)
    ax.text(pad_x + l.pad_size_um, pad_y, "Top contact", va="center", fontsize=9)
    taper_ax.set(xlim=(-5, taper + 20), ylim=(-width * 1.5, width * 1.5), title="Input taper detail (axes scaled independently)")
    if r.enabled:
        ax.text(ring_x, top - 15, f"Ring R={r.radius_um:g} um", ha="center", fontsize=9)
        zoom_ax.set(xlim=(ring_x - 12, ring_x + 12), ylim=(-2, 6), title=f"Ring/bus detail; drawn gap {l.ring_gap_um:g} um")
        zoom_ax.set_aspect("equal")
    else:
        zoom_ax.set(xlim=(x1 - 20, amplifier_out + 5), ylim=(-width * 1.5, width * 1.5), title="Output taper detail (axes scaled independently)")
    fig.tight_layout()
    fig.savefig(output / "layout.png", dpi=180)
    plt.close(fig)
    # Round-trip the binary artifact to detect a failed/incomplete GDS export.
    check = gdstk.read_gds(str(gds))
    if not check.top_level() or not check.top_level()[0].polygons:
        raise RuntimeError("GDS export contains no geometry")
