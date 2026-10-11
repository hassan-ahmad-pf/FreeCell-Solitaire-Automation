#!/usr/bin/env python3
"""Run the FreeCell regression suite and print a PASS/FAIL summary.

You do not need to say whether this is a first or subsequent launch.
verifyFirstLaunch looks at the screen: it walks the policy links when the
T&C card is up, and skips them when it is already gone. Every later case
starts from launch_to_menu(), which clears those gates if they return.

The suite goes OFFLINE (Airplane Mode + Wi-Fi off) before gameplay cases so
interstitials cannot cover a transition, then turns Wi-Fi back on in a
``finally`` so the next ``wda.sh`` can trust the developer cert. FreeCell
is never on screen while the network is up: it is closed before Wi-Fi
comes on and killed after going offline. Only a fresh install's Terms card
takes FirstLaunch online, for its policy links. WDA must already be
running — start it while the phone is still online.

SKIP_OFFLINE=1 leaves the network up (ads may interrupt).

Install the dev build fresh before a full run and leave it unopened: the
win cases use its QA code, and the first cases read fresh-install state.
With only the App Store (prod) build installed, pass --prod: it leaves out
catalog.DEV_BUILD (their cases read "dev build") and tests not written yet.

Each test records the TestRail cases it owns (docs/testrail/catalog.py)
through caselog. A test FAILS when it raises, when any of its cases failed,
or when it records some of its cases but not all. A test that records none
is graded at test level: every case it owns gets the test's own pass/fail,
and the screenshots it took go on its first case. Results go to
log/run_results.json after every test; scripts/gen_regression_report.py
turns them into log/freecell_regression.html.

Not in this suite (run standalone, usually online):
    verifySubsequentLaunch — fails if T&C/ATT is up (attach-only check)
  the 13 "Online - later" cases (catalog.ONLINE_LATER): App Store pages,
  Game Center, online support, and Daily tables

Run:
  DEVICE_UDID=... ./.venv/bin/python -u tests/run_all.py
  DEVICE_UDID=... ./.venv/bin/python -u tests/run_all.py --prod
  DEVICE_UDID=... ./.venv/bin/python -u tests/run_all.py verifyPlay verifyHelp
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "docs", "testrail"))

import caselog  # noqa: E402
import catalog  # noqa: E402
import config  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402
from cases import CASES  # noqa: E402

RESULTS_PATH = config.LOG / "run_results.json"


# Order is about app state, on a freshly installed dev build.
# FirstLaunch first: the T&C card shows only on a fresh install.
# Then everything that reads fresh state, before anything deals: empty
# Stats, the Last Score "no game completed" notice, and Daily's first-visit
# tips (Daily cannot deal offline, so it never leaves a table).
# FirstGame is the first deal: its rules prompt (Yes -> Help) and the
# Welcome alert on leaving the table (Options). The promo strip appears
# once a game has been played, so Promo Icons follows it — on the default
# felt and before QA's watermark. Menu pages next; More Games before
# Choose Look, whose deal restores Surface 1 / Cards 1 so later table crops
# still match. Then the table: Play, GamePlay, the table-only Options,
# rotation, Rich Features (OFF also hides "tap to raise" inside the tableau
# crop, so after GamePlay), Rank Strip, and Relaunch, which kills the app
# and so must precede the QA unlock.
# QA wins next: victory, the four levels, then Last Score (needs a win),
# then Solo Stats, which resets Solo first so its win is the only score.
# QA Off before the resets; Reset Cancelled needs Solo's score still there,
# and resetStats wipes it last.
TESTS = [
    "verifyFirstLaunch",
    "verifyMainMenu",
    "verifyStats",
    "verifyLastScoreNotice",
    "verifyDaily",
    "verifyFirstGame",
    "verifyPromoIcons",
    "verifyOptions",
    "verifyHelp",
    "verifyAbout",
    "verifyAdFreePrompt",
    "submitFeedback",
    "verifyMoreGames",
    "verifyChooseLook",
    "verifyPlay",
    "verifyGamePlay",
    "verifyTableOptions",
    "verifyRotationLock",
    "verifyRichFeaturesOn",
    "verifyRichFeaturesOff",
    "verifyRankStrip",
    "verifyRelaunch",
    "verify_qa_victory",
    "verifyDifficultyLevels",
    "verifyLastScore",
    "verifySoloStats",
    "verifyQaOff",
    "verifyResetCancelled",
    "resetStats",
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
    "hint_undo",
    "hint_hints",
    "back_game",
    "table_menu",
    "drawer_options",
    "opt_rich_features",
    "opt_rank_strip",
    "about_emblem",
    "about_version",
    "qa_watermark",
    "qa_panel",
    "screen_victory",
    "tc_continue",
    "att_prompt",
    "att_allow",
]


def _written(name: str) -> bool:
    return os.path.isfile(os.path.join(ROOT, "tests", f"{name}.py"))


def prod_tests() -> list[str]:
    """TESTS without the dev-build tests and the ones not written yet."""
    return [name for name in TESTS
            if name not in catalog.DEV_BUILD and _written(name)]


def preflight(tests: list[str]) -> list[str]:
    problems = []
    problems.extend(config.validate())
    unknown = [name for name in tests if not _written(name)]
    if unknown:
        problems.append("no such test: " + ", ".join(unknown))
    uncatalogued = [name for name in tests if name not in catalog.CATALOG]
    if uncatalogued:
        problems.append("not in docs/testrail/catalog.py: "
                        + ", ".join(uncatalogued))
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


def settle_between_cases(after: str) -> str | None:
    """Leave leftover screens so the next case starts from the menu.

    A table is not a lost app — tap Back. After a process kill, WDA HTTP
    blinks; wait that out instead of aborting QA / Solo Stats. Only if
    the runner itself is dead do we go online and start wda.sh.
    """
    try:
        if helpers.wait_for_status(2.0) is None:
            print(f"  WDA HTTP blinked after {after} — waiting it out",
                  flush=True)
            if not helpers.recover_after_app_kill():
                print("  still down — going online and restarting WDA",
                      flush=True)
                try:
                    ui.ensure_online()
                except Exception:  # noqa: BLE001
                    pass
                if not helpers.revive_wda():
                    return (
                        f"WDA dropped after {after} and could not be restarted. "
                        "Turn Wi-Fi on, unlock the phone, then ./scripts/wda.sh."
                    )
                if os.environ.get("SKIP_OFFLINE") != "1":
                    if not ui.ensure_offline():
                        print("  WARNING: revived WDA but could not go offline again",
                              flush=True)
        helpers.reconnect()
    except Exception as exc:  # noqa: BLE001
        if helpers.recover_after_app_kill() or helpers.revive_wda():
            try:
                helpers.reconnect()
            except Exception as retry_exc:  # noqa: BLE001
                return (
                    f"WDA dropped after {after}: {retry_exc}. "
                    "Turn Wi-Fi on and start ./scripts/wda.sh."
                )
        else:
            return (
                f"WDA dropped after {after}: {exc}. "
                "Turn Wi-Fi on and start ./scripts/wda.sh — "
                "do not let Airtest relaunch XCTest while offline."
            )
    try:
        if ui.at_table(timeout=1.0) or ui.is_on("back_game") or ui.is_on("screen_table"):
            ui.leave_table()
        if ui.expect_screen("victory", timeout=0.5):
            ui.leave_victory() or ui.tap("victory_menu", settle=1.4) or ui.back()
        if ui.is_on("look_close"):
            ui.tap("look_close", settle=1.2)
        ui.leave_stats()
        ui.leave_daily()
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: could not leave leftover screen: {exc}", flush=True)
    return None


def restore_online() -> None:
    """Close FreeCell, then turn Wi-Fi back on (the next wda.sh needs it)."""
    if os.environ.get("SKIP_OFFLINE") == "1":
        return
    print("closing FreeCell, then restoring Wi-Fi so the next WDA start "
          "can trust the cert…", flush=True)
    try:
        helpers.wda_status()
    except Exception as exc:  # noqa: BLE001
        print(f"  WDA blinked ({exc}) — recovering before radios", flush=True)
        if not helpers.recover_after_app_kill() and not helpers.revive_wda():
            print(
                "  WDA is down — turn Wi-Fi / Airplane Mode on by hand, "
                "then ./scripts/wda.sh",
                flush=True,
            )
            return
    if ui.ensure_online():
        print("  device is online", flush=True)
        return
    print("  could not leave Airplane Mode — close FreeCell, then turn "
          "Wi-Fi on by hand", flush=True)


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
    try:
        helpers.wda_status()
    except Exception as exc:  # noqa: BLE001
        return (
            f"WDA died while going offline: {exc}. "
            "Radios will be restored if the runner is still reachable."
        )
    print("device is offline (WDA still up over USB)", flush=True)
    return None


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(
        timespec="seconds")


def _screen_size() -> str:
    """Size of the newest capture in log/, for the report header."""
    try:
        from PIL import Image

        newest = max(config.LOG.glob("*.png"), key=os.path.getmtime)
        with Image.open(newest) as image:
            return f"{image.width}x{image.height}"
    except (ValueError, OSError):
        return ""


def _run_metadata(started: float, prod: bool) -> dict:
    version, build = helpers.installed_build() or ("", "")
    return {
        "schema": 1,
        "suite": "FreeCell Obj-C regression",
        "build_kind": "prod" if prod else "dev",
        "started": _iso(started),
        "device": {
            "model": helpers.device_model(),
            "ios": helpers.os_version(),
            "udid": config.DEVICE_UDID or "",
            "screen": "",
        },
        "app": {"name": config.GAME_NAME, "bundle": config.BUNDLE_ID,
                "version": version, "build": build},
    }


def _previous_tests(app: dict) -> dict:
    """Earlier results for the same build, so a partial re-run keeps the rest."""
    try:
        previous = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if previous.get("app", {}).get("build") != app.get("build"):
        return {}
    return {t["name"]: t for t in previous.get("tests", [])
            if isinstance(t, dict) and t.get("name")}


def _case_table(tests: dict, prod: bool = False) -> list[dict]:
    """Every TestRail case with this run's status, in cases.py order."""
    recorded = {}
    for test in tests.values():
        for result in test.get("cases", []):
            recorded[result["id"]] = result
    rows = []
    for spec in CASES:
        cid = spec["id"]
        owner = catalog.owner(cid)
        row = {"id": cid, "title": spec["title"], "section": spec["section"],
               "test": owner or "", "detail": "", "shots": [], "seconds": 0.0}
        if cid in catalog.ONLINE_LATER:
            row.update(status="online later", detail=catalog.ONLINE_LATER[cid])
        elif cid in recorded:
            result = recorded[cid]
            row.update(status=result["status"], detail=result["detail"],
                       shots=result["shots"], seconds=result["seconds"])
        elif prod and owner in catalog.DEV_BUILD:
            row.update(status="dev build", detail=catalog.DEV_BUILD[owner])
        elif owner in tests:
            row.update(status="not reached",
                       detail=tests[owner].get("error", ""))
        else:
            row["status"] = "not run"
        rows.append(row)
    return rows


