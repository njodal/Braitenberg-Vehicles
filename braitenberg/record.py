"""Record a scenario to an animated GIF, without opening a window.

    python -m braitenberg.record scenarios/vehicle5-moth.yaml --seconds 40 --out moth.gif

Frames are drawn by the same renderer as the simulator window, panel included,
using SDL's dummy video driver. Needs Pillow (`pip install -e ".[record]"`).
"""

from __future__ import annotations

import argparse
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from braitenberg.render import Renderer  # noqa: E402
from braitenberg.scenario import load_scenario  # noqa: E402


def record(scenario_path: str, out: str, seconds: float, every: float = 0.1,
           speed: float = 2.0, scale: float = 0.6, seed: int | None = None) -> int:
    """Write a GIF of the first `seconds` of simulated time; return the number of frames.

    A frame is taken every `every` simulated seconds and played `speed` times faster.
    """
    scenario = load_scenario(scenario_path)
    if seed is not None:
        scenario.simulation.seed = seed
    pygame.init()
    try:
        renderer = Renderer(scenario)
        screen = pygame.display.set_mode(renderer.window_size)
        steps_per_frame = max(1, round(every / scenario.simulation.dt))
        size = tuple(round(n * scale) for n in renderer.window_size)
        frames = []
        for _ in range(round(seconds / (steps_per_frame * scenario.simulation.dt)) + 1):
            renderer.draw(screen)
            image = pygame.transform.smoothscale(screen, size)
            frames.append(Image.frombytes("RGB", size, pygame.image.tobytes(image, "RGB")))
            renderer.advance(steps_per_frame)
    finally:
        pygame.quit()
    duration = max(20, round(1000 * steps_per_frame * scenario.simulation.dt / speed))
    palette = frames[0].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    frames = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=duration, loop=0,
                   optimize=True)
    return len(frames)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m braitenberg.record",
                                     description="Record a scenario to an animated GIF.")
    parser.add_argument("scenario", help="scenario file")
    parser.add_argument("--out", required=True, help="GIF file to write")
    parser.add_argument("--seconds", type=float, default=20, help="simulated seconds to record")
    parser.add_argument("--every", type=float, default=0.1,
                        help="simulated seconds between frames (default 0.1)")
    parser.add_argument("--speed", type=float, default=2.0,
                        help="playback speed relative to simulated time (default 2)")
    parser.add_argument("--scale", type=float, default=0.6, help="image scale (default 0.6)")
    parser.add_argument("--seed", type=int, help="override simulation.seed")
    args = parser.parse_args(argv)
    n = record(args.scenario, args.out, args.seconds, args.every, args.speed, args.scale, args.seed)
    print(f"{args.out}: {n} frames")


if __name__ == "__main__":
    main()
