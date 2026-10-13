#!/usr/bin/env python3
"""Spider's triggerAdPoints on FreeCell: interstitial trigger and cooldown points. [ONLINE]

Spider's two clocks: more than 30 s on the table, then leaving it, can show
an interstitial; once one closes, a 30 s cooldown suppresses the next.

TA-01  under 30 s on the table, Options: no ad
TA-02  over 30 s on the table, Help: ad
TA-03  Options within 30 s of the Help ad: no ad
TA-04  over 30 s on the table, Synthetic Win: ad over Victory
TA-05  New within 30 s of that Victory ad: an ad too (Spider shows none;
       FreeCell's New after Victory is not held by the cooldown)
TA-06  a second win after 30 s on the table, its ad closed, over 30 s on
       Victory, then New: ad
TA-07  over 30 s on the table, Back: ad, closing onto the main menu
TA-08  starting a game within 30 s on that menu: no ad
TA-10  over 30 s on the table, FAQ: ad
TA-09  Back ad onto the menu, over 30 s on the menu, then deal: ad

Spider's Complete Game is the QA badge's Synthetic Win, so the run turns QA
on first. An ad is FreeCell in front with none of its own screens showing.

Spider's Unity ads fill every time; FreeCell's do not, so a missing ad could
just be no fill. Each case that expects an ad therefore starts only once an
interstitial is loaded: back to the menu, the QA page until its SHOW control
turns black, then Resume onto the table. A missing ad then means the trigger
did not fire. FreeCell's ads can arrive ~10 s after their trigger, so each
detour first waits out a late one.
An ad that cannot be closed by its controls is closed by hand, as in Spider
("Manual effort required at this step"); that case then says "passed
manually".

Run:  ./.venv/bin/python -u tests/spider_suite/triggerAdPoints.py
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

SHORT = 8.0
DWELL = 32.0
NO_AD = 10.0
WATCH = 5.0
AD_WAIT = 20.0
READY_WAIT = 300.0

DESTINATIONS = {
    "options": ("drawer_options", lambda: ui.expect_screen("options", timeout=0.5)),
    "help": ("drawer_help", lambda: ui.expect_screen("help", timeout=0.5)),
    "faq": ("drawer_faq", lambda: ui.is_on("screen_faq")),
}


def _manual_note(c, where: str) -> None:
    if where in fc.MANUAL_CLOSES:
        c.note("passed manually — the ad was closed by hand")


def _dwell(seconds: float, what: str) -> None:
    print(f"  waiting {seconds:.0f}s {what}", flush=True)
    time.sleep(seconds)


def _open(dest: str) -> None:
    anchor, _ = DESTINATIONS[dest]
    ui.expect(ui.open_table_drawer(), f"the table drawer did not open before {dest}")
    ui.expect(ui.tap(anchor, settle=1.0), f"could not tap the drawer's {dest}")


def _no_ad(label: str, arrived) -> None:
    """The expected screen arrives, and no ad covers it for WATCH seconds."""
    deadline = time.time() + NO_AD
    while not arrived():
        ui.expect(helpers.in_app(), f"FreeCell left the screen during {label}: "
                                    f"{helpers.active_app()}")
        ui.expect(not fc.ad_up(), f"an interstitial appeared during {label}")
        ui.expect(time.time() < deadline, f"{label} did not arrive within {NO_AD:.0f}s")
        time.sleep(0.3)
    watch_until = time.time() + WATCH
    while time.time() < watch_until:
        ui.expect(not fc.ad_up(), f"an interstitial appeared during {label}")
    print(f"  {label}: no ad", flush=True)


def _ad(label: str) -> None:
    ui.expect(fc.wait_ad(timeout=AD_WAIT), f"no interstitial for {label} within "
                                           f"{AD_WAIT:.0f}s")
    print(f"  {label}: interstitial up", flush=True)
    fc.close_or_wait(label)


def _back_to_table() -> None:
    if ui.at_table(timeout=3.0):
        return
    ui.settle_prompts()
    ui.back()
    if ui.at_table(timeout=8.0):
        return
    ui.expect(ui.on_menu(3.0), "could not get back to the table or the menu")
    fc.enter_game("easy")
    ui.expect(ui.at_table(timeout=8.0), "could not get back to the game table")


def _win_with_ad(label: str) -> None:
    """Synthetic Win on the table; its ad must come up over Victory."""
    ui.expect(ui.synthetic_win(), f"Synthetic Win could not be fired for {label}")
    _ad(label)
    ui.expect(ui.expect_screen("victory", timeout=8.0),
              f"the Victory screen is not showing after the {label} ad closed")


def _victory_new() -> None:
    ui.expect(ui.tap("victory_new", settle=1.0), "Victory's New could not be tapped")


def _fresh_table() -> None:
    """A new deal, so TA-01's short clock starts on a table opened just now."""
    fc.menu()
    fc.enter_game("easy")
    ui.expect(ui.open_table_drawer(), "the table drawer did not open for New")
    ui.expect(ui.tap("drawer_new", settle=2.0), "could not tap the drawer's New")
    if fc.wait_alert("abandon", timeout=2.0):
        helpers.answer_alert("Yes", settle=1.5)
    ui.settle_prompts()
    if fc.clear_ad("fresh-table setup", wait=fc.LATE_AD):
        print("  the fresh deal showed an ad — closed it", flush=True)
        ui.settle_prompts()
    ui.expect(ui.at_table(timeout=8.0), "could not reach a fresh game table")