def _write_results(meta: dict, tests: dict, started: float) -> list[dict]:
    finished = time.time()
    cases = _case_table(tests, prod=meta.get("build_kind") == "prod")
    order = list(dict.fromkeys(TESTS + list(tests)))
    payload = dict(meta)
    payload["finished"] = _iso(finished)
    payload["duration_seconds"] = round(finished - started, 1)
    payload["device"] = dict(meta["device"], screen=_screen_size())
    payload["tests"] = [tests[name] for name in order if name in tests]
    payload["cases"] = cases
    config.LOG.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(payload, indent=2) + "\n",
                            encoding="utf-8")
    return cases


def _run_once(name: str) -> None:
    importlib.import_module(f"tests.{name}").run()
    caselog.raise_if_failed()
    recorded = {r["id"] for r in caselog.results()}
    silent = [cid for cid in catalog.CATALOG.get(name, []) if cid not in recorded]
    if recorded and silent:
        raise AssertionError("returned without recording " + ", ".join(silent))


def _shots_since(started: float) -> list[str]:
    """Captures written to log/ since *started*, oldest first."""
    try:
        fresh = [(path.stat().st_mtime, path) for path in config.LOG.glob("*.png")]
    except OSError:
        return []
    return [str(path) for mtime, path in sorted(fresh) if mtime >= started]


