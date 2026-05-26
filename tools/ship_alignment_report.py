#!/usr/bin/env python3
"""Generate a static alignment report for the ShuttleA ship scene.

This tool intentionally works without Godot. It reads the current `.tscn`
resources and the source OBJ, computes approximate transformed AABBs, and
reports where collision/interior pieces are placed relative to the visual mesh.
It is not a replacement for rendered screenshots, but it gives us repeatable
geometry evidence instead of hand-placing pieces blindly.
"""

from __future__ import annotations

import math
import re
import sys
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SHIP_SCENE = ROOT / "scenes/ship/Ship.tscn"
SHUTTLE_VISUAL_SCENE = ROOT / "scenes/ship/OpenGameArtShuttleVisual.tscn"
SHUTTLE_OBJ = ROOT / "assets/models/ship/placeholders/oga_3d_space_ship_pack/ShuttleA.obj"
REPORT_PATH = ROOT / "reports/ship_alignment_report.md"
TOP_SVG_PATH = ROOT / "reports/ship_alignment_top.svg"
SIDE_SVG_PATH = ROOT / "reports/ship_alignment_side.svg"
FRONT_SVG_PATH = ROOT / "reports/ship_alignment_front.svg"
HULL_PROFILE_CSV_PATH = ROOT / "reports/ship_hull_profile.csv"
FIT_TARGETS_JSON_PATH = ROOT / "reports/ship_fit_targets.json"

REQUIRED_AUTHORED_OBJ_ASSETS = [
    "assets/models/ship/interior/cabin_floor_tapered.obj",
    "assets/models/ship/interior/cabin_wall_panel.obj",
    "assets/models/ship/interior/forward_bulkhead_tapered.obj",
    "assets/models/ship/interior/rear_bulkhead_tapered.obj",
    "assets/models/ship/interior/cockpit_console_tapered.obj",
    "assets/models/ship/interior/cockpit_screen_cluster.obj",
    "assets/models/ship/interior/cockpit_control_cluster.obj",
    "assets/models/ship/interior/pilot_chair_frame.obj",
    "assets/models/ship/interior/pilot_chair_cushions.obj",
    "assets/models/ship/interior/hatch_door_recessed.obj",
    "assets/models/ship/interior/hatch_frame_beveled.obj",
    "assets/models/ship/interior/cabin_rib_frame.obj",
    "assets/models/ship/interior/cabin_inner_shell.obj",
    "assets/models/ship/interior/cockpit_canopy_frame.obj",
    "assets/models/ship/interior/cockpit_canopy_glass.obj",
    "assets/models/ship/interior/cabin_detail_panels.obj",
    "assets/models/ship/interior/cockpit_viewport_bezel.obj",
]


@dataclass
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def scale(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x * other.x, self.y * other.y, self.z * other.z)

    def tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def data(self) -> list[float]:
        return [round(self.x, 4), round(self.y, 4), round(self.z, 4)]


@dataclass
class Bounds:
    min: Vec3
    max: Vec3

    @property
    def size(self) -> Vec3:
        return self.max - self.min

    @property
    def center(self) -> Vec3:
        return Vec3(
            (self.min.x + self.max.x) * 0.5,
            (self.min.y + self.max.y) * 0.5,
            (self.min.z + self.max.z) * 0.5,
        )

    def outside_distance(self, outer: "Bounds") -> Vec3:
        return Vec3(
            max(0.0, outer.min.x - self.min.x, self.max.x - outer.max.x),
            max(0.0, outer.min.y - self.min.y, self.max.y - outer.max.y),
            max(0.0, outer.min.z - self.min.z, self.max.z - outer.max.z),
        )

    def contains(self, other: "Bounds", margin: float = 0.0) -> bool:
        return (
            other.min.x >= self.min.x - margin
            and other.max.x <= self.max.x + margin
            and other.min.y >= self.min.y - margin
            and other.max.y <= self.max.y + margin
            and other.min.z >= self.min.z - margin
            and other.max.z <= self.max.z + margin
        )

    def overlap_size(self, other: "Bounds") -> Vec3:
        return Vec3(
            max(0.0, min(self.max.x, other.max.x) - max(self.min.x, other.min.x)),
            max(0.0, min(self.max.y, other.max.y) - max(self.min.y, other.min.y)),
            max(0.0, min(self.max.z, other.max.z) - max(self.min.z, other.min.z)),
        )

    def data(self) -> dict[str, list[float]]:
        return {
            "min": self.min.data(),
            "max": self.max.data(),
            "center": self.center.data(),
            "size": self.size.data(),
        }


@dataclass
class Transform:
    position: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.0, 0.0))
    rotation: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.0, 0.0))
    scale: Vec3 = field(default_factory=lambda: Vec3(1.0, 1.0, 1.0))

    def apply(self, point: Vec3) -> Vec3:
        p = point.scale(self.scale)
        p = rotate_x(p, self.rotation.x)
        p = rotate_y(p, self.rotation.y)
        p = rotate_z(p, self.rotation.z)
        return p + self.position

    def combine(self, child: "Transform") -> "Transform":
        transformed_position = self.apply(child.position)
        return Transform(
            transformed_position,
            self.rotation + child.rotation,
            self.scale.scale(child.scale),
        )


@dataclass
class ResourceDef:
    type_name: str
    values: dict[str, object]


@dataclass
class NodeDef:
    name: str
    type_name: str
    parent: str
    values: dict[str, object]
    transform: Transform

    @property
    def path(self) -> str:
        if self.parent in ("", "."):
            return self.name
        return f"{self.parent}/{self.name}"


def rotate_x(v: Vec3, angle: float) -> Vec3:
    c = math.cos(angle)
    s = math.sin(angle)
    return Vec3(v.x, v.y * c - v.z * s, v.y * s + v.z * c)


