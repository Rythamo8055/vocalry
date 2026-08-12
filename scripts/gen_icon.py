import math
import struct
import sys
import zlib
from pathlib import Path

def write_png(path, size, pix):
    raw = b""
    for y in range(size):
        raw += b"\x00"
        for x in range(size):
            raw += bytes(pix[y * size + x])
    comp = zlib.compress(raw)
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    path.write_bytes(png)

def main(size=512, path=None):
    path = path or Path(__file__).parent / ".." / "src-tauri" / "icons" / "icon.png"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pix = []
    cx = cy = size / 2
    for y in range(size):
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist = math.hypot(dx, dy)
            rr = size * 0.42
            if dist > rr:
                pix.append((0, 0, 0, 0))
                continue
            t = math.atan2(dy, dx)
            a = (t + math.pi) / (2 * math.pi)
            r = int(34 + 62 * a)
            g = int(140 + 45 * a)
            b = int(255)
            alpha = 255
            if dist > rr * 0.94:
                alpha = int(255 * (1 - (dist - rr * 0.94) / (rr * 0.06)))
            pix.append((r, g, b, alpha))
    write_png(path, size, pix)
    print(f"wrote {path}")

if __name__ == "__main__":
    main()
