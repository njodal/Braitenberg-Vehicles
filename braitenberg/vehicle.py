"""A vehicle built from a definition file (specs/vehicle-definition.md).

Vehicles know nothing about the world: the simulation reads the stimulus at each
sensor, hands the readings to the vehicle and applies the arena's edge rule
after the vehicle moves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from braitenberg.definition import ACTIVE_STRENGTH, ENERGY_SENSOR, VehicleDefinition, element_name


@dataclass
class Part:
    """A sensor, actuator or unit, in body coordinates (+y forward, [-1, 1]).

    A camera or an array of units is one part, whose value and level are lists (a list of rows
    for a camera or a two-dimensional array), one entry per pixel or element.
    """

    kind: str     # sensor | camera | motor | unit | array
    name: str
    position: tuple[float, float]
    label: str
    value: float | list
    level: float | list  # activity in [0, 1]
    threshold: float | None = None  # units and arrays only
    shape: tuple[int, ...] | None = None  # cameras and arrays only


@dataclass
class Wire:
    source: str   # Part names
    target: str
    sign: int     # +1 excitatory, -1 inhibitory
    level: float
    active: bool = True  # connections with strength 0.7 or less carry no signal
    strength: float = 1.0
    learning: str | None = None  # the learning type, for a connection that learns (Vehicle 7)
    source_index: tuple[int, ...] | None = None  # the pixel or element, from a camera or an array
    target_index: tuple[int, ...] | None = None  # the element, into an array
    label: str = ""   # the input's `from` as written, when it has indices, e.g. lump[i-1]


@dataclass
class Diagram:
    """A vehicle's structure and live signals, for the diagram panel (specs/vehicle-diagram.md)."""

    title: str
    subtitle: str
    parts: list[Part]
    wires: list[Wire]
    params: dict[str, str]


def clamp01(x: float) -> float:
    return min(max(x, 0.0), 1.0)


