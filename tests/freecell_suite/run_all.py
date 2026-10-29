#!/usr/bin/env python3
"""Run the FreeCell suite and print a PASS/FAIL summary.

The suite's tests in order, one line per case with its ID and title, then
the report. The order visits each screen once where the network and the
data allow (catalog.py says why). The Daily cases (from FreeCell's TestRail
list) run in verifyDaily, their statistics reset in verifyStatistics; the
timer, score, Show Status Bar, Show Card Messages and Maintain Card Spacing
cases (GP-12, GP-25, OP-10, OP-11, OP-12, OP-15, OP-16) run in verifyGamePlay.
tests/freecell_suite/catalog.py says where every test stands:

  run    a test in tests/freecell_suite/<module>.py runs and records its
         cases
  dev    needs the dev build — SKIP on the prod build; --dev runs the ones
         that have a module
  skip   cannot run on this install (FL-06: not installed from TestFlight)

A bare run is the main suite; the standalone tests (Choose Look, Ad-free,
Feedback, and the dev-only Ads, Ad trigger points, Last Score) run only when
named or with --all, which slots each in where its screen and network fit.
Every invocation merges into the same results, so the report covers both.

Network: the radios are set in Settings before FreeCell first opens;
verifyFirstLaunch opens the policy links online, then goes offline for the
middle of the suite; at the promo-strip step (skipped on prod) the phone
comes back online for the reset tests and Contact Us online. The run ends
online.

Prereqs: FreeCell freshly installed from the App Store and NOT opened (the
first test reads the first launch), phone online and unlocked, WDA up via
scripts/wda.sh, DEVICE_UDID exported, a Mail account on the phone.

Run:  ./.venv/bin/python -u tests/freecell_suite/run_all.py                # main suite
      ./.venv/bin/python -u tests/freecell_suite/run_all.py verifyChooseLook \\
          verifyAdFreeVersion submitFeedback                              # standalone
      ./.venv/bin/python -u tests/freecell_suite/run_all.py verifyPlay verifyGamePlay
      ./.venv/bin/python -u tests/freecell_suite/run_all.py --offline     # Airplane Mode cases only
      ./.venv/bin/python -u tests/freecell_suite/run_all.py --dev
      ./.venv/bin/python -u tests/freecell_suite/run_all.py --dev --all   # main suite + standalone

For a live, coloured console (presentations): ./scripts/regression.sh

Results: log/freecell_suite_results.json after every test, then
scripts/gen_suite_report.py writes log/freecell_suite_report.html.

When a test fails, the report is written, each failed test runs once more
(the network set as on the first run), and the report is written again.
A failed case that passes on the rerun is a plain pass in the report; the
results JSON keeps its first failure (first_failure). --no-rerun turns
this off.

Stopped midway (Ctrl+C, or ./scripts/regression.sh stop), the runner writes
the results and the report at once: the cases run so far keep their
results, the rest read "not run". Then it puts the network back on.
"""
from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [HERE, ROOT]

import caselog  # noqa: E402
import catalog  # noqa: E402
import config  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402

RESULTS_PATH = config.LOG / "freecell_suite_results.json"
REPORT_PATH = config.LOG / "freecell_suite_report.html"
REPORT_SCRIPT = os.path.join(ROOT, "scripts", "gen_suite_report.py")

