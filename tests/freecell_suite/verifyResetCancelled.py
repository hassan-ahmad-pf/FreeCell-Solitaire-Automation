#!/usr/bin/env python3
"""verifyResetCancelled: declining reset keeps the scores.

RS-03  Reset Solo Statistics asks first; No closes the question, Statistics
       stays open, and the page is unchanged

FreeCell asks with a native alert ("reset local scores"). The page is
compared above the banner ad, which changes on its own when online.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyResetCancelled.py
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

PAGE = (0, 200, 1290, 2300)
SAME = 0.02


def run() -> None:
    fc.menu()
    ui.expect(ui.open_stats(), "Stats did not open from the main menu")
    ui.open_stats_tab("solo")
    ui.expect(ui.scroll_to_bottom("reset_solo_stats", max_swipes=20),
              "could not reach Reset Solo Statistics")
    ui.settle(4.0)

    with caselog.case("RS-03") as c:
        before = c.shot(ui.shoot("StatsResetCancelledBefore"))
        ui.expect(ui.tap("reset_solo_stats", settle=1.5),
                  "Reset Solo Statistics could not be tapped")
        text = fc.wait_alert("reset local scores", timeout=6.0)
        ui.expect(text, "Reset Solo Statistics did not ask to confirm "
                        f"(alert on screen: {helpers.alert_text()!r})")
        ui.expect(helpers.answer_alert("No", settle=1.5), "could not press No")
        ui.expect(not helpers.alert_text(), "the reset question stayed up after No")
        ui.expect(ui.is_on("reset_solo_stats"), "No did not leave Statistics on screen")
        ui.settle(4.0)
        after = c.shot(ui.shoot("StatsResetCancelledAfter"))
        changed = fc.diff_frac(before, after, PAGE)
        ui.expect(changed <= SAME, f"No changed {changed:.2%} of the Statistics page — "
                                   f"the scores may have been reset ({before}, {after})")
        c.note(f"No kept Statistics open; page diff {changed:.2%}")

    ui.expect(ui.to_menu(), "could not return to the menu after declining reset")
    print("PASS: declining Reset Solo Statistics left Statistics open and unchanged")


if __name__ == "__main__":
    fc.main(run)
