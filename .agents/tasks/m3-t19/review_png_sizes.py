import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

for path in sorted((ROOT / "docs" / "assets" / "ui_v3").glob("*.png")):
    with path.open("rb") as handle:
        head = handle.read(24)
    ok = head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR"
    width, height = struct.unpack(">II", head[16:24]) if ok else (0, 0)
    print(f"{path.name:40} {'png' if ok else 'BAD'} {width}x{height} {path.stat().st_size}")