# Every template a port taps or asserts. Checked up front so a missing crop
# is one message, not a run that dies half way.
REQUIRED = [
    "menu_play", "menu_daily", "menu_stats", "menu_options", "menu_help", "menu_about",
    "more_games", "choose_look", "menu_logo", "screen_menu", "screen_play",
    "screen_stats", "screen_options", "screen_help", "screen_about", "screen_faq",
    "screen_more_games", "screen_choose_look", "screen_choose_look_cards",
    "screen_table", "page_back", "back_game", "table_menu", "tableau",
    "hint_undo", "hint_hints", "hint_lower", "hint_more", "contact_us",
    "reset_solo_stats", "about_version", "about_help", "about_adfree", "about_faq",
    "about_more_games", "about_feedback", "faq_feedback", "help_faq_link",
    "mg_cardgames", "mg_spiderette", "drawer_replay", "drawer_abandon",
    "drawer_options", "drawer_new", "drawer_help", "drawer_faq", "resume",
    "difficulty_easy", "difficulty_medium", "difficulty_hard", "difficulty_expert",
    "difficulty_master", "opt_rich_features", "look_close", "look_surface_tab",
    "look_cards_tab", "stats_best_zero", "stats_easy_none", "tc_continue",
    "tc_terms_link", "tc_terms_page", "tc_privacy_link", "tc_privacy_page",
    "att_prompt", "att_allow", "ad_close", "faq_header", "mg_header", "promo_close", "hint_deck",
    # dev build: QA, Synthetic Win, Victory, Last Score, Game Center, the QA page
    "about_emblem", "about_reset_alerts", "qa_watermark", "qa_badge_a", "qa_panel", "qa_90_99", "qa_win",
    "screen_victory", "victory_ranking", "victory_leaderboards", "victory_achieve",
    "victory_help", "victory_new", "victory_stats", "victory_level_easy",
    "screen_last_score", "last_score_next", "gc_back", "gc_leaderboards", "gc_achievements",
    "qa_page_adapters", "qa_page_back",
    # Daily (FreeCell's own DY cases)
    "daily_back", "daily_tip1", "daily_tip2", "daily_weekdays", "daily_weekdays_mon",
    "daily_faq_link",
    "daily_gold_star", "daily_levels", "daily_relaxed_note", "daily_table_star",
    "daily_popup_days", "faq_daily_heading", "reset_daily_stats",
]


def _iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or time.time()).astimezone().isoformat(timespec="seconds")


def preflight() -> list[str]:
    problems = []
    absent = [name for name in REQUIRED if not ui.have(name)]
    if absent:
        problems.append(f"missing {len(absent)} template(s) in assets/: {', '.join(absent)}")
    try:
        helpers.wda_status()
    except Exception:  # noqa: BLE001
        problems.append(f"WDA is not reachable at {config.WDA_URL} — start it with "
                        "scripts/wda.sh while the phone is online and unlocked")
    if not config.DEVICE_UDID:
        problems.append("DEVICE_UDID is not set — export the UDID you passed to scripts/wda.sh")
    return problems


def _load(module: str):
    path = os.path.join(HERE, f"{module}.py")
    spec = importlib.util.spec_from_file_location(f"freecell_suite_{module}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _offline_ids(ids: list[str]) -> list[str]:
    return [c for c in ids if c not in catalog.ONLINE_CASES]


def _plan(picked: list[str], dev: bool, offline: bool, everything: bool = False) -> list[tuple]:
    """(test name, module, runs?, ids, reason) in the suite's order."""
    out = []
    for name, module, kind, ids, why in catalog.RUN_ORDER:
        if picked and name not in picked and module not in picked:
            continue
        if not picked and not offline and not everything and name in catalog.STANDALONE:
            continue
        if offline and (kind != "run" or not _offline_ids(ids)):
            continue
        runs = bool(module) and (kind == "run" or (kind == "dev" and dev))
        reason = why if kind in ("dev", "skip") else ""
        if kind == "dev" and dev and not module:
            reason = "no FreeCell port yet"
        out.append((name, module, runs, ids, reason))
    return out


def _network_first(plan: list[tuple], offline: bool) -> None:
    """Set the radios in Settings before FreeCell first opens, so every run
    starts the same way: Settings, then the game, never the game sent to the
    background for Settings. verifyFirstLaunch starts online (a fresh
    install's Terms card loads its policy pages); so do the tests from
    ONLINE_FROM on. The rest start offline."""
    first = next((name for name, _m, runs, _ids, _w in plan if runs), None)
    if first is None:
        return
    order = [name for name, *_rest in catalog.RUN_ORDER]
    want_online = not offline and (first == "verifyFirstLaunch" or fc.is_online()
                                   or order.index(first) >= order.index(catalog.ONLINE_FROM))
    print("\nnetwork: checking the internet connection in Settings before FreeCell opens",
          flush=True)
    try:
        if not want_online:
            ok = ui.offline(restore=False)
        elif first == "verifyFirstLaunch" or fc.is_online():
            ok = ui.online()
        else:
            fc.go_online()
            ok = True
    except Exception as exc:  # noqa: BLE001
        print(f"  {exc}", flush=True)
        ok = False
    if not ok:
        print("WARNING: Settings did not take the network change; each test sets it itself",
              flush=True)
    elif not want_online:
        print("network: offline — Airplane Mode on, Wi-Fi off", flush=True)
    elif ui.wifi_name():
        print(f"network: online — Airplane Mode off, Wi-Fi joined {ui.wifi_name()}", flush=True)
    else:
        print("WARNING: Wi-Fi is on but joined no network — the online cases need one",
              flush=True)


def _case_row(cid: str, test: str, status: str, detail: str = "", rec: dict | None = None):
    rec = rec or {}
    return {
        "id": cid, "title": catalog.TITLES[cid], "section": catalog.SECTIONS[cid],
        "test": test, "status": status, "detail": detail,
        "shots": rec.get("shots", []), "notes": rec.get("notes", []),
        "seconds": rec.get("seconds", 0.0),
    }


def _previous(names: set[str], scope: set[str]) -> tuple[list, list, str]:
    """Tests, cases and start time of an earlier run that this invocation does
    not redo; ones the catalog no longer lists are dropped."""
    try:
        old = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], [], ""
    listed = {name for name, *_rest in catalog.RUN_ORDER}
    known = set(catalog.TITLES)
    tests = [t for t in old.get("tests", [])
             if t.get("name") not in names and t.get("name") in listed]
    cases = [c for c in old.get("cases", [])
             if c.get("id") not in scope and c.get("id") in known]
    return tests, cases, old.get("started", "") if tests else ""


