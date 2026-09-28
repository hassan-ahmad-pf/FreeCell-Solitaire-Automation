#!/usr/bin/env python3
"""Run the FreeCell regression suite and print a PASS/FAIL summary.

You do not need to say whether this is a first or subsequent launch.
verifyFirstLaunch looks at the screen: it walks the policy links when the
T&C card is up, and skips them when it is already gone. Every later case
starts from launch_to_menu(), which clears those gates if they return.

The suite goes OFFLINE (Airplane Mode + Wi-Fi off) before gameplay cases so
interstitials cannot cover a transition. WDA must already be running — start
it while the phone is still online. verifyFirstLaunch stays online long
enough to walk the policy links, then takes the device offline.

SKIP_OFFLINE=1 leaves the network up (ads may interrupt).

Not in this suite (run standalone, usually online):
    verifySubsequentLaunch — fails if T&C/ATT is up (attach-only check)
  ads / App Store / Mail / Game Center cases — not implemented yet

Run:
  DEVICE_UDID=... ./.venv/bin/python -u tests/run_all.py
  DEVICE_UDID=... ./.venv/bin/python -u tests/run_all.py verifyPlay verifyHelp
"""
from __future__ import annotations

import importlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402


TESTS = [
    "verifyFirstLaunch",
    "verifyMainMenu",
    "verifyStats",
    "verifyOptions",
    "verifyHelp",
    "verifyAbout",
    "verifyMoreGames",
    "verifyChooseLook",
    "verifyDaily",
    "verifyPlay",
    "verifyGamePlay",
    "verifyRelaunch",
    "verify_qa_victory",
    "verifySoloStats",
]

REQUIRED = [
    "screen_menu",
    "menu_play",
    "menu_daily",
    "menu_stats",
    "menu_options",
    "menu_help",
    "menu_about",
    "more_games",
    "choose_look",
    "screen_daily",
    "daily_back",
    "screen_stats",
    "stats_solo_tab",
    "stats_daily_tab",
    "stats_best_zero",
    "stats_easy_none",
    "reset_stats",
    "reset_solo_stats",
    "reset_yes",
    "screen_options",
    "screen_help",
    "screen_about",
    "screen_more_games",
    "screen_choose_look",
    "look_close",
    "look_surface_tab",
    "look_cards_tab",
    "screen_play",
    "difficulty_easy",
    "screen_table",
    "table_foundations",
    "table_cells",
    "tableau",
    "back_game",
    "about_emblem",
    "about_version",
    "qa_watermark",
    "qa_panel",
    "screen_victory",
    "tc_continue",
    "att_prompt",
    "att_allow",
]


def preflight() -> list[str]:
    problems = []
    problems.extend(config.validate())
    missing = [name for name in REQUIRED if not ui.have(name)]
    if missing:
        problems.append("missing templates: " + ", ".join(missing))
    try:
        helpers.wda_status()
    except Exception as exc:  # noqa: BLE001
        problems.append(
            f"WDA is not reachable at {config.WDA_URL}: {exc}. "
            "Start it with ./scripts/wda.sh (uses the signed build in wda/, "
            "phone unlocked and online)."
        )
    return problems


def go_offline() -> str | None:
    """Take the device offline, or explain why the suite must stop."""
    if os.environ.get("SKIP_OFFLINE") == "1":
        print("SKIP_OFFLINE=1 — leaving the network up (ads may interrupt)",
              flush=True)
        return None
    print("going offline (Airplane Mode + Wi-Fi off)…", flush=True)
    if not ui.ensure_offline():
        return ("could not enable Airplane Mode and turn Wi-Fi off — "
                "refusing to run cases while ads can fire")
    print("device is offline", flush=True)
    return None


def main() -> int:
    picked = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    tests = picked or TESTS
    problems = preflight()
    if problems:
        print("preflight failed:", flush=True)
        for problem in problems:
            print(f"  - {problem}", flush=True)
        return 2

    print(f"device: {config.DEVICE_UDID or '(unset)'}", flush=True)
    print(f"wda:    {config.WDA_URL}", flush=True)
    print(f"bundle: {config.BUNDLE_ID}", flush=True)
    print(f"cases:  {len(tests)}", flush=True)
    for index, name in enumerate(tests, 1):
        print(f"  {index:2}/{len(tests)}  {name}", flush=True)

    wait_for_first_launch = tests[0] == "verifyFirstLaunch"
    if wait_for_first_launch:
        print("network: FirstLaunch stays online for policy links, "
              "then the suite goes offline", flush=True)
    else:
        problem = go_offline()
        if problem:
            print(f"preflight failed:\n  - {problem}", flush=True)
            return 2

    results = []
    for index, name in enumerate(tests, 1):
        print(f"\n>>> [{index}/{len(tests)}] START  {name}", flush=True)
        started = time.time()
        try:
            importlib.import_module(f"tests.{name}").run()
            ok, error = True, ""
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {exc}", flush=True)
            ok, error = False, str(exc)
        elapsed = time.time() - started
        results.append((name, ok, elapsed, error))
        print(
            f"<<< [{index}/{len(tests)}] {'PASS' if ok else 'FAIL'}  "
            f"{name}  ({elapsed:.1f}s)",
            flush=True,
        )
        if name == "verifyFirstLaunch" and wait_for_first_launch:
            problem = go_offline()
            if problem:
                print(f"FAIL: {problem}", flush=True)
                results.append(("offline", False, 0.0, problem))
                break
        try:
            helpers.connect()
            helpers.launch_app(force=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  WARNING: could not reattach: {exc}", flush=True)

    print("\n" + "=" * 56, flush=True)
    print("  FreeCell regression", flush=True)
    passed = sum(1 for _, ok, _, _ in results if ok)
    failed = 0
    for name, ok, elapsed, _ in results:
        if not ok:
            failed += 1
        print(f"  {'PASS' if ok else 'FAIL'}  {name:24} ({elapsed:5.1f}s)",
              flush=True)
    print(f"  {passed}/{len(results)} passed", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
