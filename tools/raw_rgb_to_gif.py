#!/usr/bin/env python3
"""Assemble raw RGB walkthrough frames into a small animated GIF.

This avoids depending on ffmpeg, ImageMagick, Pillow, or imageio on the host.
It uses a fixed 3-3-2 RGB palette and GIF LZW compression.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "reports/ship_walkthrough"
DEFAULT_OUTPUT = DEFAULT_INPUT / "ship_walkthrough.gif"


def palette() -> bytes:
    table = bytearray()
    for r in range(6):
        for g in range(6):
            for b in range(6):
                table.extend((r * 51, g * 51, b * 51))
    for index in range(40):
        value = round(index * 255 / 39)
        table.extend((value, value, value))
    return bytes(table)


def quantize_rgb(data: bytes) -> bytes:
    out = bytearray(len(data) // 3)
    for i in range(0, len(data), 3):
        r, g, b = data[i], data[i + 1], data[i + 2]
        if max(r, g, b) - min(r, g, b) < 18:
            gray = round(((r + g + b) / 3) * 39 / 255)
            out[i // 3] = 216 + gray
        else:
            qr = min(5, round(r / 51))
            qg = min(5, round(g / 51))
            qb = min(5, round(b / 51))
            out[i // 3] = qr * 36 + qg * 6 + qb
    return bytes(out)


def lzw_encode(indexes: bytes, min_code_size: int = 8) -> bytes:
    clear_code = 1 << min_code_size
    end_code = clear_code + 1

    output = bytearray()
    bit_buffer = 0
    bit_count = 0

    def write_code(code: int, code_size: int) -> None:
        nonlocal bit_buffer, bit_count
        bit_buffer |= code << bit_count
        bit_count += code_size
        while bit_count >= 8:
            output.append(bit_buffer & 0xFF)
            bit_buffer >>= 8
            bit_count -= 8

    dictionary: dict[bytes, int] = {bytes([i]): i for i in range(clear_code)}
    next_code = end_code + 1
    code_size = min_code_size + 1

    write_code(clear_code, code_size)
    current = bytes([indexes[0]])

    for value in indexes[1:]:
        candidate = current + bytes([value])
        if candidate in dictionary:
            current = candidate
            continue

        write_code(dictionary[current], code_size)

        if next_code < 4096:
            dictionary[candidate] = next_code
            next_code += 1
            if next_code > (1 << code_size) and code_size < 12:
                code_size += 1
        else:
            write_code(clear_code, code_size)
            dictionary = {bytes([i]): i for i in range(clear_code)}
            next_code = end_code + 1
            code_size = min_code_size + 1

        current = bytes([value])

    write_code(dictionary[current], code_size)
    write_code(end_code, code_size)

    if bit_count:
        output.append(bit_buffer & 0xFF)

    return bytes(output)


def subblocks(data: bytes) -> bytes:
    out = bytearray()
    for index in range(0, len(data), 255):
        chunk = data[index:index + 255]
        out.append(len(chunk))
        out.extend(chunk)
    out.append(0)
    return bytes(out)


def write_gif(input_dir: Path, output_path: Path) -> None:
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    width = int(manifest["width"])
    height = int(manifest["height"])
    fps = int(manifest["fps"])
    frame_count = int(manifest["frame_count"])
    delay = max(1, round(100 / fps))
    hold_last_seconds = float(manifest.get("hold_last_seconds", 1.0))
    hold_last_delay = max(0, round(hold_last_seconds * 100))
    frame_dir = input_dir / str(manifest["frames_directory"])

    frames = sorted(frame_dir.glob("frame_*.rgb"))
    if len(frames) != frame_count:
        raise RuntimeError(f"Expected {frame_count} frames, found {len(frames)} in {frame_dir}")

    output = bytearray()
    output.extend(b"GIF89a")
    output.extend(struct.pack("<HH", width, height))
    output.extend(bytes([0b11110111, 0, 0]))
    output.extend(palette())
    output.extend(b"!\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00")

    expected_bytes = width * height * 3
    for index, frame in enumerate(frames):
        raw = frame.read_bytes()
        if len(raw) != expected_bytes:
            raise RuntimeError(f"{frame} has {len(raw)} bytes; expected {expected_bytes}")
        indexed = quantize_rgb(raw)
        image_data = lzw_encode(indexed)
        frame_delay = delay + hold_last_delay if index == len(frames) - 1 else delay

        output.extend(b"!\xf9\x04")
        output.extend(bytes([0]))
        output.extend(struct.pack("<H", frame_delay))
        output.extend(bytes([0, 0]))
        output.extend(b",")
        output.extend(struct.pack("<HHHH", 0, 0, width, height))
        output.extend(bytes([0, 8]))
        output.extend(subblocks(image_data))

    output.extend(b";")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output)


def main() -> int:
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    write_gif(input_dir, output_path)
    resolved_output = output_path.resolve()
    try:
        display_path = resolved_output.relative_to(ROOT)
    except ValueError:
        display_path = resolved_output
    print(f"Wrote {display_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
