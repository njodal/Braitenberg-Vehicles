"""What a camera sees: lines of sight against things (specs/camera.md).

Things stand on the ground: sources with a radius are upright cylinders, and
vehicles are boxes. The ground and the sky are dark. This module must not import pygame.
"""

from __future__ import annotations

import math

import numpy as np

from braitenberg.definition import FACES, SensorDef

FRONT, BACK, LEFT, RIGHT, TOP = range(len(FACES))   # indices into FACES


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
                 heading: float, things: np.ndarray, delta, sight_range: float = math.inf,
                 boxes: np.ndarray | None = None) -> np.ndarray:
    """Each pixel's reading: the average brightness its lines of sight see.

    `things` has one row (x, y, radius, height, brightness) per upright cylinder, and `boxes`
    one row (x, y, half width, half length, heading, height, then the brightness of each face
    in the order of FACES) per box, such as a vehicle, whose length lies along its heading. `delta(dx, dy)` is the arena's displacement
    rule, so that with wrapping each thing is seen the shortest way around.
    """
    rows, columns, _ = azimuth.shape
    things = np.asarray(things, dtype=float).reshape(-1, 5)
    boxes = (np.zeros((0, 11)) if boxes is None
             else np.asarray(boxes, dtype=float).reshape(-1, 11))
    a = heading + azimuth.reshape(-1, 1)
    cos_a, sin_a = np.cos(a), np.sin(a)
    # Along the ground, each line of sight is inside a thing's footprint for s in [s0, s1].
    spans, tops, brightness = [], [], []
    cylinders = 0

    if len(things):
        dx, dy = delta(things[:, 0] - x, things[:, 1] - y)
        radius = things[:, 2]
        near = np.hypot(dx, dy) - radius <= sight_range   # farther things are not seen and hide nothing
        dx, dy, radius = dx[near], dy[near], radius[near]
        along = cos_a * dx + sin_a * dy
        across2 = dx * dx + dy * dy - along * along
        half = np.sqrt(np.maximum(radius * radius - across2, 0.0))
        s1 = along + half
        crosses = (across2 <= radius * radius) & (s1 >= 0)
        spans.append((np.maximum(along - half, 0.0), s1, crosses))
        tops.append(things[near, 3])
        brightness.append(np.broadcast_to(things[near, 4], crosses.shape))
        cylinders = crosses.shape[1]

    if len(boxes):
        dx, dy = delta(boxes[:, 0] - x, boxes[:, 1] - y)
        hw, hl, turn = boxes[:, 2], boxes[:, 3], boxes[:, 4]
        fx, fy = np.cos(turn), np.sin(turn)    # the box's forward; its right is (fy, -fx)
        # The camera in the box's frame: u across, to the right, and v along, forward.
        u, v = -(dx * fy - dy * fx), -(dx * fx + dy * fy)
        gap = np.hypot(np.maximum(np.abs(u) - hw, 0.0), np.maximum(np.abs(v) - hl, 0.0))
        near = gap <= sight_range
        u, v, hw, hl, fx, fy = u[near], v[near], hw[near], hl[near], fx[near], fy[near]
        du, dv = cos_a * fy - sin_a * fx, cos_a * fx + sin_a * fy
        # Slabs: the line of sight is within the box's width, and within its length, for
        # s between the two crossings of each pair of sides.
        slabs = []
        for p, d, h in ((u, du, hw), (v, dv, hl)):
            with np.errstate(divide="ignore", invalid="ignore"):
                t0, t1 = (-h - p) / d, (h - p) / d
            parallel = d == 0
            inside = np.abs(p) <= h
            slabs.append((np.where(parallel, np.where(inside, -np.inf, np.inf), np.minimum(t0, t1)),
                          np.where(parallel, np.where(inside, np.inf, -np.inf), np.maximum(t0, t1))))
        (lo_u, hi_u), (lo_v, hi_v) = slabs
        enter, leave = np.maximum(lo_u, lo_v), np.minimum(hi_u, hi_v)
        spans.append((np.maximum(enter, 0.0), leave, (enter <= leave) & (leave >= 0)))
        tops.append(boxes[near, 5])
        # The side a line of sight comes in through, and the one it leaves through.
        side_in = np.where(lo_u >= lo_v, np.where(du > 0, LEFT, RIGHT), np.where(dv > 0, BACK, FRONT))
        side_out = np.where(hi_u <= hi_v, np.where(du > 0, RIGHT, LEFT), np.where(dv > 0, FRONT, BACK))
        box_faces, box_sides = boxes[near, 6:], (enter, leave, side_in, side_out)

    if not spans or sum(len(t) for t in tops) == 0:
        return np.zeros((rows, columns))
    s0, s1, crosses = (np.concatenate(z, axis=1) for z in zip(*spans))
    top = np.concatenate(tops)

    slope = np.tan(elevation.reshape(-1, 1))
    # Its elevation, height + s * slope, is between the ground and the thing's top for s in [z0, z1].
    with np.errstate(divide="ignore"):
        to_ground = np.where(slope != 0, -height / slope, np.inf)
        to_top = np.where(slope != 0, (top - height) / slope, np.inf)
    level = slope == 0
    within = (height >= 0) & (height <= top)
    z0 = np.where(level, np.where(within, -np.inf, np.inf), np.minimum(to_ground, to_top))
    z1 = np.where(level, np.where(within, np.inf, -np.inf), np.maximum(to_ground, to_top))
    enter = np.maximum(s0, z0)
    if len(boxes) and box_faces.size:
        # Which face of each box a line of sight meets: the top when it comes down onto it,
        # the side it comes in through, or, from inside the box, the one it would leave by.
        box = slice(cylinders, None)
        enter_side, leave_side, side_in, side_out = box_sides
        from_inside = enter_side <= 0
        up_through_top = z1[:, box] < leave_side
        face = np.where(z0[:, box] > s0[:, box], TOP,
                        np.where(from_inside, np.where(up_through_top, TOP, side_out), side_in))
        brightness.append(box_faces[np.arange(box_faces.shape[0]), face])
    brightness = np.concatenate(brightness, axis=1)
    hits = crosses & (enter <= np.minimum(s1, z1))
    hit_at = np.where(hits, enter, np.inf)
    first = np.argmin(hit_at, axis=1)
    seen = np.isfinite(hit_at[np.arange(len(first)), first])
    sees = np.where(seen, brightness[np.arange(len(first)), first], 0.0)
    return sees.reshape(azimuth.shape).mean(axis=2)
