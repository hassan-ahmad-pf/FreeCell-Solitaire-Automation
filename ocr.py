"""Read on-screen numbers with macOS Vision (scripts/vision_ocr.swift).

FreeCell's scores are drawn in two fonts (Victory/Statistics and the Daily
score popup), so pixel templates cannot compare them; Vision reads both.
The Swift reader is compiled into log/bin on first use (about a minute).
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import config

SOURCE = Path(__file__).resolve().parent / "scripts" / "vision_ocr.swift"
BINARY = config.LOG / "bin" / "vision_ocr"
# Vision reads "47,739" as "47, 739", "47.739" or "47‚739" (U+201A) now and then.
NUMBER = re.compile(r"\d{1,3}(?:[,.\u201a] ?\d{3})+|\d+")
ROW_TOLERANCE = 22


@dataclass
class Line:
    x0: int
    y0: int
    x1: int
    y1: int
    text: str

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


def _binary() -> Path:
    if not BINARY.exists() or BINARY.stat().st_mtime < SOURCE.stat().st_mtime:
        BINARY.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", str(SOURCE), "-o", str(BINARY)], check=True,
                       capture_output=True, timeout=300)
    return BINARY


def read(image, box: tuple[int, int, int, int] | None = None) -> list[Line]:
    """Text lines in *image* (a path or PIL image), in screen pixels."""
    from PIL import Image

    img = Image.open(image) if isinstance(image, (str, Path)) else image
    x0, y0 = (box[0], box[1]) if box else (0, 0)
    if box:
        img = img.crop(box)
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        img.convert("RGB").save(tmp.name)
        out = subprocess.run([str(_binary()), tmp.name], capture_output=True, text=True,
                             timeout=60).stdout
    lines = []
    for row in out.splitlines():
        parts = row.split("\t", 4)
        if len(parts) == 5:
            a, b, c, d = (int(p) for p in parts[:4])
            lines.append(Line(a + x0, b + y0, c + x0, d + y0, parts[4]))
    return lines


def numbers(text: str) -> list[int]:
    return [int(re.sub(r"[,.\u201a ]", "", n)) for n in NUMBER.findall(text)]


def rows(lines: list[Line]) -> list[tuple[float, str]]:
    """Group lines sharing a baseline; each row's text joined left to right."""
    grouped: list[list[Line]] = []
    for line in sorted(lines, key=lambda ln: ln.cy):
        if grouped and abs(grouped[-1][0].cy - line.cy) <= ROW_TOLERANCE:
            grouped[-1].append(line)
        else:
            grouped.append([line])
    return [(sum(ln.cy for ln in g) / len(g),
             " ".join(ln.text for ln in sorted(g, key=lambda ln: ln.x0))) for g in grouped]
