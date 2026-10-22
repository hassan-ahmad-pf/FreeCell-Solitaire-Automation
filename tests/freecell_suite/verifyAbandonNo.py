#!/usr/bin/env python3
"""verifyAbandonNo: declining abandon keeps the picker.

PL-04  with a paused game, Easy asks to abandon it; No keeps the picker open,
       no table starts, and the paused game (its Resume ribbon) is still there

A paused game is made first if the picker has no Resume ribbon (verifyPlay
leaves one). It ends by resuming that game, so verifyRelaunch carries on
with it on the table.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyAbandonNo.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402


def _open_picker() -> None:
    ui.expect(ui.tap("menu_play", settle=2.0), "Play control not found on the menu")
    ui.expect(ui.wait_for("difficulty_easy", timeout=6.0), "Play did not open the picker")


def run() -> None:
    fc.menu()
    _open_picker()
    if not ui.is_on("resume"):
        print("  no paused game — dealing Easy and making one move first", flush=True)
        ui.expect(ui.tap("difficulty_easy", settle=2.0), "Easy could not be tapped")
        ui.answer_prompt("abandon", "Yes")
        ui.expect(ui.at_table(), "Easy did not reach the table")
        ui.await_rules_prompt()
        fc.play_one_move(" before pausing it")
        ui.expect(ui.leave_table() and ui.on_menu(6.0), "could not leave the table")
        _open_picker()
        ui.expect(ui.is_on("resume"), "leaving a moved game did not pause it")

    with caselog.case("PL-04") as c:
        ui.expect(ui.tap("difficulty_easy", settle=1.5), "Easy could not be tapped")
        caselog.step("Check FreeCell asks whether to abandon the paused game")
        text = fc.wait_alert("abandon", timeout=6.0)
        ui.expect(text, "Easy over a paused game did not ask to abandon it")
        c.shot(ui.shoot("AbandonPrompt"))
        ui.expect(helpers.answer_alert("No", settle=1.5), "could not press No")
        caselog.step("Check the picker is still open and the paused game kept (Resume shows)")
        ui.expect(not helpers.alert_text(), "the abandon question stayed up after No")
        ui.expect(ui.wait_for("difficulty_easy", timeout=4.0), "No closed the picker")
        ui.expect(not ui.at_table(timeout=1.5), "No started a new table anyway")
        ui.expect(ui.is_on("resume"), "No discarded the paused game (no Resume ribbon)")
        c.shot(ui.shoot("AbandonNo"))
        c.note("No kept the picker and the paused game")

    ui.expect(ui.tap("resume", settle=2.0), "Resume could not be tapped")
    ui.expect(ui.at_table(), "Resume did not reach the game table")
    print("PASS: declining abandon kept the picker open and the paused game")


if __name__ == "__main__":
    fc.main(run)
