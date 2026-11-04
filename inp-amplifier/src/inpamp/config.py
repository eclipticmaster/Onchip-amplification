"""Strict, unit-explicit YAML inputs; errors never silently select a default."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Positive = Annotated[float, Field(gt=0)]
Nonnegative = Annotated[float, Field(ge=0)]
Fraction = Annotated[float, Field(gt=0, le=1)]
Reflectivity = Annotated[float, Field(ge=0, lt=1)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class Device(Model):
    length_um: Positive = 1000.0
    width_um: Positive = 2.0
    core_thickness_um: Positive = 0.4
    active_thickness_um: Positive = 0.12
    current_mA: Nonnegative = 250.0
    injection_efficiency: Fraction = 0.7
    internal_loss_per_m: Nonnegative = 1500.0
    input_loss_dB: Nonnegative = 1.5
    output_loss_dB: Nonnegative = 1.5
    input_reflectivity: Reflectivity = 0.0001
    output_reflectivity: Reflectivity = 0.0001

    @model_validator(mode="after")
    def active_inside_core(self):
        if self.active_thickness_um > self.core_thickness_um:
            raise ValueError("active_thickness_um must fit inside core_thickness_um")
        return self


class Material(Model):
    # Effective InGaAsP active region on an InP platform, not bulk-InP gain.
    differential_gain_m2: Positive = 2.5e-20
    transparency_density_m3: Positive = 1.5e24
    recombination_A_per_s: Positive = 1.0e8
    recombination_B_m3_per_s: Nonnegative = 1.0e-16
    recombination_C_m6_per_s: Nonnegative = 3.0e-41
    gain_peak_nm: Positive = 1550.0
    gain_fwhm_nm: Positive = 70.0
    gain_compression_per_W: Nonnegative = 5.0
    spontaneous_emission_factor: Annotated[float, Field(ge=1)] = 2.0
    linewidth_enhancement_factor: Nonnegative = 5.0
    reference_temperature_K: Positive = 300.0
    transparency_temperature_scale_K: Positive = 100.0
    gain_peak_shift_nm_per_K: Nonnegative = 0.4


class Source(Model):
    wavelength_nm: Positive = 1550.0
    input_power_mW: Positive = 1.0


class Thermal(Model):
    enabled: bool = True
    ambient_K: Positive = 300.0
    resistance_K_per_W: Nonnegative = 30.0
    junction_voltage_V: Positive = 1.3


class Mode(Model):
    enabled: bool = True
    core_index: Positive = 3.4
    cladding_index: Positive = 3.17
    x_span_um: Positive = 8.0
    y_span_um: Positive = 4.0
    nx: Annotated[int, Field(ge=21, le=501)] = 121
    ny: Annotated[int, Field(ge=21, le=501)] = 101
    # Used only if enabled=false; can be replaced by a vector solver/measurement.
    confinement_factor: Fraction = 0.25
    effective_area_um2: Positive = 1.0


class Numerics(Model):
    z_cells: Annotated[int, Field(ge=4, le=1000)] = 64
    ase_bins: Annotated[int, Field(ge=5, le=501)] = 41
    ase_bandwidth_nm: Positive = 140.0
    include_ase: bool = True
    max_iterations: Annotated[int, Field(ge=10, le=10000)] = 1500
    relative_tolerance: Annotated[float, Field(gt=0, le=0.01)] = 1.0e-6
    relaxation: Annotated[float, Field(gt=0, le=0.5)] = 0.15
    osnr_bandwidth_nm: Positive = 0.1


class Transient(Model):
    enabled: bool = True
    initial_current_mA: Nonnegative = 125.0
    step_time_ns: Positive = 0.5
    duration_ns: Positive = 5.0
    samples: Annotated[int, Field(ge=50, le=10000)] = 501

    @model_validator(mode="after")
    def step_in_window(self):
        if self.step_time_ns >= self.duration_ns:
            raise ValueError("step_time_ns must be less than duration_ns")
        return self


class Microcomb(Model):
    enabled: bool = True
    link_loss_dB: Nonnegative = 2.0
    radius_um: Positive = 100.0
    group_index: Positive = 1.9
    effective_index: Positive = 1.9
    effective_area_um2: Positive = 0.8
    n2_m2_per_W: Positive = 2.4e-19
    intrinsic_Q: Positive = 2.0e6
    coupling_Q: Positive = 2.0e6
    D2_MHz: float = 2.0
    D3_kHz: float = 0.0
    detuning_start: float = -2.0
    detuning_end: float = 3.0
    modes: Annotated[int, Field(ge=32, le=2048)] = 256
    time_step: Positive = 0.002
    scan_time: Nonnegative = 60.0
    hold_time: Positive = 40.0
    record_every: Annotated[int, Field(ge=1)] = 100
    seed: Annotated[int, Field(ge=0)] = 7
    field_noise_per_sqrt_tau: Nonnegative = 1.0e-5

    @model_validator(mode="after")
    def reasonable_grid(self):
        if self.modes & (self.modes - 1):
            raise ValueError("microcomb.modes must be a power of two")
        if (self.scan_time + self.hold_time) / self.time_step > 2_000_000:
            raise ValueError("LLE exceeds 2 million steps; shorten time or increase time_step")
        if self.time_step > 0.05:
            raise ValueError("microcomb.time_step must be <= 0.05")
        return self


class Layout(Model):
    enabled: bool = True
    taper_length_um: Positive = 150.0
    port_width_um: Positive = 0.8
    pad_size_um: Positive = 80.0
    pad_offset_um: Positive = 120.0
    bus_width_um: Positive = 1.0
    ring_width_um: Positive = 1.5
    ring_gap_um: Positive = 0.4


class Sweeps(Model):
    enabled: bool = True
    current_mA: Annotated[list[Nonnegative], Field(min_length=1, max_length=100)] = [50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 350.0]
    input_power_mW: Annotated[list[Positive], Field(min_length=1, max_length=100)] = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]


class LumericalMode(Model):
    trial_modes: Annotated[int, Field(ge=1, le=50)] = 6
    mesh_step_nm: Positive = 25.0
    wavelength_start_nm: Positive = 1500.0
    wavelength_stop_nm: Positive = 1600.0
    wavelength_points: Annotated[int, Field(ge=3, le=501)] = 21


class LumericalFDTD(Model):
    # Passive transition coupon, not a millimetre-long active-gain FDTD run.
    taper_length_um: Positive = 20.0
    buffer_um: Annotated[float, Field(ge=1)] = 2.0
    transverse_span_um: Positive = 4.0
    vertical_span_um: Positive = 3.0
    mesh_step_nm: Positive = 50.0
    simulation_time_fs: Positive = 5000.0
    wavelength_points: Annotated[int, Field(ge=3, le=501)] = 21
    max_estimated_cells: Annotated[int, Field(ge=1000)] = 20_000_000


class CircuitBinding(Model):
    element: str
    property: str
    quantity: Literal["source.frequency_Hz", "source.power_W", "device.current_A", "device.length_m", "device.width_m", "device.active_thickness_m", "device.active_volume_m3", "thermal.ambient_K", "material.linewidth_enhancement_factor"]


class CircuitProperty(Model):
    element: str
    property: str
    value: float | int | str | bool


class CircuitResult(Model):
    element: str
    result: str
    label: str


class LumericalCircuit(Model):
    # A licensed native SOA model/template is required for an actual active run.
    # Exact property/result names depend on the chosen SOA/CML and version.
    template_path: str | None = None
    inspect_elements: list[str] = ["pump_laser", "inp_soa", "bias_current", "output_osa"]
    bindings: list[CircuitBinding] = Field(default_factory=lambda: [
        CircuitBinding(element="pump_laser", property="frequency", quantity="source.frequency_Hz"),
        CircuitBinding(element="pump_laser", property="power", quantity="source.power_W"),
        CircuitBinding(element="bias_current", property="amplitude", quantity="device.current_A"),
    ])
    fixed_properties: list[CircuitProperty] = Field(default_factory=list)
    results: list[CircuitResult] = Field(default_factory=lambda: [
        CircuitResult(element="output_osa", result="spectrum", label="output_spectrum"),
    ])


class Lumerical(Model):
    hide_gui: bool = False
    core_material: str | None = None
    cladding_material: str | None = None
    mode: LumericalMode = Field(default_factory=LumericalMode)
    fdtd: LumericalFDTD = Field(default_factory=LumericalFDTD)
    interconnect: LumericalCircuit = Field(default_factory=LumericalCircuit)


class Config(Model):
    schema_version: Literal[1] = 1
    name: str = "Illustrative InP SOA pumping a SiN Kerr resonator"
    parameter_status: Literal["illustrative", "calibrated"] = "illustrative"
    calibration_notes: str = "No measured device data; see docs/references.md."
    device: Device = Field(default_factory=Device)
    material: Material = Field(default_factory=Material)
    source: Source = Field(default_factory=Source)
    thermal: Thermal = Field(default_factory=Thermal)
    mode: Mode = Field(default_factory=Mode)
    numerics: Numerics = Field(default_factory=Numerics)
    transient: Transient = Field(default_factory=Transient)
    microcomb: Microcomb = Field(default_factory=Microcomb)
    layout: Layout = Field(default_factory=Layout)
    sweeps: Sweeps = Field(default_factory=Sweeps)
    lumerical: Lumerical = Field(default_factory=Lumerical)

    @model_validator(mode="after")
    def physical_domains(self):
        if self.mode.core_index <= self.mode.cladding_index:
            raise ValueError("mode.core_index must exceed mode.cladding_index")
        if self.mode.x_span_um <= self.device.width_um or self.mode.y_span_um <= self.device.core_thickness_um:
            raise ValueError("mode simulation window must surround the core")
        if self.material.gain_peak_nm <= self.numerics.ase_bandwidth_nm / 2:
            raise ValueError("ASE wavelength range must be positive")
        if self.layout.pad_offset_um <= self.layout.pad_size_um / 2 + self.device.width_um:
            raise ValueError("layout.pad_offset_um must leave clearance for the optical ridge")
        if self.layout.ring_width_um >= self.microcomb.radius_um:
            raise ValueError("layout.ring_width_um must be smaller than the ring radius")
        if self.parameter_status == "calibrated" and self.calibration_notes.startswith("No measured"):
            raise ValueError("Provide calibration_notes identifying measured data for calibrated parameters")
        if self.lumerical.mode.wavelength_stop_nm <= self.lumerical.mode.wavelength_start_nm:
            raise ValueError("Lumerical stop wavelength must exceed start wavelength")
        if self.lumerical.fdtd.transverse_span_um <= max(self.device.width_um, self.layout.port_width_um):
            raise ValueError("FDTD transverse span must exceed both taper widths")
        if self.lumerical.fdtd.vertical_span_um <= self.device.core_thickness_um:
            raise ValueError("FDTD vertical span must exceed core thickness")
        labels = [r.label for r in self.lumerical.interconnect.results]
        if len(labels) != len(set(labels)) or any(not s.isidentifier() or not s.isascii() for s in labels):
            raise ValueError("INTERCONNECT result labels must be unique ASCII identifiers")
        return self


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def merge(base, update):
    result = deepcopy(base)
    for key, value in update.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result


def read_yaml(path: Path, chain=()):
    path = path.resolve()
    if path in chain:
        raise ValueError(f"Cyclic YAML extends: {path}")
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    parent = data.pop("extends", None)
    if parent is not None:
        if not isinstance(parent, str):
            raise ValueError("extends must name a relative YAML file")
        data = merge(read_yaml(path.parent / parent, (*chain, path)), data)
    return data


def load_config(path: str | Path, overrides=()) -> Config:
    data = read_yaml(Path(path))
    for override in overrides:
        key, sep, value = override.partition("=")
        parts = key.split(".")
        if not sep or any(not p for p in parts):
            raise ValueError("Overrides must have the form section.parameter=value")
        target = data
        for part in parts[:-1]:
            target = target.setdefault(part, {})
            if not isinstance(target, dict):
                raise ValueError(f"Not a configuration section: {key}")
        target[parts[-1]] = yaml.load(value, Loader=UniqueLoader)
    return Config.model_validate(data)
