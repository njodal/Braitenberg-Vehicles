"""Headless simulation loop and the command line shared by all vehicle modules.

This module must not import pygame; the renderer is imported only when a run
asks for a window.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import math
from pathlib import Path

import numpy as np

from braitenberg.vehicle import VEHICLE_TYPES
from braitenberg.world import World, WorldError, load_world

WORLDS_DIR = Path(__file__).resolve().parent.parent / "worlds"


class Simulation:
    """Steps every vehicle in a world. Works on its own copy of the world."""

    def __init__(self, world: World):
        self.world = copy.deepcopy(world)
        self.rng = np.random.default_rng(self.world.simulation.seed)
        self.dt = self.world.simulation.dt
        self.time = 0.0
        self.steps = 0
        self.vehicles = [self.make_vehicle(p) for p in self.world.vehicles]

    def make_vehicle(self, placement):
        cls = VEHICLE_TYPES[placement.type]
        x, y = placement.position
        return cls(x, y, placement.heading, placement.sensor,
                   dataclasses.replace(placement.params))

    def step(self) -> None:
        for v in self.vehicles:
            sx, sy = v.sensor_position()
            v.step(float(self.world.stimulus_at(v.sensor, sx, sy)), self.dt, self.rng)
            self.world.arena.apply_edges(v)
        self.time += self.dt
        self.steps += 1

    def run(self, steps: int) -> None:
        for _ in range(steps):
            self.step()


def parse_args(argv, default_world: str):
    parser = argparse.ArgumentParser(description="Run a Braitenberg vehicle simulation.")
    parser.add_argument("world", nargs="?", default=str(WORLDS_DIR / default_world),
                        help=f"world file (default: worlds/{default_world})")
    parser.add_argument("--headless", action="store_true",
                        help="run without a window, as fast as possible")
    parser.add_argument("--steps", type=int, default=10_000,
                        help="steps to run when headless (default: 10000)")
    parser.add_argument("--seed", type=int, help="override simulation.seed")
    return parser.parse_args(argv)


def load_with_overrides(args) -> World:
    world = load_world(args.world)
    if args.seed is not None:
        world.simulation.seed = args.seed
    return world


def main(default_world: str, argv=None) -> None:
    args = parse_args(argv, default_world)
    try:
        world = load_with_overrides(args)
    except WorldError as e:
        raise SystemExit(f"error: {e}")
    if args.headless:
        sim = Simulation(world)
        sim.run(args.steps)
        print(f"{world.name}: {sim.steps} steps, t = {sim.time:g}")
        for i, v in enumerate(sim.vehicles):
            print(f"  vehicle {i}: position ({v.x:.2f}, {v.y:.2f}), "
                  f"heading {math.degrees(v.heading) % 360:.1f} deg, speed {v.speed:.3f}")
    else:
        from braitenberg.render import run_window
        run_window(world)
