#!/usr/bin/env python3
"""Audit Shuttle P3 enclosure quality against voxel and traversal data.

This is a geometry-quality check for generated interior walls/ceilings. It is
not a player-controller validation. It looks for the failure class that appears
when rectangular enclosure bands are forced onto a curved/tapered hull:

- discontinuous seams between adjacent wall bands;
- walls intruding into traversal lanes;
- rectangular bands that should become polygon/mesh strips because the voxel
  envelope changes too much within the band.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[2]
BANDS_PATH = ROOT / "assets/models/ship/shuttle_p3/shuttle_p3_enclosure_bands.json"
VOXELS_PATH = ROOT / "reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_voxels_full_compact.json"
FEATURES_PATH = ROOT / "reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_voxels_with_traversal_features.json"
CONTRACT_PATH = ROOT / "assets/source/blender/ships/shuttle_p3/shuttle_p3_interior_layout_contract.json"
REPORT_JSON = ROOT / "reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_enclosure_quality_report.json"
REPORT_MD = ROOT / "reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_enclosure_quality_report.md"


@dataclass(frozen=True)
class Band:
    name: str
    kind: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    source: dict

    @property
    def side(self) -> str:
        if "LeftWall" in self.name:
            return "left"
        if "RightWall" in self.name:
            return "right"
        return "none"

    @property
    def z_min(self) -> float:
        return self.center[2] - self.size[2] * 0.5

    @property
    def z_max(self) -> float:
        return self.center[2] + self.size[2] * 0.5

    @property
    def y_min(self) -> float:
        return self.center[1] - self.size[1] * 0.5

    @property
    def y_max(self) -> float:
        return self.center[1] + self.size[1] * 0.5

    @property
    def half_width(self) -> float:
        return abs(self.center[0])


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * p))
    return ordered[max(0, min(len(ordered) - 1, index))]


def load_bands() -> list[Band]:
    raw = json.loads(BANDS_PATH.read_text(encoding="utf-8"))
    bands = []
    for item in raw["bands"]:
        center = tuple(float(v) for v in item["center"])
        size = tuple(float(v) for v in item["size"])
        source = item.get("source", {})
        bands.append(Band(item["name"], item["kind"], center, size, source if isinstance(source, dict) else {}))
    return bands


def wall_bands(bands: list[Band]) -> list[Band]:
    return [band for band in bands if band.kind == "wall" and band.side != "none"]


def load_voxels() -> list[tuple[float, float, float, int, float]]:
    raw = json.loads(VOXELS_PATH.read_text(encoding="utf-8"))
    return [(float(v[0]), float(v[1]), float(v[2]), int(v[3]), float(v[4])) for v in raw["voxels"]]


def load_feature_voxels() -> list[tuple[float, float, float, str]]:
    raw = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))
    result: list[tuple[float, float, float, str]] = []
    for v in raw["voxels"]:
        x, y, z = float(v[0]), float(v[1]), float(v[2])
        tags = [str(tag) for tag in v[5]]
        category = "other"
        if any("Stairs" in tag for tag in tags):
            category = "stairs"
        elif any("Cockpit" in tag for tag in tags):
            category = "cockpit"
        elif any("Cargo" in tag for tag in tags):
            category = "cargo"
        result.append((x, y, z, category))
    return result


def load_layout_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


LAYOUT_CONTRACT = load_layout_contract()
STAIR_CONTRACT = LAYOUT_CONTRACT["stair_paths"]["cargo_to_cockpit_left"]
STAIR_LEFT_PATH = [tuple(float(value) for value in point) for point in STAIR_CONTRACT["points"]]
STAIR_SURFACE_WIDTH = float(STAIR_CONTRACT["surface_width"])
STAIR_WALL_CLEARANCE = float(STAIR_CONTRACT["wall_clearance"])


def authored_stair_required_half_width(z_min: float, z_max: float) -> float | None:
    samples: list[float] = []
    for start, end in zip(STAIR_LEFT_PATH, STAIR_LEFT_PATH[1:]):
        x0, _y0, z0 = start
        x1, _y1, z1 = end
        low = min(z0, z1)
        high = max(z0, z1)
        if high < z_min or low > z_max:
            continue

        for index in range(8):
            t = index / 7.0
            z = z0 + (z1 - z0) * t
            if z_min - 0.1 <= z <= z_max + 0.1:
                x = x0 + (x1 - x0) * t
                samples.append(abs(x) + STAIR_SURFACE_WIDTH * 0.5 + STAIR_WALL_CLEARANCE)

    return max(samples) if samples else None


def band_feature_clearance(band: Band, feature_voxels: list[tuple[float, float, float, str]]) -> dict | None:
    is_stair_transition = -3.9 <= band.z_max and band.z_min <= -0.2
    if not is_stair_transition:
        return None

    relevant = [
        abs(x)
        for x, _y, z, category in feature_voxels
        if band.z_min - 0.12 <= z <= band.z_max + 0.12
        and category == "stairs"
    ]
    if not relevant:
        return None

    authored_stair_width = authored_stair_required_half_width(band.z_min, band.z_max)
    max_route_x = max(relevant + ([authored_stair_width - STAIR_WALL_CLEARANCE] if authored_stair_width is not None else []))
    clearance = band.half_width - max_route_x
    min_clearance = STAIR_WALL_CLEARANCE
    return {
        "band": band.name,
        "route_max_abs_x": round(max_route_x, 3),
        "wall_abs_x": round(band.half_width, 3),
        "clearance": round(clearance, 3),
        "status": "pass" if clearance >= min_clearance else "fail",
        "recommendation": "Move wall outward or convert the wall to a curved/polygon strip around the stair route."
        if clearance < min_clearance
        else "",
    }


def band_envelope_fit(
    band: Band,
    voxels: list[tuple[float, float, float, int, float]],
    feature_voxels: list[tuple[float, float, float, str]],
) -> dict | None:
    slice_count = max(3, min(8, int(round((band.z_max - band.z_min) / 0.35))))
    samples: list[float] = []
    for index in range(slice_count):
        z0 = band.z_min + (band.z_max - band.z_min) * index / slice_count
        z1 = band.z_min + (band.z_max - band.z_min) * (index + 1) / slice_count
        shell_xs = [
            abs(x)
            for x, y, z, _can_stand, _head in voxels
            if z0 <= z <= z1 and band.y_min <= y <= band.y_max
        ]
        shell_sample = percentile(shell_xs, 0.98)
        route_xs = [
            abs(x)
            for x, _y, z, _category in feature_voxels
            if z0 - 0.18 <= z <= z1 + 0.18
        ]
        route_sample = max(route_xs) + 0.32 if route_xs else None
        authored_route = band.source.get("route_half_width")
        authored_route_sample = float(authored_route) + 0.32 if authored_route is not None else None
        authored_stair_sample = (
            authored_stair_required_half_width(z0, z1)
            if "StairTransition" in band.name
            else None
        )
        candidates = [
            value
            for value in (shell_sample, route_sample, authored_route_sample, authored_stair_sample)
            if value is not None
        ]
        if candidates:
            samples.append(max(candidates))

    if len(samples) < 2:
        return None

    variation = max(samples) - min(samples)
    average_envelope = mean(samples)
    max_envelope = max(samples)
    protrusion = band.half_width - max_envelope
    needs_polygon = (band.z_max - band.z_min > 0.9 and variation > 0.55) or protrusion > 0.38
    return {
        "band": band.name,
        "wall_abs_x": round(band.half_width, 3),
        "envelope_p98_min": round(min(samples), 3),
        "envelope_p98_max": round(max(samples), 3),
        "envelope_p98_mean": round(average_envelope, 3),
        "variation": round(variation, 3),
        "protrusion": round(protrusion, 3),
        "status": "fail" if needs_polygon else "pass",
        "recommendation": "Replace this rectangular band with a polygon/mesh strip or split it into more voxel-derived slices."
        if needs_polygon
        else "",
    }


def seam_checks(bands: list[Band]) -> list[dict]:
    issues: list[dict] = []
    for side in ("left", "right"):
        side_bands = sorted([band for band in bands if band.side == side], key=lambda band: band.z_min)
        for previous, current in zip(side_bands, side_bands[1:]):
            gap = current.z_min - previous.z_max
            width_step = abs(current.half_width - previous.half_width)
            y_bottom_step = abs(current.y_min - previous.y_min)
            y_top_step = abs(current.y_max - previous.y_max)
            status = "pass"
            reasons = []
            if gap > 0.08:
                status = "fail"
                reasons.append(f"z gap {gap:.2f}m")
            if -0.15 <= gap <= 0.15 and width_step > 0.42:
                status = "fail"
                reasons.append(f"wall width step {width_step:.2f}m")
            if -0.15 <= gap <= 0.15 and max(y_bottom_step, y_top_step) > 0.65:
                status = "fail"
                reasons.append(f"wall height discontinuity {max(y_bottom_step, y_top_step):.2f}m")
            if status == "fail":
                issues.append(
                    {
                        "side": side,
                        "from": previous.name,
                        "to": current.name,
                        "z_gap": round(gap, 3),
                        "width_step": round(width_step, 3),
                        "y_bottom_step": round(y_bottom_step, 3),
                        "y_top_step": round(y_top_step, 3),
                        "status": status,
                        "reason": "; ".join(reasons),
                        "recommendation": "Blend adjacent wall edges with a polygon strip or generate overlapping seam caps.",
                    }
                )
    return issues


def write_reports(payload: dict) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Shuttle P3 Enclosure Quality Report",
        "",
        f"- Status: `{payload['status']}`",
        f"- Wall bands checked: `{payload['wall_band_count']}`",
        f"- Seam failures: `{payload['summary']['seam_failures']}`",
        f"- Clearance failures: `{payload['summary']['clearance_failures']}`",
        f"- Envelope fit failures: `{payload['summary']['envelope_fit_failures']}`",
        "",
        "## Seam / Continuity Failures",
        "",
    ]
    if payload["seam_issues"]:
        for issue in payload["seam_issues"]:
            lines.append(f"- `{issue['from']}` -> `{issue['to']}`: {issue['reason']}. {issue['recommendation']}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Traversal Clearance Failures", ""])
    clearance_failures = [item for item in payload["clearance_checks"] if item["status"] == "fail"]
    if clearance_failures:
        for item in clearance_failures:
            lines.append(
                f"- `{item['band']}`: clearance `{item['clearance']}m` "
                f"(wall x `{item['wall_abs_x']}`, route x `{item['route_max_abs_x']}`). {item['recommendation']}"
            )
    else:
        lines.append("- None.")

    lines.extend(["", "## Rectangular Band Fit Failures", ""])
    fit_failures = [item for item in payload["envelope_fit_checks"] if item["status"] == "fail"]
    if fit_failures:
        for item in fit_failures:
            lines.append(
                f"- `{item['band']}`: voxel envelope variation `{item['variation']}m`, "
                f"protrusion `{item['protrusion']}m`. {item['recommendation']}"
            )
    else:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Pipeline Implication",
            "",
            "Any failure here means the enclosure generator should produce a curved/polygonal wall strip,",
            "more local slices, or seam caps before the layout is considered ready for art detail.",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    bands = load_bands()
    walls = wall_bands(bands)
    voxels = load_voxels()
    feature_voxels = load_feature_voxels()

    seam_issues = seam_checks(walls)
    clearance_checks = [check for band in walls if (check := band_feature_clearance(band, feature_voxels))]
    envelope_fit_checks = [check for band in walls if (check := band_envelope_fit(band, voxels, feature_voxels))]

    summary = {
        "seam_failures": len(seam_issues),
        "clearance_failures": sum(1 for item in clearance_checks if item["status"] == "fail"),
        "envelope_fit_failures": sum(1 for item in envelope_fit_checks if item["status"] == "fail"),
    }
    status = "pass" if all(value == 0 for value in summary.values()) else "fail"
    payload = {
        "schema_version": 1,
        "ship_id": "shuttle_p3",
        "source_layout_contract": str(CONTRACT_PATH.relative_to(ROOT)),
        "status": status,
        "wall_band_count": len(walls),
        "summary": summary,
        "seam_issues": seam_issues,
        "clearance_checks": clearance_checks,
        "envelope_fit_checks": envelope_fit_checks,
    }
    write_reports(payload)
    print(f"Wrote {REPORT_JSON.relative_to(ROOT)}")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    print(f"Status: {status}")
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
