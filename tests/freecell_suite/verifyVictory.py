#!/usr/bin/env python3
"""verifyVictory: the win screen, reached with Synthetic Win. [DEV]

FreeCell's Complete Game is the QA badge's Synthetic Win card on the table:
pick 90% - 99%, then WIN. The card closes by itself on the win, so nothing
covers the Victory screen afterwards.

VI-01  Easy, Synthetic Win, the Victory screen
VI-02  ranking header, current / rank / best, leaderboards, achievements,
       help, new and stats are all drawn
VI-03  the footer says "easy level"
VI-04  Victory's own back returns to the main menu

Needs QA on (openDebugTools leaves it on); turns it on itself when it is off.
The leaderboards and achievements links need Options' Game Center switch on,
which the test also makes sure of first.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyVictory.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402

LEVEL = "easy"

PARTS = {
    "victory_ranking": "the 'ranking for' header",
    "screen_victory": "the current/rank/best column headers",
    "victory_leaderboards": "the leaderboards link",
    "victory_achieve": "the achievements link",
    "victory_help": "the help button",
    "victory_new": "the new button",
    "victory_stats": "the stats button",
}


def run() -> None:
    fc.menu()
    fc.game_center_on()
    fc.ensure_qa()

    with caselog.case("VI-01") as c:
        fc.enter_game(LEVEL)
        c.shot(ui.shoot("VictoryTable"))
        ui.expect(ui.complete_game(),
                  "Synthetic Win (90% - 99%, WIN) did not reach the Victory screen")
        ui.expect(not ui.is_on("qa_panel"), "the Synthetic Win card is still open "
                                            "over the Victory screen")
        c.shot(ui.shoot("VictoryScreen"))
        c.note(f"{LEVEL.title()} won through Synthetic Win; Victory showing")

    with caselog.case("VI-02") as c:
        missing = [f"{d} ({n})" for n, d in PARTS.items() if not ui.is_on(n)]
        ui.expect(not missing, f"the Victory screen is missing {len(missing)} "
                               f"element(s): {'; '.join(missing)}")
        c.note(f"all {len(PARTS)} parts drawn")

    with caselog.case("VI-03") as c:
        ui.expect(ui.is_on(f"victory_level_{LEVEL}"),
                  f"the Victory footer does not say '{LEVEL} level', so it does not "
                  "reflect the game just played")
        c.note(f"footer: {LEVEL} level")

    with caselog.case("VI-04") as c:
        ui.expect(ui.leave_victory(),
                  "Victory's back did not return to the main menu")
        ui.expect(not ui.at_table(timeout=1.0), "Victory's back landed on a table")
        c.shot(ui.shoot("VictoryBack"))
        c.note("back to the main menu")

    print("PASS: the Victory screen renders, names the level, and back leaves it")


if __name__ == "__main__":
    fc.main(run)