def rotate_y(v: Vec3, angle: float) -> Vec3:
    c = math.cos(angle)
    s = math.sin(angle)
    return Vec3(v.x * c + v.z * s, v.y, -v.x * s + v.z * c)


def rotate_z(v: Vec3, angle: float) -> Vec3:
    c = math.cos(angle)
    s = math.sin(angle)
    return Vec3(v.x * c - v.y * s, v.x * s + v.y * c, v.z)


def parse_vec3(value: str) -> Vec3:
    match = re.search(r"Vector3\(([^)]*)\)", value)
    if not match:
        return Vec3(0.0, 0.0, 0.0)
    parts = [float(part.strip()) for part in match.group(1).split(",")]
    return Vec3(parts[0], parts[1], parts[2])


def parse_tscn(path: Path) -> tuple[dict[str, ResourceDef], list[NodeDef]]:
    resources: dict[str, ResourceDef] = {}
    nodes: list[NodeDef] = []
    current_kind: str | None = None
    current_id = ""
    current_header: dict[str, str] = {}
    current_values: dict[str, object] = {}

    def flush() -> None:
        nonlocal current_kind, current_id, current_header, current_values
        if current_kind == "sub_resource":
            resources[current_id] = ResourceDef(current_header.get("type", ""), dict(current_values))
        elif current_kind == "node":
            name = current_header.get("name", "")
            type_name = current_header.get("type", "")
            parent = current_header.get("parent", ".")
            position = current_values.get("position", Vec3(0.0, 0.0, 0.0))
            rotation = current_values.get("rotation", Vec3(0.0, 0.0, 0.0))
            scale = current_values.get("scale", Vec3(1.0, 1.0, 1.0))
            assert isinstance(position, Vec3)
            assert isinstance(rotation, Vec3)
            assert isinstance(scale, Vec3)
            nodes.append(NodeDef(name, type_name, parent, dict(current_values), Transform(position, rotation, scale)))
        current_kind = None
        current_id = ""
        current_header = {}
        current_values = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("["):
            flush()
            if line.startswith("[sub_resource"):
                current_kind = "sub_resource"
                current_header = parse_header(line)
                current_id = current_header.get("id", "")
            elif line.startswith("[node"):
                current_kind = "node"
                current_header = parse_header(line)
            continue
        if "=" not in line or current_kind is None:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if value.startswith("Vector3("):
            current_values[key] = parse_vec3(value)
        elif value.startswith("SubResource("):
            current_values[key] = re.search(r'"([^"]+)"', value).group(1)  # type: ignore[union-attr]
        elif value.startswith("ExtResource("):
            match = re.search(r'"([^"]+)"', value)
            current_values[key] = "ExtResource:" + match.group(1)  # type: ignore[union-attr]
        else:
            current_values[key] = value
    flush()
    return resources, nodes


def parse_ext_resources(path: Path) -> dict[str, tuple[str, str]]:
    resources: dict[str, tuple[str, str]] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("[ext_resource"):
            continue
        header = parse_header(line)
        resource_id = header.get("id")
        resource_type = header.get("type")
        resource_path = header.get("path")
        if resource_id and resource_type and resource_path:
            resources[resource_id] = (resource_type, resource_path)
    return resources


def parse_header(line: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, quoted in re.findall(r'(\w+)="([^"]*)"', line):
        values[key] = quoted
    for key, bare in re.findall(r"(\w+)=([^\s\]]+)", line):
        values.setdefault(key, bare)
    return values


def load_obj_vertices(path: Path) -> list[Vec3]:
    vertices: list[Vec3] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("v "):
            continue
        _, x, y, z = line.split(maxsplit=3)
        vertices.append(Vec3(float(x), float(y), float(z)))
    return vertices


def load_obj_vertices_for_material(path: Path, material_name: str) -> list[Vec3]:
    vertices: list[Vec3] = []
    selected_indexes: set[int] = set()
    active_material: str | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            _, x, y, z = line.split(maxsplit=3)
            vertices.append(Vec3(float(x), float(y), float(z)))
            continue
        if line.startswith("usemtl "):
            active_material = line.split(maxsplit=1)[1].strip()
            continue
        if active_material != material_name or not line.startswith("f "):
            continue
        for raw_part in line.split()[1:]:
            vertex_index = int(raw_part.split("/", 1)[0])
            if vertex_index < 0:
                vertex_index = len(vertices) + vertex_index + 1
            selected_indexes.add(vertex_index - 1)

    return [vertices[index] for index in sorted(selected_indexes)]


def load_ext_mesh_bounds(resource_path: str, transform: Transform) -> Bounds | None:
    if not resource_path.startswith("res://") or not resource_path.endswith(".obj"):
        return None
    local_path = ROOT / resource_path.removeprefix("res://")
    if not local_path.exists():
        return None
    vertices = load_obj_vertices(local_path)
    return bounds_from_points(transform.apply(vertex) for vertex in vertices)


def bounds_from_points(points: Iterable[Vec3]) -> Bounds:
    points = list(points)
    return Bounds(
        Vec3(min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)),
        Vec3(max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)),
    )


def box_bounds(size: Vec3, transform: Transform) -> Bounds:
    hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
    corners = [
        Vec3(x, y, z)
        for x in (-hx, hx)
        for y in (-hy, hy)
        for z in (-hz, hz)
    ]
    return bounds_from_points(transform.apply(corner) for corner in corners)