def _write(payload: dict, kept: tuple[list, list, str]) -> None:
    order = {name: i for i, (name, *_rest) in enumerate(catalog.RUN_ORDER)}
    ids = [c["id"] for c in catalog.CASES]
    out = dict(payload)
    out["tests"] = sorted(kept[0] + payload["tests"], key=lambda t: order.get(t["name"], 99))
    out["cases"] = sorted(kept[1] + payload["cases"], key=lambda c: ids.index(c["id"]))
    if kept[0]:
        starts = [t.get("started") or kept[2] for t in out["tests"]]
        out["started"] = min(filter(None, starts + [payload["started"]]))
        out["duration_seconds"] = round(sum(t.get("seconds", 0) + t.get("rerun_seconds", 0)
                                            for t in out["tests"]), 1)
    config.LOG.mkdir(parents=True, exist_ok=True)
    tmp = RESULTS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, RESULTS_PATH)


NOT_RUN = "not run — the regression was stopped before this case"


def _quiet(*_args, **_kwargs) -> None:
    pass


def _case_rows(name: str, ids: list[str], dev: bool, offline: bool, error: str = "",
               stopped: bool = False, recorded: dict | None = None,
               say: bool = True) -> tuple[list[dict], bool]:
    """A test's case rows from what caselog recorded, and whether one failed.
    A case left unrecorded was not reached after a failure, or, *stopped*,
    not run because the regression was stopped first."""
    log = print if say else _quiet
    if recorded is None:
        recorded = {r["id"]: r for r in caselog.results()}
    runnable = [cid for cid in ids if dev or cid not in catalog.DEV_CASES]
    rows, bad = [], False
    for cid in ids:
        if offline and cid in catalog.ONLINE_CASES:
            log(f"    [ONLINE] {cid} {catalog.TITLES[cid]} — online pass; "
                "keeps its last result", flush=True)
            continue
        if cid not in runnable:
            why = catalog.DEV_CASES[cid]
            log(f"    [SKIP] {cid} {catalog.TITLES[cid]} — {why}", flush=True)
            rows.append(_case_row(cid, name, "dev", why))
            continue
        rec = recorded.get(cid)
        if rec is None and stopped:
            rows.append(_case_row(cid, name, "stop", NOT_RUN))
            continue
        if rec is None:
            detail = ("not reached — the test stopped first: " + error if error
                      else "the test did not record this case")
            log(f"    [FAIL] {cid} {catalog.TITLES[cid]} — {detail}", flush=True)
            rows.append(_case_row(cid, name, "fail", detail))
            bad = True
            continue
        rows.append(_case_row(cid, name, rec["status"], rec["detail"], rec))
        bad = bad or rec["status"] == "fail"
    return rows, bad


