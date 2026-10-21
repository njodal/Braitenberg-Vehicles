"""Vehicle definition files: body, sensors, actuators and units (specs/vehicle-definition.md)."""

from __future__ import annotations

import itertools
import math
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from braitenberg.yamlfile import Parser, read_yaml

# Sensor types are stimulus names, checked against the world by the scenario loader.
ACTUATOR_TYPES = ("motor",)
UNIT_TYPES = ("threshold",)
CONNECTION_TYPES = ("excitatory", "inhibitory")
LEARNING_TYPES = ("mnemotrix",)
# Sensor response types: required fields, and optional fields with their defaults.
RESPONSE_FIELDS = {
    "linear": (set(), {}),
    "peak": ({"at", "width"}, {"height": 1.0}),
    "step": ({"at"}, {"height": 1.0}),
}
ACTIVE_STRENGTH = 0.7  # a connection is active when its strength is above this
NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")
# An input's `from`: a name, or a camera or array with indices, e.g. retina[0, 3] or lump[i-1].
FROM_PATTERN = re.compile(r"([a-z][a-z0-9_]*)\s*(?:\[([^\]]*)\])?\Z")
INDEX_EXPRESSION = re.compile(r"([ij])\s*(?:([+-])\s*(\d+))?\Z")
INDEX_RANGE = re.compile(r"(\d+)\s*:\s*(\d+)\Z")


def element_name(name: str, index: tuple[int, ...]) -> str:
    """The signal name of a pixel or array element, e.g. retina[0, 3] or front[2]."""
    return f"{name}[{', '.join(str(k) for k in index)}]"


@dataclass
class Learning:
    """How a connection's strength changes while the vehicle runs (Vehicle 7)."""

    type: str = "mnemotrix"
    learn: float = 0.0    # per second, while the source fires and the target's other inputs fire it
    forget: float = 0.0   # per second, while the source fires and they do not


@dataclass
class Connection:
    source: str             # name of a sensor or unit
    sign: int = 1           # +1 excitatory, -1 inhibitory
    strength: float = 1.0   # from 0 to 1; the connection is active above ACTIVE_STRENGTH
    learning: Learning | None = None   # for a learning connection, strength is where it starts
    label: str = ""         # `from` as written, e.g. lump[i-1]; empty when it is just the source

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
    height: float = 0.0     # as cameras see it; the loader defaults it to size / 2


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

    def outputs(self, readings: np.ndarray) -> np.ndarray:
        """`output` for an array of readings, such as a camera's pixels."""
        if self.type == "peak":
            return self.height * np.exp(-0.5 * ((readings - self.at) / self.width) ** 2)
        if self.type == "step":
            return np.where(readings >= self.at, self.height, 0.0)
        return readings


@dataclass
class Camera:
    """A sensor's camera: a matrix of pixels looking out from the body (specs/camera.md)."""

    columns: int
    rows: int
    vertical_field_of_view: float   # degrees
    direction: float = 0.0          # degrees from the heading, + to the left
    tilt: float = 0.0               # degrees, + up
    height: float = 0.0             # above the ground; the loader defaults it to the vehicle's height
    range: float = math.inf
    samples: int = 3                # samples x samples lines of sight per pixel

    @property
    def shape(self) -> tuple[int, int]:
        return self.rows, self.columns


@dataclass
class SensorDef:
    name: str
    type: str     # the stimulus it reads
    position: tuple[float, float]
    response: Response = field(default_factory=Response)
    field_of_view: float = 360.0   # degrees, centered on the vehicle's heading
    camera: Camera | None = None   # a camera's output is a matrix of pixels, not one value

    def pixels(self) -> list[str]:
        """The signal names of a camera's pixels, row by row."""
        return [element_name(self.name, (r, c)) for r in range(self.camera.rows)
                for c in range(self.camera.columns)]


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
    array: str | None = None             # the array this unit is an element of (Vehicle 8)
    index: tuple[int, ...] | None = None  # its index in that array


ENERGY_SENSOR = "energy"   # a sensor type the vehicle reads from itself, not from the world


@dataclass
class Energy:
    """An internal store that movement uses up and a stimulus recharges (see '5. Energy')."""

    initial: float
    max: float
    consumption: float          # per unit of distance traveled
    charge_from: str | None = None
    charge_gain: float = 1.0    # per second, per unit of charge_from at the body center
    basal: float = 0.0          # per second, for being alive, even standing still


