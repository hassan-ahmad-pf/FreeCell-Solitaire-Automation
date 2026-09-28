#!/usr/bin/env python3
"""A finished Easy game lands on Solo stats, then Reset Solo wipes them.

Wins a regular (not Daily) Easy game, reads the victory *current* score,
opens Statistics on the Solo tab, and checks that score's digits appear
there. Then scrolls to Reset Solo Statistics, taps Yes on both popups
(which returns to the menu), opens Stats again, and checks Solo is back
to none / 0.

Resets Solo first so an older higher best cannot hide this run's score.
"""
from __future__ import annotations

import sys

import freecell_ui as ui

SCORE_MATCH = 0.72


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    ui.expect(ui.open_stats(), "Stats did not open")
    ui.expect(ui.is_on("stats_solo_tab") or ui.open_stats_tab("solo"),
              "the Solo heading is missing")
    ui.expect(ui.is_on("stats_daily_tab"),
              "the Daily heading is missing")
    headings = ui.shoot("StatsHeadings")

    ui.expect(ui.reset_solo_stats(),
              "Reset Solo Statistics at the bottom of Solo was not found "
              "or both Yes popups were not confirmed")
    ui.expect(ui.on_menu(8.0),
              "the main menu did not come back after both Yes")
    ui.expect(ui.open_stats(),
              "did not tap Stats on the main menu after reset")
    ui.open_stats_tab("solo")
    ui.expect(ui.stats_are_default(),
              "Solo was not cleared to none/0 after the first reset")
    print("  Solo is clear (none/0) — leaving Stats to play")
    ui.expect(ui.to_menu(), "could not leave Stats after the first reset")
    ui.expect(ui.open_dev_panel(), "QA is not available to complete a game")
    ui.expect(ui.start_game("easy"), "Easy did not reach the table")
    ui.expect(ui.complete_game(), "the Easy game did not reach victory")
    victory = ui.shoot("SoloStatsVictory")
    score = ui.victory_score_crop()

    ui.expect(ui.to_menu(), "could not leave victory for Stats")
    ui.expect(ui.open_stats(), "Stats did not open after the win")
    ui.open_stats_tab("solo")
    solo = ui.shoot("SoloStatsAfterWin")
    hit = ui.score_on_stats(score, solo)
    ui.expect(hit >= SCORE_MATCH,
              f"victory current score {score} was not found on Solo stats "
              f"(ink match {hit:.3f} < {SCORE_MATCH}, see {victory} / {solo})")
    print(f"  Solo shows the victory score (ink match {hit:.3f}) — {solo}")
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
    ui.expect(ui.stats_are_default(),
              f"Solo stats were not cleared to none/0 after reset "
              f"(see {cleared})")
    ui.expect(ui.to_menu(), "could not return to the menu after checking reset")
    print(f"PASS: Solo showed the Easy victory score, then Reset Solo "
          f"restored the defaults — {headings}, {victory}, {solo}, {cleared}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