def _stop_rows(plan: list[tuple], current: tuple[str, float] | None, tests: list[dict],
               cases: list[dict], dev: bool, offline: bool, last: dict[str, float]) -> None:
    """At a stop: the test that was running keeps the cases it finished; its
    other cases, and every case of the tests not started, read not run.
    *estimate* keeps the last run's time for the console's next estimate."""
    done = {t["name"] for t in tests}
    for name, module, runs, ids, _reason in plan:
        if name in done or not runs:
            continue
        ran = current is not None and current[0] == name
        rows, _bad = _case_rows(name, ids, dev, offline, stopped=True,
                                recorded=None if ran else {}, say=False)
        seconds = round(time.time() - current[1], 1) if ran else 0.0
        tests.append({"name": name, "module": module, "status": "stop",
                      "started": _iso(current[1]) if ran else "", "seconds": seconds,
                      "estimate": max(last.get(name, 0.0), seconds),
                      "error": "stopped while it ran" if ran
                      else "not started — the regression was stopped first"})
        cases.extend(rows)


def _list_cases(ids: list[str], dev: bool, offline: bool) -> None:
    """The test's cases in the order it runs them, before it starts; then
    the ones it leaves out, with why."""
    left_out = {cid: catalog.DEV_CASES[cid] for cid in ids
                if not dev and cid in catalog.DEV_CASES}
    left_out.update({cid: "online pass; keeps its last result" for cid in ids
                     if offline and cid in catalog.ONLINE_CASES})
    runs = [cid for cid in ids if cid not in left_out]
    for n, cid in enumerate(runs, 1):
        print(f"    [LIST] {n}/{len(runs)} {cid} {catalog.TITLES[cid]}", flush=True)
    for cid, why in left_out.items():
        print(f"    [LIST] -/{len(runs)} {cid} {catalog.TITLES[cid]} (not run here: {why})",
              flush=True)


def _last_seconds() -> dict[str, float]:
    try:
        old = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {t["name"]: float(t.get("estimate") or t.get("seconds") or 0.0)
            for t in old.get("tests", []) if t.get("name")}


def _run_one(i: int, total: int, name: str, module: str, ids: list[str], dev: bool,
             offline: bool, word: str = "START") -> tuple[dict, list[dict]]:
    """Run one test; its test row and case rows."""
    print(f"\n>>> [{i}/{total}] {word:6} {name}", flush=True)
    _list_cases(ids, dev, offline)
    caselog.begin(name)
    os.environ["TEST_NAME"] = name
    t0 = time.time()
    error = ""
    try:
        _load(module).run()
    except Exception as exc:  # noqa: BLE001
        error = str(exc) or type(exc).__name__
        print(f"FAIL: {error}", flush=True)
    dt = time.time() - t0

    rows, bad = _case_rows(name, ids, dev, offline, error)
    ok = not error and not bad
    print(f"<<< [{i}/{total}] {'PASS' if ok else 'FAIL'}  {name}  ({dt:.1f}s)", flush=True)
    return ({"name": name, "module": module, "status": "pass" if ok else "fail",
             "started": _iso(t0), "seconds": round(dt, 1), "error": error}, rows)