def global_transforms(nodes: list[NodeDef]) -> dict[str, Transform]:
    by_path: dict[str, NodeDef] = {node.path: node for node in nodes}
    memo: dict[str, Transform] = {}

    def resolve(path: str) -> Transform:
        if path in memo:
            return memo[path]
        node = by_path[path]
        if node.parent in ("", "."):
            memo[path] = node.transform
        else:
            memo[path] = resolve(node.parent).combine(node.transform)
        return memo[path]

    for node in nodes:
        resolve(node.path)
    return memo


def fmt(v: Vec3) -> str:
    return f"({v.x:6.2f}, {v.y:5.2f}, {v.z:6.2f})"


def max_component(v: Vec3) -> float:
    return max(abs(v.x), abs(v.y), abs(v.z))


def find_slice(vertices: list[Vec3], label: str, predicate) -> tuple[str, Bounds | None]:
    selected = [vertex for vertex in vertices if predicate(vertex)]
    return label, bounds_from_points(selected) if selected else None


def target_comparison(name: str, target: Bounds, actual: Bounds) -> str:
    center_delta = actual.center - target.center
    size_delta = actual.size - target.size
    overlap = actual.overlap_size(target)
    return (
        f"| `{name}` | `{fmt(target.center)}` | `{fmt(actual.center)}` | "
        f"`{fmt(center_delta)}` | `{fmt(target.size)}` | `{fmt(actual.size)}` | "
        f"`{fmt(size_delta)}` | `{fmt(overlap)}` |"
    )


def fit_comparison_data(name: str, target: Bounds, actual: Bounds) -> dict[str, object]:
    center_delta = actual.center - target.center
    size_delta = actual.size - target.size
    overlap = actual.overlap_size(target)
    return {
        "name": name,
        "target_bounds": target.data(),
        "actual_bounds": actual.data(),
        "center_delta": center_delta.data(),
        "size_delta": size_delta.data(),
        "overlap": overlap.data(),
    }


def top_projection_empty_space(
    bounds: Bounds,
    visual_vertices: list[Vec3],
    z_window: float = 0.45,
    margin: float = 0.25,
    samples_per_axis: int = 18,
) -> tuple[float, float]:
    checked = 0
    outside = 0
    max_distance = 0.0
    if bounds.size.x <= 0.0 or bounds.size.z <= 0.0:
        return 0.0, 0.0

    for z_index in range(samples_per_axis):
        z_t = (z_index + 0.5) / samples_per_axis
        z = bounds.min.z + bounds.size.z * z_t
        z_vertices = [vertex for vertex in visual_vertices if abs(vertex.z - z) <= z_window]
        if not z_vertices:
            continue
        min_x = min(vertex.x for vertex in z_vertices) - margin
        max_x = max(vertex.x for vertex in z_vertices) + margin
        for x_index in range(samples_per_axis):
            x_t = (x_index + 0.5) / samples_per_axis
            x = bounds.min.x + bounds.size.x * x_t
            checked += 1
            if x < min_x:
                outside += 1
                max_distance = max(max_distance, min_x - x)
            elif x > max_x:
                outside += 1
                max_distance = max(max_distance, x - max_x)

    if checked == 0:
        return 0.0, 0.0
    return outside / checked, max_distance


def write_report(text: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text, encoding="utf-8")


def write_projection_svgs(
    visual_vertices: list[Vec3],
    visual_bounds: Bounds,
    cockpit_candidate: Bounds | None,
    collision_rows: list[tuple[str, Bounds, Vec3]],
    visual_rows: list[tuple[str, Bounds, Vec3]],
    glass_rows: list[tuple[str, Bounds, Vec3]],
) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_projection_svg(
        TOP_SVG_PATH,
        "Top projection: X/Z",
        "x",
        "z",
        visual_vertices,
        visual_bounds,
        cockpit_candidate,
        collision_rows,
        visual_rows,
        glass_rows,
    )
    write_projection_svg(
        SIDE_SVG_PATH,
        "Side projection: Z/Y",
        "z",
        "y",
        visual_vertices,
        visual_bounds,
        cockpit_candidate,
        collision_rows,
        visual_rows,
        glass_rows,
    )
    write_projection_svg(
        FRONT_SVG_PATH,
        "Front projection: X/Y",
        "x",
        "y",
        visual_vertices,
        visual_bounds,
        cockpit_candidate,
        collision_rows,
        visual_rows,
        glass_rows,
    )


