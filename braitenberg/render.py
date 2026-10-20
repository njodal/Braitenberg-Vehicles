"""Real-time pygame renderer. The only module that imports pygame.

It reads the simulation state and draws it; user interaction (dragging sources,
pausing, resetting) changes only the running simulation, never the files.

Keys: space pause/resume, right arrow step (when paused), R reset, T trail,
Tab next stimulus, +/- simulation speed, Esc quit. Drag sources with the mouse;
click a vehicle to show it in the diagram panel (specs/vehicle-diagram.md).
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np
import pygame

from braitenberg.sim import Simulation
from braitenberg.vehicle import Diagram
from braitenberg.scenario import Scenario
from braitenberg.world import Source

MAX_WINDOW_SIDE = 720
PANEL_WIDTH = 420
ROW = 20                  # height of one readout line in the panel
MAX_DIAGRAM_RADIUS = 150
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
SELECTED_RING = (120, 220, 255)
PANEL_BG = (22, 24, 34)
PANEL_BORDER = (60, 64, 84)
PANEL_DIM = (150, 155, 175)
BODY_OUTLINE = (180, 185, 205)
WIRE_OFF = (60, 64, 90)
WIRE_ON = (255, 230, 140)
WIRE_INACTIVE = (70, 74, 96)


def heat_colors(values: np.ndarray) -> np.ndarray:
    """Map values in [0, 1] to RGB through HEAT_STOPS."""
    pos = np.clip(values, 0, 1) * (len(HEAT_STOPS) - 1)
    i = np.minimum(pos.astype(int), len(HEAT_STOPS) - 2)
    frac = (pos - i)[..., None]
    return (HEAT_STOPS[i] * (1 - frac) + HEAT_STOPS[i + 1] * frac).astype(np.uint8)


class Renderer:
    def __init__(self, scenario: Scenario):
        self.original = scenario
        world = scenario.world
        arena = world.arena
        self.scale = MAX_WINDOW_SIDE / max(arena.width, arena.height)
        self.size = (round(arena.width * self.scale), round(arena.height * self.scale))
        self.window_size = (self.size[0] + PANEL_WIDTH, self.size[1])
        self.stimulus_names = list(world.stimuli)
        sensors = [s for p in scenario.vehicles for s in p.definition.sensors]
        first_sensor = sensors[0].type if sensors else None
        self.stimulus_index = (self.stimulus_names.index(first_sensor)
                               if first_sensor in self.stimulus_names else 0)
        self.show_trail = True
        self.paused = False
        # About 0.05 simulated seconds per frame, whatever the time step.
        self.steps_per_frame = max(1, round(0.05 / scenario.simulation.dt))
        self.dragging: tuple[str, int] | None = None
        self.selected = 0
        self.font = pygame.font.Font(None, 20)
        self.title_font = pygame.font.Font(None, 26)
        self.small_font = pygame.font.Font(None, 17)
        self.reset()

    # --- state ---

    def reset(self) -> None:
        self.sim = Simulation(self.original)
        self.trails = [deque(maxlen=TRAIL_LENGTH) for _ in self.sim.vehicles]
        self.record_trails()
        self.heatmap = None
        if self.selected >= len(self.sim.vehicles):
            self.selected = 0

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
            if self.dragging is None:
                picked = self.vehicle_at(event.pos)
                if picked is not None:
                    self.selected = picked
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

    def vehicle_at(self, pos) -> int | None:
        if pos[0] >= self.size[0]:
            return None
        best, best_d = None, GRAB_RADIUS
        for i, v in enumerate(self.sim.vehicles):
            vx, vy = self.to_screen(v.x, v.y)
            d = math.hypot(pos[0] - vx, pos[1] - vy)
            if d <= best_d:
                best, best_d = i, d
        return best

    # --- drawing ---

    def draw(self, surface: pygame.Surface) -> None:
        self.draw_field(surface)
        if self.show_trail:
            self.draw_trails(surface)
        self.draw_sources(surface)
        self.draw_vehicles(surface)
        self.draw_hud(surface)
        self.draw_panel(surface)

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
            length = max(v.half_size * self.scale, 8)
            # Screen y points down, so the screen angle is the negated heading.
            a = -v.heading
            points = [
                (cx + length * math.cos(a), cy + length * math.sin(a)),
                (cx + length * 0.6 * math.cos(a + 2.5), cy + length * 0.6 * math.sin(a + 2.5)),
                (cx + length * 0.6 * math.cos(a - 2.5), cy + length * 0.6 * math.sin(a - 2.5)),
            ]
            pygame.draw.polygon(surface, VEHICLE_FILL, points)
            pygame.draw.polygon(surface, VEHICLE_OUTLINE, points, 1)
        if self.sim.vehicles:
            v = self.sim.vehicles[self.selected]
            pygame.draw.circle(surface, SELECTED_RING, self.to_screen(v.x, v.y),
                               max(v.half_size * self.scale, 8) + 5, 2)

    def draw_hud(self, surface: pygame.Surface) -> None:
        lines = [f"t = {self.sim.time:.1f}   x{self.steps_per_frame}"
                 + ("   PAUSED" if self.paused else ""),
                 f"stimulus: {self.stimulus or '-'}",
                 "space pause  Right step  R reset  T trail  +/- speed",
                 "Tab stimulus  drag source  click vehicle"]
        y = 6
        for line in lines:
            text = self.font.render(line, True, TEXT)
            surface.blit(text, (8, y))
            y += text.get_height() + 2


    # --- diagram panel ---

    def draw_panel(self, surface: pygame.Surface) -> None:
        left, height = self.size[0], self.size[1]
        surface.fill(PANEL_BG, (left, 0, PANEL_WIDTH, height))
        pygame.draw.line(surface, PANEL_BORDER, (left, 0), (left, height), 2)
        x0 = left + 16
        if not self.sim.vehicles:
            surface.blit(self.font.render("No vehicles in this scenario", True, PANEL_DIM),
                         (x0, 16))
            return
        diagram = self.sim.vehicles[self.selected].diagram()
        surface.blit(self.title_font.render(diagram.title, True, TEXT), (x0, 14))
        surface.blit(self.font.render(diagram.subtitle, True, PANEL_DIM), (x0, 38))
        # Readouts and vehicle values fill the bottom; the diagram gets the space above them.
        readouts_top = height - 10 - ROW * (len(diagram.parts) + 2) - 8
        top = 62
        radius = min(MAX_DIAGRAM_RADIUS, (PANEL_WIDTH - 60) / 2, (readouts_top - top - 60) / 2)
        center = (left + PANEL_WIDTH // 2, top + 30 + radius)
        self.draw_diagram(surface, diagram, center, radius)
        y = self.draw_readouts(surface, diagram, x0, min(readouts_top, center[1] + radius + 24))
        self.draw_params(surface, diagram, x0, y + 8)

    def draw_diagram(self, surface: pygame.Surface, diagram: Diagram,
                     center: tuple[int, int], radius: float) -> None:
        def at(position):  # body coordinates (+y forward) to screen
            return center[0] + position[0] * radius, center[1] - position[1] * radius

        body = pygame.Rect(0, 0, 2 * radius, 2 * radius)  # the body spans [-1, 1] on both axes
        body.center = center
        pygame.draw.rect(surface, BODY_OUTLINE, body, 2, border_radius=int(radius * 0.3))

        parts = {p.name: p for p in diagram.parts}
        for w in diagram.wires:
            a, b = at(parts[w.source].position), at(parts[w.target].position)
            color = lerp_color(WIRE_OFF, WIRE_ON, w.level) if w.active else WIRE_INACTIVE
            width = 4 if w.active else 1
            if w.source == w.target:  # a unit feeding back into itself
                pygame.draw.circle(surface, color, (a[0] + 12, a[1] - 12), 12, min(width, 3))
                label_at = (a[0] + 26, a[1] - 30)
            else:
                pygame.draw.line(surface, color, a, b, width)
                # Near the target, so crossed wires do not label the same spot.
                label_at = (a[0] + 0.85 * (b[0] - a[0]) + 8, a[1] + 0.85 * (b[1] - a[1]) - 22)
            surface.blit(self.title_font.render("+" if w.sign > 0 else "-", True, color), label_at)

        for p in diagram.parts:
            x, y = at(p.position)
            fill = tuple(int(c) for c in heat_colors(np.array(p.level)))
            if p.kind == "sensor":
                # A round sensor with two short antennae pointing forward.
                for dx in (-9, 9):
                    pygame.draw.line(surface, BODY_OUTLINE, (x, y), (x + dx, y - 22), 2)
                pygame.draw.circle(surface, fill, (x, y), 13)
                pygame.draw.circle(surface, BODY_OUTLINE, (x, y), 13, 2)
            elif p.kind == "motor":
                rect = pygame.Rect(0, 0, 34, 22)
                rect.center = (x, y)
                pygame.draw.rect(surface, fill, rect, border_radius=4)
                pygame.draw.rect(surface, BODY_OUTLINE, rect, 2, border_radius=4)
            else:
                pygame.draw.circle(surface, fill, (x, y), 10)
                pygame.draw.circle(surface, BODY_OUTLINE, (x, y), 10, 2)
            label = self.small_font.render(p.name, True, PANEL_DIM)
            surface.blit(label, (x - label.get_width() / 2, y + 15))

    def draw_readouts(self, surface: pygame.Surface, diagram: Diagram, x0: int, y: int) -> int:
        """One line per part: name and label, a level bar, and the value."""
        width = PANEL_WIDTH - 32
        bar_x, bar_width = x0 + 200, width - 200 - 52
        for p in diagram.parts:
            name = self.font.render(p.name, True, TEXT)
            surface.blit(name, (x0, y + 2))
            surface.blit(self.small_font.render(p.label, True, PANEL_DIM),
                         (x0 + name.get_width() + 6, y + 4))
            pygame.draw.rect(surface, PANEL_BORDER, (bar_x, y + 7, bar_width, 6), border_radius=3)
            filled = round(bar_width * p.level)
            if filled:
                color = tuple(int(c) for c in heat_colors(np.array(p.level)))
                pygame.draw.rect(surface, color, (bar_x, y + 7, filled, 6), border_radius=3)
            value = self.font.render(f"{p.value:.2f}", True, TEXT)
            surface.blit(value, (x0 + width - value.get_width(), y + 2))
            y += ROW
        return y

    def draw_params(self, surface: pygame.Surface, diagram: Diagram, x0: int, y: int) -> None:
        items = [f"{name} {value}" for name, value in diagram.params.items()]
        for line in ("   ".join(items[:2]), "   ".join(items[2:])):
            surface.blit(self.font.render(line, True, PANEL_DIM), (x0, y + 2))
            y += ROW


def lerp_color(a, b, t: float) -> tuple[int, int, int]:
    t = min(max(t, 0.0), 1.0)
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def run_window(scenario: Scenario) -> None:
    pygame.init()
    try:
        renderer = Renderer(scenario)
        screen = pygame.display.set_mode(renderer.window_size)
        pygame.display.set_caption(scenario.name)
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