def _rerun(plan: list[tuple], tests: list[dict], cases: list[dict], dev: bool,
           offline: bool) -> None:
    """Run each test that failed once more. A case that failed takes the
    rerun's result only if it passes there; a case that passed keeps its
    first result. The network is set as the first run had it."""
    redo = [p for p in plan if p[0] in {t["name"] for t in tests if t["status"] == "fail"}]
    first = {c["id"]: c for c in cases if c["status"] == "fail"}
    print("\n" + "-" * 64, flush=True)
    print(f"  RERUN — {len(first)} failed case(s) in {len(redo)} test(s); "
          "each test runs once more", flush=True)
    for c in first.values():
        print(f"    {c['id']} {c['title']}  ({c['test']})", flush=True)
    order = [name for name, *_rest in catalog.RUN_ORDER]
    online_at = order.index(catalog.ONLINE_FROM)
    for i, (name, module, _runs, ids, _why) in enumerate(redo, 1):
        if not offline:
            if order.index(name) >= online_at:
                fc.go_online()
            else:
                fc.go_offline()
        row, rows = _run_one(i, len(redo), name, module, ids, dev, offline, "RERUN")
        again = {r["id"]: r for r in rows}
        for cid in ids:
            new = again.get(cid)
            if cid not in first:
                if new and new["status"] == "fail":
                    print(f"    note: {cid} passed on the first run and failed on the rerun "
                          f"— it keeps the first-run pass: {new['detail']}", flush=True)
                continue
            old = first[cid]
            if new and new["status"] == "pass":
                cases[cases.index(old)] = dict(new, rerun="pass", first_failure=old["detail"])
                print(f"    [RERUN PASS] {cid} {old['title']} — first run: {old['detail']}",
                      flush=True)
            else:
                why = (f"{new['status']}: {new['detail']}" if new
                       else "not recorded")
                old["rerun"] = new["status"] if new else "fail"
                old["detail"] = f"{old['detail']} — rerun {why}"
                print(f"    [RERUN FAIL] {cid} {old['title']} — {why}", flush=True)
        t = next(t for t in tests if t["name"] == name)
        t["rerun_seconds"], t["rerun_status"] = row["seconds"], row["status"]
        still = any(c["status"] == "fail" for c in cases if c["test"] == name)
        unexplained = row["status"] == "fail" and not any(r["status"] == "fail" for r in rows)
        if still or unexplained:
            if row["error"] and row["error"] != t["error"]:
                t["error"] = f"{t['error']} — rerun: {row['error']}" if t["error"] else row["error"]
        else:
            t["status"], t["error"] = "pass", ""


def _summary(tests: list[dict], cases: list[dict], heading: str) -> list[dict]:
    print("\n" + "=" * 64, flush=True)
    print(f"  {heading}", flush=True)
    for t in tests:
        mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "stop": "STOP"}[t["status"]]
        again = f"  + rerun {t['rerun_seconds']:.1f}s" if t.get("rerun_status") else ""
        took = ("(not started)" if t["status"] == "stop" and not t["started"]
                else f"({t['seconds']:6.1f}s)")
        print(f"  {mark}  {t['name']:24} {took}{again}", flush=True)
    by = {}
    for c in cases:
        by[c["status"]] = by.get(c["status"], 0) + 1
    executed = by.get("pass", 0) + by.get("fail", 0)
    stop = f", {by['stop']} not run (stopped)" if by.get("stop") else ""
    print(f"\n  cases: {by.get('pass', 0)}/{executed} executed passed, "
          f"{by.get('fail', 0)} failed, {by.get('skip', 0)} skipped, "
          f"{by.get('dev', 0)} dev build{stop}", flush=True)
    rescued = [c["id"] for c in cases if c.get("rerun") == "pass"]
    if rescued:
        print(f"  passed on the rerun: {', '.join(rescued)}", flush=True)
    failed = [c for c in cases if c["status"] == "fail"]
    if failed:
        print("\n  failed cases:", flush=True)
        for c in failed:
            print(f"    {c['id']} {c['title']} — {c['detail']}", flush=True)
    return failed


def _report() -> None:
    try:
        proc = subprocess.run([sys.executable, REPORT_SCRIPT, "--results", str(RESULTS_PATH),
                               "--out", str(REPORT_PATH)],
                              capture_output=True, text=True, timeout=180)
        if proc.returncode:
            print(f"WARNING: report generation failed: {proc.stderr.strip()}", flush=True)
        else:
            print(f"  report: {REPORT_PATH}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: report generation failed: {exc}", flush=True)


