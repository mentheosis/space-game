#!/usr/bin/env python3
"""Generate project-authored ShuttleA interior OBJ meshes.

The meshes are deliberately simple enough to maintain in source control, but
they avoid the blockout problem of filled rib slabs and rectangular wall boxes.
"""

from __future__ import annotations

import math
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

    def box(self, cx: float, cy: float, cz: float, sx: float, sy: float, sz: float) -> None:
        x0, x1 = cx - sx * 0.5, cx + sx * 0.5
        y0, y1 = cy - sy * 0.5, cy + sy * 0.5
        z0, z1 = cz - sz * 0.5, cz + sz * 0.5
        verts = [
            self.v(x0, y0, z0),
            self.v(x1, y0, z0),
            self.v(x1, y1, z0),
            self.v(x0, y1, z0),
            self.v(x0, y0, z1),
            self.v(x1, y0, z1),
            self.v(x1, y1, z1),
            self.v(x0, y1, z1),
        ]
        self.faces.append(tuple(verts[0:4]))
        self.faces.append((verts[4], verts[7], verts[6], verts[5]))
        self.faces.append((verts[0], verts[4], verts[5], verts[1]))
        self.faces.append((verts[1], verts[5], verts[6], verts[2]))
        self.faces.append((verts[2], verts[6], verts[7], verts[3]))
        self.faces.append((verts[3], verts[7], verts[4], verts[0]))

    def write(self, path: Path, comment: str) -> None:
        lines = [f"# {comment}", f"o {self.name}"]
        for x, y, z in self.vertices:
            lines.append(f"v {x:.4f} {y:.4f} {z:.4f}")
        for face in self.faces:
            lines.append("f " + " ".join(str(index) for index in face))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_ring_prism(
    obj: ObjWriter,
    outer: list[tuple[float, float]],
    inner: list[tuple[float, float]],
    z_front: float,
    z_back: float,
) -> None:
    front_outer = [obj.v(x, y, z_front) for x, y in outer]
    front_inner = [obj.v(x, y, z_front) for x, y in inner]
    back_outer = [obj.v(x, y, z_back) for x, y in outer]
    back_inner = [obj.v(x, y, z_back) for x, y in inner]

    for i in range(len(outer)):
        j = (i + 1) % len(outer)
        obj.quad(front_outer[i], front_outer[j], front_inner[j], front_inner[i], True)
        obj.quad(back_outer[j], back_outer[i], back_inner[i], back_inner[j], True)
        obj.quad(front_outer[j], back_outer[j], back_inner[j], front_inner[j], True)
        obj.quad(back_outer[i], front_outer[i], front_inner[i], back_inner[i], True)


def oval_profile(width: float, bottom: float, top: float, segments: int = 18) -> list[tuple[float, float]]:
    center_y = (bottom + top) * 0.5
    radius_y = (top - bottom) * 0.5
    points: list[tuple[float, float]] = []
    for i in range(segments):
        angle = 2.0 * 3.141592653589793 * i / segments
        points.append((width * 0.5 * math.cos(angle), center_y + radius_y * math.sin(angle)))
    return points


def generate_cabin_floor_tapered() -> None:
    """Opaque supported floor running from rear hatch through cockpit approach."""
    obj = ObjWriter("cabin_floor_tapered")

    sections = [
        (-10.65, 0.72),
        (-8.85, 0.88),
        (-6.70, 1.18),
        (-4.35, 1.55),
        (-2.10, 2.02),
        (0.35, 2.32),
        (2.20, 2.28),
        (3.55, 1.92),
    ]
    top: list[tuple[int, int]] = []
    bottom: list[tuple[int, int]] = []
    for z, half_width in sections:
        top.append((obj.v(-half_width, 0.10, z), obj.v(half_width, 0.10, z)))
        bottom.append((obj.v(-half_width, -0.14, z), obj.v(half_width, -0.14, z)))

    for index in range(len(sections) - 1):
        lt0, rt0 = top[index]
        lt1, rt1 = top[index + 1]
        lb0, rb0 = bottom[index]
        lb1, rb1 = bottom[index + 1]
        obj.quad(lt0, lt1, rt1, rt0, True)
        obj.quad(lb1, lb0, rb0, rb1, True)
        obj.quad(lt1, lt0, lb0, lb1, True)
        obj.quad(rt0, rt1, rb1, rb0, True)

    # Side skirts make the walkway read as supported rather than transparent.
    # Keep their underside inside the ShuttleA exterior lower hull AABB so
    # static alignment stays strict while still giving the floor visible mass.
    for z, half_width in [(-8.20, 0.96), (-6.20, 1.22), (-4.20, 1.50), (-2.20, 1.82), (0.00, 2.10), (2.10, 2.04)]:
        obj.box(-half_width, 0.08, z, 0.12, 0.34, 1.24)
        obj.box(half_width, 0.08, z, 0.12, 0.34, 1.24)

    obj.write(OUT / "cabin_floor_tapered.obj", "Project-authored opaque supported ShuttleA cabin floor.")


