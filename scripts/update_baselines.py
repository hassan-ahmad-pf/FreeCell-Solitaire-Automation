#!/usr/bin/env python3
"""Promote an Obj-C capture pass into baselines/ and learn volatile masks.

For every screen in ``visual.SCREENS`` that ``tests/capture_baselines.py``
captured, this writes one shot to ``baselines/<Name>.png``, re-encoded
losslessly (every decoded pixel is WDA's, the file about a quarter smaller) —
the one closest to the per-pixel median of the three, so the fewest glints
and no late transition frame (``--pick`` forces one) — and learns
``baselines/<Name>.volatile.png`` from all three: steady motion (smileys)
plus any glint baked into the picked shot. Screens flagged ``animated``
(More Games) mask whatever moved across their shots and those of every
``--also`` pass. It then rewrites ``baselines/MANIFEST.md`` and
``baselines/baselines.json`` (identity, source pass per screen, how each
screen is reached, masks).

Refuses unless the pass's ``capture.json`` says FreeCell 7.42.5 (279) at
1290x2796: the baselines are the Obj-C reference, and a Unity capture must
never land here. Existing baselines are only replaced with ``--replace``.

Usage:
    ./.venv/bin/python scripts/update_baselines.py
    ./.venv/bin/python scripts/update_baselines.py --replace --only HelpMid
    ./.venv/bin/python scripts/update_baselines.py --src log/objc_pass2 \
        --also log/objc_baselines --replace
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import config  # noqa: E402
import visual  # noqa: E402


def mask_names() -> dict:
    """Box tuple → its constant name in visual.py, for the manifest."""
    names = {}
    for key, value in vars(visual).items():
        if key.isupper() and isinstance(value, tuple) and len(value) == 4 \
                and all(isinstance(v, int) for v in value):
            names.setdefault(value, key)
    return names


def describe(boxes, names) -> str:
    return ", ".join(names.get(tuple(b), str(tuple(b))) for b in boxes) or "—"


def write_lossless(src: Path, target: Path) -> None:
    """*src* re-encoded smaller; refuses unless every decoded pixel matches."""
    with Image.open(src) as im:
        pixels = np.asarray(im)
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
    if not np.array_equal(pixels, np.asarray(Image.open(buf))):
        raise SystemExit(f"re-encoding {src} changed its pixels")
    target.write_bytes(buf.getvalue())


def guard(capture: dict) -> str | None:
    """Why this capture must not become a baseline, or None."""
    got = (capture.get("version"), capture.get("build"))
    want = (config.OBJC_VERSION, config.OBJC_BUILD)
    if got != want:
        return (f"capture.json says {got[0] or '?'} ({got[1] or '?'}); only the "
                f"Obj-C reference build {want[0]} ({want[1]}) may be promoted. "
                "Unity captures are compared with tests/compare_unity.py, never "
                "baselined.")
    if capture.get("size") != [visual.W, visual.H]:
        return f"capture.json size {capture.get('size')} is not {visual.W}x{visual.H}"
    return None


def write_manifest(record: dict, names: dict) -> None:
    identity = record["identity"]
    lines = [
        "# FreeCell Obj-C baselines",
        "",
        "The reference the Unity port is compared against. **Never re-baseline "
        "these to a Unity build** — a large diff is the finding.",
        "",
        f"- App: {identity['name']} {identity['version']} (build "
        f"{identity['build']}, About shows \"279 build 60706F\"), "
        f"`{identity['bundle_id']}`",
        f"- Device: {identity['model']} (iPhone 15 Pro Max), iOS "
        f"{identity['ios']}, portrait {visual.W}x{visual.H}",
        "- Captured by `tests/capture_baselines.py` on fresh installs; last "
        f"promoted {record['promoted']}. Each screen's pass and kept shot (of "
        "3, the one closest to their per-pixel median) are in "
        "`baselines.json`",
        f"- Daily table: {record.get('daily_date', '?')}, "
        f"{record.get('daily_level', '?')} — a Unity capture must deal the same "
        "date for `DailyTable` to be comparable",
        "- Network: offline except the Terms / Privacy pages; QA locked except "
        "phase B",
        "",
        "Every screen masks the status bar; screens above the wood tray also "
        "mask `BANNER` (house cross-promo banner and the wood below it). "
        "`volatile` is the share of the screen masked by "
        "`<Name>.volatile.png`: motion seen in at least two of the three "
        "shots, plus any glint in the shot that was kept (More Games: "
        "anything that moved in any shot of either pass). A comparison takes "
        "the per-pixel median of its own shots, so a one-off glint needs no "
        "mask.",
        "",
        "About is not listed as a bottom page: it fits on one screen.",
        "",
        "| Screen | Phase | Reached by | State | Masks | Volatile | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, screen in visual.SCREENS.items():
        entry = record["screens"].get(name)
        if not entry:
            continue
        lines.append(
            f"| `{name}` | {screen.phase} | {screen.how} | {screen.state} | "
            f"{describe(screen.ignore, names)} | {entry['volatile_pct']:.2f}% | "
            f"{screen.note} |")
    missing = [n for n in visual.SCREENS if n not in record["screens"]]
    if missing:
        lines += ["", "Not baselined yet: " + ", ".join(f"`{n}`" for n in missing)]
    (visual.BASELINES / "MANIFEST.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", default=str(config.LOG / "objc_baselines"))
    parser.add_argument("--pick", type=int, choices=(1, 2, 3),
                        help="force this shot (default: the most typical)")
    parser.add_argument("--also", action="append", default=[],
                        help="another pass whose shots join the volatile "
                             "mask of animated screens (repeatable)")
    parser.add_argument("--only", default="")
    parser.add_argument("--replace", action="store_true",
                        help="overwrite baselines that already exist")
    args = parser.parse_args()

    src = Path(args.src)
    capture_json = src / "capture.json"
    if not capture_json.exists():
        print(f"no capture.json in {src} — run tests/capture_baselines.py first")
        return 2
    capture = json.loads(capture_json.read_text())
    refusal = guard(capture)
    if refusal:
        print(f"REFUSED: {refusal}")
        return 2

    only = {n.strip() for n in args.only.split(",") if n.strip()}
    base = visual.BASELINES
    base.mkdir(parents=True, exist_ok=True)
    book_path = base / "baselines.json"
    book = json.loads(book_path.read_text()) if book_path.exists() else {"screens": {}}

    promoted, skipped = [], []
    for name in visual.SCREENS:
        if only and name not in only:
            continue
        entry = capture.get("screens", {}).get(name)
        if not entry:
            reason = capture.get("missing", {}).get(name, "not captured")
            skipped.append((name, reason))
            continue
        target = base / f"{name}.png"
        if target.exists() and not args.replace:
            skipped.append((name, "baseline exists (pass --replace)"))
            continue
        if entry.get("assistive_touch"):
            skipped.append((name, "AssistiveTouch was on screen"))
            continue
        if entry.get("banner") is False:
            skipped.append((name, "captured before the banner was drawn"))
            continue
        shots = [src / s for s in entry["shots"]]
        if not all(s.exists() for s in shots):
            skipped.append((name, "a shot file is missing"))
            continue
        pick = args.pick - 1 if args.pick else visual.typical_shot(shots)
        write_lossless(shots[pick], target)
        if visual.SCREENS[name].animated:
            pooled = shots + [s for d in args.also
                              for s in visual.capture_shots(d, name)]
            vol = visual.build_volatile_mask(pooled, span=True)
        else:
            vol = visual.build_volatile_mask(shots, pick)
        vol_path = visual.volatile_path(name)
        pct = 0.0
        if vol is not None and (vol > 127).any():
            cv2.imwrite(str(vol_path), vol)
            pct = 100.0 * float((vol > 127).mean())
        else:
            vol_path.unlink(missing_ok=True)
        book["screens"][name] = {
            "source": src.name, "shot": pick + 1,
            "volatile_pct": round(pct, 3),
            "settled": entry.get("settled"), "captured": entry.get("at"),
        }
        promoted.append((name, pick + 1, pct))

    book["identity"] = {k: capture.get(k) for k in
                        ("bundle_id", "name", "version", "build", "model", "ios",
                         "size", "started")}
    book.pop("pick", None)
    book["promoted"] = dt.datetime.now().isoformat(timespec="seconds")
    notes = capture.get("notes", {})
    for key in ("daily_date", "daily_level"):
        if key in notes:
            book[key] = notes[key]
    book_path.write_text(json.dumps(book, indent=2) + "\n")
    write_manifest(book, mask_names())

    for name, shot, pct in promoted:
        print(f"  promoted {name:20s} shot {shot}  volatile {pct:5.2f}%")
    for name, reason in skipped:
        print(f"  skipped  {name:20s} {reason}")
    print(f"\n{len(promoted)} promoted, {len(skipped)} skipped → {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
