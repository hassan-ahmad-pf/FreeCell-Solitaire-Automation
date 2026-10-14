#!/usr/bin/env python3
"""Run Spider's regression suite on FreeCell and print a PASS/FAIL summary.

Spider's tests/run_all.py on the FreeCell build: Spider's test order, case
IDs and titles (game name swapped), one line per case, and Spider's report.
FreeCell's Daily cases (DY-01..14, from FreeCell's own TestRail list) run
in two FreeCell-only tests slotted into that order.
tests/spider_suite/catalog.py says where every test stands:

  run    a FreeCell port (tests/spider_suite/<module>.py) runs and records
         its cases
  dev    needs the dev build — SKIP on the prod build; --dev runs the ones
         that have a FreeCell port
  skip   cannot run on this install (FL-06: not installed from TestFlight)
  later  a Spider-only feature FreeCell does not have — listed, not run

As in Spider, a bare run is the main suite (Spider's TESTS); the standalone
tests (Choose Look, Ad-free, Feedback, and the dev-only Ads, Ad trigger
points, Last Score) run only when named. Every invocation merges into the
same results, so the report covers both.

Network, as in Spider: verifyFirstLaunch opens the policy links online, then
goes offline for the middle of the suite; at the promo-strip step (skipped on
prod) the phone comes back online for the reset tests and Contact Us online.
The run ends online.

Prereqs: FreeCell freshly installed from the App Store and NOT opened (the
first test reads the first launch), phone online and unlocked, WDA up via
scripts/wda.sh, DEVICE_UDID exported, a Mail account on the phone.

Run:  ./.venv/bin/python -u tests/spider_suite/run_all.py                # main suite
      ./.venv/bin/python -u tests/spider_suite/run_all.py verifyChooseLook \\
          verifyAdFreeVersion submitFeedback                              # standalone
      ./.venv/bin/python -u tests/spider_suite/run_all.py verifyPlay verifyGamePlay
      ./.venv/bin/python -u tests/spider_suite/run_all.py --offline     # Airplane Mode cases only
      ./.venv/bin/python -u tests/spider_suite/run_all.py --dev

Results: log/spider_suite_results.json after every test, then
scripts/gen_spider_format_report.py writes log/freecell_spider_regression.html.
"""
from __future__ import annotations

import importlib.util
import json
import os
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

RESULTS_PATH = config.LOG / "spider_suite_results.json"
REPORT_PATH = config.LOG / "freecell_spider_regression.html"
REPORT_SCRIPT = os.path.join(ROOT, "scripts", "gen_spider_format_report.py")

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
    "daily_back", "daily_tip1", "daily_tip2", "daily_weekdays", "daily_faq_link",
    "daily_gold_star", "daily_levels", "daily_relaxed_note", "daily_level_easy",
    "daily_level_medium", "daily_level_hard", "daily_level_easy_r", "daily_table_star",
    "daily_table_medium", "daily_popup_days", "faq_daily_heading",
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
    spec = importlib.util.spec_from_file_location(f"spider_suite_{module}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _offline_ids(ids: list[str]) -> list[str]:
    return [c for c in ids if c not in catalog.ONLINE_CASES and c not in catalog.LATER]


def _plan(picked: list[str], dev: bool, offline: bool) -> list[tuple]:
    """(spider name, module, runs?, ids, reason) in Spider's order."""
    out = []
    for spider, module, kind, ids, why in catalog.RUN_ORDER:
        if picked and spider not in picked and module not in picked:
            continue
        if not picked and not offline and spider in catalog.STANDALONE:
            continue
        if offline and (kind != "run" or not _offline_ids(ids)):
            continue
        runs = bool(module) and (kind == "run" or (kind == "dev" and dev))
        reason = why if kind in ("dev", "skip") else ""
        if kind == "dev" and dev and not module:
            reason = "no FreeCell port yet"
        out.append((spider, module, runs, ids, reason))
    return out


def _case_row(cid: str, test: str, status: str, detail: str = "", rec: dict | None = None):
    rec = rec or {}
    return {
        "id": cid, "title": catalog.TITLES[cid], "section": catalog.SECTIONS[cid],
        "test": test, "status": status, "detail": detail,
        "shots": rec.get("shots", []), "notes": rec.get("notes", []),
        "seconds": rec.get("seconds", 0.0),
    }


def _previous(names: set[str], scope: set[str]) -> tuple[list, list, str]:
    """Tests, cases and start time of an earlier run that this invocation does not redo."""
    try:
        old = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], [], ""
    tests = [t for t in old.get("tests", []) if t.get("name") not in names]
    return (tests, [c for c in old.get("cases", []) if c.get("id") not in scope],
            old.get("started", "") if tests else "")