def generate_cabin_wall_panel() -> None:
    """Thick side liner panel with a sloped upper shoulder."""
    obj = ObjWriter("cabin_wall_panel")

    # Local X thickness, Y height, Z length. The scene mirrors this by placing
    # instances on either side, so keep it asymmetric but substantial.
    obj.box(0.00, -0.18, 0.00, 0.18, 0.54, 6.72)
    obj.box(0.04, 0.48, 0.00, 0.20, 0.70, 6.52)
    obj.box(-0.06, 1.04, 0.00, 0.16, 0.44, 5.90)
    for z in [-2.55, -1.20, 0.15, 1.50, 2.70]:
        obj.box(-0.16, 0.36, z, 0.08, 0.54, 0.16)
    obj.write(OUT / "cabin_wall_panel.obj", "Project-authored thick ShuttleA side wall liner.")


def generate_forward_bulkhead_tapered() -> None:
    """Low cockpit transition coaming that does not read as a canopy arch."""
    obj = ObjWriter("forward_bulkhead_tapered")

    # This used to be a full oval ring. That made the cockpit read as an
    # archway and caused the walkthrough camera to visibly pass through trim.
    obj.box(0.0, 0.04, -0.02, 2.36, 0.14, 0.22)
    obj.box(-1.18, 0.30, -0.02, 0.16, 0.58, 0.20)
    obj.box(1.18, 0.30, -0.02, 0.16, 0.58, 0.20)
    obj.box(-0.72, 0.56, -0.02, 0.54, 0.10, 0.18)
    obj.box(0.72, 0.56, -0.02, 0.54, 0.10, 0.18)
    obj.write(OUT / "forward_bulkhead_tapered.obj", "Project-authored low ShuttleA cockpit transition coaming.")


def generate_cabin_rib_frame() -> None:
    """Segmented dimensional rib; no filled paper-card center faces."""
    obj = ObjWriter("cabin_rib_frame")

    # Vertical and shoulder beams are intentionally separated. This reads as a
    # structural skeleton, not a flat decorative card.
    for side in [-1.0, 1.0]:
        obj.box(side * 2.02, 0.22, 0.0, 0.24, 1.64, 0.30)
        obj.box(side * 1.70, 1.08, 0.0, 0.26, 0.72, 0.30)
        obj.box(side * 1.20, 1.54, 0.0, 0.66, 0.22, 0.30)
        obj.box(side * 0.48, 1.76, 0.0, 0.82, 0.18, 0.30)

    obj.box(0.0, 1.84, 0.0, 0.82, 0.16, 0.30)
    obj.box(-1.92, -0.54, 0.0, 0.36, 0.26, 0.30)
    obj.box(1.92, -0.54, 0.0, 0.36, 0.26, 0.30)
    obj.write(OUT / "cabin_rib_frame.obj", "Project-authored segmented ShuttleA structural rib frame.")


def generate_cabin_inner_shell() -> None:
    """Curved cabin wall and ceiling liner following the measured hull volume."""
    obj = ObjWriter("cabin_inner_shell")
    sections = [
        # z, half width, crown height. These values follow the measured
        # ShuttleA hull taper: narrow cockpit, broader mid-body, narrower aft.
        (-10.95, 0.76, 2.48),
        (-9.70, 1.02, 3.03),
        (-8.30, 1.18, 3.34),
        (-6.70, 1.22, 3.26),
        (-5.45, 1.42, 2.92),
        (-4.42, 1.22, 2.24),
        (-3.46, 1.64, 2.42),
        (-2.44, 2.10, 2.56),
        (-1.18, 2.46, 2.66),
        (0.18, 2.62, 2.70),
        (1.54, 2.58, 2.66),
        (2.82, 2.34, 2.54),
        (4.02, 1.92, 2.36),
    ]
    rings: list[list[int]] = []
    for z, half_width, crown_y in sections:
        profile = [
            (-half_width * 0.96, -0.07),
            (-half_width * 1.02, 0.52),
            (-half_width * 0.92, 1.28),
            (-half_width * 0.58, crown_y - 0.42),
            (-half_width * 0.24, crown_y - 0.10),
            (0.0, crown_y),
            (half_width * 0.24, crown_y - 0.10),
            (half_width * 0.58, crown_y - 0.42),
            (half_width * 0.92, 1.28),
            (half_width * 1.02, 0.52),
            (half_width * 0.96, -0.07),
        ]
        rings.append([obj.v(x, y, z) for x, y in profile])

    for zi in range(len(rings) - 1):
        current = rings[zi]
        nxt = rings[zi + 1]
        current_z = sections[zi][0]
        next_z = sections[zi + 1][0]
        for pi in range(len(profile) - 1):
            # The ShuttleA exterior has a canopy that rolls back over the pilot.
            # Leave the forward roof liner open so the cockpit reads as a glass
            # canopy rather than an opaque tunnel/arch.
            if next_z <= -4.42 and 1 <= pi <= 9:
                continue
            if next_z <= -1.18 and 3 <= pi <= 7:
                continue
            obj.quad(current[pi], nxt[pi], nxt[pi + 1], current[pi + 1], True)

    obj.write(OUT / "cabin_inner_shell.obj", "Project-authored curved ShuttleA cabin interior shell.")


