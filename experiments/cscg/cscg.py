"""A clone-structured cognitive graph (CSCG) that learns a traffic light's sequence.

An exploration, not part of the simulator: see README.md next to this file.

    python experiments/cscg/cscg.py            # graphs and predictions as text
    python experiments/cscg/cscg.py --plot     # also save predictions.png
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np

COLORS = "VAR"  # green (verde), yellow (amarillo), red


@dataclass
class CSCG:
    """A cloned HMM: each color has n_clones hidden states that can only emit it."""

    T: np.ndarray  # transitions between all clones, rows sum to 1 (or 0 if unused)
    n_clones: int

    def clones(self, color: str) -> slice:
        i = COLORS.index(color)
        return slice(i * self.n_clones, (i + 1) * self.n_clones)

    def name(self, state: int) -> str:
        return f"{COLORS[state // self.n_clones]}{state % self.n_clones}"

    def edges(self) -> dict[tuple[int, int], float]:
        return {(int(u), int(v)): float(self.T[u, v]) for u, v in zip(*np.nonzero(self.T))}

    def predict(self, seen: str) -> list[dict[str, float]]:
        """After each color seen, the probability of each color on the next tick."""
        belief = np.zeros(len(self.T))
        belief[self.clones(seen[0])] = 1
        belief *= self.T.sum(1) > 0  # only clones that were used
        belief /= belief.sum()
        out = []
        for t, color in enumerate(seen):
            if t:
                belief = belief @ self.T
                mask = np.zeros_like(belief)
                mask[self.clones(color)] = 1
                belief *= mask
                belief /= belief.sum()
            ahead = belief @ self.T
            out.append({c: float(ahead[self.clones(c)].sum()) for c in COLORS})
        return out


def train(seq: str, n_clones: int = 6, iters: int = 100, seed: int = 0) -> CSCG:
    """Soft EM on the transitions, then Viterbi EM to make them sparse, as in George et al. 2021."""
    rng = np.random.default_rng(seed)
    x = [COLORS.index(c) for c in seq]
    n, S = n_clones, len(COLORS) * n_clones
    cl = [slice(i * n, (i + 1) * n) for i in range(len(COLORS))]
    T = rng.random((S, S))
    T /= T.sum(1, keepdims=True)

    for _ in range(iters):
        a = np.zeros((len(x), n))
        a[0] = 1 / n
        for t in range(1, len(x)):
            a[t] = a[t - 1] @ T[cl[x[t - 1]], cl[x[t]]]
            a[t] /= a[t].sum()
        b = np.ones((len(x), n))
        for t in range(len(x) - 2, -1, -1):
            b[t] = T[cl[x[t]], cl[x[t + 1]]] @ b[t + 1]
            b[t] /= b[t].sum()
        C = np.zeros((S, S))
        for t in range(len(x) - 1):
            xi = a[t][:, None] * T[cl[x[t]], cl[x[t + 1]]] * b[t + 1][None, :]
            C[cl[x[t]], cl[x[t + 1]]] += xi / xi.sum()
        T = C + 1e-3
        T /= T.sum(1, keepdims=True)

    for _ in range(20):
        states = viterbi(T, x, n)
        C = np.zeros((S, S))
        np.add.at(C, (states[:-1], states[1:]), 1)
        T = C + 1e-6
        T /= T.sum(1, keepdims=True)
    # keep only the transitions the decoded sequence uses
    C = np.zeros((S, S))
    np.add.at(C, (states[:-1], states[1:]), 1)
    return CSCG(C / np.maximum(C.sum(1, keepdims=True), 1), n)


def viterbi(T: np.ndarray, x: list[int], n: int) -> np.ndarray:
    a = np.zeros((len(x), n))
    a[0] = 1 / n
    ptr = np.zeros((len(x), n), int)
    for t in range(1, len(x)):
        M = a[t - 1][:, None] * T[x[t - 1] * n:(x[t - 1] + 1) * n, x[t] * n:(x[t] + 1) * n]
        ptr[t], a[t] = M.argmax(0), M.max(0)
        a[t] /= a[t].sum()
    path = np.zeros(len(x), int)
    path[-1] = a[-1].argmax()
    for t in range(len(x) - 1, 0, -1):
        path[t - 1] = ptr[t][path[t]]
    return np.array(x) * n + path


def ring(model: CSCG, start: str = "V") -> list[int]:
    """The clones in the order the cycle visits them, following the likeliest transition."""
    edges = model.edges()
    out = {u: max((v for (uu, v) in edges if uu == u), key=lambda v: edges[(u, v)]) for (u, _) in edges}
    # start at the clone entered from a red one
    first = next(v for (u, v) in edges if COLORS[u // model.n_clones] == "R" and COLORS[v // model.n_clones] == start)
    order, s = [first], out[first]
    while s != first:
        order.append(s)
        s = out[s]
    return order


def mermaid(model: CSCG) -> str:
    """The learned graph as a Mermaid flowchart, clones numbered in the order of the cycle."""
    order = ring(model)
    used = sorted({s for e in model.edges() for s in e})
    count = {c: 0 for c in COLORS}
    label = {}
    for s in order + [s for s in used if s not in order]:
        c = COLORS[s // model.n_clones]
        count[c] += 1
        label[s] = f"{c}{count[c]}"
    lines = ["flowchart LR"]
    for (u, v), p in sorted(model.edges().items(), key=lambda e: (order + used).index(e[0][0])):
        arrow = "-->" if p > 0.999 else f"-- {p:.2f} -->"
        lines.append(f"  {label[u]} {arrow} {label[v]}")
    fill = {"V": "#97C459", "A": "#EF9F27", "R": "#F09595"}
    for c in COLORS:
        names = ",".join(sorted(label[s] for s in used if COLORS[s // model.n_clones] == c))
        lines.append(f"  classDef {c} fill:{fill[c]},stroke:#444")
        lines.append(f"  class {names} {c}")
    return "\n".join(lines)


def fixed_light(cycles: int = 150) -> str:
    return "VVVVVAAARRRR" * cycles


def varying_light(cycles: int = 150, seed: int = 1) -> str:
    """Each color lasts one tick more or less than in fixed_light, at random."""
    rng = np.random.default_rng(seed)
    return "".join("V" * rng.integers(4, 7) + "A" * rng.integers(2, 5) + "R" * rng.integers(3, 6) for _ in range(cycles))


CASES = [
    ("Fixed, first cycle", fixed_light, "VVVVVAAARRRR"),
    ("Fixed, second cycle", fixed_light, "VVVVVAAARRRR" * 2),
    ("Varying, after one cycle", varying_light, "VVVVVAAARRRR" + "VVVVVVAARRRRR"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plot", action="store_true", help="save predictions.png next to this file")
    args = parser.parse_args()
    models = {f: train(f()) for f in (fixed_light, varying_light)}
    for f, model in models.items():
        print(f"{f.__name__}: {len(ring(model))} clones in the ring\n{mermaid(model)}\n")
    rows = []
    for title, f, seen in CASES:
        shown = seen[-13:] if title.startswith("Varying") else seen[-12:]
        preds = models[f].predict(seen)[-len(shown):]
        rows.append((title, shown, preds))
        print(title)
        for c, p in zip(shown, preds):
            print(f"  sees {c}  next " + "  ".join(f"{k} {v:.2f}" for k, v in p.items()))
    if args.plot:
        plot(rows, Path(__file__).with_name("predictions.png"))


def plot(rows, path: Path) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    rgb = {"V": "#639922", "A": "#EF9F27", "R": "#E24B4A"}
    fig, axes = plt.subplots(len(rows), 1, figsize=(8, 1.6 * len(rows)))
    for ax, (title, seen, preds) in zip(axes, rows):
        for i, c in enumerate(COLORS):
            cmap = LinearSegmentedColormap.from_list(c, ["white", rgb[c]])
            for t, p in enumerate(preds):
                ax.add_patch(plt.Rectangle((t, 2 - i), 0.95, 0.9, color=cmap(p[c])))
                if p[c] > 0:
                    ax.text(t + 0.47, 2.45 - i, f"{round(100 * p[c])}", ha="center", va="center", fontsize=7,
                            color="white" if p[c] > 0.55 else "#555")
        for t, c in enumerate(seen):
            ax.add_patch(plt.Rectangle((t, 3.1), 0.95, 0.9, color=rgb[c]))
            ax.text(t + 0.47, 3.55, c, ha="center", va="center", fontsize=8, color="white")
        ax.set_xlim(0, len(seen))
        ax.set_ylim(0, 4.1)
        ax.set_yticks([0.45, 1.45, 2.45, 3.55], ["next R", "next A", "next V", "sees"], fontsize=8)
        ax.set_xticks([])
        ax.set_title(title, fontsize=9, loc="left")
        for side in ax.spines.values():
            side.set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"saved {path}")


if __name__ == "__main__":
    main()
