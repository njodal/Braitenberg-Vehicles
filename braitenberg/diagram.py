"""Draw a vehicle definition as a static SVG diagram, for specs and docs.

    python -m braitenberg.diagram vehicles/vehicle5-moth.yaml --out specs/images/vehicle5-moth.svg

It uses the same parts, positions and wires as the simulator's diagram panel
(specs/vehicle-diagram.md), drawn without live signals. It does not import pygame.
"""

from __future__ import annotations

import argparse
import copy
import math
from html import escape

from braitenberg.definition import VehicleDefinition, load_definition
from braitenberg.vehicle import Vehicle

RADIUS = 170            # pixels per body unit: the body spans [-1, 1]
LARGE_RADIUS = 380      # for a vehicle with cameras or arrays of units, which have many parts
MARGIN = 70
TITLE_HEIGHT = 50
LEGEND_HEIGHT = 40
EXCITATORY = "#2563eb"
INHIBITORY = "#dc2626"
INACTIVE = "#9ca3af"
LEARNING = "#7c3aed"    # Mnemotrix wires (Vehicle 7), whatever their sign
INK = "#1f2937"
DIM = "#6b7280"
PART_SIZE = {"sensor": 14, "motor": 17, "unit": 17}   # radius used to stop wires at the edge
UNIT_RADIUS = 16


LEGEND_COLUMNS = 2
WIRE_COLORS = {"exc": EXCITATORY, "inh": INHIBITORY, "off": INACTIVE, "learn": LEARNING}


GRID_WIDTH = 0.6        # body units: the width of a camera's or an array's grid of cells
MAX_CELL = 10           # pixels


def grid_size(shape, radius: float = RADIUS) -> tuple[float, float]:
    """Width and height, in pixels, of the grid of cells that draws a camera or an array."""
    rows, columns = shape if len(shape) == 2 else (1, shape[0])
    cell = min(MAX_CELL, GRID_WIDTH * radius / columns)
    return columns * cell, rows * cell


def edge(part, ux: float, uy: float, radius: float = RADIUS) -> float:
    """Distance from a part's center to its outline, in direction (ux, uy)."""
    if part.shape is None:
        return PART_SIZE[part.kind]
    w, h = grid_size(part.shape, radius)
    return min(w / 2 / abs(ux) if ux else math.inf, h / 2 / abs(uy) if uy else math.inf) + 2


def bundles(wires) -> list:
    """Wires between the same parts, with the same sign, drawn as one.

    Each element of an array, or pixel of a camera, has its own wires; drawn one by one they
    would hide the diagram. They are drawn as one arrow, labeled with the inputs as written
    (such as `lump[i]`), however many elements they connect.
    """
    groups, labels = {}, {}
    for w in wires:
        key = (w.source, w.target, w.sign, w.learning, w.active)
        if key in groups:
            first = groups[key]
            first.level = max(first.level, w.level)
            first.strength = max(first.strength, w.strength)
        else:
            groups[key] = copy.copy(w)
            labels[key] = []
        if w.label and w.label not in labels[key]:
            labels[key].append(w.label)
    for key, w in groups.items():
        w.label = ", ".join(labels[key])
    return list(groups.values())


def wire_kind(w) -> str:
    if w.learning:
        return "learn"
    return "off" if not w.active else "exc" if w.sign > 0 else "inh"


