#!/usr/bin/env python3
"""Spider's verifyPlay on FreeCell: the picker lists five levels and Easy deals.

PL-01  Play opens the difficulty picker; no game starts
PL-02  Easy, Medium, Hard, Expert and Master are listed
PL-03  Easy (Yes to abandon a paused game) reaches the game table

Run:  ./.venv/bin/python -u tests/spider_suite/verifyPlay.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402


def run() -> None:
    fc.menu()
    with caselog.case("PL-01") as c:
        ui.expect(ui.tap("menu_play", settle=2.0), "Play control not found on the menu")
        ui.expect(ui.expect_screen("play"), "Play did not open the difficulty picker")
        ui.expect(not ui.at_table(timeout=1.0), "Play started a game instead of asking")
        c.shot(ui.shoot("PlayPicker"))
        c.note("difficulty picker opened")
    with caselog.case("PL-02") as c:
        missing = [level for level in ui.DIFFICULTIES if not ui.is_on(f"difficulty_{level}")]
        ui.expect(not missing, f"the picker does not list {missing}")
        c.note("Easy, Medium, Hard, Expert, Master listed")
    with caselog.case("PL-03") as c:
        ui.expect(ui.tap("difficulty_easy", settle=2.0), "Easy could not be tapped")
        ui.answer_prompt("abandon", "Yes")
        ui.expect(ui.expect_screen("table", timeout=12.0), "Easy did not reach the game table")
        ui.await_rules_prompt()
        ui.expect(ui.is_on("back_game") and ui.is_on("table_menu"),
                  "the table's top bar (back, menu) is not showing")
        c.shot(ui.shoot("PlayEasy"))
        c.note("Easy dealt a table")
    ui.expect(ui.to_menu(), "could not return to the menu after Play")
    print("PASS: the picker lists five levels and Easy dealt a table")


if __name__ == "__main__":
    fc.main(run)
