#!/usr/bin/env python3
"""verifyAds: pin AppLovin in MAX's debugger, then the leave-game ad. [ONLINE]

FreeCell's Dev Panel is its QA page — tap the menu's CONFIDENTIAL watermark
with QA on — and its Max Debugger button is the page's "Max: Adapters" row,
which opens AppLovin's MAX Mediation Debugger. The debugger is native UIKit
with a real accessibility tree.

AD-01  online, QA on, the QA page opens and offers Max: Adapters
AD-02  Adapters opens the MAX Mediation Debugger, FreeCell still in front
AD-03  the Ads section's Select Live Network (or Live Network) row is on screen
AD-04  its picker opens and AppLovin carries the checkmark
AD-06  debugger closed, a game, 30 s, Back: an interstitial plays inside
       FreeCell and its close controls (store X, then the ad X) close it.
       If Back shows none, the next resume shows it, which also passes.
AD-07  after the ad, the game table is showing again (FreeCell's Back ad
       closes onto the menu, so the paused game is resumed)

Rows scrolled out of view stay in the debugger's tree with untappable rects,
so rows are looked up visible-only. "AppLovin" is also listed under the
debugger's Completed SDK Integrations, so it is looked for only once the
picker's own navigation bar is up.

Ends on the table. An ad that will not close by its
controls is closed by hand ("Manual effort required at this step").

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyAds.py
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402
from caselog import says  # noqa: E402

DEBUGGER = "MAX Mediation Debugger"
LIVE_NETWORK = "Select Live Network"
LIVE_NETWORK_SELECTED = "Live Network"
NETWORK = "AppLovin"
SWIPES = 8
TABLE_WAIT = 32.0
BACK_AD_WAIT = 20.0
ENTER_AD_WAIT = 20.0


def _window(title: str, timeout: float = 8.0) -> bool:
    return bool(fc.named("NavigationBar", title, timeout=timeout))


def _debugger_open(timeout: float = 8.0) -> bool:
    return _window(DEBUGGER, timeout=timeout)


def _live_row() -> tuple[str, dict] | None:
    for label in (LIVE_NETWORK, LIVE_NETWORK_SELECTED):
        r = fc.visible_rect("StaticText", label)
        if r:
            return label, r
    return None


@says(f"Scroll the debugger down to its Ads section ({LIVE_NETWORK})")
def _scroll_to_live_row() -> tuple[str, dict] | None:
    for _ in range(SWIPES):
        found = _live_row()
        if found:
            return found
        helpers.wda_swipe((645, 2100), (645, 1000), duration_ms=500, settle=1.5)
    return _live_row()


def _same_row(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    ay, by = a["y"] + a["height"] / 2, b["y"] + b["height"] / 2
    return abs(ay - by) <= max(a["height"], b["height"], 24)


def _open_debugger() -> None:
    ui.expect(ui.tap("qa_page_adapters", settle=5.0),
              "the QA page has no 'Max: Adapters' row to tap")


def _unwind() -> None:
    """Leave debugger windows and the QA page a previous run left up."""
    if _window(LIVE_NETWORK, timeout=1.0):
        print(f"  a previous run left the {LIVE_NETWORK!r} window open — backing out",
              flush=True)
        fc.tap_named("Button", "BackButton", settle=2.0)
    if _debugger_open(timeout=1.0):
        print("  a previous run left the debugger open — closing it", flush=True)
        fc.tap_named("Button", "Done", settle=2.0)
    if ui.is_on("qa_page_back"):
        ui.tap("qa_page_back", settle=2.0)


@says("Go back into the game: Play, then Resume")
def _resume_table() -> None:
    """Back onto the paused game from the menu: Play → Resume (or Easy)."""
    if ui.at_table(timeout=2.0):
        return
    ui.settle_prompts()
    if not ui.on_menu(3.0):
        ui.expect(ui.to_menu(), "could not reach the menu to resume the game")
    if not ui.tap("menu_play", settle=2.0):
        helpers.wda_tap(ui.MENU_PLAY, settle=2.0)
    ui.expect(ui.wait_for("difficulty_easy", timeout=6.0), "Play did not open the picker")
    if ui.is_on("resume"):
        ui.expect(ui.tap("resume", settle=2.0), "Resume could not be tapped")
    else:
        ui.expect(ui.tap("difficulty_easy", settle=2.0), "Easy could not be tapped")
        ui.answer_prompt("abandon")


def run() -> None:
    fc.go_online()
    caselog.step("Bring FreeCell to the front")
    try:
        helpers.launch_app(force=False)
    except Exception:  # noqa: BLE001
        pass
    _unwind()
    fc.menu()

    with caselog.case("AD-01") as c:
        fc.ensure_qa()
        ui.expect(ui.tap("qa_watermark", settle=3.0),
                  "the menu has no CONFIDENTIAL watermark to open the QA page from")
        caselog.step("Check the QA page opened with its 'Max: Adapters' row")
        ui.expect(ui.seen("qa_page_adapters", timeout=6.0),
                  "the QA page did not open, or it has no 'Max: Adapters' row")
        c.shot(ui.shoot("ad_dev_panel"))
        c.note("QA page open, offers Max: Adapters")

    with caselog.case("AD-02") as c:
        _open_debugger()
        caselog.step(f"Check the {DEBUGGER} opened inside FreeCell")
        ui.expect(_debugger_open(timeout=12.0),
                  f"'Adapters' did not open the {DEBUGGER} — in front: "
                  f"{helpers.active_app() or 'unknown'}")
        ui.expect(helpers.in_app(), "the debugger left FreeCell")
        c.shot(ui.shoot("ad_max_debugger"))
        c.note(f"{DEBUGGER} open, FreeCell in front")

    with caselog.case("AD-03") as c:
        found = _scroll_to_live_row()
        if not found:
            print("  Ads section not in view — reopening the debugger from the top",
                  flush=True)
            fc.tap_named("Button", "Done", settle=2.0)
            _open_debugger()
            ui.expect(_debugger_open(timeout=12.0), "reopening Adapters did not bring "
                                                    "the debugger back")
            found = _scroll_to_live_row()
        ui.expect(found, f"never brought {LIVE_NETWORK!r} or {LIVE_NETWORK_SELECTED!r} "
                         f"into view in {SWIPES} swipes")
        row_label, row = found
        c.shot(ui.shoot("ad_ads_section"))
        c.note(f"Ads section: {row_label!r} on screen")

    with caselog.case("AD-04") as c:
        already = row_label == LIVE_NETWORK_SELECTED and _same_row(
            row, fc.visible_rect("StaticText", NETWORK))
        print(f"  {NETWORK} already the live network: {already}", flush=True)
        caselog.step(f"Tap '{row_label}' in the debugger")
        fc.tap_rect(row, settle=3.0)
        caselog.step(f"Check the '{LIVE_NETWORK}' picker opened and lists {NETWORK}")
        ui.expect(_window(LIVE_NETWORK), f"tapping {row_label!r} did not open the "
                                         f"{LIVE_NETWORK!r} picker")
        pick = fc.visible_rect("StaticText", NETWORK)
        ui.expect(pick, f"{NETWORK!r} is not listed on the {LIVE_NETWORK!r} picker")
        tick = fc.named("Button", "checkmark")
        print(f"  a network was already ticked: {bool(tick)}", flush=True)
        if not _same_row(pick, fc.rect(tick) if tick else None):
            caselog.step(f"Tap {NETWORK} to make it the live network")
            fc.tap_rect(pick, settle=3.0)
        caselog.step(f"Check the checkmark is on {NETWORK}")
        tick = fc.named("Button", "checkmark", timeout=8.0)
        ui.expect(_same_row(fc.visible_rect("StaticText", NETWORK),
                            fc.rect(tick) if tick else None),
                  f"the checkmark is not on {NETWORK} after selecting it")
        c.shot(ui.shoot("ad_applovin"))
        c.note(f"{NETWORK} ticked on {LIVE_NETWORK}")

    with caselog.case("AD-06") as c:
        ui.expect(fc.tap_named("Button", "BackButton", settle=2.0),
                  f"could not back out of the {LIVE_NETWORK!r} picker")
        ui.expect(fc.tap_named("Button", "Done", settle=2.0),
                  "the debugger has no Done button")
        ui.expect(not _debugger_open(timeout=2.0), "the debugger did not close")
        ui.expect(ui.tap("qa_page_back", settle=2.0), "the QA page has no back control")
        ui.expect(ui.on_menu(6.0), "back from the QA page did not reach the main menu")
        fc.loaded_table("the leave-game ad")
        caselog.step(f"Wait {TABLE_WAIT:.0f} s on the game table (ads have a cooldown)")
        time.sleep(TABLE_WAIT)
        ui.expect(ui.tap("back_game", settle=1.0), "the table's Back could not be tapped")
        where = "leave-game"
        if not fc.wait_ad(timeout=BACK_AD_WAIT):
            print("  no interstitial on Back — trying the next resume", flush=True)
            where = "resume"
            _resume_table()
            ui.expect(fc.wait_ad(timeout=ENTER_AD_WAIT),
                      "neither Back nor the next resume showed an interstitial")
        caselog.step("Check the ad plays inside FreeCell")
        ui.expect(helpers.in_app(), f"the {where} ad left FreeCell for "
                                    f"{helpers.active_app()}")
        c.shot(ui.shoot("ad_interstitial"))
        fc.close_or_wait(where)
        if where in fc.MANUAL_CLOSES:
            c.note("passed manually — the ad was closed by hand")
        c.note(f"{where} interstitial played inside FreeCell and closed")

    with caselog.case("AD-07") as c:
        if not ui.at_table(timeout=6.0):
            print("  the ad closed onto the menu — resuming the paused game", flush=True)
            _resume_table()
            if fc.ad_up():
                fc.close_or_wait("resume after the ad")
        ui.settle_prompts()
        caselog.step("Check the game table is showing after the ad")
        ui.expect(ui.at_table(timeout=10.0), "the game table is not showing after the ad")
        c.shot(ui.shoot("ad_back_on_table"))
        c.note("back on the game table")

    print(f"PASS: {NETWORK} pinned in MAX's debugger, the leave-game ad closed, back "
          "on the table")


if __name__ == "__main__":
    fc.main(run)
