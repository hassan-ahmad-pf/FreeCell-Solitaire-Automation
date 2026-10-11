#!/usr/bin/env python3
"""Win an Easy game, prove its score on Solo, then Reset Solo to none/0.

Solo must read none/0 before the win, or an older, higher best score
(QA victory runs last and leaves one for the next run) would outrank
this game's. So Reset Solo Statistics runs first, unconditionally, and
none/0 is required before playing.

Start a new (not Daily) game, complete it, capture the victory CURRENT
score, tap Back from victory to the main menu, open Stats, and check that
score is Solo's best score. The victory "best" column is this week's
ranking, which Reset Solo does not clear, so it is not the number used.
Then scroll to Reset Solo Statistics, Yes both popups (back to the menu),
open Stats again, and check Solo shows none / 0.
"""
from __future__ import annotations

import sys

import freecell_ui as ui

# The right number peaks at 0.93; a different number (45,235 against
# 48,504) peaked at 0.70.
SCORE_MATCH = 0.80


def reset_before_win() -> str:
    """Reset Solo unconditionally, then require none/0 before playing."""
    ui.expect(ui.open_stats(), "did not tap Stats on the main menu")
    ui.open_stats_tab("solo")
    before = ui.shoot("SoloStatsBefore")
    found = ("already reads none/0" if ui.stats_are_default(before)
             else "has games from before this case")
    print(f"  Solo {found} — resetting before the win so its best score "
          f"can only be this game ({before})")
    ui.expect(ui.reset_solo_stats(),
              "could not reset Solo stats before the win")
    ui.expect(ui.open_stats(),
              "did not tap Stats on the main menu after the first reset")
    ui.open_stats_tab("solo")
    empty = ui.shoot("SoloStatsEmpty")
    ui.expect(ui.stats_are_default(empty),
              f"Solo was not none/0 before the win (see {empty}) — "
              f"the victory score would not be Solo's best")
    print(f"  Solo reads none/0 before the win — {empty}")
    ui.leave_stats()
    ui.expect(ui.on_menu(6.0), "Stats did not return to the main menu")
    return empty


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    empty = reset_before_win()
    ui.expect(ui.open_dev_panel(), "QA is not available to complete a game")
    ui.expect(ui.start_game("easy"), "Easy did not reach the table")
    ui.expect(ui.complete_game(), "the Easy game did not reach victory")
    victory = ui.shoot("SoloStatsVictory")
    score = ui.victory_score_crop()

    print("  tapping back from victory to the main menu")
    ui.expect(ui.leave_victory(),
              "Back from victory did not reach the main menu")
    ui.expect(ui.open_stats(),
              "did not tap Stats on the main menu after the win")
    ui.open_stats_tab("solo")
    solo = ui.shoot("SoloStatsAfterWin")
    hit = ui.score_on_stats(score, solo)
    ui.expect(hit >= SCORE_MATCH,
              f"the victory score {score} is not Solo's best score "
              f"(ink match {hit:.3f} < {SCORE_MATCH}, see {victory} / {solo})")
    print(f"  Solo's best score is the victory score (ink match {hit:.3f}) — {solo}")
    print("  scrolling to the bottom of Solo for Reset Solo Statistics")

    ui.expect(ui.reset_solo_stats(),
              "Reset Solo Statistics at the bottom of Solo was not tappable "
              "or both Yes popups were not confirmed")
    ui.expect(ui.on_menu(8.0),
              "the main menu did not come back after both Yes")
    ui.expect(ui.open_stats(),
              "did not tap Stats on the main menu after reset")
    ui.open_stats_tab("solo")
    cleared = ui.shoot("SoloStatsAfterReset")
    ui.expect(ui.stats_are_default(cleared),
              f"Solo stats were not cleared to none/0 after reset "
              f"(see {cleared})")
    ui.leave_stats()
    print(f"PASS: Solo started none/0, showed the Easy victory score, then "
          f"Reset Solo restored none/0 — {empty}, {victory}, {solo}, {cleared}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
