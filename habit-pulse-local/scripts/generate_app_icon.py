from __future__ import annotations

import struct
import subprocess
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
ICONSET_DIR = ASSETS_DIR / "HabitPulse.iconset"
ICNS_FILE = ASSETS_DIR / "HabitPulse.icns"


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    payload = chunk_type + data
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", crc)


def write_png(path: Path, width: int, height: int, pixels: list[list[tuple[int, int, int, int]]]) -> None:
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for red, green, blue, alpha in row:
            raw.extend((red, green, blue, alpha))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    compressed = zlib.compress(bytes(raw), level=9)

    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", ihdr)
    png += png_chunk(b"IDAT", compressed)
    png += png_chunk(b"IEND", b"")

    path.write_bytes(png)


def inside_rounded_rect(x: int, y: int, size: int, radius: int) -> bool:
    if radius <= 0:
        return 0 <= x < size and 0 <= y < size

    if radius <= x < size - radius and 0 <= y < size:
        return True
    if radius <= y < size - radius and 0 <= x < size:
        return True

    corners = [
        (radius, radius),
        (size - radius - 1, radius),
        (radius, size - radius - 1),
        (size - radius - 1, size - radius - 1),
    ]
    for cx, cy in corners:
        dx = x - cx
        dy = y - cy
        if dx * dx + dy * dy <= radius * radius:
            return True
    return False


def render_icon(size: int) -> list[list[tuple[int, int, int, int]]]:
    radius = max(3, int(size * 0.22))
    border = max(1, int(size * 0.03))

    cell_size = max(3, int(size * 0.17))
    gap = max(1, int(size * 0.04))
    grid_size = cell_size * 3 + gap * 2
    start_x = (size - grid_size) // 2
    start_y = (size - grid_size) // 2

    done = (96, 191, 114, 255)
    missed = (224, 109, 109, 255)
    pending = (212, 220, 207, 255)
    pattern = [
        [done, done, pending],
        [done, missed, done],
        [pending, done, missed],
    ]

    pixels: list[list[tuple[int, int, int, int]]] = []
    for y in range(size):
        row: list[tuple[int, int, int, int]] = []
        tint = y / max(1, size - 1)
        back_r = int(35 + (68 - 35) * tint)
        back_g = int(92 + (132 - 92) * tint)
        back_b = int(58 + (93 - 58) * tint)

        for x in range(size):
            if not inside_rounded_rect(x, y, size, radius):
                row.append((0, 0, 0, 0))
                continue

            color = (back_r, back_g, back_b, 255)

            edge = (
                x < border
                or y < border
                or x >= size - border
                or y >= size - border
                or not inside_rounded_rect(x, y, size, max(0, radius - border))
            )
            if edge:
                color = (22, 61, 40, 255)

            for row_idx in range(3):
                for col_idx in range(3):
                    cx = start_x + col_idx * (cell_size + gap)
                    cy = start_y + row_idx * (cell_size + gap)
                    if cx <= x < cx + cell_size and cy <= y < cy + cell_size:
                        color = pattern[row_idx][col_idx]

            row.append(color)
        pixels.append(row)
    return pixels


def build_iconset() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    if ICONSET_DIR.exists():
        for item in ICONSET_DIR.iterdir():
            item.unlink()
    ICONSET_DIR.mkdir(parents=True, exist_ok=True)

    icon_sizes = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }

    for file_name, size in icon_sizes.items():
        target = ICONSET_DIR / file_name
        write_png(target, size, size, render_icon(size))


def build_icns() -> None:
    build_iconset()
    subprocess.run(
        ["iconutil", "-c", "icns", str(ICONSET_DIR), "-o", str(ICNS_FILE)],
        check=True,
    )


if __name__ == "__main__":
    build_icns()
    print(f"Icon created at {ICNS_FILE}")