class Vehicle:
    def __init__(self, definition: VehicleDefinition, x: float, y: float, heading: float,
                 label: str = "", dt: float = 0.05):
        self.definition = definition
        self.label = label or definition.general.name
        self.x = x
        self.y = y
        self.heading = heading  # radians, 0 = +x, counterclockwise; body +y points this way
        self.half_size = definition.general.size / 2
        self.sensor_readings = {s.name: 0.0 for s in definition.sensors}  # stimulus at the sensor
        # Output after response: one per sensor, or one per pixel of a camera.
        self.sensor_values = {name: 0.0 for s in definition.sensors for name in self.outputs_of(s)}
        self.unit_outputs = {u.name: 0.0 for u in definition.units}
        self.motor_speeds = {a.name: 0.0 for a in definition.actuators}
        self.speed = 0.0        # forward speed
        self.turn_rate = 0.0
        self.energy = definition.energy.initial if definition.energy else None
        self.dt = dt
        # Current strength of each learning connection, by (unit name, input index). Each vehicle
        # starts from its definition's strengths and learns on its own; the definition never changes.
        self.strengths = {(u.name, j): c.strength for u in definition.units
                          for j, c in enumerate(u.inputs) if c.learning}
        self.fixed_strengths = {(p.name, j): c.strength
                                for p in [*definition.units, *definition.actuators]
                                for j, c in enumerate(p.inputs) if not c.learning}
        # A unit's delay and simultaneity window, in steps (see 'Signal flow' in the spec).
        self.unit_steps = {u.name: max(1, round(u.delay / dt)) for u in definition.units}
        self.setup_signals()

    @staticmethod
    def outputs_of(sensor) -> list[str]:
        return sensor.pixels() if sensor.camera else [sensor.name]

    def setup_signals(self) -> None:
        """Arrays that let `think` update hundreds of units at once (Vehicle 8)."""
        d = self.definition
        names = [*self.sensor_values, *self.unit_outputs]
        self.signal_index = {name: k for k, name in enumerate(names)}
        units = d.units
        self.unit_names = [u.name for u in units]
        steps = np.array([self.unit_steps[u.name] for u in units], dtype=int)
        self.steps = steps
        self.thresholds = np.array([u.threshold for u in units])
        # Activations on their way to becoming outputs: a unit's output is its activation
        # `steps` steps ago (zero before that).
        self.activations = np.zeros((int(steps.max(initial=0)) + 1, len(units)))
        # Recent values of every signal, for the simultaneity windows; -inf where none yet.
        self.window = int(steps.max(initial=1))
        self.history = np.full((self.window, len(names)), -np.inf)
        self.t = 0
        self.windows = sorted(set(steps.tolist()))   # distinct window lengths
        group = {n: g for g, n in enumerate(self.windows)}
        # Every unit input, in the order of the units and of their inputs, so that their sum
        # adds up in the same order as a sum over the inputs one by one.
        unit_of, signal_of, sign, group_of, first = [], [], [], [], []
        for k, u in enumerate(units):
            first.append(len(unit_of))
            for c in u.inputs:
                unit_of.append(k)
                signal_of.append(self.signal_index[c.source])
                sign.append(float(c.sign))
                group_of.append(group[steps[k]])
        self.input_unit = np.array(unit_of, dtype=int)
        self.input_signal = np.array(signal_of, dtype=int)
        self.input_sign = np.array(sign)
        self.input_group = np.array(group_of, dtype=int)
        self.input_first = first   # index of each unit's first input
        self.input_active = np.array([c.active for u in units for c in u.inputs], dtype=bool)
        # Learning inputs: (unit position, input index within the unit).
        self.learning_inputs = [(k, j) for k, u in enumerate(units)
                                for j, c in enumerate(u.inputs) if c.learning]
        self.references = self.signal_references()

    # --- geometry ---

    def body_to_world(self, bx: float, by: float) -> tuple[float, float]:
        """A point in body coordinates (+x right, +y forward) to arena coordinates."""
        c, s = math.cos(self.heading), math.sin(self.heading)
        # forward = (c, s), right = (s, -c)
        return (self.x + self.half_size * (by * c + bx * s),
                self.y + self.half_size * (by * s - bx * c))

    def sensor_points(self) -> list[tuple[str, str, float, float]]:
        """(sensor name, stimulus, x, y) for every sensor that reads the field of a stimulus."""
        return [(s.name, s.type, *self.body_to_world(*s.position)) for s in self.definition.sensors
                if s.type != ENERGY_SENSOR and not s.camera]

    def cameras(self) -> list[tuple]:
        """(sensor, x, y) for every camera, at its place in the arena."""
        return [(s, *self.body_to_world(*s.position)) for s in self.definition.sensors if s.camera]

    # --- signals ---

    def think(self, readings: dict) -> None:
        """Update units and motors from this step's sensor readings (see 'Signal flow').

        A camera's reading is a matrix with one value per pixel.
        """
        d = self.definition
        readings = dict(readings)
        for sensor in d.sensors:
            if sensor.type == ENERGY_SENSOR:
                readings[sensor.name] = self.energy
        self.sensor_readings = readings
        values = {}
        for sensor in d.sensors:
            if sensor.camera:
                pixels = sensor.response.outputs(np.asarray(readings[sensor.name], dtype=float))
                values.update(zip(sensor.pixels(), pixels.ravel().tolist()))
            else:
                values[sensor.name] = sensor.response.output(readings[sensor.name])
        self.sensor_values = values
        # Outputs now: the activations computed one delay ago.
        n_units = len(self.unit_names)
        outputs = self.activations[(self.t - self.steps) % len(self.activations), np.arange(n_units)]
        self.unit_outputs = dict(zip(self.unit_names, outputs.tolist()))
        signals = np.concatenate([np.fromiter(values.values(), float, len(values)), outputs])
        self.history[self.t % self.window] = signals
        for k, j in self.learning_inputs:   # active or not by their strength at the start of the step
            self.input_active[self.input_first[k] + j] = self.is_active(self.unit_names[k], j)
        # Each input's largest value within its unit's window, for each window length.
        recent = np.stack([self.history[(self.t - np.arange(n)) % self.window].max(axis=0)
                           for n in self.windows]) if self.windows else np.zeros((0, len(signals)))
        inputs = recent[self.input_group, self.input_signal]
        contributions = np.where(self.input_active, self.input_sign * inputs, 0.0)
        sums = np.bincount(self.input_unit, contributions, minlength=n_units)
        self.activations[self.t % len(self.activations)] = sums >= self.thresholds
        # Learning: a connection whose source is on learns when the unit's other inputs
        # fire it, and forgets when they do not (see 'Learning connections').
        learned = {}
        for k, j in self.learning_inputs:
            u = d.units[k]
            first = self.input_first[k]
            if inputs[first + j] > 0:
                signals_k = contributions[first:first + len(u.inputs)].tolist()
                others = sum(signals_k[:j] + signals_k[j + 1:])
                c = u.inputs[j]
                rate = c.learning.learn if others >= u.threshold else -c.learning.forget
                learned[(u.name, j)] = clamp01(self.strengths[(u.name, j)] + rate * self.dt)
        self.strengths.update(learned)  # takes effect from the next step
        self.t += 1
        for a in d.actuators:
            total = sum(c.sign * self.signal(c.source) for c in a.inputs if c.active)
            self.motor_speeds[a.name] = min(max(a.base_speed + a.gain * total, 0.0), a.max_speed)

    @property
    def pending(self) -> dict[str, list[float]]:
        """Each unit's activations on their way to becoming outputs, oldest first."""
        rows = len(self.activations)
        return {name: [self.activations[(self.t - n + m) % rows, k] for m in range(n)]
                for k, (name, n) in enumerate(zip(self.unit_names, self.steps.tolist()))}

    def is_active(self, unit: str, index: int) -> bool:
        """Whether a unit's input carries a signal now, with its current strength."""
        return self.connection_strength(unit, index) > ACTIVE_STRENGTH

    def connection_strength(self, target: str, index: int) -> float:
        """The current strength of input `index` of unit or actuator `target`."""
        key = (target, index)
        return self.strengths[key] if key in self.strengths else self.fixed_strengths[key]

    def strength(self, source: str, target: str) -> float:
        """The current strength of the first connection from `source` into `target`."""
        parts = {p.name: p for p in [*self.definition.units, *self.definition.actuators]}
        index = next(j for j, c in enumerate(parts[target].inputs) if c.source == source)
        return self.connection_strength(target, index)

    def signal(self, name: str) -> float:
        if name in self.sensor_values:
            return self.sensor_values[name]
        return self.unit_outputs[name]

    # --- movement ---

    def move(self, dt: float, rng: np.random.Generator) -> None:
        actuators = self.definition.actuators
        speeds = [self.motor_speeds[a.name] for a in actuators]
        xs = [a.position[0] * self.half_size for a in actuators]
        self.speed = sum(speeds) / len(speeds)
        sxx = sum(x * x for x in xs)
        self.turn_rate = sum(s * x for s, x in zip(speeds, xs)) / sxx if sxx > 0 else 0.0
        noise_std = self.definition.general.noise_std
        noise = noise_std * math.sqrt(dt) * rng.standard_normal() if noise_std else 0.0
        self.heading += self.turn_rate * dt + noise
        self.x += self.speed * math.cos(self.heading) * dt
        self.y += self.speed * math.sin(self.heading) * dt

    def step(self, readings: dict[str, float], dt: float, rng: np.random.Generator,
             charge_reading: float = 0.0) -> None:
        """One step. `charge_reading` is the energy's charge_from stimulus at the body center."""
        self.think(readings)
        self.move(dt, rng)
        self.update_energy(charge_reading, dt, abs(self.speed) * dt)

    def update_energy(self, charge_reading: float, dt: float, distance: float) -> None:
        e = self.definition.energy
        if e is None:
            return
        gain = e.charge_gain * charge_reading * dt if e.charge_from else 0.0
        used = e.consumption * distance + e.basal * dt
        self.energy = min(max(self.energy + gain - used, 0.0), e.max)

    # --- diagram ---

    def diagram(self) -> Diagram:
        d = self.definition
        levels: dict[str, float] = {}   # by signal name
        for s in d.sensors:
            for name in self.outputs_of(s):
                value = self.sensor_values[name]
                if s.response.type != "linear":
                    ref = s.response.height  # nonlinear responses top out at their height
                elif s.type == ENERGY_SENSOR:
                    ref = d.energy.max
                else:
                    ref = self.references.get(name, 1.0)
                levels[name] = clamp01(value / ref) if ref > 0 else (1.0 if value > 0 else 0.0)
        levels.update(self.unit_outputs)
        parts = []
        for s in d.sensors:
            if s.camera:
                rows, columns = s.camera.shape
                grid = lambda table: [[table[element_name(s.name, (r, c))] for c in range(columns)]
                                      for r in range(rows)]
                parts.append(Part("camera", s.name, s.position, s.type, grid(self.sensor_values),
                                  grid(levels), shape=s.camera.shape))
            else:
                parts.append(Part("sensor", s.name, s.position, s.type,
                                  self.sensor_values[s.name], levels[s.name]))
        positions = self.unit_layout()
        group_of = {}   # signal name -> part name
        for u in d.units:
            if u.array:
                group_of[u.name] = u.array
                if u.index != (0,) * len(u.index):
                    continue
                shape = d.arrays[u.array]
                elements = [e for e in d.units if e.array == u.array]
                values = [self.unit_outputs[e.name] for e in elements]
                if len(shape) == 2:
                    values = [values[r * shape[1]:(r + 1) * shape[1]] for r in range(shape[0])]
                parts.append(Part("array", u.array, positions[u.array],
                                  f"threshold {u.threshold:g}", values, values, u.threshold, shape))
            else:
                value = self.unit_outputs[u.name]
                parts.append(Part("unit", u.name, positions[u.name], f"threshold {u.threshold:g}",
                                  value, value, u.threshold))
        for a in d.actuators:
            value = self.motor_speeds[a.name]
            level = clamp01(value / a.max_speed) if a.max_speed > 0 else 0.0
            parts.append(Part(a.type, a.name, a.position, a.type, value, level))
        for s in d.sensors:
            if s.camera:
                group_of.update((name, s.name) for name in s.pixels())
        indices = {u.name: u.index for u in d.units if u.array}
        indices.update((element_name(s.name, (r, c)), (r, c)) for s in d.sensors if s.camera
                       for r in range(s.camera.rows) for c in range(s.camera.columns))
        wires = []
        for target in [*d.units, *d.actuators]:
            for j, c in enumerate(target.inputs):
                strength = self.connection_strength(target.name, j)
                active = strength > ACTIVE_STRENGTH
                wires.append(Wire(group_of.get(c.source, c.source),
                                  group_of.get(target.name, target.name), c.sign,
                                  levels[c.source] if active else 0.0, active, strength,
                                  c.learning.type if c.learning else None,
                                  indices.get(c.source), indices.get(target.name), c.label))
        return Diagram(
            title=self.label,
            subtitle=f"Vehicle {d.general.type}: {d.general.name}",
            parts=parts,
            wires=wires,
            params={"size": f"{d.general.size:g}", "noise_std": f"{d.general.noise_std:g}",
                    "speed": f"{self.speed:.2f}", "turn rate": f"{self.turn_rate:.2f}",
                    **({"energy": f"{self.energy:.0f}/{d.energy.max:g}"} if d.energy else {})},
        )

    def signal_references(self) -> dict[str, float]:
        """For each sensor output: the reading at which its strongest excitatory target
        saturates or fires."""
        refs: dict[str, list[float]] = {}
        for a in self.definition.actuators:
            for c in a.inputs:
                if c.active and c.sign > 0 and a.gain > 0:
                    refs.setdefault(c.source, []).append((a.max_speed - a.base_speed) / a.gain)
        for u in self.definition.units:
            for c in u.inputs:
                if c.active and c.sign > 0 and u.threshold > 0:
                    refs.setdefault(c.source, []).append(u.threshold)
        return {name: min(values) for name, values in refs.items()}

    def sensor_reference(self, name: str) -> float:
        """Reading at which the sensor's strongest excitatory target saturates or fires."""
        return self.references.get(name, 1.0)

    def unit_layout(self) -> dict[str, tuple[float, float]]:
        """Diagram positions of units and arrays: their own, or spread across the middle."""
        groups: dict[str, tuple[float, float] | None] = {}
        for u in self.definition.units:
            groups.setdefault(u.array or u.name, u.position)
        n = len(groups)
        return {name: position if position is not None else (-0.6 + 1.2 * (i + 0.5) / n, 0.0)
                for i, (name, position) in enumerate(groups.items())}
