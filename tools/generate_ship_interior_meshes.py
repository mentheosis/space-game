#!/usr/bin/env python3
"""Generate project-authored ShuttleA interior OBJ meshes.

The meshes are deliberately simple enough to maintain in source control, but
they avoid the blockout problem of filled rib slabs and rectangular wall boxes.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/ship/interior"


class ObjWriter:
    def __init__(self, name: str) -> None:
        self.name = name
        self.vertices: list[tuple[float, float, float]] = []
        self.faces: list[tuple[int, ...]] = []

    def v(self, x: float, y: float, z: float) -> int:
        self.vertices.append((x, y, z))
        return len(self.vertices)

    def face(self, *indexes: int) -> None:
        self.faces.append(indexes)

    def quad(self, a: int, b: int, c: int, d: int, double_sided: bool = False) -> None:
        self.face(a, b, c, d)
        if double_sided:
            self.face(d, c, b, a)

    def write(self, path: Path, comment: str) -> None:
        lines = [f"# {comment}", f"o {self.name}"]
        for x, y, z in self.vertices:
            lines.append(f"v {x:.4f} {y:.4f} {z:.4f}")
        for face in self.faces:
            lines.append("f " + " ".join(str(index) for index in face))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_cabin_rib_frame() -> None:
    """Open U-frame ring; no filled center faces."""
    obj = ObjWriter("cabin_rib_frame")
    outer = [
        (-2.26, -1.02),
        (-2.18, -0.18),
        (-1.95, 0.72),
        (-1.34, 1.18),
        (0.0, 1.34),
        (1.34, 1.18),
        (1.95, 0.72),
        (2.18, -0.18),
        (2.26, -1.02),
    ]
    inner = [
        (-1.92, -0.86),
        (-1.84, -0.14),
        (-1.58, 0.52),
        (-1.08, 0.88),
        (0.0, 1.02),
        (1.08, 0.88),
        (1.58, 0.52),
        (1.84, -0.14),
        (1.92, -0.86),
    ]
    front_outer = [obj.v(x, y, -0.08) for x, y in outer]
    front_inner = [obj.v(x, y, -0.08) for x, y in inner]
    back_outer = [obj.v(x, y, 0.08) for x, y in outer]
    back_inner = [obj.v(x, y, 0.08) for x, y in inner]

    for i in range(len(outer) - 1):
        obj.quad(front_outer[i], front_outer[i + 1], front_inner[i + 1], front_inner[i], True)
        obj.quad(back_outer[i + 1], back_outer[i], back_inner[i], back_inner[i + 1], True)
        obj.quad(front_outer[i + 1], back_outer[i + 1], back_inner[i + 1], front_inner[i + 1], True)
        obj.quad(back_outer[i], front_outer[i], front_inner[i], back_inner[i], True)

    obj.quad(front_outer[0], back_outer[0], back_inner[0], front_inner[0], True)
    obj.quad(front_outer[-1], front_inner[-1], back_inner[-1], back_outer[-1], True)
    obj.write(OUT / "cabin_rib_frame.obj", "Project-authored open ShuttleA cabin rib frame.")


def generate_cabin_inner_shell() -> None:
    """Curved cabin wall and ceiling liner following the measured hull volume."""
    obj = ObjWriter("cabin_inner_shell")
    sections = [
        (-3.72, 0.72),
        (-2.72, 0.84),
        (-1.48, 1.0),
        (-0.18, 1.08),
        (1.18, 1.0),
        (2.42, 0.9),
        (3.42, 0.78),
    ]
    profile = [
        (-2.24, 0.12),
        (-2.44, 0.72),
        (-2.24, 1.42),
        (-1.48, 2.16),
        (-0.62, 2.50),
        (0.0, 2.58),
        (0.62, 2.50),
        (1.48, 2.16),
        (2.24, 1.42),
        (2.44, 0.72),
        (2.24, 0.12),
    ]
    rings: list[list[int]] = []
    for z, width_scale in sections:
        y_scale = 0.96 if z > 2.0 else 1.0
        rings.append([obj.v(x * width_scale, y * y_scale, z) for x, y in profile])

    for zi in range(len(rings) - 1):
        current = rings[zi]
        nxt = rings[zi + 1]
        for pi in range(len(profile) - 1):
            obj.quad(current[pi], nxt[pi], nxt[pi + 1], current[pi + 1], True)

    for ring in (rings[0], rings[-1]):
        for pi in range(len(profile) - 1):
            # short end lips; leave the center open for cockpit/hatch pieces
            if pi < 2 or pi > len(profile) - 4:
                obj.quad(ring[pi], ring[pi + 1], ring[5], ring[5], True)

    obj.write(OUT / "cabin_inner_shell.obj", "Project-authored curved ShuttleA cabin interior shell.")


def generate_cockpit_canopy_frame() -> None:
    """Open trapezoid canopy frame matching the cockpit candidate volume."""
    obj = ObjWriter("cockpit_canopy_frame")

    def box(name: str, cx: float, cy: float, cz: float, sx: float, sy: float, sz: float) -> None:
        x0, x1 = cx - sx * 0.5, cx + sx * 0.5
        y0, y1 = cy - sy * 0.5, cy + sy * 0.5
        z0, z1 = cz - sz * 0.5, cz + sz * 0.5
        verts = [
            obj.v(x0, y0, z0),
            obj.v(x1, y0, z0),
            obj.v(x1, y1, z0),
            obj.v(x0, y1, z0),
            obj.v(x0, y0, z1),
            obj.v(x1, y0, z1),
            obj.v(x1, y1, z1),
            obj.v(x0, y1, z1),
        ]
        obj.faces.append(tuple(verts[0:4]))
        obj.faces.append((verts[4], verts[7], verts[6], verts[5]))
        obj.faces.append((verts[0], verts[4], verts[5], verts[1]))
        obj.faces.append((verts[1], verts[5], verts[6], verts[2]))
        obj.faces.append((verts[2], verts[6], verts[7], verts[3]))
        obj.faces.append((verts[3], verts[7], verts[4], verts[0]))

    box("front_brow", 0.0, 2.04, -5.55, 2.55, 0.16, 0.14)
    box("rear_brow", 0.0, 3.12, -2.40, 2.75, 0.16, 0.14)
    box("left_rail", -1.36, 2.62, -3.95, 0.14, 0.16, 3.22)
    box("right_rail", 1.36, 2.62, -3.95, 0.14, 0.16, 3.22)
    box("center_spine", 0.0, 2.66, -3.95, 0.12, 0.12, 3.02)
    obj.write(OUT / "cockpit_canopy_frame.obj", "Project-authored open cockpit canopy frame.")


def generate_cockpit_canopy_glass() -> None:
    """Separate transparent canopy panes that do not pass through pilot eye space."""
    obj = ObjWriter("cockpit_canopy_glass")

    # Forward windscreen.
    a = obj.v(-1.08, 1.88, -5.82)
    b = obj.v(1.08, 1.88, -5.82)
    c = obj.v(1.34, 2.90, -4.62)
    d = obj.v(-1.34, 2.90, -4.62)
    obj.quad(a, b, c, d, True)

    # Crown window, high enough to avoid the standing/pilot camera path.
    e = obj.v(-1.34, 2.90, -4.62)
    f = obj.v(1.34, 2.90, -4.62)
    g = obj.v(1.18, 3.28, -2.55)
    h = obj.v(-1.18, 3.28, -2.55)
    obj.quad(e, f, g, h, True)

    # Left and right quarter panes.
    i = obj.v(-1.34, 1.98, -5.25)
    j = obj.v(-1.74, 2.18, -4.45)
    k = obj.v(-1.52, 3.05, -2.72)
    l = obj.v(-1.18, 3.28, -2.55)
    obj.quad(i, j, k, l, True)

    m = obj.v(1.34, 1.98, -5.25)
    n = obj.v(1.18, 3.28, -2.55)
    o = obj.v(1.52, 3.05, -2.72)
    p = obj.v(1.74, 2.18, -4.45)
    obj.quad(m, n, o, p, True)

    obj.write(OUT / "cockpit_canopy_glass.obj", "Project-authored segmented cockpit canopy glass.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    generate_cabin_rib_frame()
    generate_cabin_inner_shell()
    generate_cockpit_canopy_frame()
    generate_cockpit_canopy_glass()


if __name__ == "__main__":
    main()
