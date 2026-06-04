"""Small deterministic OBJ helpers for MX01 generated collision tools."""

from __future__ import annotations


Vec3 = tuple[float, float, float]


def box_vertices(center: Vec3, size: Vec3) -> list[Vec3]:
    cx, cy, cz = center
    sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
    return [
        (cx - sx, cy - sy, cz - sz),
        (cx + sx, cy - sy, cz - sz),
        (cx + sx, cy + sy, cz - sz),
        (cx - sx, cy + sy, cz - sz),
        (cx - sx, cy - sy, cz + sz),
        (cx + sx, cy - sy, cz + sz),
        (cx + sx, cy + sy, cz + sz),
        (cx - sx, cy + sy, cz + sz),
    ]


def box_faces(vertex_offset: int) -> list[list[int]]:
    o = vertex_offset
    return [
        [o + 1, o + 2, o + 3, o + 4],
        [o + 5, o + 8, o + 7, o + 6],
        [o + 1, o + 5, o + 6, o + 2],
        [o + 2, o + 6, o + 7, o + 3],
        [o + 3, o + 7, o + 8, o + 4],
        [o + 4, o + 8, o + 5, o + 1],
    ]


def write_box_obj(path, objects: list[dict], header: str) -> dict:
    lines = [f"# {header}"]
    total_vertices = 0
    total_faces = 0
    for obj in objects:
        vertices = box_vertices(tuple(obj["center"]), tuple(obj["size"]))
        faces = box_faces(total_vertices)
        lines.append(f"o {obj['name']}")
        lines.append(f"usemtl {obj.get('material', obj.get('role', 'MX01_Collision'))}")
        for x, y, z in vertices:
            lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
        for face in faces:
            lines.append("f " + " ".join(str(index) for index in face))
        total_vertices += len(vertices)
        total_faces += len(faces)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"vertices": total_vertices, "faces": total_faces, "objects": len(objects)}