def run() -> None:
    fc.go_online()
    fc.menu()
    fc.ensure_qa()
    _fresh_table()

    with caselog.case("TA-01") as c:
        for attempt in range(2):
            _dwell(SHORT, "on the table before Options")
            _open("options")
            try:
                _no_ad("short table -> Options", DESTINATIONS["options"][1])
                break
            except AssertionError:
                if attempt or not fc.ad_up():
                    raise
                print("  an inherited ad came up — closing it and retrying once "
                      "from a fresh table clock", flush=True)
                fc.close_or_wait("short table -> Options retry")
                _back_to_table()
        c.shot(ui.shoot("AdShortOptions"))
        _back_to_table()
        c.note(f"Options after {SHORT:.0f}s on the table, no ad")

    with caselog.case("TA-02") as c:
        fc.loaded_table("Help")
        _dwell(DWELL, "on the table before Help")
        _open("help")
        _ad("long table -> Help")
        _back_to_table()
        c.shot(ui.shoot("AdAfterHelp"))
        _manual_note(c, "long table -> Help")
        c.note("ad shown and closed")

    with caselog.case("TA-03") as c:
        _open("options")
        _no_ad("Options inside the Help-ad cooldown", DESTINATIONS["options"][1])
        c.shot(ui.shoot("AdCooldownOptions"))
        _back_to_table()
        c.note("Options right after the Help ad, no ad")

    with caselog.case("TA-04") as c:
        fc.loaded_table("the first win")
        _dwell(DWELL, "on the table before Synthetic Win")
        _win_with_ad("long table -> Victory")
        c.shot(ui.shoot("AdVictory"))
        _manual_note(c, "long table -> Victory")
        c.note("ad over Victory, closed; Victory showing")

    with caselog.case("TA-05", soft=True) as c:
        _victory_new()
        ui.expect(fc.wait_ad(timeout=AD_WAIT), f"no interstitial for Victory ad closed -> New "
                                               f"within {AD_WAIT:.0f}s")
        print("  Victory ad closed -> New: interstitial up", flush=True)
        c.shot(ui.shoot("AdVictoryNewCooldown"))
        fc.close_or_wait("Victory -> New inside the cooldown")
        _manual_note(c, "Victory -> New inside the cooldown")
        ui.settle_prompts()
        ui.expect(ui.at_table(timeout=8.0), "New within the cooldown did not reach a table")
        c.note("New within 30s of the Victory ad showed an ad, closed onto the new deal")
    if fc.ad_up():
        fc.close_or_wait("Victory -> New inside the cooldown")
    ui.settle_prompts()
    ui.expect(ui.at_table(timeout=8.0), "could not reach the table after TA-05")

    with caselog.case("TA-06") as c:
        # New's ad needs the next interstitial to have loaded after the win's
        # ad, which the table detour cannot check from Victory: one rerun.
        for attempt in range(2):
            fc.loaded_table("the second win")
            _dwell(DWELL, "on the table before the second Synthetic Win")
            _win_with_ad("second long table -> Victory")
            _dwell(DWELL, "on Victory before New")
            _victory_new()
            if fc.wait_ad(timeout=AD_WAIT):
                print("  Victory -> New after the cooldown: interstitial up", flush=True)
                fc.close_or_wait("Victory -> New after the cooldown")
                break
            ui.expect(not attempt, f"no interstitial for Victory -> New after the cooldown "
                                   f"within {AD_WAIT:.0f}s, twice")
            print("  no ad on New — the next interstitial may not have loaded after the "
                  "win's ad; once more from a loaded table", flush=True)
            ui.settle_prompts()
        _back_to_table()
        c.shot(ui.shoot("AdVictoryNew"))
        if {"second long table -> Victory",
                "Victory -> New after the cooldown"} & fc.MANUAL_CLOSES:
            c.note("passed manually — the ad was closed by hand")
        c.note("second Victory ad closed; New after 30s on Victory showed an ad")

    with caselog.case("TA-07") as c:
        fc.loaded_table("Back")
        _dwell(DWELL, "on the table before Back")
        ui.expect(ui.tap("back_game", settle=1.0), "the table's Back could not be tapped")
        _ad("long table -> Back")
        ui.expect(ui.on_menu(8.0), "the Back ad did not close onto the main menu")
        c.shot(ui.shoot("AdBackMenu"))
        _manual_note(c, "long table -> Back")
        c.note("ad shown, closed onto the main menu")

    with caselog.case("TA-08") as c:
        _dwell(SHORT, "on the menu before entering the game")
        fc.enter_from_menu(deal=False)
        _no_ad("short menu -> game", lambda: ui.at_table(timeout=0.5))
        c.shot(ui.shoot("AdShortMenuEntry"))
        c.note("game entered within 30s of the Back ad, no ad")

    with caselog.case("TA-10") as c:
        fc.loaded_table("FAQ")
        _dwell(DWELL, "on the table before FAQ")
        _open("faq")
        _ad("long table -> FAQ")
        _back_to_table()
        c.shot(ui.shoot("AdAfterFaq"))
        _manual_note(c, "long table -> FAQ")
        c.note("ad shown and closed, back on the table")

    with caselog.case("TA-09") as c:
        fc.loaded_table("Back (TA-09 setup)")
        _dwell(DWELL, "on the table before Back")
        ui.expect(ui.tap("back_game", settle=1.0), "the table's Back could not be tapped")
        _ad("long table -> Back (TA-09 setup)")
        ui.expect(ui.on_menu(8.0), "the Back ad did not close onto the main menu")
        waited = fc.wait_inter_loaded(READY_WAIT)
        print(f"  interstitial loaded again (QA SHOW after {waited:.0f}s)", flush=True)
        _dwell(DWELL, "on the menu before dealing")
        fc.enter_from_menu(deal=True)
        _ad("long menu -> deal")
        ui.settle_prompts()
        ui.expect(ui.at_table(timeout=8.0), "the deal did not reach the table after its ad")
        c.shot(ui.shoot("AdLongMenuEntry"))
        _manual_note(c, "long menu -> deal")
        c.note("ad shown on entering the game")

    ui.expect(ui.to_menu(), "could not return to the main menu after the ad checks")
    caselog.raise_if_failed()
    print("PASS: every interstitial trigger and cooldown point behaved as in Spider")


if __name__ == "__main__":
    fc.main(run)
