"""Draw a vehicle definition as a static SVG diagram, for specs and docs.

    python -m braitenberg.diagram vehicles/vehicle5-moth.yaml --out specs/images/vehicle5-moth.svg

It uses the same parts, positions and wires as the simulator's diagram panel
(specs/vehicle-diagram.md), drawn without live signals. It does not import pygame.
"""

from __future__ import annotations

import argparse
import math
from html import escape

from braitenberg.definition import VehicleDefinition, load_definition
from braitenberg.vehicle import Vehicle

RADIUS = 170            # pixels per body unit: the body spans [-1, 1]
MARGIN = 70
TITLE_HEIGHT = 50
LEGEND_HEIGHT = 40
EXCITATORY = "#2563eb"
INHIBITORY = "#dc2626"
INACTIVE = "#9ca3af"
INK = "#1f2937"
DIM = "#6b7280"
PART_SIZE = {"sensor": 14, "motor": 17, "unit": 12}   # radius used to stop wires at the edge


def definition_svg(definition: VehicleDefinition) -> str:
    diagram = Vehicle(definition, 0, 0, 0).diagram()
    width = 2 * RADIUS + 2 * MARGIN
    height = TITLE_HEIGHT + 2 * RADIUS + 2 * MARGIN + LEGEND_HEIGHT
    cx, cy = width / 2, TITLE_HEIGHT + MARGIN + RADIUS
    parts = {p.name: p for p in diagram.parts}
    sensor_types = {s.name: s.type for s in definition.sensors}

    def at(position):
        return cx + position[0] * RADIUS, cy - position[1] * RADIUS

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Helvetica, Arial, sans-serif">',
        "<defs>",
        *(f'<marker id="arrow-{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
          f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
          f'fill="{color}"/></marker>'
          for name, color in (("exc", EXCITATORY), ("inh", INHIBITORY), ("off", INACTIVE))),
        "</defs>",
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="{width / 2}" y="32" text-anchor="middle" font-size="20" font-weight="bold" '
        f'fill="{INK}">Vehicle {escape(definition.general.type)}: '
        f'{escape(definition.general.name)}</text>',
        f'<rect x="{cx - RADIUS}" y="{cy - RADIUS}" width="{2 * RADIUS}" height="{2 * RADIUS}" '
        f'rx="{RADIUS * 0.3}" fill="#f9fafb" stroke="{DIM}" stroke-width="2"/>',
    ]

    for w in diagram.wires:
        kind = "off" if not w.active else "exc" if w.sign > 0 else "inh"
        color = {"exc": EXCITATORY, "inh": INHIBITORY, "off": INACTIVE}[kind]
        dash = ' stroke-dasharray="5,4"' if not w.active else ""
        source, target = parts[w.source], parts[w.target]
        x1, y1 = at(source.position)
        if w.source == w.target:  # a unit feeding back into itself: a loop above it
            r = PART_SIZE[target.kind]
            out.append(f'<path d="M{x1 + r * 0.7:.1f},{y1 - r * 0.7:.1f} '
                       f'C{x1 + 3 * r:.1f},{y1 - 4 * r:.1f} {x1 + 4 * r:.1f},{y1 - r:.1f} '
                       f'{x1 + r:.1f},{y1:.1f}" fill="none" stroke="{color}" stroke-width="2"'
                       f'{dash} marker-end="url(#arrow-{kind})"/>')
            label_x, label_y = x1 + 3.4 * r, y1 - 2.6 * r
        else:
            x2, y2 = at(target.position)
            length = math.hypot(x2 - x1, y2 - y1) or 1
            ux, uy = (x2 - x1) / length, (y2 - y1) / length
            start = PART_SIZE[source.kind]
            end = PART_SIZE[target.kind] + 2
            out.append(f'<line x1="{x1 + ux * start:.1f}" y1="{y1 + uy * start:.1f}" '
                       f'x2="{x2 - ux * end:.1f}" y2="{y2 - uy * end:.1f}" stroke="{color}" '
                       f'stroke-width="2"{dash} marker-end="url(#arrow-{kind})"/>')
            # The sign sits near the target, beside the wire, so crossed wires do not share it.
            label_x = x1 + 0.8 * (x2 - x1) - uy * 9
            label_y = y1 + 0.8 * (y2 - y1) + ux * 9
        sign = "+" if w.sign > 0 else "−"
        out.append(f'<text x="{label_x:.1f}" y="{label_y + 5:.1f}" text-anchor="middle" '
                   f'font-size="15" font-weight="bold" fill="{color}">{sign}</text>')

    for p in diagram.parts:
        x, y = at(p.position)
        if p.kind == "sensor":
            for dx in (-8, 8):
                out.append(f'<line x1="{x}" y1="{y}" x2="{x + dx}" y2="{y - 24}" stroke="{INK}" '
                           f'stroke-width="2"/>')
            out.append(f'<circle cx="{x}" cy="{y}" r="13" fill="#fde68a" stroke="{INK}" '
                       f'stroke-width="2"/>')
            caption = [p.name, sensor_types[p.name]]
        elif p.kind == "motor":
            out.append(f'<rect x="{x - 17}" y="{y - 11}" width="34" height="22" rx="4" '
                       f'fill="#c7d2fe" stroke="{INK}" stroke-width="2"/>')
            caption = [p.name]
        else:
            out.append(f'<circle cx="{x}" cy="{y}" r="11" fill="white" stroke="{INK}" '
                       f'stroke-width="2"/>')
            caption = [p.name, p.label]
        for i, text in enumerate(caption):
            out.append(f'<text x="{x}" y="{y + 28 + 13 * i}" text-anchor="middle" '
                       f'font-size="{12 if i == 0 else 10}" fill="{INK if i == 0 else DIM}">'
                       f'{escape(text)}</text>')

    legend_y = height - LEGEND_HEIGHT / 2
    items = [("exc", EXCITATORY, "", "+ excitatory"), ("inh", INHIBITORY, "", "− inhibitory")]
    if any(not w.active for w in diagram.wires):
        items.append(("off", INACTIVE, ' stroke-dasharray="5,4"', "inactive (strength ≤ 0.7)"))
    x = MARGIN
    for kind, color, dash, text in items:
        out.append(f'<line x1="{x}" y1="{legend_y}" x2="{x + 30}" y2="{legend_y}" stroke="{color}" '
                   f'stroke-width="2"{dash} marker-end="url(#arrow-{kind})"/>')
        out.append(f'<text x="{x + 40}" y="{legend_y + 4}" font-size="12" fill="{INK}">'
                   f'{escape(text)}</text>')
        x += 170
    out.append("</svg>")
    return "\n".join(out) + "\n"


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
