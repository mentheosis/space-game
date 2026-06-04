#!/usr/bin/env python3
"""Normalize the MX01 reference OBJ into deterministic ship-local source data."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[3]
SHIP_DIR = ROOT / "ships" / "MX01"
DEFAULT_CONFIG = SHIP_DIR / "config" / "mx01_collision_generation.json"


Vec3 = tuple[float, float, float]
FaceRef = tuple[int, int | None]


@dataclass(frozen=True)
class SourceFace:
    object_name: str
    material_name: str
    source_face_index: int
    vertices: tuple[FaceRef, ...]


@dataclass
class NormalizedMesh:
    vertices: list[Vec3]
    triangles: list[tuple[int, int, int]]
    materials: list[str]
    source_face_indices: list[int]
    degenerate_triangles_removed: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_obj(path: Path) -> tuple[list[Vec3], list[Vec3], list[SourceFace], list[str], list[str]]:
    vertices: list[Vec3] = []
    normals: list[Vec3] = []
    faces: list[SourceFace] = []
    objects: list[str] = []
    materials: list[str] = []

    object_name = "default"
    material_name = "default"
    source_face_index = 0

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        tag = parts[0]
        if tag == "o" and len(parts) >= 2:
            object_name = " ".join(parts[1:])
            objects.append(object_name)
        elif tag == "usemtl" and len(parts) >= 2:
            material_name = " ".join(parts[1:])
            materials.append(material_name)
        elif tag == "v" and len(parts) >= 4:
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif tag == "vn" and len(parts) >= 4:
            normals.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif tag == "f" and len(parts) >= 4:
            refs: list[FaceRef] = []
            for token in parts[1:]:
                fields = token.split("/")
                vertex_index = parse_obj_index(fields[0], len(vertices))
                normal_index = None
                if len(fields) >= 3 and fields[2]:
                    normal_index = parse_obj_index(fields[2], len(normals))
                refs.append((vertex_index, normal_index))
            faces.append(SourceFace(object_name, material_name, source_face_index, tuple(refs)))
            source_face_index += 1

    return vertices, normals, faces, sorted(set(objects)), sorted(set(materials))


def parse_obj_index(token: str, count: int) -> int:
    value = int(token)
    if value < 0:
        return count + value
    return value - 1


def triangle_count(face: SourceFace) -> int:
    return max(0, len(face.vertices) - 2)


def select_objects(faces: list[SourceFace], policy: str) -> tuple[list[str], list[SourceFace], dict[str, int]]:
    counts: Counter[str] = Counter()
    for face in faces:
        counts[face.object_name] += triangle_count(face)

    if not counts:
        raise RuntimeError("No faces found in source OBJ.")

    if policy != "highest_triangle_count":
        raise RuntimeError(f"Unsupported selected_object_policy: {policy}")

    selected = min(
        (name for name, count in counts.items() if count == max(counts.values())),
        key=lambda name: name,
    )
    selected_faces = [face for face in faces if face.object_name == selected]
    return [selected], selected_faces, dict(sorted(counts.items()))


def bounds(points: Iterable[Vec3]) -> dict[str, list[float]]:
    items = list(points)
    if not items:
        return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0], "size": [0.0, 0.0, 0.0], "center": [0.0, 0.0, 0.0]}
    mins = [min(point[index] for point in items) for index in range(3)]
    maxs = [max(point[index] for point in items) for index in range(3)]
    return {
        "min": [round(value, 6) for value in mins],
        "max": [round(value, 6) for value in maxs],
        "size": [round(maxs[index] - mins[index], 6) for index in range(3)],
        "center": [round((mins[index] + maxs[index]) * 0.5, 6) for index in range(3)],
    }


def quantize_key(point: Vec3, epsilon: float) -> tuple[int, int, int]:
    return tuple(int(round(value / epsilon)) for value in point)


def transform_point(point: Vec3, center: Vec3, scale: float) -> Vec3:
    return (
        (point[0] - center[0]) * scale,
        (point[1] - center[1]) * scale,
        (point[2] - center[2]) * scale,
    )


def triangle_area(a: Vec3, b: Vec3, c: Vec3) -> float:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def normalize_mesh(source_vertices: list[Vec3], selected_faces: list[SourceFace], config: dict) -> tuple[NormalizedMesh, dict]:
    selected_vertex_indices = sorted({vertex_index for face in selected_faces for vertex_index, _normal in face.vertices})
    selected_points = [source_vertices[index] for index in selected_vertex_indices]
    source_bounds = bounds(selected_points)
    center = tuple(source_bounds["center"]) if config["coordinate_transform"].get("center_selected_bounds", True) else (0.0, 0.0, 0.0)
    scale = float(config["coordinate_transform"].get("scale", 1.0))
    weld_epsilon = float(config["weld_epsilon"])
    area_epsilon = weld_epsilon * weld_epsilon

    vertex_by_key: dict[tuple[int, int, int], int] = {}
    output_vertices: list[Vec3] = []

    def intern(source_index: int) -> int:
        point = transform_point(source_vertices[source_index], center, scale)
        key = quantize_key(point, weld_epsilon)
        if key in vertex_by_key:
            return vertex_by_key[key]
        vertex_by_key[key] = len(output_vertices)
        output_vertices.append(point)
        return vertex_by_key[key]

    triangles: list[tuple[int, int, int]] = []
    materials: list[str] = []
    source_face_indices: list[int] = []
    removed = 0
    for face in selected_faces:
        refs = list(face.vertices)
        for start in range(1, len(refs) - 1):
            tri = (intern(refs[0][0]), intern(refs[start][0]), intern(refs[start + 1][0]))
            if len(set(tri)) < 3:
                removed += 1
                continue
            a, b, c = (output_vertices[index] for index in tri)
            if triangle_area(a, b, c) <= area_epsilon:
                removed += 1
                continue
            triangles.append(tri)
            materials.append(face.material_name)
            source_face_indices.append(face.source_face_index)

    normalized = NormalizedMesh(output_vertices, triangles, materials, source_face_indices, removed)
    transform_report = {
        "scale": scale,
        "center_offset": [round(value, 6) for value in center],
        "weld_epsilon": weld_epsilon,
        "area_epsilon": area_epsilon,
    }
    return normalized, {"selected_source_bounds": source_bounds, "transform": transform_report}


def edge_report(mesh: NormalizedMesh) -> dict:
    edge_counts: Counter[tuple[int, int]] = Counter()
    for a, b, c in mesh.triangles:
        for edge in ((a, b), (b, c), (c, a)):
            edge_counts[tuple(sorted(edge))] += 1
    open_edges = sum(1 for count in edge_counts.values() if count == 1)
    non_manifold_edges = sum(1 for count in edge_counts.values() if count > 2)
    return {
        "unique_edges": len(edge_counts),
        "open_edges": open_edges,
        "non_manifold_edges": non_manifold_edges,
        "edge_incidence_histogram": {str(key): value for key, value in sorted(Counter(edge_counts.values()).items())},
    }


def material_report(mesh: NormalizedMesh) -> list[dict]:
    counts: Counter[str] = Counter(mesh.materials)
    return [{"material": material, "triangles": counts[material]} for material in sorted(counts)]


def write_obj(path: Path, mesh: NormalizedMesh) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# MX01 normalized skin generated by ships/MX01/tools/normalize_mx01_skin.py",
        "o MX01_NormalizedSkin",
    ]
    for vertex in mesh.vertices:
        lines.append(f"v {vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}")

    current_material = None
    for triangle, material in zip(mesh.triangles, mesh.materials):
        if material != current_material:
            current_material = material
            lines.append(f"usemtl {material}")
        a, b, c = (index + 1 for index in triangle)
        lines.append(f"f {a} {b} {c}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, audit: dict) -> None:
    lines = [
        "# MX01 Source Audit",
        "",
        f"- Source OBJ: `{audit['source']['obj_path']}`",
        f"- Source OBJ SHA256: `{audit['source']['obj_sha256']}`",
        f"- Selected object: `{', '.join(audit['selection']['selected_objects'])}`",
        f"- Source vertices: `{audit['source']['vertex_count']}`",
        f"- Source faces: `{audit['source']['face_count']}`",
        f"- Normalized vertices: `{audit['normalized']['vertex_count']}`",
        f"- Normalized triangles: `{audit['normalized']['triangle_count']}`",
        f"- Degenerate triangles removed: `{audit['normalized']['degenerate_triangles_removed']}`",
        f"- Open edges: `{audit['topology']['open_edges']}`",
        f"- Non-manifold edges: `{audit['topology']['non_manifold_edges']}`",
        "",
        "## Bounds",
        "",
        f"- Selected source bounds: `{audit['source']['selected_source_bounds']}`",
        f"- Normalized bounds: `{audit['normalized']['bounds']}`",
        "",
        "## Materials",
        "",
    ]
    for row in audit["materials"]:
        lines.append(f"- `{row['material']}`: {row['triangles']} triangles")
    lines.extend(
        [
            "",
            "## Object Triangle Counts",
            "",
        ]
    )
    for name, count in audit["selection"]["object_triangle_counts"].items():
        lines.append(f"- `{name}`: {count}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve_output(config: dict, key: str) -> Path:
    return ROOT / config["normalization_outputs"][key]


def build_audit(config_path: Path, config: dict, obj_path: Path, mtl_path: Path | None, source_vertices: list[Vec3], source_normals: list[Vec3], source_faces: list[SourceFace], source_objects: list[str], source_materials: list[str], selected_objects: list[str], object_counts: dict[str, int], mesh: NormalizedMesh, mesh_details: dict, normalized_obj: Path) -> dict:
    topology = edge_report(mesh)
    script_path = Path(__file__).resolve()
    audit = {
        "ship_id": config["ship_id"],
        "source": {
            "obj_path": rel(obj_path),
            "obj_sha256": sha256(obj_path),
            "mtl_path": rel(mtl_path) if mtl_path and mtl_path.exists() else None,
            "mtl_sha256": sha256(mtl_path) if mtl_path and mtl_path.exists() else None,
            "vertex_count": len(source_vertices),
            "normal_count": len(source_normals),
            "face_count": len(source_faces),
            "object_names": source_objects,
            "material_names": source_materials,
            "selected_source_bounds": mesh_details["selected_source_bounds"],
        },
        "selection": {
            "policy": config["selected_object_policy"],
            "selected_objects": selected_objects,
            "object_triangle_counts": object_counts,
        },
        "normalized": {
            "obj_path": rel(normalized_obj),
            "obj_sha256": sha256(normalized_obj),
            "vertex_count": len(mesh.vertices),
            "triangle_count": len(mesh.triangles),
            "degenerate_triangles_removed": mesh.degenerate_triangles_removed,
            "bounds": bounds(mesh.vertices),
            "transform": mesh_details["transform"],
        },
        "topology": topology,
        "materials": material_report(mesh),
        "config": {
            "path": rel(config_path),
            "sha256": sha256(config_path),
            "effective_values": config,
        },
        "tools": {
            "normalize_mx01_skin.py": {
                "path": rel(script_path),
                "sha256": sha256(script_path),
            }
        },
    }
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_config(config_path)
    obj_path = (ROOT / config["source_obj"]).resolve()
    mtl_path = (ROOT / config["source_mtl"]).resolve() if config.get("source_mtl") else None

    source_vertices, source_normals, source_faces, source_objects, source_materials = parse_obj(obj_path)
    selected_objects, selected_faces, object_counts = select_objects(source_faces, config["selected_object_policy"])
    mesh, mesh_details = normalize_mesh(source_vertices, selected_faces, config)

    normalized_obj = resolve_output(config, "normalized_obj")
    write_obj(normalized_obj, mesh)

    audit = build_audit(
        config_path,
        config,
        obj_path,
        mtl_path,
        source_vertices,
        source_normals,
        source_faces,
        source_objects,
        source_materials,
        selected_objects,
        object_counts,
        mesh,
        mesh_details,
        normalized_obj,
    )

    audit_json = resolve_output(config, "audit_json")
    audit_md = resolve_output(config, "audit_md")
    manifest_json = resolve_output(config, "manifest_json")
    write_json(audit_json, audit)
    write_markdown(audit_md, audit)
    write_json(
        manifest_json,
        {
            "ship_id": config["ship_id"],
            "stage": "normalization",
            "source_obj": audit["source"]["obj_path"],
            "source_obj_sha256": audit["source"]["obj_sha256"],
            "config": audit["config"],
            "outputs": {
                "normalized_obj": audit["normalized"]["obj_path"],
                "normalized_obj_sha256": audit["normalized"]["obj_sha256"],
                "audit_json": rel(audit_json),
                "audit_md": rel(audit_md),
            },
            "tools": audit["tools"],
        },
    )
    print(f"Wrote {rel(normalized_obj)}")
    print(f"Wrote {rel(audit_json)}")
    print(f"Wrote {rel(audit_md)}")
    print(f"Wrote {rel(manifest_json)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
