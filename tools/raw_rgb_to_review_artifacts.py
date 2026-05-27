#!/usr/bin/env python3
"""Create high-fidelity review artifacts from Godot raw RGB frame captures."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMPED_ARTIFACT_RETENTION = 3


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_rgb_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    rows = bytearray()
    row_len = width * 3
    for y in range(height):
        rows.append(0)
        start = y * row_len
        rows.extend(rgb[start : start + row_len])

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += png_chunk(b"IDAT", zlib.compress(bytes(rows), 6))
    png += png_chunk(b"IEND", b"")
    path.write_bytes(png)


def resize_nearest(rgb: bytes, width: int, height: int, out_w: int, out_h: int) -> bytes:
    output = bytearray(out_w * out_h * 3)
    for y in range(out_h):
        source_y = y * height // out_h
        for x in range(out_w):
            source_x = x * width // out_w
            source = (source_y * width + source_x) * 3
            target = (y * out_w + x) * 3
            output[target : target + 3] = rgb[source : source + 3]
    return bytes(output)


def build_contact_sheet(
    output_path: Path,
    frames: list[Path],
    width: int,
    height: int,
    samples: list[int],
    columns: int = 4,
) -> None:
    thumb_w = min(480, width)
    thumb_h = max(1, round(thumb_w * height / width))
    rows = (len(samples) + columns - 1) // columns
    sheet_w = columns * thumb_w
    sheet_h = rows * thumb_h
    sheet = bytearray([18, 18, 20] * sheet_w * sheet_h)

    for index, frame_index in enumerate(samples):
        frame_rgb = frames[frame_index].read_bytes()
        thumb = resize_nearest(frame_rgb, width, height, thumb_w, thumb_h)
        col = index % columns
        row = index // columns
        for y in range(thumb_h):
            src = y * thumb_w * 3
            dst_x = col * thumb_w
            dst_y = row * thumb_h + y
            dst = (dst_y * sheet_w + dst_x) * 3
            sheet[dst : dst + thumb_w * 3] = thumb[src : src + thumb_w * 3]

    write_rgb_png(output_path, sheet_w, sheet_h, bytes(sheet))


def write_mp4(
    output_path: Path,
    frames: list[Path],
    width: int,
    height: int,
    fps: int,
    hold_last_seconds: float,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg was not found on PATH")

    command = [
        ffmpeg,
        "-y",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        f"{width}x{height}",
        "-framerate",
        str(fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]

    hold_frames = max(0, round(hold_last_seconds * fps))
    with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
        assert process.stdin is not None
        for frame in frames:
            process.stdin.write(frame.read_bytes())
        if frames and hold_frames > 0:
            last = frames[-1].read_bytes()
            for _ in range(hold_frames):
                process.stdin.write(last)
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError(f"ffmpeg failed with exit code {process.returncode}")


def prune_timestamped_artifacts(input_dir: Path, stem: str, keep: int = TIMESTAMPED_ARTIFACT_RETENTION) -> None:
    patterns = [
        f"{stem}_*.mp4",
        f"{stem}_contact_sheet_*.png",
    ]

    for pattern in patterns:
        artifacts = [
            path
            for path in input_dir.glob(pattern)
            if "_current" not in path.name and path.is_file()
        ]
        artifacts.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for path in artifacts[keep:]:
            path.unlink()
            import_sidecar = Path(f"{path}.import")
            if import_sidecar.exists():
                import_sidecar.unlink()

    for import_sidecar in input_dir.glob(f"{stem}_contact_sheet_*.png.import"):
        png_path = Path(str(import_sidecar)[: -len(".import")])
        if not png_path.exists():
            import_sidecar.unlink()


def main() -> int:
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports/ship_walkthrough"
    stem = sys.argv[2] if len(sys.argv) > 2 else input_dir.name
    input_dir = input_dir if input_dir.is_absolute() else ROOT / input_dir

    manifest_path = input_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    width = int(manifest["width"])
    height = int(manifest["height"])
    frame_count = int(manifest["frame_count"])
    fps = int(manifest["fps"])
    hold_last_seconds = float(manifest.get("hold_last_seconds", 0.0))
    frames_dir = input_dir / str(manifest["frames_directory"])
    frames = sorted(frames_dir.glob("frame_*.rgb"))

    if len(frames) != frame_count:
        raise RuntimeError(f"Expected {frame_count} frames, found {len(frames)} in {frames_dir}")

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    sample_indexes = sorted(set(
        max(0, min(frame_count - 1, round((frame_count - 1) * t)))
        for t in [0.0, 0.06, 0.12, 0.22, 0.32, 0.42, 0.52, 0.62, 0.72, 0.82, 0.90, 0.96, 1.0]
    ))

    contact_sheet = input_dir / f"{stem}_contact_sheet_{timestamp}.png"
    current_contact_sheet = input_dir / f"{stem}_contact_sheet_current.png"
    mp4 = input_dir / f"{stem}_{timestamp}.mp4"
    current_mp4 = input_dir / f"{stem}_current.mp4"

    build_contact_sheet(contact_sheet, frames, width, height, sample_indexes)
    shutil.copyfile(contact_sheet, current_contact_sheet)
    write_mp4(mp4, frames, width, height, fps, hold_last_seconds)
    shutil.copyfile(mp4, current_mp4)
    prune_timestamped_artifacts(input_dir, stem)

    print(f"Contact sheet: {contact_sheet.relative_to(ROOT)}")
    print(f"Current contact sheet: {current_contact_sheet.relative_to(ROOT)}")
    print(f"MP4: {mp4.relative_to(ROOT)}")
    print(f"Current MP4: {current_mp4.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