def _test_level_cases(name: str, ok: bool, error: str, shots: list[str],
                      seconds: float) -> list[dict]:
    """Rows for a test that recorded no case: each gets the test's own result."""
    ids = catalog.CATALOG.get(name, [])
    status = "pass" if ok else "fail"
    rows = []
    for index, cid in enumerate(ids):
        detail = (f"test-level result ({name} does not grade this case "
                  "on its own yet)")
        if not ok:
            detail += f": {error}"
        if index and shots:
            detail += f"; screenshots are on {ids[0]}"
        rows.append({"id": cid, "status": status, "detail": detail,
                     "shots": [] if index else shots, "notes": [],
                     "test": name, "seconds": 0.0 if index else seconds})
    print(f"    test-level: {len(ids)} cases {status} ({', '.join(ids)}), "
          f"{len(shots)} screenshots", flush=True)
    return rows


def _run_test(name: str) -> tuple[bool, str]:
    """Run one test; it fails when it raises, a case failed, or one went unrecorded."""
    caselog.begin(name)
    try:
        _run_once(name)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        if not helpers.is_link_error(exc):
            print(f"FAIL: {exc}", flush=True)
            return False, str(exc)
        print(f"  link/session blip ({exc}) — reconnect and retry once",
              flush=True)
    caselog.begin(name)
    try:
        helpers.reconnect()
        _run_once(name)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", flush=True)
        return False, str(exc)


