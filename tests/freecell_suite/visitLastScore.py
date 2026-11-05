#!/usr/bin/env python3
"""visitLastScore: Play → LAST SCORE while already online after the promo strip.

LS-01  Play → LAST SCORE opens "Last Won Game Score" and shows the won
       game's score (current / rank / best)
LS-02  the forward arrow, 4 taps 2 s apart, steps week → month → overall →
       day → week and stays on the screen
LS-05  back leaves for the main menu

Sits before verifyStatistics: a Solo reset would wipe the won score. Needs
a won game since Statistics were last reset (Victory / Daily / Difficulty
usually provide it; without one, an Easy game is won through Synthetic Win
first).

Run:  ./.venv/bin/python -u tests/freecell_suite/visitLastScore.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import daily  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402
from caselog import says  # noqa: E402

TAPS = 4
TAP_DELAY = 2.0
PERIOD_CHANGED = 0.01
PERIOD_SAME = 0.02


def _period_box(arrow) -> tuple[int, int, int, int]:
    """The 'ranking for / <period> / won N' block beside the arrow."""
    return (int(0.15 * 1290), arrow[1] - 100, int(0.85 * 1290), arrow[1] + 125)


@says("Open Last Score: Play, then LAST SCORE")
def _open_last_score() -> None:
    if not ui.tap("menu_play", settle=2.0):
        helpers.wda_tap(ui.MENU_PLAY, settle=2.0)
    ui.expect(ui.expect_screen("play", timeout=6.0), "Play did not open the picker")
    helpers.wda_tap(ui.LAST_SCORE, settle=3.0)
    if not ui.seen("screen_last_score", timeout=6.0) and fc.ad_up():
        fc.close_or_wait("LAST SCORE")


@says("Win an Easy game with Synthetic Win first, so there is a last score to show")
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


def _stay_online() -> bool:
    """Keep the promo-icons session if it is already up. True when this
    module had to go online or reopen the menu."""
    fresh = False
    if not ui.known_online():
        fc.go_online()
        fresh = True
    if ui.on_menu(2.0):
        return fresh
    fc.menu()
    return True


def _ensure_last_score() -> None:
    if ui.seen("screen_last_score", timeout=2.0):
        return
    if not ui.on_menu(2.0):
        ui.to_menu() or ui.on_menu(4.0)
    _open_last_score()
    if ui.seen("screen_last_score", timeout=4.0):
        return
    print("  no won game since Statistics were reset — winning an Easy game first",
          flush=True)
    ui.expect(ui.to_menu(), "could not leave the picker for the setup win")
    _win_once()
    _open_last_score()
    ui.expect(ui.seen("screen_last_score", timeout=4.0),
              "LAST SCORE did not open a screen headed 'Last Won Game Score' — "
              "a won game is needed first")


def run() -> None:
    _stay_online()

    with caselog.case("LS-01") as c:
        _ensure_last_score()
        caselog.step("Check the screen is headed 'Last Won Game Score'")
        ui.expect(ui.seen("screen_last_score", timeout=4.0),
                  "LAST SCORE did not open a screen headed 'Last Won Game Score' — "
                  "a won game is needed first")
        shot = c.shot(ui.shoot("last_score"))
        caselog.step("Check current / rank / best and the won game's score are showing")
        ui.expect(ui.is_on("screen_victory"),
                  "Last Score has no current / rank / best columns for the won game")
        table = daily.check_victory_table(shot)
        shown = table["score"]
        ui.expect(isinstance(shown["current"], int) and shown["current"] > 0,
                  "Last Score opened but the won game's score is not showing")
        c.note(f"header: Last Won Game Score; current {shown['current']:,}  "
               f"rank {shown['rank']}  best {shown['best']} "
               f"(online, after the promo strip)")

    with caselog.case("LS-02") as c:
        _ensure_last_score()
        arrow = ui.find("last_score_next")
        ui.expect(arrow, "Last Score has no forward arrow beside 'ranking for'")
        box = _period_box(arrow)
        first = prev = ui.shoot("last_score_tap0")
        for i in range(1, TAPS + 1):
            caselog.step(f"Tap the forward arrow beside 'ranking for' ({i} of {TAPS}) and "
                         "check the period changes")
            helpers.tap(arrow, settle=TAP_DELAY)
            now = c.shot(ui.shoot(f"last_score_tap{i}"))
            moved = fc.diff_frac(prev, now, box)
            print(f"  tap {i}/{TAPS}: period changed {moved:.3f}", flush=True)
            ui.expect(moved > PERIOD_CHANGED, f"tap {i} on the forward arrow did not "
                                              "change the ranking period")
            prev = now
        caselog.step(f"Check {TAPS} taps brought the period back to where it started")
        ui.expect(fc.diff_frac(first, prev, box) < PERIOD_SAME,
                  f"{TAPS} taps did not bring the ranking period back to where it "
                  "started (week → month → overall → day → week)")
        ui.expect(ui.is_on("screen_last_score"),
                  "the forward arrow navigated off Last Score")
        c.note(f"{TAPS} taps: every tap changed the period, the 4th is back at the start")

    with caselog.case("LS-05") as c:
        _ensure_last_score()
        ui.back(settle=2.0)
        if not ui.on_menu(3.0):
            ui.expect(ui.to_menu(), "back from Last Score did not lead to the main menu")
        caselog.step("Check the main menu is showing")
        ui.expect(ui.on_menu(4.0), "back from Last Score did not reach the main menu")
        c.shot(ui.shoot("last_score_back"))
        c.note("back on the main menu")

    print("PASS: Last Score opens with the won score, cycles its period, and "
          "back returns to the main menu")


if __name__ == "__main__":
    fc.main(run)
