#!/usr/bin/env python3
"""Generate first-pass MX01 dynamic exterior compound collision."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mesh_writer import write_box_obj


ROOT = Path(__file__).resolve().parents[3]
SHIP_DIR = ROOT / "ships" / "MX01"
DEFAULT_CONFIG = SHIP_DIR / "config" / "mx01_collision_generation.json"


Vec3 = tuple[float, float, float]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_config_path(config: dict, section: str, key: str) -> Path:
    return ROOT / config[section][key]


def parse_vertices(path: Path) -> list[Vec3]:
    vertices: list[Vec3] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "v" and len(parts) >= 4:
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
    return vertices


def bounds(points: list[Vec3]) -> dict:
    mins = [min(point[index] for point in points) for index in range(3)]
    maxs = [max(point[index] for point in points) for index in range(3)]
    return {
        "min": [round(value, 6) for value in mins],
        "max": [round(value, 6) for value in maxs],
        "center": [round((mins[index] + maxs[index]) * 0.5, 6) for index in range(3)],
        "size": [round(maxs[index] - mins[index], 6) for index in range(3)],
    }


def in_range(value: float, limits: tuple[float | None, float | None]) -> bool:
    low, high = limits
    if low is not None and value < low:
        return False
    if high is not None and value > high:
        return False
    return True


def select(vertices: list[Vec3], x: tuple[float | None, float | None] = (None, None), y: tuple[float | None, float | None] = (None, None), z: tuple[float | None, float | None] = (None, None)) -> list[Vec3]:
    return [point for point in vertices if in_range(point[0], x) and in_range(point[1], y) and in_range(point[2], z)]


def make_box(name: str, role: str, region_bounds: dict, padding: float, material: str, source: str, vertex_count: int) -> dict:
    size = [max(0.1, value + padding * 2.0) for value in region_bounds["size"]]
    return {
        "name": name,
        "role": role,
        "kind": "convex_box",
        "center": region_bounds["center"],
        "size": [round(value, 6) for value in size],
        "material": material,
        "source": source,
        "source_vertex_count": vertex_count,
    }


def generate(config: dict, vertices: list[Vec3]) -> tuple[dict, dict]:
    b = bounds(vertices)
    x_min, y_min, z_min = b["min"]
    x_max, y_max, z_max = b["max"]
    z_front = z_min + (z_max - z_min) * 0.70
    z_aft = z_min + (z_max - z_min) * 0.22
    x_port = x_min + (x_max - x_min) * 0.70
    x_starboard = x_min + (x_max - x_min) * 0.30
    y_belly = y_min + (y_max - y_min) * 0.30
    y_upper = y_min + (y_max - y_min) * 0.66
    padding = 0.15
    region_specs = [
        ("COL_MX01_dynamic_aft_body", "ship_world_dynamic_body", {"z": (None, z_aft)}, "aft longitudinal hull"),
        ("COL_MX01_dynamic_central_body", "ship_world_dynamic_body", {"z": (z_aft, z_front), "x": (x_starboard, x_port)}, "central longitudinal hull"),
        ("COL_MX01_dynamic_forward_nose", "ship_world_dynamic_body", {"z": (z_front, None)}, "forward nose hull"),
        ("COL_MX01_dynamic_port_lateral", "ship_world_dynamic_lateral", {"x": (x_port, None), "z": (z_aft, z_front)}, "port lateral structures"),
        ("COL_MX01_dynamic_starboard_lateral", "ship_world_dynamic_lateral", {"x": (None, x_starboard), "z": (z_aft, z_front)}, "starboard lateral structures"),
        ("COL_MX01_dynamic_belly_support", "ship_world_dynamic_landing", {"y": (None, y_belly), "z": (z_aft, z_front)}, "belly landing/contact volume"),
        ("COL_MX01_dynamic_upper_superstructure", "ship_world_dynamic_body", {"y": (y_upper, None), "z": (z_aft, z_front), "x": (x_starboard, x_port)}, "upper central volume"),
    ]
    objects: list[dict] = []
    skipped = []
    for name, role, filters, label in region_specs:
        points = select(vertices, x=filters.get("x", (None, None)), y=filters.get("y", (None, None)), z=filters.get("z", (None, None)))
        if len(points) < 8:
            skipped.append({"name": name, "reason": "too_few_vertices", "source_vertex_count": len(points)})
            continue
        objects.append(make_box(name, role, bounds(points), padding, "MX01_DynamicCollision", label, len(points)))

    payload = {
        "ship_id": config["ship_id"],
        "method": "spatial_partition_compound_convex_boxes_v1",
        "objects": objects,
        "skipped_regions": skipped,
    }
    report = {
        "ship_id": config["ship_id"],
        "method": payload["method"],
        "status": "PASS" if len(objects) >= 5 and not skipped else "WARN",
        "counts": {
            "collision_objects": len(objects),
            "skipped_regions": len(skipped),
            "convex_regions": len(objects),
            "concave_regions": 0,
        },
        "source_bounds": b,
        "notes": "First-pass dynamic collision uses simple convex boxes. It is suitable for broad moving-ship physics tests, not final skin fit.",
    }
    return payload, report


def write_markdown(path: Path, report: dict, payload: dict) -> None:
    lines = [
        "# MX01 Dynamic Collision Report",
        "",
        f"- Method: `{report['method']}`",
        f"- Status: `{report['status']}`",
        f"- Convex regions: `{report['counts']['convex_regions']}`",
        f"- Concave regions: `{report['counts']['concave_regions']}`",
        f"- Skipped regions: `{report['counts']['skipped_regions']}`",
        "",
        "## Regions",
        "",
    ]
    for obj in payload["objects"]:
        lines.append(f"- `{obj['name']}`: center={obj['center']}, size={obj['size']}, source_vertices={obj['source_vertex_count']}")
    lines.extend(["", "## Notes", "", report["notes"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_json(config_path)
    normalized_obj = resolve_config_path(config, "normalization_outputs", "normalized_obj")
    vertices = parse_vertices(normalized_obj)
    payload, report = generate(config, vertices)

    collision_json = resolve_config_path(config, "dynamic_collision_outputs", "collision_json")
    collision_obj = resolve_config_path(config, "dynamic_collision_outputs", "collision_obj")
    report_json = resolve_config_path(config, "dynamic_collision_outputs", "report_json")
    report_md = resolve_config_path(config, "dynamic_collision_outputs", "report_md")
    manifest_json = resolve_config_path(config, "dynamic_collision_outputs", "manifest_json")

    write_json(collision_json, payload)
    obj_counts = write_box_obj(collision_obj, payload["objects"], "MX01 dynamic exterior collision")
    report["obj_counts"] = obj_counts
    report["source"] = {"normalized_obj": rel(normalized_obj), "normalized_obj_sha256": sha256(normalized_obj)}
    report["config"] = {"path": rel(config_path), "sha256": sha256(config_path), "effective_values": config}
    report["tools"] = {
        "generate_mx01_dynamic_collision.py": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "mesh_writer.py": {"path": rel((Path(__file__).resolve().parent / "mesh_writer.py")), "sha256": sha256(Path(__file__).resolve().parent / "mesh_writer.py")},
    }
    report["outputs"] = {"collision_json": rel(collision_json), "collision_obj": rel(collision_obj)}
    write_json(report_json, report)
    write_markdown(report_md, report, payload)
    write_json(
        manifest_json,
        {
            "ship_id": config["ship_id"],
            "stage": "dynamic_collision_generation",
            "source": report["source"],
            "config": report["config"],
            "outputs": {
                "collision_json": rel(collision_json),
                "collision_json_sha256": sha256(collision_json),
                "collision_obj": rel(collision_obj),
                "collision_obj_sha256": sha256(collision_obj),
                "report_json": rel(report_json),
                "report_md": rel(report_md),
            },
            "tools": report["tools"],
        },
    )
    print(f"Wrote {rel(collision_json)}")
    print(f"Wrote {rel(collision_obj)}")
    print(f"Wrote {rel(report_json)}")
    print(f"Wrote {rel(report_md)}")
    print(f"Wrote {rel(manifest_json)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