def _print_summary(meta: dict, tests: dict, cases: list[dict]) -> None:
    app = meta["app"]
    build = f"{app['version']} (build {app['build']})" if app["build"] else "?"
    print("\n" + "=" * 64, flush=True)
    print(f"  FreeCell regression — {build}", flush=True)
    for test in tests.values():
        mine = [c for c in cases if c["test"] == test["name"]]
        passed = sum(1 for c in mine if c["status"] == "pass")
        print(f"  {'PASS' if test['ok'] else 'FAIL'}  {test['name']:24} "
              f"({test['seconds']:6.1f}s)  cases {passed}/{len(mine)}",
              flush=True)
    passed = sum(1 for t in tests.values() if t["ok"])
    print(f"  tests: {passed}/{len(tests)} passed", flush=True)
    counts: dict[str, int] = {}
    for row in cases:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    order = ["pass", "fail", "skip", "block", "not reached", "dev build",
             "not run", "online later"]
    print("  cases: " + ", ".join(f"{counts[k]} {k}" for k in order
                                  if counts.get(k)), flush=True)
    bad = [c for c in cases if c["status"] in ("fail", "not reached")]
    for row in bad:
        detail = f" — {row['detail']}" if row["detail"] else ""
        print(f"    {row['status'].upper():11} {row['id']}  {row['title']}"
              f"{detail}", flush=True)
    print(f"  results: {RESULTS_PATH}", flush=True)


def main() -> int:
    os.environ["FREECELL_SUITE"] = "1"
    prod = "--prod" in sys.argv[1:]
    picked = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    tests = picked or (prod_tests() if prod else TESTS)
    problems = preflight(tests)
    if problems:
        print("preflight failed:", flush=True)
        for problem in problems:
            print(f"  - {problem}", flush=True)
        return 2
    run_started = time.time()
    meta = _run_metadata(run_started, prod)
    app = meta["app"]
    print(f"device: {config.DEVICE_UDID or '(unset)'} "
          f"({meta['device']['model'] or '?'}, iOS {meta['device']['ios'] or '?'})",
          flush=True)
    print(f"wda:    {config.WDA_URL}", flush=True)
    print(f"app:    {config.BUNDLE_ID} {app['version'] or '?'} "
          f"(build {app['build'] or '?'}) — {meta['build_kind']} build",
          flush=True)
    print(f"tests:  {len(tests)}", flush=True)
    for index, name in enumerate(tests, 1):
        print(f"  {index:2}/{len(tests)}  {name}  "
              f"[{len(catalog.CATALOG.get(name, []))} cases]", flush=True)
    if prod:
        left = [name for name in TESTS if name not in tests]
        for name in left:
            why = catalog.DEV_BUILD.get(name) or "not written yet"
            print(f"  skip   {name}  — {why}", flush=True)

    # Offline before any case. FirstLaunch goes online itself only when a
    # fresh install's Terms card is up; going offline after it kills
    # FreeCell, so nothing it loaded online reaches a later case.
    problem = go_offline()
    if problem:
        print(f"preflight failed:\n  - {problem}", flush=True)
        return 2

    done = _previous_tests(app)
    for name in tests:
        done.pop(name, None)
    ran: dict[str, dict] = {}
    try:
        for index, name in enumerate(tests, 1):
            print(f"\n>>> [{index}/{len(tests)}] START  {name}", flush=True)
            started = time.time()
            ok, error = _run_test(name)
            elapsed = time.time() - started
            cases = caselog.results() or _test_level_cases(
                name, ok, error, _shots_since(started), round(elapsed, 1))
            ran[name] = done[name] = {
                "name": name, "ok": ok, "seconds": round(elapsed, 1),
                "error": error, "run_at": _iso(time.time()),
                "cases": cases,
            }
            _write_results(meta, done, run_started)
            print(
                f"<<< [{index}/{len(tests)}] {'PASS' if ok else 'FAIL'}  "
                f"{name}  ({elapsed:.1f}s)",
                flush=True,
            )
            stop = None
            if name == "verifyFirstLaunch":
                problem = go_offline()
                stop = problem and ("offline", problem)
            if not stop:
                problem = settle_between_cases(name)
                stop = problem and ("wda", problem)
            if stop:
                label, problem = stop
                print(f"FAIL: {problem}", flush=True)
                ran[label] = done[label] = {
                    "name": label, "ok": False, "seconds": 0.0,
                    "error": problem, "run_at": _iso(time.time()), "cases": [],
                }
                break
    finally:
        restore_online()
        cases = _write_results(meta, done, run_started)

    _print_summary(meta, ran, cases)
    return 0 if ran and all(t["ok"] for t in ran.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
