#!/usr/bin/env python3
"""visitLastScore: Play → LAST SCORE and its Game Center links. [ONLINE]

LS-01  Play → LAST SCORE opens a screen headed "Last Won Game Score"
LS-02  the forward arrow, 4 taps 2 s apart, steps week → month → overall →
       day → week and stays on the screen
LS-03  leaderboards opens Game Center (OK on its first-time notice); its back
       arrow reaches Leaderboards; back again and a tap below the dashboard
       returns to Last Score
LS-04  the same for achievements, headed Achievements
LS-05  back leaves for the main menu

Needs a won game since Statistics were last reset (triggerAdPoints' wins
normally provide it; without one, an Easy game is won through Synthetic Win
first) and a signed-in Game Center account, online.

FreeCell's leaderboards link opens the board of the level last won ("Easy •
Scores"); its back arrow is what shows Leaderboards. The Game Center sheet is
a remote view FreeCell's tree does not carry, so its headings and back arrow
are matched by their white lettering (find_ink): the sheet is translucent,
whatever is behind it tints the colours. The notice card before the first
sheet is FreeCell's own and is read from the tree.

Run:  ./.venv/bin/python -u tests/freecell_suite/visitLastScore.py
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

TAPS = 4
TAP_DELAY = 2.0
PERIOD_CHANGED = 0.01
PERIOD_SAME = 0.02
SHEET_BOTTOM = (645, int(2796 * 0.95))


def _ink(name: str, timeout: float = 8.0):
    deadline = time.time() + timeout
    while True:
        point = ui.find_ink(name)
        if point or time.time() >= deadline:
            return point
        time.sleep(0.5)


def _period_box(arrow) -> tuple[int, int, int, int]:
    """The 'ranking for / <period> / won N' block beside the arrow."""
    return (int(0.15 * 1290), arrow[1] - 100, int(0.85 * 1290), arrow[1] + 125)


def _open_last_score() -> None:
    if not ui.tap("menu_play", settle=2.0):
        helpers.wda_tap(ui.MENU_PLAY, settle=2.0)
    ui.expect(ui.expect_screen("play", timeout=6.0), "Play did not open the picker")
    helpers.wda_tap(ui.LAST_SCORE, settle=3.0)
    if not ui.seen("screen_last_score", timeout=6.0) and fc.ad_up():
        fc.close_or_wait("LAST SCORE")


def _notice() -> bool:
    """OK FreeCell's first-time Game Center card if it came up."""
    if not fc.named("StaticText", "Game Center", timeout=1.5):
        return False
    shot = ui.shoot("game_center_notice")
    ui.expect(fc.tap_named("Button", "OK", settle=5.0),
              f"the Game Center notice has no OK button to press — {shot}")
    print("  OK'd the first-time Game Center notice", flush=True)
    return True


def _close_sheet(link: str) -> None:
    """Back to the dashboard, then a tap below it, back on Last Score."""
    back = _ink("gc_back", timeout=4.0)
    ui.expect(back, f"Game Center's sheet after '{link}' has no back arrow (top-left)")
    helpers.tap(back, settle=3.0)
    helpers.wda_tap(SHEET_BOTTOM, settle=3.0)
    ui.expect(ui.seen("screen_last_score", timeout=8.0),
              f"after '{link}', back and a tap below the dashboard did not return "
              "to Last Score")


def _game_center(link: str, control: str, heading: str, title: str, c) -> None:
    ui.expect(ui.tap(control, settle=4.5), f"Last Score has no '{link}' link to tap")
    _notice()
    ui.expect(not ui.is_on("screen_last_score"),
              f"tapping '{link}' presented nothing — Last Score is still showing. "
              "Check the phone is online and signed in to Game Center")
    ui.expect(_ink("gc_back", timeout=10.0),
              f"'{link}' covered Last Score, but not with Game Center's sheet")
    if not ui.find_ink(heading):
        c.shot(ui.shoot(f"game_center_{link}_board"))
        helpers.tap(ui.find_ink("gc_back"), settle=3.0)
    ui.expect(_ink(heading, timeout=6.0),
              f"Game Center opened from '{link}' but never showed its {title} page")
    c.shot(ui.shoot(f"game_center_{link}"))
    _close_sheet(link)


