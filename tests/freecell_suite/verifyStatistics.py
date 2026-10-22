#!/usr/bin/env python3
"""verifyStatistics: every Statistics case, in three visits (DESTRUCTIVE).

Visit 1, from the main menu:
ST-01  Stats opens Statistics and the main menu is gone
RS-06  Reset Daily Statistics, then No: Statistics stays on Daily and the
       Daily scores are unchanged
RS-04  tapped again: "Would you like to reset local scores?" (No / Yes),
       Yes, then "Just to be on the safe side…" (No / Yes)
RS-05  Yes again: the main menu; Statistics → Daily reads 0 / none, and
       the Solo scores are untouched
Visit 2, carrying on from RS-05's check:
ST-03  the Solo tab scrolls all the way down to Reset Solo Statistics
RS-03  Reset Solo Statistics, then No: Statistics stays open and unchanged
RS-01  tapped again: it asks to confirm ("reset local scores")
RS-02  Yes, then Yes on "just to be on the safe side": the main menu; Solo
       reads best score 0 and Easy none
Visit 3, carrying on from RS-02's check:
ST-04  Back returns to the main menu

A confirmed reset always sends FreeCell to the main menu, so three visits is
the fewest. It runs after every test that needs the wins it wipes
(verifyMoreGamesIcons draws its strip only after a won game). Pages are
compared above the banner ad, which changes on its own when online.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyStatistics.py
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import daily  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402
from caselog import says  # noqa: E402

PAGE = (0, 200, 1290, 2300)
SAME = 0.02


def _open_stats(c) -> None:
    """Tap Stats; a second tap only when the first left a bare menu (no alert)."""
    ui.expect(ui.tap("menu_stats", settle=2.2), "Stats control not found on the menu")
    if ui.expect_screen("stats", timeout=8.0):
        return
    shot = c.shot(ui.shoot("StatsNotOpened"))
    alert = helpers.alert_text()
    answered = ui.settle_prompts()
    menu = ui.on_menu(1.0)
    print(f"  Statistics did not open (menu up: {menu}, alert: {alert!r}, "
          f"answered: {answered}, see {shot})", flush=True)
    if menu and not alert and ui.tap("menu_stats", settle=2.2) and ui.expect_screen("stats"):
        c.note("the first Stats tap left the menu up with no alert — the second opened it")
        return
    raise AssertionError(f"tapping Stats did not open Statistics (menu up: {menu}, "
                         f"alert: {alert!r}, see {shot})")


def _stats(tab: str) -> None:
    """Statistics on *tab*, opened from the main menu unless it is already up."""
    if tab == "daily":
        daily.open_daily_stats()
        return
    if not ui.expect_screen("stats", timeout=1.0):
        ui.expect(ui.open_stats(), "Statistics did not open from the main menu")
        fc.clear_ad("Statistics", wait=2.0 if fc.is_online() else 0.0)
    ui.open_stats_tab("solo")
    time.sleep(1.0)


def _read(name: str) -> tuple[list[dict], str]:
    """The tab on screen, read from the top of the page; [] when unreadable."""
    shot = ui.shoot(name)
    return daily.stats_sections(shot), shot


@says(lambda name, max_swipes=20: f"Scroll down until {ui.label(name)} shows")
def _swipes_to(name: str, max_swipes: int = 20) -> int:
    """Swipe the page up until *name* shows; how many swipes that took."""
    for n in range(max_swipes):
        if ui.is_on(name):
            return n
        ui.scroll(True)
    ui.expect(ui.is_on(name), f"could not scroll down to {ui.label(name)}")
    return max_swipes


@says("Scroll back to the top of the page")
def _back_to_top(swipes: int) -> None:
    """As many swipes back as it took to get down: a page with an animated
    banner never holds still, so 'until it stops moving' cannot end it."""
    for _ in range(swipes + 1):
        ui.scroll(False)
    ui.settle(3.0)


def _ask_solo_reset() -> str:
    if not ui.is_on("reset_solo_stats"):
        _stats("solo")
        ui.expect(ui.scroll_to_bottom("reset_solo_stats", max_swipes=20),
                  "could not reach Reset Solo Statistics")
    ui.expect(ui.tap("reset_solo_stats", settle=1.5), "Reset Solo Statistics could not be tapped")
    caselog.step("Check FreeCell asks to confirm resetting the local scores")
    text = fc.wait_alert("reset local scores", timeout=6.0)
    ui.expect(text, "Reset Solo Statistics did not ask to confirm "
                    f"(alert on screen: {helpers.alert_text()!r})")
    return text


def run() -> None:
    fc.menu()

    with caselog.case("ST-01") as c:
        _open_stats(c)
        caselog.step("Check Statistics opened")
        ui.expect(not ui.on_menu(1.0), "the main menu is still showing")
        c.shot(ui.shoot("Stats"))
        c.note("Statistics opened")
    fc.clear_ad("Statistics", wait=2.0 if fc.is_online() else 0.0)

    _stats("solo")
    solo, solo_shot = _read("SoloStatsBeforeDailyReset")
    _stats("daily")
    before, before_shot = _read("DailyStatsBeforeReset")

    with caselog.case("RS-06", soft=True) as c:
        ui.expect(before, f"could not read the Daily statistics (see {before_shot})")
        swipes = _swipes_to("reset_daily_stats")
        ui.expect(ui.tap("reset_daily_stats", settle=1.5),
                  "Reset Daily Statistics could not be tapped")
        caselog.step("Check FreeCell asks to confirm resetting the local scores")
        ui.expect(fc.wait_alert("reset local scores", timeout=6.0),
                  f"Reset Daily Statistics did not ask to confirm "
                  f"(alert on screen: {helpers.alert_text()!r})")
        c.shot(ui.shoot("ResetDailyAsk"))
        ui.expect(helpers.answer_alert("No", settle=1.5), "could not press No")
        caselog.step("Check the alert closed and Statistics stayed on the Daily tab")
        ui.expect(not helpers.alert_text(), "an alert is still up after No")
        ui.expect(daily.daily_tab_on(ui.screen_rgb()), "No did not leave Statistics on Daily")
        c.shot(ui.shoot("ResetDailyNo"))
        _back_to_top(swipes)
        after, shot = _read("DailyStatsAfterNo")
        c.shot(shot)
        caselog.step("Check the Daily scores did not change")
        ui.expect(after and after[:len(before)] == before[:len(after)],
                  f"declining changed the Daily scores ({daily.stats_summary(before)} → "
                  f"{daily.stats_summary(after) if after else 'unreadable'}, see {shot})")
        c.note("No kept Statistics on Daily; the scores are unchanged "
               f"({daily.stats_summary(after)})")

    with caselog.case("RS-04", soft=True) as c:
        text = daily.tap_reset()
        caselog.step("Check the alert offers No and Yes")
        buttons = helpers.alert_buttons()
        ui.expect({"No", "Yes"} <= set(buttons), f"the alert offers {buttons}, not No and Yes")
        ui.expect(helpers.answer_alert("Yes", settle=1.5), "could not press Yes")
        caselog.step("Check the second 'just to be on the safe side' question appears")
        second = fc.wait_alert("safe side", timeout=6.0)
        ui.expect(second, "the second 'safe side' confirmation did not appear")
        c.shot(ui.shoot("ResetDailySafeSide"))
        c.note(f"'{text.splitlines()[0]}', Yes, then '{second.splitlines()[0]}'")

    with caselog.case("RS-05", soft=True) as c:
        ui.expect(helpers.answer_alert("Yes", settle=1.5), "could not press the second Yes")
        ui.expect(ui.on_menu(10.0), "the main menu did not come back after both Yes")
        _stats("daily")
        after, shot = _read("DailyStatsAfterReset")
        c.shot(shot)
        caselog.step("Check Daily reads 0 / none on every level")
        ui.expect(after and daily.stats_empty(after),
                  f"Daily did not go to 0 / none after the reset "
                  f"({daily.stats_summary(after) if after else 'unreadable'}, see {shot})")
        _stats("solo")
        solo_after, solo_after_shot = _read("SoloStatsAfterDailyReset")
        c.shot(solo_after_shot)
        caselog.step("Check the Solo scores did not change")
        ui.expect(solo, f"the Solo scores could not be read before the Daily reset "
                        f"(see {solo_shot})")
        ui.expect(solo_after and solo_after[daily.TOTALS] == solo[daily.TOTALS],
                  f"the Daily reset changed the Solo scores ({daily.stats_summary(solo)} → "
                  f"{daily.stats_summary(solo_after) if solo_after else 'unreadable'}, "
                  f"see {solo_after_shot})")
        c.note(f"both Yes: the main menu; Daily reads {daily.stats_summary(after)} and every "
               f"level none; Solo unchanged ({daily.stats_summary(solo_after)})")

    if helpers.alert_text():
        helpers.answer_alert("No", settle=1.5)

    with caselog.case("ST-03") as c:
        _stats("solo")
        ui.expect(ui.scroll_to_bottom("reset_solo_stats", max_swipes=20),
                  "could not scroll down to Reset Solo Statistics")
        c.shot(ui.shoot("StatsBottom"))
        c.note("Reset Solo Statistics reached at the bottom")

    with caselog.case("RS-03", soft=True) as c:
        ui.settle(4.0)
        before_page = c.shot(ui.shoot("StatsResetCancelledBefore"))
        _ask_solo_reset()
        ui.expect(helpers.answer_alert("No", settle=1.5), "could not press No")
        caselog.step("Check the question closed and Statistics did not change")
        ui.expect(not helpers.alert_text(), "the reset question stayed up after No")
        ui.expect(ui.is_on("reset_solo_stats"), "No did not leave Statistics on screen")
        ui.settle(4.0)
        after_page = c.shot(ui.shoot("StatsResetCancelledAfter"))
        changed = fc.diff_frac(before_page, after_page, PAGE)
        ui.expect(changed <= SAME, f"No changed {changed:.2%} of the Statistics page — "
                                   f"the scores may have been reset ({before_page}, {after_page})")
        c.note(f"No kept Statistics open; page diff {changed:.2%}")

    with caselog.case("RS-01") as c:
        text = _ask_solo_reset()
        c.shot(ui.shoot("ResetStats"))
        c.note(text.splitlines()[0])

    with caselog.case("RS-02", soft=True) as c:
        ui.expect(helpers.answer_alert("Yes", settle=1.5), "could not press Yes")
        caselog.step("Check the second 'just to be on the safe side' question appears")
        ui.expect(fc.wait_alert("safe side", timeout=6.0),
                  "the second 'safe side' confirmation did not appear")
        ui.expect(helpers.answer_alert("Yes", settle=1.5), "could not press the second Yes")
        ui.expect(ui.on_menu(10.0), "the main menu did not come back after both Yes")
        _stats("solo")
        cleared = c.shot(ui.shoot("ResetStatsAfter"))
        caselog.step("Check every Solo score reads none / 0")
        ui.expect(ui.stats_are_default(cleared),
                  f"Solo did not read none / 0 after the reset (see {cleared})")
        c.note("both confirmations accepted; Solo reads none / 0")

    with caselog.case("ST-04") as c:
        if not ui.expect_screen("stats", timeout=1.0):
            _stats("solo")
        ui.expect(ui.leave_stats(), "Statistics back could not be tapped")
        fc.clear_ad("Statistics back", wait=3.0 if fc.is_online() else 0.0)
        caselog.step("Check the main menu is showing")
        ui.expect(ui.on_menu(6.0), "Statistics back did not return to the main menu")
        c.note("back on the main menu")

    caselog.raise_if_failed()
    print("PASS: Statistics opened and scrolled; Daily and Solo resets were declined, then "
          "confirmed twice and wiped only their own scores; Back returned to the menu")


if __name__ == "__main__":
    fc.main(run)
