#!/usr/bin/env python3
"""Standardize ship review evidence and remove stale generated artifacts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
DEFAULT_KEEP = 3


@dataclass(frozen=True)
class EvidenceSet:
    id: str
    directory: Path
    stem: str
    title: str


EVIDENCE_SETS = [
    EvidenceSet(
        id="ship_walkthrough",
        directory=REPORTS / "ship_walkthrough",
        stem="ship_walkthrough",
        title="Full ship interior walkthrough",
    ),
    EvidenceSet(
        id="ship_cockpit_walkthrough",
        directory=REPORTS / "ship_cockpit_walkthrough",
        stem="ship_cockpit_walkthrough",
        title="Cockpit-focused walkthrough",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    parser.add_argument("--no-delete-frames", action="store_true")
    return parser.parse_args()


def remove_path(path: Path, removed: list[str]) -> None:
    if path.exists() and path.is_file():
        path.unlink()
        removed.append(str(path.relative_to(ROOT)))
    sidecar = Path(f"{path}.import")
    if sidecar.exists() and sidecar.is_file():
        sidecar.unlink()
        removed.append(str(sidecar.relative_to(ROOT)))


def keep_newest(paths: list[Path], keep: int, removed: list[str]) -> list[Path]:
    paths = [path for path in paths if path.exists() and path.is_file()]
    paths.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for stale in paths[keep:]:
        remove_path(stale, removed)
    return paths[:keep]


def timestamped_artifacts(evidence: EvidenceSet) -> dict[str, list[Path]]:
    directory = evidence.directory
    return {
        "mp4": [
            path
            for path in directory.glob(f"{evidence.stem}_*.mp4")
            if "_current" not in path.name
        ],
        "contact_sheet": [
            path
            for path in directory.glob(f"{evidence.stem}_contact_sheet_*.png")
            if "_current" not in path.name
        ],
    }


def remove_legacy_artifacts(evidence: EvidenceSet, removed: list[str]) -> None:
    directory = evidence.directory
    legacy_patterns = [
        "*.gif",
        "contact_sheet_*.png",
        "contact_sheet_latest.png",
        "walkthrough_contact_sheet_*.png",
        "walkthrough_contact_sheet_current.ppm",
        "aft_review_frame_*.png",
        "frame_*_current.png",
    ]
    for pattern in legacy_patterns:
        for path in directory.glob(pattern):
            remove_path(path, removed)
    debug_png = directory / "debug_png"
    if debug_png.exists():
        for path in debug_png.glob("*.png"):
            remove_path(path, removed)


def remove_raw_frames(evidence: EvidenceSet, removed: list[str]) -> None:
    frames_dir = evidence.directory / "frames"
    if not frames_dir.exists():
        return
    for path in frames_dir.glob("frame_*.rgb"):
        remove_path(path, removed)


def current_artifacts(evidence: EvidenceSet) -> dict[str, str | None]:
    current_mp4 = evidence.directory / f"{evidence.stem}_current.mp4"
    current_contact_sheet = evidence.directory / f"{evidence.stem}_contact_sheet_current.png"
    return {
        "mp4": str(current_mp4.relative_to(ROOT)) if current_mp4.exists() else None,
        "contact_sheet": str(current_contact_sheet.relative_to(ROOT)) if current_contact_sheet.exists() else None,
    }


def standardize(evidence: EvidenceSet, keep: int, delete_frames: bool) -> dict[str, object]:
    removed: list[str] = []
    kept_timestamped = {}
    for artifact_type, paths in timestamped_artifacts(evidence).items():
        kept = keep_newest(paths, keep, removed)
        kept_timestamped[artifact_type] = [str(path.relative_to(ROOT)) for path in kept]

    remove_legacy_artifacts(evidence, removed)
    if delete_frames:
        remove_raw_frames(evidence, removed)

    return {
        "id": evidence.id,
        "title": evidence.title,
        "directory": str(evidence.directory.relative_to(ROOT)),
        "current": current_artifacts(evidence),
        "kept_timestamped": kept_timestamped,
        "removed_count": len(removed),
        "removed": removed,
    }


def write_index(results: list[dict[str, object]], keep: int) -> None:
    index = {
        "schema_version": 1,
        "retention_policy": {
            "timestamped_artifacts_per_type": keep,
            "raw_rgb_frames": "deleted after MP4/contact-sheet generation",
            "current_aliases": "preserved",
        },
        "evidence": results,
    }
    (REPORTS / "ship_evidence_index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Ship Evidence Index",
        "",
        "Current review artifacts:",
        "",
    ]
    for result in results:
        current = result["current"]
        lines.extend(
            [
                f"## {result['title']}",
                "",
                f"- MP4: `{current['mp4']}`",
                f"- Contact sheet: `{current['contact_sheet']}`",
                f"- Removed stale files this run: `{result['removed_count']}`",
                "",
            ]
        )
    (REPORTS / "ship_evidence_index.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    results = [
        standardize(evidence, keep=max(0, args.keep), delete_frames=not args.no_delete_frames)
        for evidence in EVIDENCE_SETS
    ]
    write_index(results, keep=max(0, args.keep))
    for result in results:
        print(f"{result['id']}: removed {result['removed_count']} stale generated file(s)")
    print("Evidence index: reports/ship_evidence_index.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
