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
# Gold Daily / Replay digits also come back as Cyrillic lookalikes:
# З4‚З69х2 for 34,369 x2; 77,90₴ for 77,902; 7ř,7З6 for 77,736.
NUMBER = re.compile(r"\d{1,3}(?:[,.\u201a\u066b' ]\s?\d{2,3})+|\d+")
_LOOKALIKES = str.maketrans({
    "О": "0", "о": "0", "Ο": "0", "０": "0",
    "І": "1", "１": "1",
    "₴": "2", "２": "2",
    "З": "3", "з": "3", "３": "3",
    "４": "4",
    "Ѕ": "5", "５": "5",
    "６": "6",
    "ř": "7", "Ř": "7", "７": "7",
    "８": "8",
    "９": "9",
    "х": "x", "Х": "x", "×": "x",
})
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


def clean(text: str) -> str:
    """Fold Vision lookalikes so a gold 34,369 is not З4‚З69."""
    return text.translate(_LOOKALIKES).replace("O", "0")


def numbers(text: str) -> list[int]:
    return [int(re.sub(r"[,.\u201a\u066b' ]", "", n)) for n in NUMBER.findall(clean(text))]


def glue(found: list[int]) -> int | None:
    """Join a score Vision split on the thousands comma.

    77 + 902 → 77,902; 34 + 369 → 34,369; two already-full scores stay
    the longer one (33,316 = 33,316). A trailing x2 is not glued on.
    """
    if not found:
        return None
    if len(found) == 1:
        return found[0]
    parts = list(found)
    if parts[-1] == 2 and len(parts) > 1:
        parts = parts[:-1]
    if all(len(str(abs(n))) >= 4 for n in parts):
        return max(parts, key=lambda n: (len(str(abs(n))), n))
    bits = [str(abs(n)) for n in parts]
    if (1 <= len(bits[0]) <= 3
            and bits[1:]
            and all(2 <= len(p) <= 3 for p in bits[1:])):
        return int("".join(bits))
    long = [n for n in parts if len(str(abs(n))) >= 4]
    return max(long, key=lambda n: (len(str(abs(n))), n)) if long else int("".join(bits))


def score(text: str) -> int | None:
    """The best score in *text*: lookalikes folded, comma groups glued."""
    found = numbers(text)
    glued = glue(found)
    picks = [n for n in ((glued,) + tuple(found)) if n is not None]
    if not picks:
        digits = re.sub(r"\D", "", clean(text))
        return int(digits) if len(digits) >= 2 else None
    return max(picks, key=lambda n: (len(str(abs(n))), n))


def same(shown: int, want: int) -> bool:
    """True when *shown* is *want*, or Vision only cut / flipped a digit.

    Comma-group cut: 77,90 for 77,902; +54 for +54,762.
    One digit of a 5+ digit score: 238,983 for 232,983 (2↔8).
    Short counts (2, 4, 6) stay exact — those are games won, not scores.
    """
    if shown == want:
        return True
    a, b = str(abs(shown)), str(abs(want))
    short, full = (a, b) if len(a) <= len(b) else (b, a)
    # Prefix only: Vision cuts the thousands group (77,90 for 77,902).
    # A suffix match would treat 69 as 34,369.
    if (len(full) >= 5 and len(short) >= 2
            and 1 <= len(full) - len(short) <= 3
            and full.startswith(short)):
        return True
    return len(a) == len(b) >= 5 and sum(x != y for x, y in zip(a, b)) == 1


def pick(nums: list[int], want: int | None = None) -> int | None:
    """A real score from *nums*: the one that matches *want*, else the longest ≥ 1000."""
    if not nums:
        return None
    if want is not None:
        for n in nums:
            if n == want or same(n, want):
                return n
        glued = glue(nums)
        if glued is not None and (glued == want or same(glued, want)):
            return glued
    long = [n for n in nums if n >= 1000]
    if long:
        return max(long, key=lambda n: (len(str(n)), n))
    glued = glue(nums)
    return glued if glued is not None else nums[0]


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
