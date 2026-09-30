#!/usr/bin/env python3
"""Diff a folder of FreeCell captures against the Obj-C baselines.

Each capture must carry its screen's name (``<Name>.png``, or the three-shot
``<Name>_{1,2,3}.png`` that tests/capture_baselines.py writes) and come from
an iPhone 15 Pro Max in portrait (1290x2796). Masks and thresholds are
``visual.SCREENS``.

For a Unity build a large diff is the finding, so the exit code is 0 whatever
the diffs are — read the table. ``--strict`` exits 1 when any screen is over
its threshold; that is the clean check for a second Obj-C pass, where every
screen must pass.

Diff images (baseline | capture, changed pixels red) and results.json go to
``log/diff/<folder name>/``.

Run:
  ./.venv/bin/python tests/compare_unity.py --dir log/unity/353
  ./.venv/bin/python tests/compare_unity.py --dir log/objc_pass2 --strict
  ./.venv/bin/python tests/compare_unity.py --dir log/unity/353 \\
      --ignore 1000,2300,1290,2420      # e.g. a Unity debug button
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import visual  # noqa: E402

HOW = ("capture the build under test into log/unity/<build>/ with one "
       "<Name>.png per screen in visual.SCREENS (for the Obj-C clean check: "
       "tests/capture_baselines.py --out log/objc_pass2)")


def latest_unity_dir() -> Path:
    root = config.LOG / "unity"
    dirs = sorted((d for d in root.glob("*") if d.is_dir()),
                  key=lambda d: d.stat().st_mtime) if root.exists() else []
    return dirs[-1] if dirs else root / "<build>"


def capture_label(folder: Path) -> str:
    info = folder / "capture.json"
    if info.exists():
        data = json.loads(info.read_text())
        if data.get("version"):
            return f"{data.get('name') or 'FreeCell'} {data['version']} ({data.get('build', '?')})"
    return folder.name


def parse_box(text: str) -> tuple:
    box = tuple(int(v) for v in text.split(","))
    if len(box) != 4:
        raise argparse.ArgumentTypeError("a box is x0,y0,x1,y1")
    return box


def run(folder: Path, shot=None, only=(), extra=(), strict=False) -> int:
    label = capture_label(folder)
    diff_dir = config.LOG / "diff" / folder.name
    names = [n for n in visual.SCREENS if not only or n in only]
    results = [visual.compare(n, visual.capture_shots(folder, n, shot),
                              extra_ignore=extra, diff_dir=diff_dir, label=label)
               for n in names]

    print(f"\n{label} vs Obj-C {config.OBJC_VERSION} ({config.OBJC_BUILD}) — "
          f"{folder}")
    print(f"  {'screen':20s} {'diff':>7s} {'max':>6s} {'largest':>8s}  verdict")
    for r in results:
        if r["status"] != "ok":
            print(f"  {r['name']:20s} {'—':>7s} {'':>6s} {'':>8s}  [{r['status']}]")
            continue
        verdict = "ok" if r["passed"] else "OVER"
        extras = []
        if not r["has_volatile"]:
            extras.append("no volatile mask")
        if r["assistive_touch"]:
            extras.append("AssistiveTouch masked")
        print(f"  {r['name']:20s} {r['diff_pct']:6.2f}% {r['max_diff_pct']:5.2f}% "
              f"{r['largest_region']:8d}  {verdict}"
              + (f"  ({', '.join(extras)})" if extras else ""))
    visual.exit_if_nothing_compared(results, folder, HOW)

    compared = [r for r in results if r["status"] == "ok"]
    over = [r["name"] for r in compared if not r["passed"]]
    diff_dir.mkdir(parents=True, exist_ok=True)
    (diff_dir / "results.json").write_text(json.dumps(
        {"label": label, "folder": str(folder), "results": results}, indent=2) + "\n")
    print(f"\n{len(compared)}/{len(results)} compared, {len(over)} over threshold"
          + (f": {', '.join(over)}" if over else "") + f"\ndiff images: {diff_dir}")
    return 1 if strict and (over or len(compared) < len(results)) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=None,
                        help="capture folder (default: newest log/unity/*)")
    parser.add_argument("--shot", type=int, choices=(1, 2, 3), default=None,
                        help="which of <Name>_{1,2,3}.png to use (default 2)")
    parser.add_argument("--only", default="")
    parser.add_argument("--ignore", type=parse_box, action="append", default=[],
                        help="extra x0,y0,x1,y1 box masked on every screen")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 unless every screen is under its threshold")
    args = parser.parse_args()
    only = {n.strip() for n in args.only.split(",") if n.strip()}
    unknown = only - set(visual.SCREENS)
    if unknown:
        print(f"unknown screens: {', '.join(sorted(unknown))}")
        return 2
    folder = args.dir or latest_unity_dir()
    return run(folder, args.shot, only, tuple(args.ignore), args.strict)


if __name__ == "__main__":
    sys.exit(main())
