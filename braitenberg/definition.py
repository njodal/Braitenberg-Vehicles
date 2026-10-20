"""Vehicle definition files: body, sensors, actuators and units (specs/vehicle-definition.md)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from braitenberg.yamlfile import Parser, read_yaml

# Sensor types are stimulus names, checked against the world by the scenario loader.
ACTUATOR_TYPES = ("motor",)
UNIT_TYPES = ("threshold",)
CONNECTION_TYPES = ("excitatory", "inhibitory")
# Sensor response types: required fields, and optional fields with their defaults.
RESPONSE_FIELDS = {
    "linear": (set(), {}),
    "peak": ({"at", "width"}, {"height": 1.0}),
    "step": ({"at"}, {"height": 1.0}),
}
ACTIVE_STRENGTH = 0.7  # a connection is active when its strength is above this
NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")


@dataclass
class Connection:
    source: str             # name of a sensor or unit
    sign: int = 1           # +1 excitatory, -1 inhibitory
    strength: float = 1.0   # from 0 to 1; the connection is active above ACTIVE_STRENGTH

    @property
    def active(self) -> bool:
        return self.strength > ACTIVE_STRENGTH

    @property
    def inhibitory(self) -> bool:
        return self.sign < 0


@dataclass
class General:
    type: str
    name: str
    size: float
    description: str = ""
    noise_std: float = 0.0


@dataclass
class Response:
    """How a sensor's output depends on its reading (see 'Responses' in the spec)."""

    type: str = "linear"
    at: float = 0.0
    width: float = 1.0
    height: float = 1.0

    def output(self, reading: float) -> float:
        if self.type == "peak":
            return self.height * math.exp(-0.5 * ((reading - self.at) / self.width) ** 2)
        if self.type == "step":
            return self.height if reading >= self.at else 0.0
        return reading


@dataclass
class SensorDef:
    name: str
    type: str     # the stimulus it reads
    position: tuple[float, float]
    response: Response = field(default_factory=Response)


@dataclass
class ActuatorDef:
    name: str
    type: str
    position: tuple[float, float]
    inputs: list[Connection]
    gain: float = 1.0
    base_speed: float = 0.0
    max_speed: float = 5.0


@dataclass
class UnitDef:
    name: str
    type: str
    threshold: float
    inputs: list[Connection]
    position: tuple[float, float] | None = None
    delay: float = 0.05     # seconds from activation to output


@dataclass
class VehicleDefinition:
    path: Path
    general: General
    sensors: list[SensorDef]
    actuators: list[ActuatorDef]
    units: list[UnitDef] = field(default_factory=list)


def load_definition(path: str | Path) -> VehicleDefinition:
    path = Path(path).resolve()
    return _DefinitionParser(path).definition(read_yaml(path))


