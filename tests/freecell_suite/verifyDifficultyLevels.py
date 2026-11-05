#!/usr/bin/env python3
"""verifyDifficultyLevels: each level deals and can be won. [DEV]

Per level: menu → Play → the level → the table → Synthetic Win → Victory →
Victory's back → the main menu. It starts at Medium (Easy is covered by
verifyPlay and verifyVictory); FreeCell's levels after Easy are Medium,
Hard, Expert and Master.

DL-01  Medium   DL-05  Medium current / rank / best
DL-02  Hard     DL-06  Hard current / rank / best
DL-03  Expert   DL-07  Expert current / rank / best
DL-04  Master   DL-08  Master current / rank / best

Each win is its own case; the table is checked on that Victory before Back.
A failure does not stop the next level.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyDifficultyLevels.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import config  # noqa: E402
import daily  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402

LEVELS = (
    ("DL-01", "DL-05", "medium"),
    ("DL-02", "DL-06", "hard"),
    ("DL-03", "DL-07", "expert"),
    ("DL-04", "DL-08", "master"),
)


def _play_and_win(win_id: str, table_id: str, level: str) -> None:
    shot = str(config.LOG / f"victory_{level}.png")
    if not ui.on_menu(2.0):
        fc.menu()
    fc.ensure_qa()
    with caselog.case(win_id, soft=True) as c:
        fc.enter_game(level)
        c.shot(ui.shoot(f"difficulty_{level}"))
        ui.expect(ui.complete_game(),
                  f"Synthetic Win on the {level.title()} table did not reach Victory")
        caselog.step(f"Check the Victory screen shows after winning {level.title()}")
        ui.expect(ui.expect_screen("victory", timeout=2.0),
                  f"Victory is not showing after the {level.title()} win")
        shot = c.shot(ui.shoot(f"victory_{level}"))
        c.note(f"{level.title()} dealt, won through Synthetic Win")
    with caselog.case(table_id, soft=True) as t:
        ui.expect(shot and os.path.exists(shot),
                  f"no Victory screen — the {level.title()} win did not finish")
        table = daily.check_victory_table(shot, daily_farm=False)
        score = table["score"]
        t.shot(shot)
        t.note(f"{level.title()}: current {score['current']:,}  "
               f"rank {score['rank']}  best {score['best']}")
    if ui.expect_screen("victory", timeout=1.5):
        ui.expect(ui.leave_victory(),
                  f"Victory's back after {level.title()} did not return to the main menu")
        ui.expect(ui.on_menu(6.0),
                  f"Victory's back after {level.title()} did not leave the main menu up")


def run() -> None:
    fc.menu()
    for win_id, table_id, level in LEVELS:
        _play_and_win(win_id, table_id, level)
        if win_id in caselog.failed() and not ui.on_menu(2.0):
            ui.to_menu()
    caselog.raise_if_failed()
    print(f"PASS: all {len(LEVELS)} levels (Medium..Master) deal, win, and return "
          "to the menu")


if __name__ == "__main__":
    fc.main(run)
