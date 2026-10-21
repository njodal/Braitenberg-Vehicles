"""Scenarios: a world, vehicles placed in it and the simulation settings (specs/scenarios.md)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from braitenberg.definition import ENERGY_SENSOR, VehicleDefinition, load_definition
from braitenberg.world import World, load_world
from braitenberg.yamlfile import ConfigError, Parser, read_yaml


@dataclass
class Placement:
    definition: VehicleDefinition
    position: tuple[float, float]
    heading: float  # radians (files use degrees)
    label: str


@dataclass
class SimulationSettings:
    dt: float = 0.05
    seed: int = 0


@dataclass
class Scenario:
    name: str
    world: World
    vehicles: list[Placement]
    simulation: SimulationSettings = field(default_factory=SimulationSettings)
    description: str = ""


def load_scenario(path: str | Path) -> Scenario:
    path = Path(path).resolve()
    return _ScenarioParser(path).scenario(read_yaml(path))


def quick_scenario(world_path: str | Path, vehicle_paths: list[str | Path],
                   starts: list[str] = ()) -> Scenario:
    """The scenario built by `--world W --vehicle V [--start x,y,heading]`."""
    def referenced(option: str, value, loader):
        try:
            return loader(value)
        except ConfigError as e:
            raise ConfigError(f"{option} {value}: {e}") from e

    world = referenced("--world", world_path, load_world)
    if len(starts) > len(vehicle_paths):
        raise ConfigError(f"--start: {len(starts)} given for {len(vehicle_paths)} vehicles")
    n = len(vehicle_paths)
    placements = []
    for i, vpath in enumerate(vehicle_paths):
        definition = referenced("--vehicle", vpath, load_definition)
        if i < len(starts):
            try:
                x, y, heading = (float(v) for v in starts[i].split(","))
            except ValueError:
                raise ConfigError(f"--start {starts[i]}: must be x,y,heading") from None
        else:
            x, y, heading = 0.2 * world.arena.width, (i + 1) * world.arena.height / (n + 1), 0.0
        placements.append(Placement(definition, (x, y), math.radians(heading),
                                    f"{definition.general.name} #{i}"))
    scenario = Scenario(name=f"{world.name} — " + ", ".join(p.definition.general.name for p in placements),
                        world=world, vehicles=placements)
    check_fit(scenario, lambda i: (f"--vehicle {vehicle_paths[i]}", f"--start for vehicle {i}"))
    return scenario


def check_fit(scenario: Scenario, keys: Callable[[int], tuple[str, str]]) -> None:
    """Vehicles must start inside the arena and read only stimuli the world defines.

    `keys(i)` names vehicle i's definition and position in error messages.
    """
    world = scenario.world
    for i, p in enumerate(scenario.vehicles):
        definition_key, position_key = keys(i)
        if not world.arena.contains(*p.position):
            raise ConfigError(f"{position_key}: [{p.position[0]:g}, {p.position[1]:g}] "
                              f"is outside the arena of world {world.path}")
        energy = p.definition.energy
        if energy and energy.charge_from and energy.charge_from not in world.stimuli:
            raise ConfigError(f"{definition_key}: energy.charge_from '{energy.charge_from}' "
                              f"is not a stimulus of world {world.path}")
        for name in p.definition.appearance:
            if name not in world.stimuli:
                raise ConfigError(f"{definition_key}: appearance '{name}' "
                                  f"is not a stimulus of world {world.path}")
        for s in p.definition.sensors:
            if s.type != ENERGY_SENSOR and s.type not in world.stimuli:
                raise ConfigError(f"{definition_key}: sensor '{s.name}' reads '{s.type}', "
                                  f"which is not a stimulus of world {world.path}")


class _ScenarioParser(Parser):
    def referenced(self, value, key: str, loader):
        try:
            return loader(self.relative_path(value, key))
        except ConfigError as e:
            raise self.error(key, f"in referenced file: {e}") from e

    def scenario(self, data) -> Scenario:
        data = self.mapping(data, "", {"name", "world", "vehicles"}, {"description", "simulation"})
        world = self.referenced(data["world"], "world", load_world)
        definitions: dict[Path, VehicleDefinition] = {}
        placements = []
        for i, (key, body) in enumerate(self.items(data["vehicles"], "vehicles", "vehicle")):
            body = self.mapping(body, key, {"definition", "position", "heading"}, {"label"})
            dpath = self.relative_path(body["definition"], f"{key}.definition")
            if dpath not in definitions:
                definitions[dpath] = self.referenced(body["definition"], f"{key}.definition",
                                                     load_definition)
            definition = definitions[dpath]
            placements.append(Placement(
                definition=definition,
                position=self.pair(body["position"], f"{key}.position"),
                heading=math.radians(self.number(body["heading"], f"{key}.heading")),
                label=self.string(body.get("label", f"{definition.general.name} #{i}"),
                                  f"{key}.label"),
            ))
        scenario = Scenario(
            name=self.string(data["name"], "name"),
            description=self.string(data.get("description", ""), "description"),
            world=world,
            vehicles=placements,
            simulation=self.simulation(data.get("simulation", {})),
        )
        try:
            check_fit(scenario, lambda i: (f"vehicles[{i}].vehicle.definition",
                                           f"vehicles[{i}].vehicle.position"))
        except ConfigError as e:
            raise ConfigError(f"{self.path}: {e}") from e
        return scenario

    def simulation(self, data) -> SimulationSettings:
        data = self.mapping(data, "simulation", set(), {"dt", "seed"})
        settings = SimulationSettings()
        if "dt" in data:
            settings.dt = self.number(data["dt"], "simulation.dt", positive=True)
        if "seed" in data:
            settings.seed = self.integer(data["seed"], "simulation.seed")
        return settings