def definition_svg(definition: VehicleDefinition) -> str:
    diagram = Vehicle(definition, 0, 0, 0).diagram()
    diagram.wires = bundles(diagram.wires)
    legend = [("exc", "", "+ excitatory"), ("inh", "", "− inhibitory")]
    if any(not w.active and not w.learning for w in diagram.wires):
        legend.append(("off", ' stroke-dasharray="5,4"', "inactive (strength ≤ 0.7)"))
    if any(w.learning for w in diagram.wires):
        legend.append(("learn", "", "M learning (Mnemotrix)"))
    legend_rows = -(-len(legend) // LEGEND_COLUMNS)
    radius = LARGE_RADIUS if any(p.shape for p in diagram.parts) else RADIUS
    width = 2 * radius + 2 * MARGIN
    height = TITLE_HEIGHT + 2 * radius + 2 * MARGIN + LEGEND_HEIGHT * legend_rows
    cx, cy = width / 2, TITLE_HEIGHT + MARGIN + radius
    bw, bl = diagram.body   # the body's proportions
    parts = {p.name: p for p in diagram.parts}
    sensors = {s.name: s for s in definition.sensors}
    actuators = {a.name: a for a in definition.actuators}

    def at(position):
        return cx + position[0] * radius * bw, cy - position[1] * radius * bl

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Helvetica, Arial, sans-serif">',
        "<defs>",
        *(f'<marker id="arrow-{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
          f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
          f'fill="{color}"/></marker>'
          for name, color in WIRE_COLORS.items()),
        "</defs>",
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="{width / 2}" y="32" text-anchor="middle" font-size="20" font-weight="bold" '
        f'fill="{INK}">Vehicle {escape(definition.general.type)}: '
        f'{escape(definition.general.name)}</text>',
        f'<rect x="{cx - radius * bw:g}" y="{cy - radius * bl:g}" width="{2 * radius * bw:g}" '
        f'height="{2 * radius * bl:g}" rx="{radius * min(bw, bl) * 0.3:g}" fill="#f9fafb" '
        f'stroke="{DIM}" stroke-width="2"/>',
    ]

    pairs: dict[frozenset, int] = {}   # bundles between the same two parts are drawn side by side
    for w in diagram.wires:
        pairs[frozenset((w.source, w.target))] = pairs.get(frozenset((w.source, w.target)), 0) + 1
    drawn: dict[frozenset, int] = {}
    for w in diagram.wires:
        kind = wire_kind(w)
        color = WIRE_COLORS[kind]
        dash = ' stroke-dasharray="5,4"' if not w.active else ""
        # A learning wire is drawn wider the stronger it starts.
        stroke = f"{1.5 + 2.5 * w.strength:.1f}" if w.learning else "2"
        source, target = parts[w.source], parts[w.target]
        x1, y1 = at(source.position)
        if w.source == w.target:  # a unit feeding back into itself: a loop above it
            r = PART_SIZE[target.kind]
            out.append(f'<path d="M{x1 + r * 0.7:.1f},{y1 - r * 0.7:.1f} '
                       f'C{x1 + 3 * r:.1f},{y1 - 4 * r:.1f} {x1 + 4 * r:.1f},{y1 - r:.1f} '
                       f'{x1 + r:.1f},{y1:.1f}" fill="none" stroke="{color}" stroke-width="{stroke}"'
                       f'{dash} marker-end="url(#arrow-{kind})"/>')
            label_x, label_y = x1 + 3.4 * r, y1 - 2.6 * r
        else:
            x2, y2 = at(target.position)
            length = math.hypot(x2 - x1, y2 - y1) or 1
            ux, uy = (x2 - x1) / length, (y2 - y1) / length
            pair = frozenset((w.source, w.target))
            k = drawn[pair] = drawn.get(pair, -1) + 1
            shift = (k - (pairs[pair] - 1) / 2) * 6
            x1, y1, x2, y2 = x1 - uy * shift, y1 + ux * shift, x2 - uy * shift, y2 + ux * shift
            start = edge(source, ux, uy, radius)
            end = edge(target, ux, uy, radius) + 2
            out.append(f'<line x1="{x1 + ux * start:.1f}" y1="{y1 + uy * start:.1f}" '
                       f'x2="{x2 - ux * end:.1f}" y2="{y2 - uy * end:.1f}" stroke="{color}" '
                       f'stroke-width="{stroke}"{dash} marker-end="url(#arrow-{kind})"/>')
            # The sign sits near the target, beside the wire, so crossed wires do not share it.
            label_x = x1 + 0.8 * (x2 - x1) - uy * 9
            label_y = y1 + 0.8 * (y2 - y1) + ux * 9
        sign = ("+" if w.sign > 0 else "−") + ("M" if w.learning else "")
        out.append(f'<text x="{label_x:.1f}" y="{label_y + 5:.1f}" text-anchor="middle" '
                   f'font-size="15" font-weight="bold" fill="{color}">{sign}</text>')
        if w.label and w.source != w.target:
            # Which pixels or elements it takes, beside the wire, past its middle.
            sx, ex = x1 + ux * start, x2 - ux * end
            sy, ey = y1 + uy * start, y2 - uy * end
            lx, ly = sx + 0.6 * (ex - sx) - uy * 8, sy + 0.6 * (ey - sy) + ux * 8
            anchor = "start" if -uy > 0.3 else "end" if -uy < -0.3 else "middle"
            out.append(f'<text x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}" font-size="10" '
                       f'font-style="italic" fill="{DIM}">{escape(w.label)}</text>')

    for p in diagram.parts:
        x, y = at(p.position)
        if p.kind == "sensor":
            for dx in (-8, 8):
                out.append(f'<line x1="{x}" y1="{y}" x2="{x + dx}" y2="{y - 24}" stroke="{INK}" '
                           f'stroke-width="2"/>')
            out.append(f'<circle cx="{x}" cy="{y}" r="13" fill="#fde68a" stroke="{INK}" '
                       f'stroke-width="2"/>')
            caption = [p.name, sensor_caption(sensors[p.name])]
        elif p.kind == "motor":
            out.append(f'<rect x="{x - 17}" y="{y - 11}" width="34" height="22" rx="4" '
                       f'fill="#c7d2fe" stroke="{INK}" stroke-width="2"/>')
            a = actuators[p.name]
            caption = [p.name] + ([f"gain {a.gain:g} \u00b7 base {a.base_speed:g}"]
                                  if (a.gain, a.base_speed) != (1, 0) else [])
        elif p.shape is not None:
            # A camera or an array of units: a grid of cells, one per pixel or element.
            w, h = grid_size(p.shape, radius)
            rows, columns = p.shape if len(p.shape) == 2 else (1, p.shape[0])
            cell = w / columns
            fill = "#fde68a" if p.kind == "camera" else "white"
            out += [f'<rect x="{x - w / 2 + c * cell:.1f}" y="{y - h / 2 + r * cell:.1f}" '
                    f'width="{cell:.1f}" height="{cell:.1f}" fill="{fill}" stroke="{INK}" '
                    f'stroke-width="0.5"/>' for r in range(rows) for c in range(columns)]
            out.append(f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" '
                       f'height="{h:.1f}" fill="none" stroke="{INK}" stroke-width="1.5"/>')
            size = "×".join(str(n) for n in p.shape)
            if p.kind == "module":
                caption = [p.name, p.label]
            elif p.kind == "camera":
                s = sensors[p.name]
                caption = [p.name, f"{sensor_caption(s)}, {size} px, "
                                   f"{s.field_of_view:g}°×{s.camera.vertical_field_of_view:g}°"]
            else:
                caption = [f"{p.name} [{size}]", f"threshold {p.threshold:g}"]
        else:
            # A unit: a circle with its threshold inside.
            out.append(f'<circle cx="{x}" cy="{y}" r="{UNIT_RADIUS}" fill="white" stroke="{INK}" '
                       f'stroke-width="2"/>')
            out.append(f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-size="11" '
                       f'font-weight="bold" fill="{INK}">{p.threshold:g}</text>')
            caption = [p.name]
        below = (UNIT_RADIUS + 15 if p.kind == "unit"
                 else grid_size(p.shape, radius)[1] / 2 + 14 if p.shape is not None else 28)
        for i, text in enumerate(caption):
            out.append(f'<text x="{x}" y="{y + below + 13 * i}" text-anchor="middle" '
                       f'font-size="{12 if i == 0 else 10}" fill="{INK if i == 0 else DIM}">'
                       f'{escape(text)}</text>')

    for i, (kind, dash, text) in enumerate(legend):
        row, column = divmod(i, LEGEND_COLUMNS)
        x = MARGIN + 180 * column
        legend_y = height - LEGEND_HEIGHT * (legend_rows - row - 0.5)
        out.append(f'<line x1="{x}" y1="{legend_y}" x2="{x + 30}" y2="{legend_y}" '
                   f'stroke="{WIRE_COLORS[kind]}" stroke-width="2"{dash} '
                   f'marker-end="url(#arrow-{kind})"/>')
        out.append(f'<text x="{x + 40}" y="{legend_y + 4}" font-size="12" fill="{INK}">'
                   f'{escape(text)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def sensor_caption(sensor) -> str:
    """The stimulus a sensor reads, and its response when it is not linear."""
    r = sensor.response
    height = f", height {r.height:g}" if r.height != 1 else ""
    if r.type == "peak":
        return f"{sensor.type}, peak at {r.at:g} \u00b1{r.width:g}{height}"
    if r.type == "step":
        return f"{sensor.type}, step at {r.at:g}{height}"
    return sensor.type


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m braitenberg.diagram",
                                     description="Draw a vehicle definition as an SVG diagram.")
    parser.add_argument("definition", help="vehicle definition file")
    parser.add_argument("--out", required=True, help="SVG file to write")
    args = parser.parse_args(argv)
    with open(args.out, "w") as f:
        f.write(definition_svg(load_definition(args.definition)))
    print(args.out)


if __name__ == "__main__":
    main()
