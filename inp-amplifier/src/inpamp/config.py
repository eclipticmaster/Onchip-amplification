"""Native Lumerical inputs and SI unit conversions; no physics simulation."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Positive = Annotated[float, Field(gt=0)]
Nonnegative = Annotated[float, Field(ge=0)]
Name = Annotated[str, Field(min_length=1)]
NativeValue = float | int | str | bool
Solver = Literal["mode", "fdtd", "interconnect"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class Device(Model):
    length_um: Positive = 1000.0
    width_um: Positive = 2.0
    core_thickness_um: Positive = 0.4
    active_thickness_um: Positive = 0.12
    current_mA: Nonnegative = 250.0

    @model_validator(mode="after")
    def active_inside_core(self):
        if self.active_thickness_um > self.core_thickness_um:
            raise ValueError("active_thickness_um must fit inside core_thickness_um")
        return self


class Source(Model):
    wavelength_nm: Positive = 1550.0
    input_power_mW: Positive = 1.0


class Thermal(Model):
    # An input to a native model when bound; no Python heating calculation.
    ambient_K: Positive = 300.0


class Mode(Model):
    core_index: Positive = 3.4
    cladding_index: Positive = 3.17
    x_span_um: Positive = 8.0
    y_span_um: Positive = 4.0


class LumericalMode(Model):
    trial_modes: Annotated[int, Field(ge=1, le=50)] = 6
    mesh_step_nm: Positive = 25.0
    wavelength_start_nm: Positive = 1500.0
    wavelength_stop_nm: Positive = 1600.0
    wavelength_points: Annotated[int, Field(ge=3, le=501)] = 21


class LumericalFDTD(Model):
    taper_length_um: Positive = 20.0
    input_width_um: Positive = 0.8
    buffer_um: Annotated[float, Field(ge=1)] = 2.0
    transverse_span_um: Positive = 4.0
    vertical_span_um: Positive = 3.0
    mesh_step_nm: Positive = 50.0
    simulation_time_fs: Positive = 5000.0
    wavelength_points: Annotated[int, Field(ge=3, le=501)] = 21
    max_estimated_cells: Annotated[int, Field(ge=1000)] = 20_000_000


class CircuitBinding(Model):
    element: Name
    property: Name
    quantity: Name


class CircuitProperty(Model):
    element: Name
    property: Name
    value: NativeValue


class CircuitResult(Model):
    element: Name
    result: Name
    label: Name


class LumericalCircuit(Model):
    template_path: str | None = None
    inspect_elements: list[Name] = ["pump_laser", "inp_soa", "bias_current", "output_osa"]
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


class Sweep(Model):
    name: Name
    solver: Solver
    parameter: Name
    values: Annotated[list[float], Field(min_length=1, max_length=100)]


class Config(Model):
    schema_version: Literal[2] = 2
    name: str = "InP pump amplifier - Lumerical only"
    parameter_status: Literal["illustrative", "calibrated"] = "illustrative"
    calibration_notes: str = "No measured device data; calibrate the native SOA/CML."
    device: Device = Field(default_factory=Device)
    source: Source = Field(default_factory=Source)
    thermal: Thermal = Field(default_factory=Thermal)
    mode: Mode = Field(default_factory=Mode)
    parameters: dict[str, NativeValue] = Field(default_factory=dict)
    sweeps: list[Sweep] = Field(default_factory=list)
    lumerical: Lumerical = Field(default_factory=Lumerical)

    @model_validator(mode="after")
    def physical_domains(self):
        if self.mode.core_index <= self.mode.cladding_index:
            raise ValueError("mode.core_index must exceed mode.cladding_index")
        if self.mode.x_span_um <= self.device.width_um or self.mode.y_span_um <= self.device.core_thickness_um:
            raise ValueError("MODE window must surround the core")
        if self.lumerical.mode.wavelength_stop_nm <= self.lumerical.mode.wavelength_start_nm:
            raise ValueError("Lumerical stop wavelength must exceed start wavelength")
        if self.lumerical.fdtd.transverse_span_um <= max(self.device.width_um, self.lumerical.fdtd.input_width_um):
            raise ValueError("FDTD transverse span must exceed both taper widths")
        if self.lumerical.fdtd.vertical_span_um <= self.device.core_thickness_um:
            raise ValueError("FDTD vertical span must exceed core thickness")
        if any(not key.isidentifier() or not key.isascii() for key in self.parameters):
            raise ValueError("Native parameter keys must be ASCII identifiers")
        available = quantities(self)
        circuit = self.lumerical.interconnect
        for binding in circuit.bindings:
            if binding.quantity not in available:
                raise ValueError(f"Unknown native binding quantity: {binding.quantity}")
        targets = [(b.element, b.property) for b in [*circuit.bindings, *circuit.fixed_properties]]
        if len(set(targets)) != len(targets):
            raise ValueError("Each native element/property may be set only once")
        labels = [r.label for r in circuit.results]
        if len(labels) != len(set(labels)) or any(not s.isidentifier() or not s.isascii() for s in labels):
            raise ValueError("INTERCONNECT result labels must be unique ASCII identifiers")
        if len({s.name for s in self.sweeps}) != len(self.sweeps):
            raise ValueError("Native sweep names must be unique")
        for sweep in self.sweeps:
            if not sweep.name.isidentifier() or not sweep.name.isascii():
                raise ValueError("Sweep names must be ASCII identifiers")
        return self


def quantities(c: Config):
    """Dimension/unit conversion only. Gain, carriers and propagation stay native."""
    return {"source.frequency_Hz": 299792458 / (c.source.wavelength_nm * 1e-9),
            "source.power_W": c.source.input_power_mW * 1e-3,
            "device.current_A": c.device.current_mA * 1e-3,
            "device.length_m": c.device.length_um * 1e-6,
            "device.width_m": c.device.width_um * 1e-6,
            "device.active_thickness_m": c.device.active_thickness_um * 1e-6,
            "device.active_volume_m3": c.device.length_um * c.device.width_um * c.device.active_thickness_um * 1e-18,
            "thermal.ambient_K": c.thermal.ambient_K,
            **{f"parameters.{k}": v for k, v in c.parameters.items()}}


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ValueError("YAML keys must be strings")
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


def with_override(c: Config, parameter, value):
    data = c.model_dump()
    parts = parameter.split(".")
    target = data
    for part in parts[:-1]:
        if not isinstance(target, dict) or part not in target:
            raise ValueError(f"Unknown sweep parameter: {parameter}")
        target = target[part]
    if not isinstance(target, dict) or parts[-1] not in target:
        raise ValueError(f"Unknown sweep parameter: {parameter}")
    target[parts[-1]] = value
    return Config.model_validate(data)


def load_config(path: str | Path, overrides=()) -> Config:
    data = read_yaml(Path(path))
    if data.get("schema_version") == 1:
        raise ValueError("Schema v1 included retired Python simulation settings. Use the v2 examples; simulation now runs only in Lumerical.")
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