def _win_once() -> None:
    """Setup: a Synthetic Win on Easy, for when Statistics were reset since the last win."""
    fc.ensure_qa()
    fc.enter_game("easy")
    ui.expect(ui.synthetic_win(), "Synthetic Win could not be fired for the setup win")
    fc.clear_ad("setup win", wait=fc.LATE_AD)
    ui.expect(ui.expect_screen("victory", timeout=8.0), "the setup win did not reach Victory")
    ui.expect(ui.leave_victory(), "Victory's back did not return to the main menu")
    fc.clear_ad("setup Victory back", wait=fc.LATE_AD)
    ui.expect(ui.on_menu(4.0) or ui.to_menu(), "not on the main menu after the setup win")


def run() -> None:
    fc.go_online()
    fc.menu()
    fc.game_center_on()

    with caselog.case("LS-01") as c:
        _open_last_score()
        if not ui.seen("screen_last_score", timeout=4.0):
            print("  no won game since Statistics were reset — winning an Easy game first",
                  flush=True)
            ui.expect(ui.to_menu(), "could not leave the picker for the setup win")
            _win_once()
            _open_last_score()
        ui.expect(ui.seen("screen_last_score", timeout=4.0),
                  "LAST SCORE did not open a screen headed 'Last Won Game Score' — "
                  "a won game is needed first")
        c.shot(ui.shoot("last_score"))
        c.note("header: Last Won Game Score")

    with caselog.case("LS-02") as c:
        arrow = ui.find("last_score_next")
        ui.expect(arrow, "Last Score has no forward arrow beside 'ranking for'")
        box = _period_box(arrow)
        first = prev = ui.shoot("last_score_tap0")
        for i in range(1, TAPS + 1):
            helpers.tap(arrow, settle=TAP_DELAY)
            now = c.shot(ui.shoot(f"last_score_tap{i}"))
            moved = fc.diff_frac(prev, now, box)
            print(f"  tap {i}/{TAPS}: period changed {moved:.3f}", flush=True)
            ui.expect(moved > PERIOD_CHANGED, f"tap {i} on the forward arrow did not "
                                              "change the ranking period")
            prev = now
        ui.expect(fc.diff_frac(first, prev, box) < PERIOD_SAME,
                  f"{TAPS} taps did not bring the ranking period back to where it "
                  "started (week → month → overall → day → week)")
        ui.expect(ui.is_on("screen_last_score"),
                  "the forward arrow navigated off Last Score")
        c.note(f"{TAPS} taps: every tap changed the period, the 4th is back at the start")

    with caselog.case("LS-03") as c:
        _game_center("leaderboards", "victory_leaderboards", "gc_leaderboards",
                     "Leaderboards", c)
        c.note("Game Center → Leaderboards, back and dismissed onto Last Score")

    with caselog.case("LS-04") as c:
        _game_center("achievements", "victory_achieve", "gc_achievements",
                     "Achievements", c)
        c.note("Game Center → Achievements, back and dismissed onto Last Score")

    with caselog.case("LS-05") as c:
        ui.back(settle=2.0)
        if not ui.on_menu(3.0):
            ui.expect(ui.to_menu(), "back from Last Score did not lead to the main menu")
        ui.expect(ui.on_menu(4.0), "back from Last Score did not reach the main menu")
        c.shot(ui.shoot("last_score_back"))
        c.note("back on the main menu")

    print("PASS: Last Score opens, cycles its period, and opens and closes Game Center")


if __name__ == "__main__":
    fc.main(run)
