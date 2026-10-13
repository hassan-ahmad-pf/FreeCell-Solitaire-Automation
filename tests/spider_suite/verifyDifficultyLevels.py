#!/usr/bin/env python3
"""Spider's verifyDifficultyLevels on FreeCell: each level deals and can be won. [DEV]

Per level: menu → Play → the level → the table → Synthetic Win → Victory →
Victory's back → the main menu. Spider starts at Medium (Easy is covered by
verifyPlay and verifyVictory); FreeCell's levels after Easy are Medium,
Hard, Expert and Master, so Spider's Bold and Expert become Expert and Master.

DL-01  Medium   DL-02  Hard   DL-03  Expert   DL-04  Master

Each level is its own case and a failure does not stop the next one.

Run:  ./.venv/bin/python -u tests/spider_suite/verifyDifficultyLevels.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402

LEVELS = (("DL-01", "medium"), ("DL-02", "hard"), ("DL-03", "expert"), ("DL-04", "master"))


def _play_and_win(level: str, c) -> None:
    if not ui.on_menu(2.0):
        fc.menu()
    fc.ensure_qa()
    fc.enter_game(level)
    c.shot(ui.shoot(f"difficulty_{level}"))
    ui.expect(ui.complete_game(),
              f"Synthetic Win on the {level.title()} table did not reach Victory")
    c.shot(ui.shoot(f"victory_{level}"))
    ui.expect(ui.leave_victory(),
              f"Victory's back after {level.title()} did not return to the main menu")
    c.note(f"{level.title()} dealt, won through Synthetic Win, back on the menu")


def run() -> None:
    fc.menu()
    for cid, level in LEVELS:
        with caselog.case(cid, soft=True) as c:
            _play_and_win(level, c)
        if cid in caselog.failed() and not ui.on_menu(2.0):
            ui.to_menu()
    caselog.raise_if_failed()
    print(f"PASS: all {len(LEVELS)} levels (Medium..Master) deal, win, and return "
          "to the menu")


if __name__ == "__main__":
    fc.main(run)