def _write(payload: dict, kept: tuple[list, list, str]) -> None:
    order = {spider: i for i, (spider, *_rest) in enumerate(catalog.RUN_ORDER)}
    ids = [c["id"] for c in catalog.CASES]
    out = dict(payload)
    out["tests"] = sorted(kept[0] + payload["tests"], key=lambda t: order.get(t["name"], 99))
    out["cases"] = sorted(kept[1] + payload["cases"], key=lambda c: ids.index(c["id"]))
    if kept[0]:
        out["started"] = min(filter(None, (kept[2], payload["started"])))
        out["duration_seconds"] = round(sum(t.get("seconds", 0) for t in out["tests"]), 1)
    config.LOG.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


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
    os.environ["SPIDER_SUITE_BUILD"] = "dev" if dev else "prod"
    offline = "--offline" in args
    picked = [a for a in args if not a.startswith("-")]
    plan = _plan(picked, dev, offline)
    total = len(plan)
    started = time.time()

    problems = preflight()
    if problems:
        print("preflight failed:", flush=True)
        for p in problems:
            print(f"  - {p}", flush=True)
        return 2

    build = helpers.installed_build() or ("", "")
    print(f"device: {config.DEVICE_UDID}", flush=True)
    print(f"wda:    {config.WDA_URL}", flush=True)
    print(f"build:  FreeCell {build[0]} ({build[1]}) — {'dev' if dev else 'prod'} run"
          f"{', offline cases only' if offline else ''}", flush=True)
    n_run = n_dev = n_skip = n_later = 0
    for spider, _m, runs, ids, _w in plan:
        n_later += sum(c in catalog.LATER for c in ids)
        mine = [c for c in ids if c not in catalog.LATER]
        if runs:
            n_run += len(_offline_ids(ids) if offline else mine)
        elif catalog.entry(spider)[2] == "skip":
            n_skip += len(mine)
        else:
            n_dev += len(mine)
    label = ("offline cases only" if offline else "main suite" if not picked
             else "named tests")
    print(f"cases:  {label} — {n_run} run, {n_dev} dev build (skipped), {n_skip} skipped, "
          f"{n_later} later", flush=True)
    for i, (spider, _module, runs, ids, reason) in enumerate(plan, 1):
        print(f"  {i:2}/{total}  {spider:24} {'' if runs else 'SKIP — ' + reason}", flush=True)

    payload = {
        "schema": 1, "suite": "Spider regression suite on FreeCell",
        "build_kind": "dev" if dev else "prod", "started": _iso(started),
        "device": {"model": helpers.device_model(), "ios": helpers.os_version(),
                   "udid": config.DEVICE_UDID, "screen": "1290x2796"},
        "app": {"name": "FreeCell", "version": build[0], "build": build[1]},
        "tests": [], "cases": [],
    }
    tests, cases = payload["tests"], payload["cases"]
    scope = {cid for _s, _m, _r, ids, _w in plan for cid in ids
             if not (offline and cid in catalog.ONLINE_CASES)}
    kept = _previous({p[0] for p in plan}, scope)

    try:
        for i, (spider, module, runs, ids, reason) in enumerate(plan, 1):
            if spider == catalog.ONLINE_FROM and not offline:
                print("\n  bringing the phone online here, as Spider's promo-strip step does",
                      flush=True)
                fc.go_online()
            if not runs:
                print(f"\n>>> [{i}/{total}] SKIP   {spider} — {reason}", flush=True)
                status = "skip" if catalog.entry(spider)[2] == "skip" else "dev"
                for cid in ids:
                    if cid in catalog.LATER:
                        print(f"    [LATER] {cid} {catalog.TITLES[cid]} — {catalog.LATER[cid]}",
                              flush=True)
                        cases.append(_case_row(cid, spider, "later", catalog.LATER[cid]))
                    else:
                        print(f"    [SKIP] {cid} {catalog.TITLES[cid]} — {reason}", flush=True)
                        cases.append(_case_row(cid, spider, status, reason))
                tests.append({"name": spider, "module": module, "status": "skip",
                              "seconds": 0.0, "error": reason})
                print(f"<<< [{i}/{total}] SKIP   {spider}", flush=True)
                continue

            print(f"\n>>> [{i}/{total}] START  {spider}", flush=True)
            caselog.begin(spider)
            os.environ["TEST_NAME"] = spider
            t0 = time.time()
            error = ""
            try:
                _load(module).run()
            except Exception as exc:  # noqa: BLE001
                error = str(exc) or type(exc).__name__
                print(f"FAIL: {error}", flush=True)
            dt = time.time() - t0

            recorded = {r["id"]: r for r in caselog.results()}
            runnable = [cid for cid in ids if cid not in catalog.LATER
                        and (dev or cid not in catalog.DEV_CASES)]
            bad = False
            for cid in ids:
                if offline and cid in catalog.ONLINE_CASES:
                    print(f"    [ONLINE] {cid} {catalog.TITLES[cid]} — online pass; "
                          "keeps its last result", flush=True)
                    continue
                if cid in catalog.LATER:
                    print(f"    [LATER] {cid} {catalog.TITLES[cid]} — {catalog.LATER[cid]}",
                          flush=True)
                    cases.append(_case_row(cid, spider, "later", catalog.LATER[cid]))
                    continue
                if cid not in runnable:
                    why = catalog.DEV_CASES[cid]
                    print(f"    [SKIP] {cid} {catalog.TITLES[cid]} — {why}", flush=True)
                    cases.append(_case_row(cid, spider, "dev", why))
                    continue
                rec = recorded.get(cid)
                if rec is None:
                    detail = ("not reached — the test stopped first: " + error if error
                              else "the test did not record this case")
                    print(f"    [FAIL] {cid} {catalog.TITLES[cid]} — {detail}", flush=True)
                    cases.append(_case_row(cid, spider, "fail", detail))
                    bad = True
                    continue
                cases.append(_case_row(cid, spider, rec["status"], rec["detail"], rec))
                bad = bad or rec["status"] == "fail"
            ok = not error and not bad
            tests.append({"name": spider, "module": module, "status": "pass" if ok else "fail",
                          "seconds": round(dt, 1), "error": error})
            print(f"<<< [{i}/{total}] {'PASS' if ok else 'FAIL'}  {spider}  ({dt:.1f}s)",
                  flush=True)
            payload["finished"] = _iso()
            payload["duration_seconds"] = round(time.time() - started, 1)
            _write(payload, kept)
    finally:
        if os.environ.get("SPIDER_SUITE_ONLINE") != "1":
            print("\n  putting the network back on", flush=True)
            try:
                ui.ensure_online()
            except Exception as exc:  # noqa: BLE001
                print(f"  WARNING: could not turn the network back on: {exc}", flush=True)

    payload["finished"] = _iso()
    payload["duration_seconds"] = round(time.time() - started, 1)
    _write(payload, kept)

    print("\n" + "=" * 64, flush=True)
    print("  Spider regression suite on FreeCell "
          f"({'dev' if dev else 'prod'} build {build[0]} ({build[1]}))", flush=True)
    for t in tests:
        mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[t["status"]]
        print(f"  {mark}  {t['name']:24} ({t['seconds']:6.1f}s)", flush=True)
    by = {}
    for c in cases:
        by[c["status"]] = by.get(c["status"], 0) + 1
    executed = by.get("pass", 0) + by.get("fail", 0)
    print(f"\n  cases: {by.get('pass', 0)}/{executed} executed passed, "
          f"{by.get('fail', 0)} failed, {by.get('skip', 0)} skipped, "
          f"{by.get('dev', 0)} dev build, {by.get('later', 0)} later", flush=True)
    failed = [c for c in cases if c["status"] == "fail"]
    if failed:
        print("\n  failed cases:", flush=True)
        for c in failed:
            print(f"    {c['id']} {c['title']} — {c['detail']}", flush=True)
    _report()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
