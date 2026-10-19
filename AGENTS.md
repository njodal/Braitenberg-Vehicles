# AGENTS.md

Instructions for AI coding agents working in this repo.

## Project

An implementation of the Vehicles from Valentino Braitenberg's book *Vehicles: Experiments in Synthetic Psychology*. The focus is Vehicles 5 and beyond, the ones with a 'nervous system' between the sensors and the actuators. See [README.md](README.md).

## Specs

Specifications live in the `specs/` folder. Read the relevant spec before implementing a vehicle or feature.

## Programming environment

The project is written in Python.

- **Simulation:** pure Python + `numpy`. Differential-drive kinematics are simple enough that no physics engine is needed.
- **Visualization:** `pygame-ce` (the community-maintained pygame fork), used for real-time rendering and interaction (moving sources, pausing, adding vehicles).
- **Analysis:** `matplotlib` for plotting internal state (neuron activity, weights, fitness) after runs.

## Architecture rule

Keep the simulation engine independent of rendering. World, vehicles and brains must not import pygame; the renderer only reads simulation state and draws it. The simulation must be able to run headless and faster than real time, which Vehicles 6+ (evolution, learning) depend on.
