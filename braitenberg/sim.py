"""Headless simulation loop and the command line (specs/scenarios.md).

This module must not import pygame; the renderer is imported only when a run
asks for a window.
"""

from __future__ import annotations

import argparse
import copy
import math

import numpy as np

from braitenberg.camera import camera_image, sight_lines
from braitenberg.scenario import Scenario, load_scenario, quick_scenario
from braitenberg.vehicle import Vehicle
from braitenberg.yamlfile import ConfigError


class Simulation:
    """Steps every vehicle of a scenario. Works on its own copy of the world."""

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.world = copy.deepcopy(scenario.world)
        self.rng = np.random.default_rng(scenario.simulation.seed)
        self.dt = scenario.simulation.dt
        self.time = 0.0
        self.steps = 0
        self.vehicles = [Vehicle(p.definition, *p.position, p.heading, p.label, self.dt)
                         for p in scenario.vehicles]
        self.sight_lines = {}   # camera sensor -> its lines of sight, computed once
        self.has_cameras = any(s.camera for p in scenario.vehicles for s in p.definition.sensors)

    def step(self) -> None:
        # Cameras and infrared sensors sense every vehicle where it was at the start of the step.
        bodies = [(v.x, v.y, v.half_width, v.half_length, v.heading, v.definition.general.height,
                   v.definition) for v in self.vehicles]
        obstacles = [(*o.box(), o.height, o) for o in self.world.obstacles]
        things = {}   # stimulus -> things of the world
        for k, v in enumerate(self.vehicles):
            sensors = {s.name: s for s in v.definition.sensors}
            others = [body[:5] for i, body in enumerate(bodies) if i != k]
            readings = {name: float(self.world.stimulus_at(
                            stimulus, x, y, self.time,
                            v.heading + math.radians(sensors[name].direction),
                            sensors[name].field_of_view, others))
                        for name, stimulus, x, y in v.sensor_points()}
            for sensor, x, y in v.cameras():
                if sensor.type not in things:
                    things[sensor.type] = self.world.things(sensor.type, self.time)
                boxes = np.array([(*body[:6], *body[6].faces(sensor.type))
                                  for i, body in enumerate(bodies) if i != k]
                                 + [(*o[:6], *o[6].faces(sensor.type)) for o in obstacles])
                key = id(sensor)
                if key not in self.sight_lines:
                    self.sight_lines[key] = sight_lines(sensor)
                readings[sensor.name] = camera_image(*self.sight_lines[key], x, y,
                                                     sensor.camera.height, v.heading,
                                                     np.array(things[sensor.type]),
                                                     self.world.arena.delta, sensor.camera.range,
                                                     boxes)
            energy = v.definition.energy
            charge = (float(self.world.stimulus_at(energy.charge_from, v.x, v.y, self.time))
                      if energy and energy.charge_from else 0.0)
            v.step(readings, self.dt, self.rng, charge)
            self.world.arena.apply_edges(v)
            self.world.block(v)
        self.time += self.dt
        self.steps += 1

    def run(self, steps: int) -> None:
        for _ in range(steps):
            self.step()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m braitenberg",
        description="Run a Braitenberg vehicle simulation from a scenario file, "
                    "or from a world and vehicles given directly.")
    parser.add_argument("scenario", nargs="?", help="scenario file")
    parser.add_argument("--world", help="world file (instead of a scenario)")
    parser.add_argument("--vehicle", action="append", default=[],
                        help="vehicle definition file; repeat for more vehicles")
    parser.add_argument("--start", action="append", default=[], metavar="X,Y,HEADING",
                        help="start of the n-th --vehicle; repeat for more vehicles")
    parser.add_argument("--headless", action="store_true",
                        help="run without a window, as fast as possible")
    parser.add_argument("--steps", type=int, default=10_000,
                        help="steps to run when headless (default: 10000)")
    parser.add_argument("--seed", type=int, help="override simulation.seed")
    args = parser.parse_args(argv)
    if args.scenario and (args.world or args.vehicle or args.start):
        parser.error("give either a scenario file or --world and --vehicle, not both")
    if not args.scenario and not (args.world and args.vehicle):
        parser.error("give a scenario file, or --world and at least one --vehicle")
    return args


def scenario_from_args(args) -> Scenario:
    if args.scenario:
        scenario = load_scenario(args.scenario)
    else:
        scenario = quick_scenario(args.world, args.vehicle, args.start)
    if args.seed is not None:
        scenario.simulation.seed = args.seed
    return scenario


def main(argv=None) -> None:
    args = parse_args(argv)
    try:
        scenario = scenario_from_args(args)
    except ConfigError as e:
        raise SystemExit(f"error: {e}")
    if args.headless:
        sim = Simulation(scenario)
        sim.run(args.steps)
        print(f"{scenario.name}: {sim.steps} steps, t = {sim.time:g}")
        for v in sim.vehicles:
            print(f"  {v.label}: position ({v.x:.2f}, {v.y:.2f}), "
                  f"heading {math.degrees(v.heading) % 360:.1f} deg, speed {v.speed:.3f}")
    else:
        from braitenberg.render import run_window
        run_window(scenario)
