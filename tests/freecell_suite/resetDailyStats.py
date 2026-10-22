#!/usr/bin/env python3
"""Reset Daily Statistics, as resetStats does Solo (FreeCell's own RS cases; DESTRUCTIVE).

RS-06  Reset Daily Statistics, then No: Statistics stays on Daily and the
       Daily scores are unchanged
RS-04  tapped again: "Would you like to reset local scores?" (No / Yes),
       Yes, then "Just to be on the safe side…" (No / Yes)
RS-05  Yes again: the main menu; Statistics → Daily reads 0 / none, and
       the Solo scores are untouched

Runs right after verifyDaily, whose wins give the reset something to wipe.

Run:  ./.venv/bin/python -u tests/freecell_suite/resetDailyStats.py
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


def run() -> None:
    fc.menu()
    before, _shot = daily.read_stats("DailyStatsBeforeReset")
    solo, _shot = daily.read_stats("SoloStatsBeforeDailyReset", tab="solo")

    with caselog.case("RS-06") as c:
        daily.tap_reset()
        c.shot(ui.shoot("ResetDailyAsk"))
        ui.expect(helpers.answer_alert("No", settle=1.5), "could not press No")
        ui.expect(not helpers.alert_text(), "an alert is still up after No")
        ui.expect(daily.daily_tab_on(ui.screen_rgb()), "No did not leave Statistics on Daily")
        c.shot(ui.shoot("ResetDailyNo"))
        ui.leave_stats()
        ui.expect(ui.on_menu(6.0) or ui.to_menu(), "Statistics back did not return to the menu")
        after, shot = daily.read_stats("DailyStatsAfterNo")
        c.shot(shot)
        ui.expect(after[:len(before)] == before[:len(after)],
                  f"declining changed the Daily scores ({daily.stats_summary(before)} → "
                  f"{daily.stats_summary(after)}, see {shot})")
        c.note("No kept Statistics on Daily; the scores are unchanged "
               f"({daily.stats_summary(after)})")

    with caselog.case("RS-04") as c:
        text = daily.tap_reset()
        buttons = helpers.alert_buttons()
        ui.expect({"No", "Yes"} <= set(buttons), f"the alert offers {buttons}, not No and Yes")
        ui.expect(helpers.answer_alert("Yes", settle=1.5), "could not press Yes")
        second = fc.wait_alert("safe side", timeout=6.0)
        ui.expect(second, "the second 'safe side' confirmation did not appear")
        c.shot(ui.shoot("ResetDailySafeSide"))
        c.note(f"'{text.splitlines()[0]}', Yes, then '{second.splitlines()[0]}'")

    with caselog.case("RS-05") as c:
        ui.expect(helpers.answer_alert("Yes", settle=1.5), "could not press the second Yes")
        ui.expect(ui.on_menu(10.0), "the main menu did not come back after both Yes")
        after, shot = daily.read_stats("DailyStatsAfterReset")
        c.shot(shot)
        ui.expect(daily.stats_empty(after), f"Daily did not go to 0 / none after the reset "
                                            f"({daily.stats_summary(after)}, see {shot})")
        solo_after, solo_shot = daily.read_stats("SoloStatsAfterDailyReset", tab="solo")
        c.shot(solo_shot)
        ui.expect(solo_after[daily.TOTALS] == solo[daily.TOTALS],
                  f"the Daily reset changed the Solo scores ({daily.stats_summary(solo)} → "
                  f"{daily.stats_summary(solo_after)}, see {solo_shot})")
        c.note(f"both Yes: the main menu; Daily reads {daily.stats_summary(after)} and every "
               f"level none; Solo unchanged ({daily.stats_summary(solo_after)})")
    print("PASS: Reset Daily Statistics declined, then confirmed twice; Daily wiped, "
          "Solo untouched")


if __name__ == "__main__":
    fc.main(run)
