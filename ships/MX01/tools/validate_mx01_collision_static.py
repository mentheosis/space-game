#!/usr/bin/env python3
"""Run static validation for generated MX01 collision artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SHIP_DIR = ROOT / "ships" / "MX01"
DEFAULT_CONFIG = SHIP_DIR / "config" / "mx01_collision_generation.json"


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


def check_file(path: Path, checks: list[dict]) -> bool:
    ok = path.exists()
    checks.append({"id": f"exists:{rel(path)}", "status": "PASS" if ok else "FAIL"})
    return ok


def check_manifest_hashes(manifest_path: Path, checks: list[dict]) -> None:
    manifest = load_json(manifest_path)
    outputs = manifest.get("outputs", {})
    for key, expected in sorted(outputs.items()):
        if not key.endswith("_sha256"):
            continue
        path_key = key.removesuffix("_sha256")
        artifact_rel = outputs.get(path_key)
        if not artifact_rel:
            continue
        artifact_path = ROOT / artifact_rel
        if not artifact_path.exists():
            checks.append({"id": f"manifest_hash:{rel(manifest_path)}:{artifact_rel}", "status": "FAIL", "reason": "missing artifact"})
            continue
        actual = sha256(artifact_path)
        checks.append(
            {
                "id": f"manifest_hash:{rel(manifest_path)}:{artifact_rel}",
                "status": "PASS" if actual == expected else "FAIL",
                "expected": expected,
                "actual": actual,
            }
        )


def write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# MX01 Static Validation Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Checks: `{report['counts']['checks']}`",
        f"- Failures: `{report['counts']['failures']}`",
        f"- Warnings: `{report['counts']['warnings']}`",
        "",
        "## Failed Checks",
        "",
    ]
    failures = [check for check in report["checks"] if check["status"] == "FAIL"]
    if failures:
        for check in failures:
            lines.append(f"- `{check['id']}`: {check.get('reason', 'failed')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Warning Checks", ""])
    warnings = [check for check in report["checks"] if check["status"] == "WARN"]
    if warnings:
        for check in warnings:
            lines.append(f"- `{check['id']}`: {check.get('reason', 'warning')}")
    else:
        lines.append("- None")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_json(config_path)
    checks: list[dict] = []

    required_sections = [
        ("normalization_outputs", "normalized_obj"),
        ("occupancy_outputs", "intervals_json"),
        ("interior_volume_outputs", "volume_json"),
        ("traversal_outputs", "graph_json"),
        ("boundary_outputs", "raw_obj"),
        ("simplification_outputs", "simplified_obj"),
        ("interior_collision_outputs", "collision_obj"),
        ("dynamic_collision_outputs", "collision_obj"),
        ("scene_outputs", "review_scene"),
        ("scene_outputs", "playable_scene"),
    ]
    for section, key in required_sections:
        check_file(resolve_config_path(config, section, key), checks)

    for manifest_path in sorted((SHIP_DIR / "reports" / "manifests").glob("mx01_*_manifest.json")):
        if manifest_path.name == "mx01_static_validation_manifest.json":
            continue
        check_manifest_hashes(manifest_path, checks)

    traversal = load_json(resolve_config_path(config, "traversal_outputs", "graph_json"))
    deck_nodes = [node for node in traversal["nodes"] if node["kind"] == "deck"]
    checks.append(
        {
            "id": "traversal:all_decks_reachable",
            "status": "PASS" if len(traversal["reachable_decks"]) == len(deck_nodes) else "FAIL",
            "reachable_decks": len(traversal["reachable_decks"]),
            "deck_nodes": len(deck_nodes),
        }
    )

    dynamic_report = load_json(resolve_config_path(config, "dynamic_collision_outputs", "report_json"))
    checks.append(
        {
            "id": "dynamic_collision:convex_only",
            "status": "PASS" if dynamic_report["counts"]["concave_regions"] == 0 and dynamic_report["counts"]["convex_regions"] > 0 else "FAIL",
            "counts": dynamic_report["counts"],
        }
    )

    occupancy_report = load_json(resolve_config_path(config, "occupancy_outputs", "report_json"))
    checks.append(
        {
            "id": "occupancy:odd_parity_rays",
            "status": "WARN" if occupancy_report["counts"]["odd_parity_rays"] else "PASS",
            "reason": "Odd parity rays remain from non-manifold/tangential cases." if occupancy_report["counts"]["odd_parity_rays"] else "No odd parity rays.",
            "odd_parity_rays": occupancy_report["counts"]["odd_parity_rays"],
        }
    )

    outside = []
    for path in SHIP_DIR.rglob("*"):
        if path.is_file() and not str(path.resolve()).startswith(str(SHIP_DIR.resolve())):
            outside.append(rel(path))
    checks.append({"id": "colocation:all_checked_files_under_mx01", "status": "PASS" if not outside else "FAIL", "outside": outside})

    failures = [check for check in checks if check["status"] == "FAIL"]
    warnings = [check for check in checks if check["status"] == "WARN"]
    report = {
        "ship_id": config["ship_id"],
        "method": "mx01_static_collision_validation_v1",
        "status": "PASS" if not failures else "FAIL",
        "counts": {"checks": len(checks), "failures": len(failures), "warnings": len(warnings)},
        "checks": checks,
        "config": {"path": rel(config_path), "sha256": sha256(config_path), "effective_values": config},
        "tools": {
            "validate_mx01_collision_static.py": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())}
        },
    }

    report_json = resolve_config_path(config, "validation_outputs", "report_json")
    report_md = resolve_config_path(config, "validation_outputs", "report_md")
    manifest_json = resolve_config_path(config, "validation_outputs", "manifest_json")
    write_json(report_json, report)
    write_markdown(report_md, report)
    write_json(
        manifest_json,
        {
            "ship_id": config["ship_id"],
            "stage": "static_validation",
            "config": report["config"],
            "outputs": {
                "report_json": rel(report_json),
                "report_json_sha256": sha256(report_json),
                "report_md": rel(report_md),
            },
            "tools": report["tools"],
        },
    )
    print(f"Wrote {rel(report_json)}")
    print(f"Wrote {rel(report_md)}")
    print(f"Wrote {rel(manifest_json)}")
    print(f"status={report['status']} failures={len(failures)} warnings={len(warnings)}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
