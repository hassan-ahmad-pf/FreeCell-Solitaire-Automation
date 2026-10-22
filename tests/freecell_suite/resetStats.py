#!/usr/bin/env python3
"""resetStats: Reset Solo Statistics, confirmed (DESTRUCTIVE).

RS-01  the link asks to confirm ("reset local scores")
RS-02  Yes, then Yes on "just to be on the safe side", wipes the local
       scores — Solo reads best score 0 and Easy none afterwards

Last of the Stats tests: it leaves the device's local
statistics at zero.

Run:  ./.venv/bin/python -u tests/freecell_suite/resetStats.py
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


def run() -> None:
    fc.menu()
    ui.expect(ui.open_stats(), "Stats did not open from the main menu")
    ui.open_stats_tab("solo")
    ui.expect(ui.scroll_to_bottom("reset_solo_stats", max_swipes=20),
              "could not reach Reset Solo Statistics")

    with caselog.case("RS-01") as c:
        ui.expect(ui.tap("reset_solo_stats", settle=1.5),
                  "Reset Solo Statistics could not be tapped")
        caselog.step("Check FreeCell asks to confirm resetting the local scores")
        text = fc.wait_alert("reset local scores", timeout=6.0)
        c.shot(ui.shoot("ResetStats"))
        ui.expect(text, "Reset Solo Statistics did not ask to confirm "
                        f"(alert on screen: {helpers.alert_text()!r})")
        c.note(text.splitlines()[0] if text else "")

    with caselog.case("RS-02") as c:
        ui.expect(helpers.answer_alert("Yes", settle=1.5), "could not press Yes")
        caselog.step("Check the second 'just to be on the safe side' question appears")
        text = fc.wait_alert("safe side", timeout=6.0)
        ui.expect(text, "the second 'safe side' confirmation did not appear")
        ui.expect(helpers.answer_alert("Yes", settle=1.5), "could not press the second Yes")
        ui.expect(ui.on_menu(10.0), "the main menu did not come back after both Yes")
        ui.expect(ui.open_stats(), "Stats did not open after the reset")
        ui.open_stats_tab("solo")
        cleared = c.shot(ui.shoot("ResetStatsAfter"))
        caselog.step("Check every Solo score reads none / 0")
        ui.expect(ui.stats_are_default(cleared),
                  f"Solo did not read none / 0 after the reset (see {cleared})")
        ui.leave_stats()
        c.note("both confirmations accepted; Solo reads none / 0")

    ui.expect(ui.to_menu(), "did not get back to the main menu after resetting")
    print("PASS: Reset Solo Statistics asked twice and wiped the local scores")


if __name__ == "__main__":
    fc.main(run)