def write_hull_profile_csv(visual_vertices: list[Vec3], visual_bounds: Bounds) -> list[tuple[float, int, Bounds | None]]:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    slice_count = 28
    z_min = visual_bounds.min.z
    z_max = visual_bounds.max.z
    step = (z_max - z_min) / slice_count
    rows: list[tuple[float, int, Bounds | None]] = []
    lines = ["z_center,vertex_count,min_x,max_x,min_y,max_y,size_x,size_y"]

    for index in range(slice_count):
        start = z_min + step * index
        end = start + step
        z_center = (start + end) * 0.5
        selected = [vertex for vertex in visual_vertices if start <= vertex.z < end]
        bounds = bounds_from_points(selected) if selected else None
        rows.append((z_center, len(selected), bounds))
        if bounds is None:
            lines.append(f"{z_center:.4f},0,,,,,")
            continue
        lines.append(
            f"{z_center:.4f},{len(selected)},{bounds.min.x:.4f},{bounds.max.x:.4f},"
            f"{bounds.min.y:.4f},{bounds.max.y:.4f},{bounds.size.x:.4f},{bounds.size.y:.4f}"
        )

    HULL_PROFILE_CSV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def write_fit_targets_json(
    visual_bounds: Bounds,
    cockpit_candidate: Bounds | None,
    targets: dict[str, Bounds],
    collision_rows: list[tuple[str, Bounds, Vec3]],
    visual_rows: list[tuple[str, Bounds, Vec3]],
    glass_rows: list[tuple[str, Bounds, Vec3]],
    collision_empty_space_rows: list[tuple[str, float, float]],
    detail_empty_space_rows: list[tuple[str, float, float]],
    authored_asset_rows: list[tuple[str, bool, bool, int | None]],
    hull_profile_rows: list[tuple[float, int, Bounds | None]],
    failures: list[str],
) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    def row_data(row: tuple[str, Bounds, Vec3]) -> dict[str, object]:
        name, bounds, outside = row
        return {
            "node": name,
            "bounds": bounds.data(),
            "outside_visual_aabb": outside.data(),
        }

    empty_space_by_name = {
        name: {
            "empty_space_ratio": round(ratio, 4),
            "max_outside_distance": round(max_distance, 4),
        }
        for name, ratio, max_distance in [*collision_empty_space_rows, *detail_empty_space_rows]
    }
    collision_by_name = {name: bounds for name, bounds, _outside in collision_rows}
    visual_by_name = {name: bounds for name, bounds, _outside in visual_rows}
    fit_comparisons: list[dict[str, object]] = []

    def append_fit_comparison(name: str, target_name: str, actual_name: str, actuals: dict[str, Bounds]) -> None:
        if target_name in targets and actual_name in actuals:
            fit_comparisons.append(fit_comparison_data(name, targets[target_name], actuals[actual_name]))

    append_fit_comparison("Interior volume vs cabin", "Cabin interior envelope", "Interior/InteriorVolume/CollisionShape3D", collision_by_name)
    append_fit_comparison("Floor plate vs walk path", "Floor / walk path", "Interior/Floor/MainPlate", visual_by_name)
    append_fit_comparison("Exterior hatch vs rear zone", "Rear hatch zone", "ExteriorHatch/MeshInstance3D", visual_by_name)
    append_fit_comparison("Interior hatch vs rear zone", "Rear hatch zone", "InteriorHatch/MeshInstance3D", visual_by_name)
    append_fit_comparison("Pilot cushion vs cockpit", "Cockpit / canopy", "PilotSeat/SeatVisual/Cushion", visual_by_name)
    append_fit_comparison("Interior canopy glass vs cockpit", "Cockpit / canopy", "Interior/Cockpit/CanopyGlassInterior", visual_by_name)

    data = {
        "source": {
            "ship_scene": str(SHIP_SCENE.relative_to(ROOT)),
            "visual_scene": str(SHUTTLE_VISUAL_SCENE.relative_to(ROOT)),
            "visual_obj": str(SHUTTLE_OBJ.relative_to(ROOT)),
        },
        "artifacts": {
            "markdown_report": str(REPORT_PATH.relative_to(ROOT)),
            "top_projection_svg": str(TOP_SVG_PATH.relative_to(ROOT)),
            "side_projection_svg": str(SIDE_SVG_PATH.relative_to(ROOT)),
            "front_projection_svg": str(FRONT_SVG_PATH.relative_to(ROOT)),
            "hull_profile_csv": str(HULL_PROFILE_CSV_PATH.relative_to(ROOT)),
            "fit_targets_json": str(FIT_TARGETS_JSON_PATH.relative_to(ROOT)),
        },
        "visual_bounds": visual_bounds.data(),
        "cockpit_candidate": cockpit_candidate.data() if cockpit_candidate is not None else None,
        "fit_targets": {
            name: bounds.data()
            for name, bounds in targets.items()
        },
        "fit_comparisons": fit_comparisons,
        "collision_shapes": [row_data(row) for row in collision_rows],
        "visual_meshes": [row_data(row) for row in visual_rows],
        "glass_meshes": [row_data(row) for row in glass_rows],
        "top_projection_empty_space": empty_space_by_name,
        "authored_assets": [
            {
                "path": asset_path,
                "exists": exists,
                "referenced_by_ship_scene": referenced,
                "vertex_count": vertex_count,
            }
            for asset_path, exists, referenced, vertex_count in authored_asset_rows
        ],
        "hull_profile": [
            {
                "z_center": round(z_center, 4),
                "vertex_count": vertex_count,
                "bounds": bounds.data() if bounds is not None else None,
            }
            for z_center, vertex_count, bounds in hull_profile_rows
        ],
        "failures": failures,
    }
    FIT_TARGETS_JSON_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_projection_svg(
    path: Path,
    title: str,
    horizontal_axis: str,
    vertical_axis: str,
    visual_vertices: list[Vec3],
    visual_bounds: Bounds,
    cockpit_candidate: Bounds | None,
    collision_rows: list[tuple[str, Bounds, Vec3]],
    visual_rows: list[tuple[str, Bounds, Vec3]],
    glass_rows: list[tuple[str, Bounds, Vec3]],
) -> None:
    width = 1400
    height = 900
    pad = 70
    x_min, x_max = axis_range(visual_bounds, horizontal_axis)
    y_min, y_max = axis_range(visual_bounds, vertical_axis)
    x_margin = max(1.0, (x_max - x_min) * 0.08)
    y_margin = max(1.0, (y_max - y_min) * 0.08)
    x_min -= x_margin
    x_max += x_margin
    y_min -= y_margin
    y_max += y_margin

    def sx(value: float) -> float:
        return pad + ((value - x_min) / (x_max - x_min)) * (width - pad * 2)

    def sy(value: float) -> float:
        return height - pad - ((value - y_min) / (y_max - y_min)) * (height - pad * 2)

    def point(vertex: Vec3) -> tuple[float, float]:
        return sx(axis_value(vertex, horizontal_axis)), sy(axis_value(vertex, vertical_axis))

    def rect(bounds: Bounds, stroke: str, fill: str, opacity: float, stroke_width: float = 2.0) -> str:
        h0, h1 = axis_range(bounds, horizontal_axis)
        v0, v1 = axis_range(bounds, vertical_axis)
        x0 = sx(h0)
        x1 = sx(h1)
        y0 = sy(v1)
        y1 = sy(v0)
        return (
            f'<rect x="{min(x0, x1):.2f}" y="{min(y0, y1):.2f}" '
            f'width="{abs(x1 - x0):.2f}" height="{abs(y1 - y0):.2f}" '
            f'fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" '
            f'stroke-width="{stroke_width}" />'
        )

    sampled_vertices = visual_vertices[:: max(1, len(visual_vertices) // 2500)]
    vertex_points = "\n".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.15" fill="#30343b" fill-opacity="0.42" />'
        for x, y in (point(vertex) for vertex in sampled_vertices)
    )

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f8fa" />',
        f'<text x="{pad}" y="38" font-family="Arial, sans-serif" font-size="24" fill="#111827">{escape_xml(title)}</text>',
        f'<text x="{pad}" y="62" font-family="Arial, sans-serif" font-size="13" fill="#4b5563">gray dots = visual OBJ vertices, red = collision, blue = interior/detail meshes, cyan = glass/canopy, orange = cockpit slice</text>',
        rect(visual_bounds, "#111827", "none", 0.0, 3.0),
        vertex_points,
    ]

    if cockpit_candidate is not None:
        svg.append(rect(cockpit_candidate, "#f97316", "#f97316", 0.12, 3.0))

    for name, bounds, _outside in visual_rows:
        if any(token in name for token in ("Glass", "Canopy")):
            continue
        svg.append(rect(bounds, "#2563eb", "#2563eb", 0.06, 1.2))

    for _name, bounds, _outside in collision_rows:
        svg.append(rect(bounds, "#dc2626", "#dc2626", 0.08, 2.4))

    for _name, bounds, _outside in glass_rows:
        svg.append(rect(bounds, "#0891b2", "#06b6d4", 0.20, 2.4))

    legend_y = height - 34
    svg.extend(
        [
            f'<text x="{pad}" y="{legend_y}" font-family="Arial, sans-serif" font-size="13" fill="#374151">Axis horizontal: {horizontal_axis.upper()} | vertical: {vertical_axis.upper()}</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def axis_value(value: Vec3, axis: str) -> float:
    if axis == "x":
        return value.x
    if axis == "y":
        return value.y
    if axis == "z":
        return value.z
    raise ValueError(axis)


def axis_range(bounds: Bounds, axis: str) -> tuple[float, float]:
    return axis_value(bounds.min, axis), axis_value(bounds.max, axis)


def escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main() -> int:
    check_mode = "--check" in sys.argv[1:]
    ship_resources, ship_nodes = parse_tscn(SHIP_SCENE)
    ship_ext_resources = parse_ext_resources(SHIP_SCENE)
    scene_ext_paths = {resource_path for _resource_type, resource_path in ship_ext_resources.values()}
    _, visual_nodes = parse_tscn(SHUTTLE_VISUAL_SCENE)
    visual_transforms = global_transforms(visual_nodes)
    shuttle_node = next(node for node in visual_nodes if node.name == "ShuttleA")
    shuttle_transform = visual_transforms[shuttle_node.path]
    visual_vertices = [shuttle_transform.apply(vertex) for vertex in load_obj_vertices(SHUTTLE_OBJ)]
    cockpit_material_vertices = [
        shuttle_transform.apply(vertex)
        for vertex in load_obj_vertices_for_material(SHUTTLE_OBJ, "Cockpit")
    ]
    visual_bounds = bounds_from_points(visual_vertices)

    ship_transforms = global_transforms(ship_nodes)

    collision_rows: list[tuple[str, Bounds, Vec3]] = []
    visual_rows: list[tuple[str, Bounds, Vec3]] = []
    glass_rows: list[tuple[str, Bounds, Vec3]] = []
    for node in ship_nodes:
        transform = ship_transforms[node.path]
        shape_id = node.values.get("shape")
        mesh_id = node.values.get("mesh")
        is_visible = node.values.get("visible", "true") != "false"
        if isinstance(shape_id, str) and shape_id in ship_resources:
            resource = ship_resources[shape_id]
            size = resource.values.get("size")
            if resource.type_name == "BoxShape3D" and isinstance(size, Vec3):
                bounds = box_bounds(size, transform)
                collision_rows.append((node.path, bounds, bounds.outside_distance(visual_bounds)))
        if not is_visible:
            continue
        if isinstance(mesh_id, str) and mesh_id in ship_resources:
            resource = ship_resources[mesh_id]
            size = resource.values.get("size")
            if resource.type_name == "BoxMesh" and isinstance(size, Vec3):
                bounds = box_bounds(size, transform)
                outside = bounds.outside_distance(visual_bounds)
                visual_rows.append((node.path, bounds, outside))
                if "Glass" in node.name or "Canopy" in node.name:
                    glass_rows.append((node.path, bounds, outside))
        elif isinstance(mesh_id, str) and mesh_id.startswith("ExtResource:"):
            resource_id = mesh_id.removeprefix("ExtResource:")
            resource_type, resource_path = ship_ext_resources.get(resource_id, ("", ""))
            if resource_type == "Mesh":
                bounds = load_ext_mesh_bounds(resource_path, transform)
                if bounds is not None:
                    outside = bounds.outside_distance(visual_bounds)
                    visual_rows.append((node.path, bounds, outside))
                    if "Glass" in node.name or "Canopy" in node.name:
                        glass_rows.append((node.path, bounds, outside))

    upper_forward_vertices = [
        vertex
        for vertex in visual_vertices
        if abs(vertex.x) <= 2.75 and vertex.y >= 1.75 and -6.5 <= vertex.z <= -1.0
    ]
    fallback_cockpit_candidate = bounds_from_points(upper_forward_vertices) if upper_forward_vertices else None
    cockpit_candidate = (
        bounds_from_points(cockpit_material_vertices)
        if cockpit_material_vertices
        else fallback_cockpit_candidate
    )
    target_slices = [
        ("Cockpit / canopy", cockpit_candidate),
        find_slice(
            visual_vertices,
            "Cabin interior envelope",
            lambda vertex: abs(vertex.x) <= 3.15 and 0.2 <= vertex.y <= 3.25 and -4.75 <= vertex.z <= 4.25,
        ),
        find_slice(
            visual_vertices,
            "Floor / walk path",
            lambda vertex: abs(vertex.x) <= 2.7 and -0.05 <= vertex.y <= 1.15 and -10.75 <= vertex.z <= 3.9,
        ),
        find_slice(
            visual_vertices,
            "Rear hatch zone",
            lambda vertex: abs(vertex.x) <= 2.7 and 0.25 <= vertex.y <= 2.75 and 2.0 <= vertex.z <= 6.75,
        ),
    ]
    targets = {name: bounds for name, bounds in target_slices if bounds is not None}
    collision_by_name = {name: bounds for name, bounds, _outside in collision_rows}
    visual_by_name = {name: bounds for name, bounds, _outside in visual_rows}
    collision_empty_space_rows = [
        (name, *top_projection_empty_space(bounds, visual_vertices))
        for name, bounds, _outside in collision_rows
    ]
    detail_empty_space_rows = [
        (name, *top_projection_empty_space(bounds, visual_vertices))
        for name, bounds, _outside in visual_rows
        if any(token in name for token in ("Hatch", "Floor", "Cockpit", "PilotSeat", "Ribs"))
    ]

    authored_asset_rows: list[tuple[str, bool, bool, int | None]] = []
    for asset_path in REQUIRED_AUTHORED_OBJ_ASSETS:
        local_path = ROOT / asset_path
        resource_path = f"res://{asset_path}"
        vertex_count: int | None = None
        if local_path.exists():
            vertex_count = len(load_obj_vertices(local_path))
        authored_asset_rows.append((asset_path, local_path.exists(), resource_path in scene_ext_paths, vertex_count))

    interior_outside = [row for row in visual_rows if row[2].x > 0.05 or row[2].y > 0.05 or row[2].z > 0.05]
    collision_outside = [row for row in collision_rows if row[2].x > 0.05 or row[2].y > 0.05 or row[2].z > 0.05]
    failures: list[str] = []
    if collision_outside:
        failures.append(f"{len(collision_outside)} collision shape(s) protrude outside ShuttleA visual AABB.")
    if interior_outside:
        failures.append(f"{len(interior_outside)} interior/detail mesh(es) protrude outside ShuttleA visual AABB.")
    for asset_path, exists, referenced, vertex_count in authored_asset_rows:
        if not exists:
            failures.append(f"Required authored OBJ asset is missing: {asset_path}.")
        elif vertex_count is not None and vertex_count < 8:
            failures.append(f"Required authored OBJ asset has too few vertices to be useful: {asset_path}.")
        if not referenced:
            failures.append(f"Required authored OBJ asset is not referenced by Ship.tscn: {asset_path}.")

    required_fit_inputs = [
        ("Cabin interior envelope", "Interior/InteriorVolume/CollisionShape3D", collision_by_name),
        ("Floor / walk path", "Interior/Floor/MainPlate", visual_by_name),
        ("Rear hatch zone", "ExteriorHatch/MeshInstance3D", visual_by_name),
        ("Rear hatch zone", "InteriorHatch/MeshInstance3D", visual_by_name),
        ("Cockpit / canopy", "PilotSeat/SeatVisual/Cushion", visual_by_name),
        ("Cockpit / canopy", "Interior/Cockpit/CanopyGlassInterior", visual_by_name),
    ]
    for target_name, actual_name, actuals in required_fit_inputs:
        if target_name not in targets:
            failures.append(f"Required fit target is missing: {target_name}.")
        if actual_name not in actuals:
            failures.append(f"Required fit comparison node is missing: {actual_name}.")

    if "Cockpit / canopy" in targets and "Interior/Cockpit/CanopyGlassInterior" in visual_by_name:
        canopy_target = targets["Cockpit / canopy"]
        canopy_bounds = visual_by_name["Interior/Cockpit/CanopyGlassInterior"]
        canopy_center_delta = canopy_bounds.center - canopy_target.center
        canopy_overlap = canopy_bounds.overlap_size(canopy_target)
        if abs(canopy_center_delta.y) > 0.75 or abs(canopy_center_delta.z) > 1.05:
            failures.append(f"Interior canopy glass center drift is too high: {fmt(canopy_center_delta)}.")
        if canopy_overlap.y < 0.75 or canopy_overlap.z < 2.2:
            failures.append(f"Interior canopy glass overlap is too low: {fmt(canopy_overlap)}.")

    if "Floor / walk path" in targets and "Interior/Floor/MainPlate" in visual_by_name:
        floor_target = targets["Floor / walk path"]
        floor_bounds = visual_by_name["Interior/Floor/MainPlate"]
        floor_center_delta = floor_bounds.center - floor_target.center
        floor_overlap = floor_bounds.overlap_size(floor_target)
        if abs(floor_center_delta.z) > 0.75:
            failures.append(f"Floor plate fore/aft drift is too high: {fmt(floor_center_delta)}.")
        if floor_overlap.z < 12.0:
            failures.append(f"Floor plate overlap is too low: {fmt(floor_overlap)}.")

    required_visible_meshes = [
        "Interior/Floor/MainPlate",
        "Interior/LeftWall/UpperPanel",
        "Interior/RightWall/UpperPanel",
        "Interior/ForwardBulkhead",
        "Interior/RearBulkhead",
        "Interior/Ribs/ForwardFrame",
        "Interior/Ribs/MidFrame",
        "Interior/Ribs/RearFrame",
        "Interior/Cockpit/ConsoleBase",
        "Interior/Cockpit/CenterScreen",
        "Interior/Cockpit/ControlCluster",
        "PilotSeat/SeatVisual/Base",
        "PilotSeat/SeatVisual/Cushion",
        "ExteriorHatch/MeshInstance3D",
        "ExteriorHatch/ExteriorHatchFrame",
        "InteriorHatch/MeshInstance3D",
        "InteriorHatch/InteriorHatchFrame",
    ]
    for mesh_name in required_visible_meshes:
        if mesh_name not in visual_by_name:
            failures.append(f"Required visible authored mesh is missing from report: {mesh_name}.")

    write_projection_svgs(
        visual_vertices,
        visual_bounds,
        cockpit_candidate,
        collision_rows,
        visual_rows,
        glass_rows,
    )
    hull_profile_rows = write_hull_profile_csv(visual_vertices, visual_bounds)
    write_fit_targets_json(
        visual_bounds,
        cockpit_candidate,
        targets,
        collision_rows,
        visual_rows,
        glass_rows,
        collision_empty_space_rows,
        detail_empty_space_rows,
        authored_asset_rows,
        hull_profile_rows,
        failures,
    )

    lines: list[str] = []
    lines.append("# Ship Alignment Report")
    lines.append("")
    lines.append("Generated by `tools/ship_alignment_report.py` from scene and OBJ source files.")
    lines.append("")
    lines.append("Projection artifacts:")
    lines.append("")
    lines.append("- `reports/ship_alignment_top.svg`")
    lines.append("- `reports/ship_alignment_side.svg`")
    lines.append("- `reports/ship_alignment_front.svg`")
    lines.append("- `reports/ship_hull_profile.csv`")
    lines.append("- `reports/ship_fit_targets.json`")
    lines.append("")
    lines.append("## ShuttleA Visual Bounds")
    lines.append("")
    lines.append(f"- min: `{fmt(visual_bounds.min)}`")
    lines.append(f"- max: `{fmt(visual_bounds.max)}`")
    lines.append(f"- size: `{fmt(visual_bounds.size)}`")
    lines.append("")
    if cockpit_candidate is not None:
        lines.append("## Cockpit Material Canopy Target")
        lines.append("")
        if cockpit_material_vertices:
            lines.append("This target is derived from vertices referenced by `usemtl Cockpit` in `ShuttleA.obj`.")
        else:
            lines.append("This target falls back to a heuristic slice because no `usemtl Cockpit` vertices were found.")
        lines.append("")
        lines.append(f"- min: `{fmt(cockpit_candidate.min)}`")
        lines.append(f"- max: `{fmt(cockpit_candidate.max)}`")
        lines.append(f"- size: `{fmt(cockpit_candidate.size)}`")
        lines.append("")
    lines.append("## Hull Width / Height Profile")
    lines.append("")
    lines.append("This table slices the ShuttleA exterior mesh along local ship length. It is the first automated check for swept wings, tail, canopy height, and places where broad boxes include too much empty space.")
    lines.append("")
    lines.append("| Z Center | Vertices | Width X | Height Y | X Range | Y Range |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for z_center, vertex_count, bounds in hull_profile_rows:
        if bounds is None:
            lines.append(f"| `{z_center:6.2f}` | `{vertex_count}` | `-` | `-` | `-` | `-` |")
            continue
        lines.append(
            f"| `{z_center:6.2f}` | `{vertex_count}` | `{bounds.size.x:5.2f}` | `{bounds.size.y:5.2f}` | "
            f"`{bounds.min.x:5.2f}..{bounds.max.x:5.2f}` | `{bounds.min.y:5.2f}..{bounds.max.y:5.2f}` |"
        )
    lines.append("")
    lines.append("## Visual Fit Targets")
    lines.append("")
    lines.append("The cockpit/canopy target is derived from ShuttleA's `usemtl Cockpit` vertices when available. The other targets are measured heuristic slices from ShuttleA used to drive scene placement before visual screenshot polish.")
    lines.append("")
    lines.append("| Target | Center | Size |")
    lines.append("| --- | --- | --- |")
    for name, bounds in targets.items():
        lines.append(f"| `{name}` | `{fmt(bounds.center)}` | `{fmt(bounds.size)}` |")
    lines.append("")
    lines.append("## Fit Target Comparisons")
    lines.append("")
    lines.append("| Check | Target Center | Actual Center | Center Delta | Target Size | Actual Size | Size Delta | Overlap |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    if "Cabin interior envelope" in targets and "Interior/InteriorVolume/CollisionShape3D" in collision_by_name:
        lines.append(target_comparison("Interior volume vs cabin", targets["Cabin interior envelope"], collision_by_name["Interior/InteriorVolume/CollisionShape3D"]))
    if "Floor / walk path" in targets and "Interior/Floor/MainPlate" in visual_by_name:
        lines.append(target_comparison("Floor plate vs walk path", targets["Floor / walk path"], visual_by_name["Interior/Floor/MainPlate"]))
    if "Rear hatch zone" in targets and "ExteriorHatch/MeshInstance3D" in visual_by_name:
        lines.append(target_comparison("Exterior hatch vs rear zone", targets["Rear hatch zone"], visual_by_name["ExteriorHatch/MeshInstance3D"]))
    if "Rear hatch zone" in targets and "InteriorHatch/MeshInstance3D" in visual_by_name:
        lines.append(target_comparison("Interior hatch vs rear zone", targets["Rear hatch zone"], visual_by_name["InteriorHatch/MeshInstance3D"]))
    if "Cockpit / canopy" in targets and "PilotSeat/SeatVisual/Cushion" in visual_by_name:
        lines.append(target_comparison("Pilot cushion vs cockpit", targets["Cockpit / canopy"], visual_by_name["PilotSeat/SeatVisual/Cushion"]))
    if "Cockpit / canopy" in targets and "Interior/Cockpit/CanopyGlassInterior" in visual_by_name:
        lines.append(target_comparison("Interior canopy glass vs cockpit", targets["Cockpit / canopy"], visual_by_name["Interior/Cockpit/CanopyGlassInterior"]))
    lines.append("")
    lines.append("## Authored Interior Asset Contract")
    lines.append("")
    lines.append("These OBJ assets are the current measurable source set for the MVP ShuttleA interior. Check mode fails if any required file is missing, too small to be useful, or no longer referenced by `Ship.tscn`.")
    lines.append("")
    lines.append("| Asset | Exists | Referenced By Ship Scene | Vertex Count |")
    lines.append("| --- | --- | --- | --- |")
    for asset_path, exists, referenced, vertex_count in authored_asset_rows:
        count_text = str(vertex_count) if vertex_count is not None else "-"
        lines.append(f"| `{asset_path}` | `{exists}` | `{referenced}` | `{count_text}` |")
    lines.append("")
    lines.append("## Collision Shape Bounds")
    lines.append("")
    lines.append("| Node | Center | Size | Outside Visual AABB |")
    lines.append("| --- | --- | --- | --- |")
    for name, bounds, outside in collision_rows:
        lines.append(f"| `{name}` | `{fmt(bounds.center)}` | `{fmt(bounds.size)}` | `{fmt(outside)}` |")
    lines.append("")
    lines.append("## Top Projection Empty-Space Estimate")
    lines.append("")
    lines.append("This samples each rectangular bound against the visual hull width at the same Z positions. High values usually mean a box includes too much empty space for swept wings, tapered hull sections, or narrow cockpit regions.")
    lines.append("")
    lines.append("| Node | Empty-Space Ratio | Max Outside Distance |")
    lines.append("| --- | --- | --- |")
    for name, ratio, max_distance in collision_empty_space_rows:
        lines.append(f"| `{name}` | `{ratio:.2f}` | `{max_distance:.2f}` |")
    for name, ratio, max_distance in detail_empty_space_rows:
        lines.append(f"| `{name}` | `{ratio:.2f}` | `{max_distance:.2f}` |")
    lines.append("")
    lines.append("## Interior / Detail Mesh Bounds")
    lines.append("")
    lines.append("| Node | Center | Size | Outside Visual AABB |")
    lines.append("| --- | --- | --- | --- |")
    for name, bounds, outside in visual_rows:
        lines.append(f"| `{name}` | `{fmt(bounds.center)}` | `{fmt(bounds.size)}` | `{fmt(outside)}` |")
    lines.append("")
    lines.append("## Glass Mesh Bounds")
    lines.append("")
    lines.append("| Node | Center | Size | Outside Visual AABB |")
    lines.append("| --- | --- | --- | --- |")
    for name, bounds, outside in glass_rows:
        lines.append(f"| `{name}` | `{fmt(bounds.center)}` | `{fmt(bounds.size)}` | `{fmt(outside)}` |")
    lines.append("")
    lines.append("## Automated Findings")
    lines.append("")
    if collision_outside:
        lines.append("- Some collision shapes protrude outside the total ShuttleA visual AABB. This can be intentional for interaction volumes, but physical blocking collision should be reviewed.")
    else:
        lines.append("- Collision shapes stay inside the total ShuttleA visual AABB.")
    if interior_outside:
        lines.append("- Some interior/detail meshes protrude outside the total ShuttleA visual AABB. These are candidates for repositioning or deferral.")
    else:
        lines.append("- Interior/detail meshes stay inside the total ShuttleA visual AABB.")
    if cockpit_candidate is not None and glass_rows:
        lines.append("- Glass/canopy comparison against the forward upper cockpit candidate:")
        for name, bounds, _outside in glass_rows:
            center_delta = bounds.center - cockpit_candidate.center
            overlap = bounds.overlap_size(cockpit_candidate)
            lines.append(
                f"  - `{name}` center delta `{fmt(center_delta)}`, overlap `{fmt(overlap)}`"
            )
    if failures:
        lines.append("- Alignment check failures:")
        for failure in failures:
            lines.append(f"  - {failure}")
    else:
        lines.append("- Alignment check gate passes.")
    lines.append("- AABB checks are broad; swept wings, curved hull, and canopy fit still need screenshot or rendered debug review.")
    lines.append("")
    lines.append("## Recommended Next Automation")
    lines.append("")
    lines.append("- Run `scripts/capture-ship-alignment.sh` on the host to generate fixed-camera screenshots.")
    lines.append("- Add colored debug materials/toggles for interior envelope, glass, collision, and visual mesh slices.")
    lines.append("- Use mesh slices or authored marker empties from Blender/Godot for cockpit, hatch, wing, and tail regions instead of hand-tuned coordinates.")

    report = "\n".join(lines) + "\n"
    write_report(report)
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)}")
    if collision_outside or interior_outside:
        print(f"collision_outside={len(collision_outside)} interior_outside={len(interior_outside)}")
    if check_mode and failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    if check_mode:
        print("Ship alignment check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