def generate_cockpit_canopy_frame() -> None:
    """Minimal canopy rails so the interior reads as one smooth bubble."""
    obj = ObjWriter("cockpit_canopy_frame")

    obj.box(0.0, 3.48, -8.15, 1.55, 0.055, 0.08)
    obj.write(OUT / "cockpit_canopy_frame.obj", "Project-authored open cockpit canopy frame.")


def generate_cockpit_canopy_glass() -> None:
    """Single fighter-style canopy dome matched to ShuttleA's Cockpit material."""
    obj = ObjWriter("cockpit_canopy_glass")

    sections = [
        (-11.34, 0.36, 1.98, 2.20),
        (-10.62, 0.66, 1.88, 2.72),
        (-9.62, 0.88, 1.82, 3.18),
        (-8.44, 0.94, 1.88, 3.48),
        (-7.18, 0.88, 2.05, 3.54),
        (-6.08, 0.54, 2.32, 3.30),
    ]
    rings: list[list[int]] = []
    for z, half_width, lower_y, crown_y in sections:
        profile = [
            (-half_width, lower_y),
            (-half_width * 0.92, lower_y + (crown_y - lower_y) * 0.34),
            (-half_width * 0.58, lower_y + (crown_y - lower_y) * 0.72),
            (0.0, crown_y),
            (half_width * 0.58, lower_y + (crown_y - lower_y) * 0.72),
            (half_width * 0.92, lower_y + (crown_y - lower_y) * 0.34),
            (half_width, lower_y),
        ]
        rings.append([obj.v(x, y, z) for x, y in profile])

    for zi in range(len(rings) - 1):
        for pi in range(len(rings[zi]) - 1):
            obj.quad(rings[zi][pi], rings[zi + 1][pi], rings[zi + 1][pi + 1], rings[zi][pi + 1], True)

    obj.write(OUT / "cockpit_canopy_glass.obj", "Project-authored segmented cockpit canopy glass.")


def generate_cabin_detail_panels() -> None:
    """Purposeful low-profile wall and floor details; no square frame clutter."""
    obj = ObjWriter("cabin_detail_panels")

    # Center tread plates, low enough to read as floor detail instead of
    # floating frame clutter.
    for z, width in [(-9.35, 0.74), (-8.10, 0.82), (-6.70, 1.02), (-5.20, 1.14), (-3.70, 1.35), (-2.10, 1.62), (-0.45, 1.86), (1.15, 1.92), (2.55, 1.70)]:
        obj.box(0.0, 0.215, z, width, 0.045, 0.62)

    # Thin side rails give scale and direction without intruding into the
    # cockpit approach. Avoid tall isolated blocks here; they read as clipping
    # clutter during the walkthrough.
    for side in [-1.0, 1.0]:
        obj.box(side * 0.92, 0.34, -7.25, 0.08, 0.12, 3.95)
        obj.box(side * 1.26, 0.36, -3.45, 0.09, 0.12, 3.20)
        obj.box(side * 1.78, 0.38, 0.75, 0.10, 0.14, 4.70)

        obj.box(side * 0.98, 0.92, -7.35, 0.06, 0.10, 3.40)
        obj.box(side * 1.36, 0.98, -3.55, 0.07, 0.10, 2.90)
        obj.box(side * 1.86, 1.02, 0.70, 0.08, 0.12, 4.25)

    obj.write(OUT / "cabin_detail_panels.obj", "Project-authored high-density cabin panel and trim details.")


def generate_cockpit_viewport_bezel() -> None:
    """Low cockpit coaming and subtle side sills below the fighter-style canopy."""
    obj = ObjWriter("cockpit_viewport_bezel")

    # Keep these below the pilot's eye line. Earlier versions used a full oval
    # ring here, which read as an archway instead of a single canopy bubble.
    obj.box(0.0, 1.70, -9.38, 1.74, 0.10, 0.34)
    obj.box(-0.92, 1.95, -8.72, 0.08, 0.08, 2.72)
    obj.box(0.92, 1.95, -8.72, 0.08, 0.08, 2.72)
    obj.box(0.0, 1.56, -7.38, 1.58, 0.08, 0.24)
    obj.write(OUT / "cockpit_viewport_bezel.obj", "Project-authored cockpit viewport bezel.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    generate_cabin_floor_tapered()
    generate_cabin_wall_panel()
    generate_forward_bulkhead_tapered()
    generate_cabin_rib_frame()
    generate_cabin_inner_shell()
    generate_cockpit_canopy_frame()
    generate_cockpit_canopy_glass()
    generate_cabin_detail_panels()
    generate_cockpit_viewport_bezel()


if __name__ == "__main__":
    main()