def main() -> int:
    args = sys.argv[1:]
    dev = "--dev" in args
    os.environ["FREECELL_SUITE_BUILD"] = "dev" if dev else "prod"
    offline = "--offline" in args
    picked = [a for a in args if not a.startswith("-")]
    everything = "--all" in args
    rerun = "--no-rerun" not in args
    plan = _plan(picked, dev, offline, everything)
    total = len(plan)
    started = time.time()
    last = _last_seconds()

    fc.hold_phone()
    problems = preflight()
    if problems:
        print("preflight failed:", flush=True)
        for p in problems:
            print(f"  - {p}", flush=True)
        return 2

    build = helpers.installed_build() or ("", "")
    heading = ("FreeCell regression suite "
               f"({'dev' if dev else 'prod'} build {build[0]} ({build[1]}))")
    print(f"device: {config.DEVICE_UDID}", flush=True)
    print(f"wda:    {config.WDA_URL}", flush=True)
    print(f"build:  FreeCell {build[0]} ({build[1]}) — {'dev' if dev else 'prod'} run"
          f"{', offline cases only' if offline else ''}", flush=True)
    n_run = n_dev = n_skip = 0
    for name, _m, runs, ids, _w in plan:
        if runs:
            n_run += len(_offline_ids(ids) if offline else ids)
        elif catalog.entry(name)[2] == "skip":
            n_skip += len(ids)
        else:
            n_dev += len(ids)
    label = ("offline cases only" if offline
             else "full regression (main suite and standalone tests)" if everything and not picked
             else "main suite" if not picked
             else "named tests")
    print(f"cases:  {label} — {n_run} run, {n_dev} dev build (skipped), {n_skip} skipped",
          flush=True)
    for i, (name, _module, runs, ids, reason) in enumerate(plan, 1):
        print(f"  {i:2}/{total}  {name:24} {'' if runs else 'SKIP — ' + reason}", flush=True)

    payload = {
        "schema": 1, "suite": "FreeCell regression suite",
        "build_kind": "dev" if dev else "prod", "started": _iso(started),
        "device": {"model": helpers.device_model(), "ios": helpers.os_version(),
                   "udid": config.DEVICE_UDID, "screen": "1290x2796"},
        "app": {"name": "FreeCell", "version": build[0], "build": build[1]},
        "plan": [name for name, _m, runs, _ids, _w in plan if runs],
        "tests": [], "cases": [],
    }
    tests, cases = payload["tests"], payload["cases"]
    scope = {cid for _s, _m, _r, ids, _w in plan for cid in ids
             if not (offline and cid in catalog.ONLINE_CASES)}
    kept = _previous({p[0] for p in plan}, scope)

    current: tuple[str, float] | None = None  # the test running, and since when
    stopped = False
    try:
        try:
            _network_first(plan, offline)
            for i, (name, module, runs, ids, reason) in enumerate(plan, 1):
                if name == catalog.ONLINE_FROM and not offline:
                    print("\n  bringing the phone online here for the online tests", flush=True)
                    fc.go_online()
                if not runs:
                    print(f"\n>>> [{i}/{total}] SKIP   {name} — {reason}", flush=True)
                    status = "skip" if catalog.entry(name)[2] == "skip" else "dev"
                    for cid in ids:
                        print(f"    [SKIP] {cid} {catalog.TITLES[cid]} — {reason}",
                              flush=True)
                        cases.append(_case_row(cid, name, status, reason))
                    tests.append({"name": name, "module": module, "status": "skip",
                                  "started": _iso(), "seconds": 0.0, "error": reason})
                    print(f"<<< [{i}/{total}] SKIP   {name}", flush=True)
                    continue

                current = (name, time.time())
                row, rows = _run_one(i, total, name, module, ids, dev, offline)
                tests.append(row)
                cases.extend(rows)
                current = None
                payload["finished"] = _iso()
                payload["duration_seconds"] = round(time.time() - started, 1)
                _write(payload, kept)

            if rerun and any(t["status"] == "fail" for t in tests):
                _summary(tests, cases, f"{heading} — first run")
                _report()
                try:
                    _rerun(plan, tests, cases, dev, offline)
                except Exception as exc:  # noqa: BLE001
                    print(f"WARNING: the rerun stopped: {exc}", flush=True)
        except KeyboardInterrupt:
            # A second stop must not cut the report short; stop --now kills outright.
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            stopped = True
            print("\n  stopped — writing the results and the report of the cases run so far",
                  flush=True)
            _stop_rows(plan, current, tests, cases, dev, offline, last)
            payload["stopped"] = payload["finished"] = _iso()
            payload["duration_seconds"] = round(time.time() - started, 1)
            _write(payload, kept)
            _summary(tests, cases, f"{heading} — stopped midway")
            _report()
    finally:
        if os.environ.get("FREECELL_SUITE_ONLINE") != "1":
            print("\n  putting the network back on", flush=True)
            try:
                ui.ensure_online()
            except Exception as exc:  # noqa: BLE001
                print(f"  WARNING: could not turn the network back on: {exc}", flush=True)
    if stopped:
        return 130

    payload["finished"] = _iso()
    payload["duration_seconds"] = round(time.time() - started, 1)
    _write(payload, kept)

    failed = _summary(tests, cases, heading)
    _report()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