class _DefinitionParser(Parser):
    def definition(self, data) -> VehicleDefinition:
        data = self.mapping(data, "", {"general", "sensors", "actuators"}, {"units"})
        general = self.general(data["general"])
        names: dict[str, str] = {}  # name -> key where it was defined
        sensors = [self.sensor(body, key, names)
                   for key, body in self.items(data["sensors"], "sensors", "sensor")]
        actuators = [self.actuator(body, key, names)
                     for key, body in self.items(data["actuators"], "actuators", "actuator")]
        units = [self.unit(body, key, names)
                 for key, body in self.items(data.get("units"), "units", "unit")]
        if not actuators:
            raise self.error("actuators", "a vehicle needs at least one actuator")
        self.check_inputs(names, actuators, units)
        return VehicleDefinition(self.path, general, sensors, actuators, units)

    def general(self, data) -> General:
        data = self.mapping(data, "general", {"type", "name", "size"}, {"description", "noise_std"})
        g = General(
            type=self.string(str(data["type"]) if isinstance(data["type"], int) else data["type"],
                             "general.type"),
            name=self.string(data["name"], "general.name"),
            size=self.number(data["size"], "general.size", positive=True),
            description=self.string(data.get("description", ""), "general.description"),
            noise_std=self.number(data.get("noise_std", 0.0), "general.noise_std"),
        )
        if g.noise_std < 0:
            raise self.error("general.noise_std", "must not be negative")
        return g

    def name(self, data, key: str, names: dict[str, str]) -> str:
        name = self.string(data["name"], f"{key}.name")
        if not NAME_PATTERN.match(name):
            raise self.error(f"{key}.name",
                             f"'{name}' must be lowercase letters, digits and _, starting with a letter")
        if name in names:
            raise self.error(f"{key}.name", f"'{name}' is already used by {names[name]}")
        names[name] = f"{key}.name"
        return name

    def body_position(self, value, key: str) -> tuple[float, float]:
        x, y = self.pair(value, key)
        if not (-1 <= x <= 1 and -1 <= y <= 1):
            raise self.error(key, f"[{x:g}, {y:g}] is outside the body ([-1, 1] on both axes)")
        return x, y

    def kind(self, value, key: str, allowed: tuple[str, ...]) -> str:
        kind = self.string(value, key)
        if kind not in allowed:
            raise self.error(key, f"unknown type '{kind}' (expected {', '.join(allowed)})")
        return kind

    def connections(self, value, key: str, parse) -> list[Connection]:
        """A list of inputs, each wrapped in `- input:` and read by `parse(body, key)`."""
        if value is None:
            raise self.error(key, "must be a list")
        return [parse(body, ikey) for ikey, body in self.items(value, key, "input")]

    def connection(self, item, key: str) -> Connection:
        item = self.mapping(item, key, {"from"}, {"type", "strength"})
        kind = self.kind(item.get("type", "excitatory"), f"{key}.type", CONNECTION_TYPES)
        strength = self.number(item.get("strength", 1.0), f"{key}.strength")
        if not 0 <= strength <= 1:
            raise self.error(f"{key}.strength", "must be between 0 and 1")
        return Connection(self.string(item["from"], f"{key}.from"),
                          sign=1 if kind == "excitatory" else -1, strength=strength)

    def sensor(self, data, key: str, names) -> SensorDef:
        data = self.mapping(data, key, {"name", "type", "position"}, {"response"})
        return SensorDef(self.name(data, key, names),
                         self.string(data["type"], f"{key}.type"),
                         self.body_position(data["position"], f"{key}.position"),
                         self.response(data["response"], f"{key}.response")
                         if "response" in data else Response())

    def response(self, data, key: str) -> Response:
        if not isinstance(data, dict):
            raise self.error(key, "must be a mapping")
        if "type" not in data:
            raise self.error(f"{key}.type", "missing required key")
        kind = self.kind(data["type"], f"{key}.type", tuple(RESPONSE_FIELDS))
        required, optional = RESPONSE_FIELDS[kind]
        data = self.mapping(data, key, {"type", *required}, set(optional))
        values = {**optional, **{k: self.number(data[k], f"{key}.{k}")
                                 for k in data if k != "type"}}
        if "width" in values and values["width"] <= 0:
            raise self.error(f"{key}.width", "must be positive")
        return Response(kind, **values)

    def actuator(self, data, key: str, names) -> ActuatorDef:
        data = self.mapping(data, key, {"name", "type", "position", "inputs"},
                            {"gain", "base_speed", "max_speed"})
        a = ActuatorDef(self.name(data, key, names),
                        self.kind(data["type"], f"{key}.type", ACTUATOR_TYPES),
                        self.body_position(data["position"], f"{key}.position"),
                        self.connections(data["inputs"], f"{key}.inputs", self.connection))
        for param in ("gain", "base_speed", "max_speed"):
            if param in data:
                setattr(a, param, self.number(data[param], f"{key}.{param}"))
        if a.max_speed < 0 or a.base_speed < 0:
            raise self.error(key, "base_speed and max_speed must not be negative")
        return a

    def unit(self, data, key: str, names) -> UnitDef:
        data = self.mapping(data, key, {"name", "type", "threshold", "inputs"},
                            {"position", "delay"})
        return UnitDef(self.name(data, key, names),
                       self.kind(data["type"], f"{key}.type", UNIT_TYPES),
                       self.number(data["threshold"], f"{key}.threshold"),
                       self.connections(data["inputs"], f"{key}.inputs", self.connection),
                       self.body_position(data["position"], f"{key}.position")
                       if "position" in data else None,
                       self.number(data.get("delay", 0.05), f"{key}.delay", positive=True))

    def check_inputs(self, names, actuators, units) -> None:
        actuator_names = {a.name for a in actuators}
        for section, wrapper, parts in (("actuators", "actuator", actuators), ("units", "unit", units)):
            for i, part in enumerate(parts):
                for j, c in enumerate(part.inputs):
                    key = f"{section}[{i}].{wrapper}.inputs[{j}].input.from"
                    if c.source in actuator_names:
                        raise self.error(key, f"'{c.source}' is an actuator; inputs must be sensors or units")
                    if c.source not in names:
                        raise self.error(key, f"'{c.source}' is not a sensor or unit of this vehicle")
