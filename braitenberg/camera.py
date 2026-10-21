"""What a camera sees: lines of sight against upright cylinders (specs/camera.md).

Things are upright cylinders standing on the ground: sources with a radius, and
vehicles. The ground and the sky are dark. This module must not import pygame.
"""

from __future__ import annotations

import math

import numpy as np

from braitenberg.definition import SensorDef


def sight_lines(sensor: SensorDef) -> tuple[np.ndarray, np.ndarray]:
    """Azimuth and elevation, in radians from the heading and from level, of every line of sight.

    Both have shape (rows, columns, samples^2): row 0 is the top, column 0 the leftmost.
    """
    cam = sensor.camera
    s = cam.samples
    w = sensor.field_of_view / cam.columns
    h = cam.vertical_field_of_view / cam.rows
    sub = (np.arange(s) + 0.5) / s   # the middle of each of the s x s cells of a pixel
    azimuth = cam.direction + sensor.field_of_view / 2 - (np.arange(cam.columns)[:, None] + sub) * w
    elevation = cam.tilt + cam.vertical_field_of_view / 2 - (np.arange(cam.rows)[:, None] + sub) * h
    shape = (cam.rows, cam.columns, s, s)
    az = np.broadcast_to(azimuth[None, :, None, :], shape)
    el = np.broadcast_to(elevation[:, None, :, None], shape)
    return (np.radians(az).reshape(cam.rows, cam.columns, s * s),
            np.radians(el).reshape(cam.rows, cam.columns, s * s))


def camera_image(azimuth: np.ndarray, elevation: np.ndarray, x: float, y: float, height: float,
                 heading: float, things: np.ndarray, delta, sight_range: float = math.inf) -> np.ndarray:
    """Each pixel's reading: the average brightness its lines of sight see.

    `things` has one row (x, y, radius, height, brightness) per thing; `delta(dx, dy)` is the
    arena's displacement rule, so that with wrapping each thing is seen the shortest way around.
    """
    rows, columns, _ = azimuth.shape
    if len(things) == 0:
        return np.zeros((rows, columns))
    dx, dy = delta(things[:, 0] - x, things[:, 1] - y)
    radius, top, brightness = things[:, 2], things[:, 3], things[:, 4]
    distance = np.hypot(dx, dy)
    near = distance - radius <= sight_range   # farther things are not seen and hide nothing
    dx, dy, radius, top, brightness = dx[near], dy[near], radius[near], top[near], brightness[near]
    if len(dx) == 0:
        return np.zeros((rows, columns))

    a = heading + azimuth.reshape(-1, 1)
    slope = np.tan(elevation.reshape(-1, 1))
    # Along the ground, the line of sight is inside a thing's footprint for s in [s0, s1].
    along = np.cos(a) * dx + np.sin(a) * dy
    across2 = dx * dx + dy * dy - along * along
    half = np.sqrt(np.maximum(radius * radius - across2, 0.0))
    s0 = np.maximum(along - half, 0.0)
    s1 = along + half
    crosses = (across2 <= radius * radius) & (s1 >= 0)
    # Its elevation, height + s * slope, is between the ground and the thing's top for s in [z0, z1].
    with np.errstate(divide="ignore"):
        to_ground = np.where(slope != 0, -height / slope, np.inf)
        to_top = np.where(slope != 0, (top - height) / slope, np.inf)
    level = slope == 0
    within = (height >= 0) & (height <= top)
    z0 = np.where(level, np.where(within, -np.inf, np.inf), np.minimum(to_ground, to_top))
    z1 = np.where(level, np.where(within, np.inf, -np.inf), np.maximum(to_ground, to_top))
    enter = np.maximum(s0, z0)
    hits = crosses & (enter <= np.minimum(s1, z1))
    hit_at = np.where(hits, enter, np.inf)
    first = np.argmin(hit_at, axis=1)
    seen = np.isfinite(hit_at[np.arange(len(first)), first])
    sees = np.where(seen, brightness[first], 0.0)
    return sees.reshape(azimuth.shape).mean(axis=2)
