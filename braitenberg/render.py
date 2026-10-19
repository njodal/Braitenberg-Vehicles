"""Real-time pygame renderer. The only module that imports pygame.

It reads the simulation state and draws it; user interaction (dragging sources,
pausing, resetting) changes only the running simulation, never the world file.

Keys: space pause/resume, right arrow step (when paused), R reset, T trail,
Tab next stimulus, +/- simulation speed, Esc quit. Drag sources with the mouse.
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np
import pygame

from braitenberg.sim import Simulation
from braitenberg.world import Source, World

MAX_WINDOW_SIDE = 720
HEATMAP_CELL = 4          # pixels per heat map sample
TRAIL_LENGTH = 800        # recent positions kept per vehicle
SOURCE_RADIUS = 7
GRAB_RADIUS = 14
FPS = 60

# Heat map color stops, from no stimulus (dark blue) to the strongest (pale yellow).
HEAT_STOPS = np.array([
    [8, 12, 40], [40, 30, 110], [150, 40, 110], [230, 100, 50], [255, 230, 140],
], dtype=float)

BACKGROUND = (8, 12, 40)
VEHICLE_FILL = (245, 245, 245)
VEHICLE_OUTLINE = (20, 20, 20)
SOURCE_FILL = (255, 255, 255)
TEXT = (235, 235, 235)


def heat_colors(values: np.ndarray) -> np.ndarray:
    """Map values in [0, 1] to RGB through HEAT_STOPS."""
    pos = np.clip(values, 0, 1) * (len(HEAT_STOPS) - 1)
    i = np.minimum(pos.astype(int), len(HEAT_STOPS) - 2)
    frac = (pos - i)[..., None]
    return (HEAT_STOPS[i] * (1 - frac) + HEAT_STOPS[i + 1] * frac).astype(np.uint8)


class Renderer:
    def __init__(self, world: World):
        self.original = world
        arena = world.arena
        self.scale = MAX_WINDOW_SIDE / max(arena.width, arena.height)
        self.size = (round(arena.width * self.scale), round(arena.height * self.scale))
        self.stimulus_names = list(world.stimuli)
        first_sensor = world.vehicles[0].sensor if world.vehicles else None
        self.stimulus_index = (self.stimulus_names.index(first_sensor)
                               if first_sensor in self.stimulus_names else 0)
        self.show_trail = True
        self.paused = False
        self.steps_per_frame = 1
        self.dragging: tuple[str, int] | None = None
        self.font = pygame.font.Font(None, 20)
        self.reset()

    # --- state ---

    def reset(self) -> None:
        self.sim = Simulation(self.original)
        self.trails = [deque(maxlen=TRAIL_LENGTH) for _ in self.sim.vehicles]
        self.record_trails()
        self.heatmap = None

    def advance(self, steps: int) -> None:
        for _ in range(steps):
            self.sim.step()
            self.record_trails()

    def record_trails(self) -> None:
        for trail, v in zip(self.trails, self.sim.vehicles):
            trail.append((v.x, v.y))

    @property
    def stimulus(self) -> str | None:
        return self.stimulus_names[self.stimulus_index] if self.stimulus_names else None

    # --- coordinates (world y points up, screen y points down) ---

    def to_screen(self, x: float, y: float) -> tuple[float, float]:
        return x * self.scale, self.size[1] - y * self.scale

    def to_world(self, px: float, py: float) -> tuple[float, float]:
        return px / self.scale, (self.size[1] - py) / self.scale

    # --- input ---

    def handle(self, event) -> bool:
        """Process one event. Returns False when the window should close."""
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            if event.key == pygame.K_SPACE:
                self.paused = not self.paused
            elif event.key == pygame.K_RIGHT and self.paused:
                self.advance(1)
            elif event.key == pygame.K_r:
                self.reset()
            elif event.key == pygame.K_t:
                self.show_trail = not self.show_trail
            elif event.key == pygame.K_TAB and self.stimulus_names:
                self.stimulus_index = (self.stimulus_index + 1) % len(self.stimulus_names)
                self.heatmap = None
            elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.steps_per_frame = min(self.steps_per_frame * 2, 256)
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.steps_per_frame = max(self.steps_per_frame // 2, 1)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.dragging = self.source_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = None
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            name, i = self.dragging
            arena = self.sim.world.arena
            x, y = self.to_world(*event.pos)
            x, y = min(max(x, 0), arena.width), min(max(y, 0), arena.height)
            old = self.sim.world.stimuli[name].sources[i]
            self.sim.world.stimuli[name].sources[i] = Source((x, y), old.intensity, old.falloff)
            self.heatmap = None
        return True

    def source_at(self, pos) -> tuple[str, int] | None:
        for name, stimulus in self.sim.world.stimuli.items():
            for i, s in enumerate(stimulus.sources):
                sx, sy = self.to_screen(*s.position)
                if math.hypot(pos[0] - sx, pos[1] - sy) <= GRAB_RADIUS:
                    return name, i
        return None

    # --- drawing ---

    def draw(self, surface: pygame.Surface) -> None:
        self.draw_field(surface)
        if self.show_trail:
            self.draw_trails(surface)
        self.draw_sources(surface)
        self.draw_vehicles(surface)
        self.draw_hud(surface)

    def draw_field(self, surface: pygame.Surface) -> None:
        if self.stimulus is None:
            surface.fill(BACKGROUND)
            return
        if self.heatmap is None:
            w, h = self.size
            cols, rows = max(w // HEATMAP_CELL, 1), max(h // HEATMAP_CELL, 1)
            xs = (np.arange(cols) + 0.5) * w / cols / self.scale
            ys = self.size[1] / self.scale - (np.arange(rows) + 0.5) * h / rows / self.scale
            gx, gy = np.meshgrid(xs, ys, indexing="ij")  # surfarray is indexed [x, y]
            values = self.sim.world.stimulus_at(self.stimulus, gx, gy)
            peak = max((s.intensity for s in self.sim.world.stimuli[self.stimulus].sources),
                       default=0)
            normalized = values / peak if peak > 0 else np.zeros_like(values)
            small = pygame.surfarray.make_surface(heat_colors(normalized))
            self.heatmap = pygame.transform.smoothscale(small, self.size)
        surface.blit(self.heatmap, (0, 0))

    def draw_trails(self, surface: pygame.Surface) -> None:
        arena = self.sim.world.arena
        for trail in self.trails:
            points = list(trail)
            n = len(points)
            for k in range(1, n):
                (x0, y0), (x1, y1) = points[k - 1], points[k]
                if abs(x1 - x0) > arena.width / 2 or abs(y1 - y0) > arena.height / 2:
                    continue  # wrapped around an edge
                fade = k / n
                color = tuple(int(b + (255 - b) * fade * 0.8) for b in BACKGROUND)
                pygame.draw.line(surface, color, self.to_screen(x0, y0), self.to_screen(x1, y1), 2)

    def draw_sources(self, surface: pygame.Surface) -> None:
        for name, stimulus in self.sim.world.stimuli.items():
            active = name == self.stimulus
            for s in stimulus.sources:
                center = self.to_screen(*s.position)
                if active:
                    pygame.draw.circle(surface, SOURCE_FILL, center, SOURCE_RADIUS)
                pygame.draw.circle(surface, SOURCE_FILL, center, SOURCE_RADIUS + 3, 2)

    def draw_vehicles(self, surface: pygame.Surface) -> None:
        for v in self.sim.vehicles:
            cx, cy = self.to_screen(v.x, v.y)
            length = 12
            # Screen y points down, so the screen angle is the negated heading.
            a = -v.heading
            points = [
                (cx + length * math.cos(a), cy + length * math.sin(a)),
                (cx + length * 0.6 * math.cos(a + 2.5), cy + length * 0.6 * math.sin(a + 2.5)),
                (cx + length * 0.6 * math.cos(a - 2.5), cy + length * 0.6 * math.sin(a - 2.5)),
            ]
            pygame.draw.polygon(surface, VEHICLE_FILL, points)
            pygame.draw.polygon(surface, VEHICLE_OUTLINE, points, 1)

    def draw_hud(self, surface: pygame.Surface) -> None:
        lines = [f"t = {self.sim.time:.1f}   x{self.steps_per_frame}"
                 + ("   PAUSED" if self.paused else ""),
                 f"stimulus: {self.stimulus or '-'}"]
        if len(self.sim.vehicles) == 1:
            v = self.sim.vehicles[0]
            lines.append(f"sensor {v.sensor_value:.2f}   speed {v.speed:.2f}")
        lines.append("space pause  Right step  R reset  T trail  Tab stimulus  +/- speed")
        y = 6
        for line in lines:
            text = self.font.render(line, True, TEXT)
            surface.blit(text, (8, y))
            y += text.get_height() + 2


def run_window(world: World) -> None:
    pygame.init()
    try:
        renderer = Renderer(world)
        screen = pygame.display.set_mode(renderer.size)
        pygame.display.set_caption(world.name)
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                running = renderer.handle(event) and running
            if not renderer.paused:
                renderer.advance(renderer.steps_per_frame)
            renderer.draw(screen)
            pygame.display.flip()
            clock.tick(FPS)
    finally:
        pygame.quit()
