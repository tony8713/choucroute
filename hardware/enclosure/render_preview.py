"""Isometric preview render of the enclosure STL -> preview.png.

Offline, headless (matplotlib) — no GL/browser needed. Not a CAD validation,
just a visual for the repo and Laurent.
"""

import sys

import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from stl import mesh as stlmesh


def render(stl_path="earbox_v1.stl", out_path="preview.png"):
    m = stlmesh.Mesh.from_file(stl_path)
    tris = m.vectors  # (n, 3, 3)

    fig = plt.figure(figsize=(8, 9), dpi=140)
    ax = fig.add_subplot(111, projection="3d")

    # simple lambert-ish shade from face normals
    n = m.normals.copy()
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n = n / ln
    light = np.array([0.4, -0.6, 0.7])
    light = light / np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.clip(n @ light, 0, 1)
    base = np.array([0.30, 0.55, 0.85])
    colors = np.clip(shade[:, None] * base[None, :], 0, 1)

    coll = Poly3DCollection(tris, facecolors=colors, edgecolors=(0, 0, 0, 0.06),
                            linewidths=0.2)
    ax.add_collection3d(coll)

    pts = tris.reshape(-1, 3)
    mins, maxs = pts.min(0), pts.max(0)
    ctr = (mins + maxs) / 2
    span = (maxs - mins).max() / 2 * 1.05
    ax.set_xlim(ctr[0] - span, ctr[0] + span)
    ax.set_ylim(ctr[1] - span, ctr[1] + span)
    ax.set_zlim(ctr[2] - span, ctr[2] + span)
    try:
        ax.set_box_aspect((1, 1, 1))
    except Exception:
        pass
    ax.view_init(elev=22, azim=-58)
    ax.set_axis_off()
    ax.set_title("earbox enclosure v1 — Orin base + decoupled reSpeaker cup",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    print("wrote", out_path)


if __name__ == "__main__":
    render(*(sys.argv[1:3] or ()))