@dataclass
class VehicleDefinition:
    path: Path
    general: General
    sensors: list[SensorDef]
    actuators: list[ActuatorDef]
    units: list[UnitDef] = field(default_factory=list)   # arrays expanded into their elements
    energy: Energy | None = None
    appearance: dict[str, float] = field(default_factory=dict)  # brightness for other cameras
    arrays: dict[str, tuple[int, ...]] = field(default_factory=dict)  # array name -> shape


def load_definition(path: str | Path) -> VehicleDefinition:
    path = Path(path).resolve()
    return _DefinitionParser(path).definition(read_yaml(path))


class _DefinitionParser(Parser):
    def definition(self, data) -> VehicleDefinition:
        data = self.mapping(data, "", {"general", "sensors", "actuators"},
                            {"units", "energy", "appearance"})
        general = self.general(data["general"])
        names: dict[str, str] = {}  # name -> key where it was defined
        sensors = [self.sensor(body, key, names, general)
                   for key, body in self.items(data["sensors"], "sensors", "sensor")]
        actuator_items = self.items(data["actuators"], "actuators", "actuator")
        actuators = [self.actuator(body, key, names) for key, body in actuator_items]
        unit_items = self.items(data.get("units"), "units", "unit")
        units = [self.unit(body, key, names) for key, body in unit_items]
        if not actuators:
            raise self.error("actuators", "a vehicle needs at least one actuator")
        # Names that take indices: cameras (rows, columns) and arrays of units.
        self.shapes = {s.name: s.camera.shape for s in sensors if s.camera}
        self.shapes.update({u.name: u.index for u in units if u.array})
        self.kinds = {**{s.name: "sensor" for s in sensors}, **{a.name: "actuator" for a in actuators},
                      **{u.name: "unit" for u in units}}
        arrays = {u.name: u.index for u in units if u.array}
        for (key, _), a in zip(actuator_items, actuators):
            a.inputs = self.resolve(a.inputs, f"{key}.inputs", None, a.name, "actuators")
        units = [element for (key, _), u in zip(unit_items, units)
                 for element in self.expand(u, key)]
        energy = self.energy(data["energy"]) if "energy" in data else None
        if energy is None:
            for i, s in enumerate(sensors):
                if s.type == ENERGY_SENSOR:
                    raise self.error(f"sensors[{i}].sensor.type",
                                     "an energy sensor needs an energy section")
        appearance = self.appearance(data["appearance"]) if "appearance" in data else {}
        return VehicleDefinition(self.path, general, sensors, actuators, units, energy,
                                 appearance, arrays)

    def appearance(self, data) -> dict[str, float]:
        if not isinstance(data, dict):
            raise self.error("appearance", "must be a mapping")
        result = {}
        for name, value in data.items():
            result[str(name)] = self.number(value, f"appearance.{name}")
            if result[str(name)] < 0:
                raise self.error(f"appearance.{name}", "must not be negative")
        return result

    # --- arrays of units and indexed inputs (specs/vehicle-08.md, specs/camera.md) ---

    def expand(self, unit: UnitDef, key: str) -> list[UnitDef]:
        """A unit, or the elements of an array (whose `index` holds its shape until now)."""
        if not unit.array:
            unit.inputs = self.resolve(unit.inputs, f"{key}.inputs", None, unit.name, "units")
            return [unit]
        shape = unit.index
        elements = []
        for index in itertools.product(*(range(n) for n in shape)):
            env = dict(zip("ij", index))
            name = element_name(unit.name, index)
            elements.append(replace(unit, name=name, index=index,
                                    inputs=self.resolve(unit.inputs, f"{key}.inputs", env, name,
                                                        "units")))
        return elements

    def resolve(self, inputs: list[Connection], key: str, env: dict | None, part: str,
                section: str) -> list[Connection]:
        """Inputs with their `from` turned into signal names, one input per pixel or element."""
        resolved = []
        for j, c in enumerate(inputs):
            prefix = f"{key}[{j}].input"
            fkey = f"{prefix}.from"
            m = FROM_PATTERN.match(c.source)
            if not m:
                raise self.error(fkey, f"'{c.source}' must be a name, or a name with indices "
                                       "such as retina[0, 3]")
            base, indices = m.group(1), m.group(2)
            kind = self.kinds.get(base)
            if kind == "actuator":
                raise self.error(fkey, f"'{c.source}' is an actuator; inputs must be sensors or units")
            if kind is None:
                raise self.error(fkey, f"'{c.source}' is not a sensor or unit of this vehicle")
            shape = self.shapes.get(base)
            if indices is None:
                if shape:
                    what = "a camera" if kind == "sensor" else "an array of units"
                    raise self.error(fkey, f"'{base}' is {what}; name its "
                                           f"{'pixels' if kind == 'sensor' else 'elements'} "
                                           f"with indices, such as {base}[{', '.join('0' * len(shape))}]")
                sources = [base]
            else:
                if not shape:
                    raise self.error(fkey, f"'{base}' is not a camera or an array of units, "
                                           "so it cannot be indexed")
                tokens = [t.strip() for t in indices.split(",")]
                if len(tokens) != len(shape):
                    raise self.error(fkey, f"'{base}' needs {len(shape)} "
                                           f"{'index' if len(shape) == 1 else 'indices'}")
                choices = [self.index(t, n, env, fkey, base) for t, n in zip(tokens, shape)]
                sources = [element_name(base, combo) for combo in itertools.product(*choices)]
            if c.learning is not None:
                if section == "actuators":
                    raise self.error(f"{prefix}.learning",
                                     "a learning connection must go into a unit, not an actuator")
                if kind != "unit":
                    raise self.error(fkey, f"'{c.source}' is a sensor; a learning connection "
                                           "must come from a unit")
                if part in sources:
                    raise self.error(fkey, "a unit cannot have a learning connection from itself")
            label = c.source if indices is not None else ""
            resolved += [replace(c, source=source, label=label) for source in sources]
        return resolved

    def index(self, token: str, size: int, env: dict | None, key: str, base: str) -> list[int]:
        """The indices one index of `from` stands for: none when an expression falls outside."""
        if token == ":":
            return list(range(size))
        if m := INDEX_RANGE.match(token):
            a, b = int(m.group(1)), int(m.group(2))
            if a >= b:
                raise self.error(key, f"the range {token} is empty")
            if b > size:
                raise self.error(key, f"the range {token} is outside '{base}' (0 to {size - 1})")
            return list(range(a, b))
        if re.fullmatch(r"-?\d+", token):
            value = int(token)
            if not 0 <= value < size:
                raise self.error(key, f"index {value} is outside '{base}' (0 to {size - 1})")
            return [value]
        if m := INDEX_EXPRESSION.match(token):
            var = m.group(1)
            if env is None:
                raise self.error(key, f"'{var}' can only be used in the inputs of an array")
            if var not in env:
                raise self.error(key, f"'{var}' is not an index of a one-dimensional array")
            value = env[var] + (int(m.group(3)) * (1 if m.group(2) == "+" else -1)
                                if m.group(2) else 0)
            return [value] if 0 <= value < size else []
        raise self.error(key, f"index '{token}' must be i, i+k, i-k, j, j+k, j-k, an integer, "
                              "a:b or :")

    def energy(self, data) -> Energy:
        data = self.mapping(data, "energy", {"initial", "max", "consumption"},
                            {"charge_from", "charge_gain", "basal"})
        e = Energy(self.number(data["initial"], "energy.initial"),
                   self.number(data["max"], "energy.max", positive=True),
                   self.number(data["consumption"], "energy.consumption"),
                   self.string(data["charge_from"], "energy.charge_from")
                   if "charge_from" in data else None,
                   self.number(data.get("charge_gain", 1.0), "energy.charge_gain"),
                   self.number(data.get("basal", 0.0), "energy.basal"))
        if not 0 <= e.initial <= e.max:
            raise self.error("energy.initial", "must be between 0 and max")
        for key in ("consumption", "charge_gain", "basal"):
            if getattr(e, key) < 0:
                raise self.error(f"energy.{key}", "must not be negative")
        return e

    def general(self, data) -> General:
        data = self.mapping(data, "general", {"type", "name", "size"},
                            {"description", "noise_std", "height"})
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
        g.height = (self.number(data["height"], "general.height", positive=True)
                    if "height" in data else g.size / 2)
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
        item = self.mapping(item, key, {"from"}, {"type", "strength", "learning"})
        kind = self.kind(item.get("type", "excitatory"), f"{key}.type", CONNECTION_TYPES)
        strength = self.number(item.get("strength", 1.0), f"{key}.strength")
        if not 0 <= strength <= 1:
            raise self.error(f"{key}.strength", "must be between 0 and 1")
        return Connection(self.string(item["from"], f"{key}.from"),
                          sign=1 if kind == "excitatory" else -1, strength=strength,
                          learning=self.learning(item["learning"], f"{key}.learning")
                          if "learning" in item else None)

    def learning(self, data, key: str) -> Learning:
        if isinstance(data, dict) and "type" in data:
            self.kind(data["type"], f"{key}.type", LEARNING_TYPES)
        data = self.mapping(data, key, {"type", "learn"}, {"forget"})
        learning = Learning(data["type"], self.number(data["learn"], f"{key}.learn"),
                            self.number(data.get("forget", 0.0), f"{key}.forget"))
        for rate in ("learn", "forget"):
            if getattr(learning, rate) < 0:
                raise self.error(f"{key}.{rate}", "must not be negative")
        return learning

    def sensor(self, data, key: str, names, general: General) -> SensorDef:
        data = self.mapping(data, key, {"name", "type", "position"},
                            {"response", "field_of_view", "camera"})
        sensor = SensorDef(self.name(data, key, names),
                           self.string(data["type"], f"{key}.type"),
                           self.body_position(data["position"], f"{key}.position"),
                           self.response(data["response"], f"{key}.response")
                           if "response" in data else Response())
        if "field_of_view" in data:
            fov_key = f"{key}.field_of_view"
            if sensor.type == ENERGY_SENSOR:
                raise self.error(fov_key, "an energy sensor has no field of view")
            sensor.field_of_view = self.number(data["field_of_view"], fov_key)
            if not 0 < sensor.field_of_view <= 360:
                raise self.error(fov_key, "must be greater than 0 and at most 360")
        if "camera" in data:
            if sensor.type == ENERGY_SENSOR:
                raise self.error(f"{key}.camera", "an energy sensor cannot be a camera")
            if "field_of_view" not in data:
                raise self.error(f"{key}.field_of_view", "a camera needs a field_of_view")
            sensor.camera = self.camera(data["camera"], f"{key}.camera", general)
        return sensor

    def camera(self, data, key: str, general: General) -> Camera:
        data = self.mapping(data, key, {"columns", "rows", "vertical_field_of_view"},
                            {"direction", "tilt", "height", "range", "samples"})
        counts = {}
        for k in ("columns", "rows", "samples"):
            counts[k] = self.integer(data.get(k, 3), f"{key}.{k}")
            if counts[k] <= 0:
                raise self.error(f"{key}.{k}", "must be a positive integer")
        cam = Camera(counts["columns"], counts["rows"],
                     self.number(data["vertical_field_of_view"], f"{key}.vertical_field_of_view"),
                     self.number(data.get("direction", 0.0), f"{key}.direction"),
                     self.number(data.get("tilt", 0.0), f"{key}.tilt"),
                     self.number(data["height"], f"{key}.height", positive=True)
                     if "height" in data else general.height,
                     self.number(data["range"], f"{key}.range", positive=True)
                     if "range" in data else math.inf,
                     counts["samples"])
        if not 0 < cam.vertical_field_of_view <= 180:
            raise self.error(f"{key}.vertical_field_of_view", "must be greater than 0 and at most 180")
        if not -180 <= cam.direction <= 180:
            raise self.error(f"{key}.direction", "must be from -180 to 180")
        if abs(cam.tilt) + cam.vertical_field_of_view / 2 > 90:
            raise self.error(f"{key}.tilt", "the view must stay within straight up and straight "
                                            "down: abs(tilt) + vertical_field_of_view / 2 <= 90")
        return cam

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
        """A unit as written; an array keeps its shape in `index` until it is expanded."""
        data = self.mapping(data, key, {"name", "type", "threshold", "inputs"},
                            {"position", "delay", "array"})
        unit = UnitDef(self.name(data, key, names),
                       self.kind(data["type"], f"{key}.type", UNIT_TYPES),
                       self.number(data["threshold"], f"{key}.threshold"),
                       self.connections(data["inputs"], f"{key}.inputs", self.connection),
                       self.body_position(data["position"], f"{key}.position")
                       if "position" in data else None,
                       self.number(data.get("delay", 0.05), f"{key}.delay", positive=True))
        if "array" in data:
            unit.array = unit.name
            unit.index = self.shape(data["array"], f"{key}.array")
        return unit

    def shape(self, value, key: str) -> tuple[int, ...]:
        dims = value if isinstance(value, list) else [value]
        if not 1 <= len(dims) <= 2 or any(isinstance(n, bool) or not isinstance(n, int) or n <= 0
                                          for n in dims):
            raise self.error(key, "must be a positive integer, or [rows, columns] of positive integers")
        return tuple(dims)
