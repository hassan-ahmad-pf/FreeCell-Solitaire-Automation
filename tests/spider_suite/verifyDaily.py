#!/usr/bin/env python3
"""FreeCell's Daily calendar, offline (FreeCell's own DY cases; Spider has no Daily).

DY-01  Daily opens the calendar from the main menu
DY-02  first visit: tip 1 "Tap on the Level Button…", the level button outlined
DY-03  tip 2 "Tap on any available date…", the dates outlined; a tap leaves
       the calendar with no tip
DY-04  this month: today orange, earlier days bright, later days dimmed
DY-05  the level button lists Standard and Relaxed Easy–Master, with the
       relaxed-rules note
DY-06  Standard Hard, Relaxed Easy (R badge) and Standard Medium each show
       on the button
DY-07  a later date does nothing
DY-11  the FAQ link under the calendar opens the FAQ on its Daily page;
       back returns to the calendar
DY-08  prod: today asks for internet; No keeps the calendar
       dev:  Daily plays offline — today (Standard Easy) deals a Daily game,
             Synthetic Win completes it, today gets the gold star
DY-09  prod: a past date asks for internet; Yes closes Daily onto the menu
       dev:  an unplayed past date deals and is completed the same way, it
             gets a star, and the monthly score popup lists both games'
             scores (Daily stats are checked in verifyDailyOnline)
DY-10  back returns to the main menu

The tips show on the first Daily visit after a fresh install only (QA's
reset alerts does not bring them back), so a rerun skips DY-02 and DY-03.

Run:  SPIDER_SUITE_BUILD=dev ./.venv/bin/python -u tests/spider_suite/verifyDaily.py
"""
from __future__ import annotations

import calendar
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

TIP_WAIT = 5.0
FIRST_VISIT = ("Daily was opened before on this install — the tips show on the first "
               "visit after a fresh install only")
OFFLINE_ALERT = "only when internet is available"
OFFLINE_LEVEL = ("standard", "easy")
LEVEL_PICKS = (("standard", "hard", "DailyLevelHard"),
               ("relaxed", "easy", "DailyLevelRelaxedEasy"),
               ("standard", "medium", "DailyLevelMedium"))


def _opened(timeout: float = 10.0) -> bool:
    """The calendar is up — or the first-visit tip card already covers it."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ui.is_on("daily_weekdays") or ui.daily_tip_up():
            return ui.is_on("daily_back") or ui.daily_tip_up()
        time.sleep(0.3)
    return False


def _tips() -> None:
    if not ui.wait_daily_tip(TIP_WAIT):
        caselog.skip("DY-02", FIRST_VISIT)
        caselog.skip("DY-03", FIRST_VISIT)
        return
    with caselog.case("DY-02") as c:
        ui.expect(ui.seen("daily_tip1", timeout=3.0),
                  "the first tip is not 'Tap on the Level Button to select your favorite level'")
        ring = daily.outline(ui.screen_rgb(), daily.TIP1_OUTLINE)
        ui.expect(ring >= daily.OUTLINE_MIN, f"the level button is not outlined ({ring} red px)")
        c.shot(ui.shoot("DailyTip1"))
        c.note("first visit: 'Tap on the Level Button to select your favorite level', "
               "the level button outlined")
    with caselog.case("DY-03") as c:
        helpers.wda_tap(ui.DAILY_TIP, settle=1.6)
        ui.expect(ui.seen("daily_tip2", timeout=4.0),
                  "the second tip is not 'Tap on any available date to play a game'")
        ring = daily.outline(ui.screen_rgb(), daily.TIP2_OUTLINE)
        ui.expect(ring >= daily.OUTLINE_MIN, f"the dates are not outlined ({ring} red px)")
        c.shot(ui.shoot("DailyTip2"))
        helpers.wda_tap(ui.DAILY_TIP, settle=1.6)
        ui.expect(not ui.wait_daily_tip(2.0), "a tip still covers the calendar after the second")
        ui.expect(daily.on_calendar(4.0), "the calendar is not showing after the tips")
        c.shot(ui.shoot("DailyAfterTips"))
        c.note("tip 2 'Tap on any available date to play a game' outlined the dates; "
               "a tap left the calendar with no tip")


def _month() -> None:
    now = daily.today()
    last = calendar.monthrange(now.year, now.month)[1]
    with caselog.case("DY-04") as c:
        bad = daily.check_month(ui.screen_rgb())
        shot = c.shot(ui.shoot("DailyMonth"))
        ui.expect(not bad, f"the calendar is not {now:%B} with today marked: {bad} (see {shot})")
        later = f", {now.day + 1}–{last} dimmed" if now.day < last else ""
        earlier = f", 1–{now.day - 1} bright" if now.day > 1 else ""
        c.note(f"{now:%B %Y}: the {now.day}th orange{earlier}{later}")


def _levels() -> None:
    with caselog.case("DY-05") as c:
        ui.expect(daily.open_levels(), "the level button did not open the level list "
                                       "(Standard and Relaxed, Easy to Master)")
        ui.expect(ui.is_on("daily_relaxed_note"), "the relaxed-rules note is not beside the list")
        c.shot(ui.shoot("DailyLevels"))
        c.note("Standard Easy–Master and Relaxed Easy–Master listed, with the relaxed-rules note")
    with caselog.case("DY-06") as c:
        for rules, level, name in LEVEL_PICKS:
            ui.expect(daily.pick_level(rules, level),
                      f"choosing {rules.title()} {level.title()} did not show on the level button")
            c.shot(ui.shoot(name))
        c.note("Standard Hard read 'Hard', Relaxed Easy 'Easy' with the R badge, "
               "Standard Medium 'Medium'")


def _future() -> None:
    now = daily.today()
    if now.day == calendar.monthrange(now.year, now.month)[1]:
        caselog.skip("DY-07", "today is the last day of the month — there is no later date")
        return
    with caselog.case("DY-07") as c:
        before = ui.shoot("DailyBeforeFutureTap")
        daily.tap_date(now.day + 1, settle=2.5)
        ui.expect(not helpers.alert_text(), "tapping a later date raised an alert")
        ui.expect(daily.on_calendar(3.0), "tapping a later date left the calendar")
        after = c.shot(ui.shoot("DailyFutureTapped"))
        changed = fc.diff_frac(before, after, box=daily.CALENDAR_BOX)
        ui.expect(changed < 0.01, f"the calendar changed after tapping a later date "
                                  f"({changed:.1%}, see {after})")
        c.note(f"tapping the {now.day + 1}th did nothing")


def _faq() -> None:
    with caselog.case("DY-11") as c:
        if not ui.tap("daily_faq_link", settle=2.0):
            helpers.wda_tap(daily.FAQ_LINK, settle=2.0)
        ui.expect(ui.seen("faq_daily_heading", timeout=6.0),
                  "the FAQ link did not open the FAQ on its Daily page")
        c.shot(ui.shoot("DailyFAQ"))
        ui.back()
        ui.expect(daily.on_calendar(6.0), "FAQ back did not return to the calendar")
        c.note("the FAQ opened on 'What are Daily games?'; back returned to the calendar")


def _offline_prod() -> None:
    now = daily.today()
    with caselog.case("DY-08") as c:
        daily.tap_date(now.day)
        text = fc.wait_alert(OFFLINE_ALERT, 8.0)
        ui.expect(text, "tapping today offline raised no 'Daily Games can be initiated only "
                        "when Internet is available' alert")
        buttons = helpers.alert_buttons()
        ui.expect({"No", "Yes"} <= set(buttons), f"the alert offers {buttons}, not No and Yes")
        c.shot(ui.shoot("DailyOfflineAlert"))
        ui.expect(helpers.answer_alert("No"), "could not answer No")
        ui.expect(daily.on_calendar(5.0), "No did not keep the calendar")
        c.note("offline, today asked for internet; No kept the calendar")
    with caselog.case("DY-09") as c:
        day = now.day - 1 if now.day > 1 else now.day
        daily.tap_date(day)
        ui.expect(fc.wait_alert(OFFLINE_ALERT, 8.0),
                  f"tapping the {day}th offline raised no internet alert")
        c.shot(ui.shoot("DailyOfflineAlertPast"))
        ui.expect(helpers.answer_alert("Yes"), "could not answer Yes")
        ui.expect(ui.on_menu(6.0), "Yes did not close Daily onto the main menu")
        ui.expect(not ui.at_table(timeout=1.0), "Yes dealt a game")
        c.note(f"offline, the {day}th asked for internet; Yes closed Daily onto the main menu")
    daily.open_calendar()


def _unplayed_past(img) -> int | None:
    """The latest earlier date with no star yet on this level's calendar."""
    for day in range(daily.today().day - 1, 0, -1):
        if not daily.star_on(img, day)[0]:
            return day
    return None


def _play_offline(day: int, where: str, gold: bool, c) -> int:
    daily.tap_date(day)
    up, is_gold = daily.on_daily_table(12.0)
    if not up and OFFLINE_ALERT in helpers.alert_text().lower():
        ui.expect(False, f"offline, the {day}th asked for internet — the dev build deals "
                         "Daily games offline")
    ui.expect(up, f"tapping the {day}th offline did not deal a Daily game")
    ui.expect(is_gold == gold, f"the {where} table's header star is "
                               f"{'gold' if is_gold else 'plain'}, expected "
                               f"{'gold' if gold else 'plain'}")
    c.shot(ui.shoot(f"DailyOffline{where.title().replace(' ', '')}Table"))
    score = daily.win_to_victory(f"offline {where}")
    c.shot(ui.shoot(f"DailyOffline{where.title().replace(' ', '')}Victory"))
    daily.back_to_calendar(f"offline {where}")
    return score


def _offline_dev() -> None:
    now = daily.today()
    level = " ".join(OFFLINE_LEVEL)
    shown = level.title()
    played: list[tuple[int, int, bool]] = []
    with caselog.case("DY-08") as c:
        ui.expect(daily.pick_level(*OFFLINE_LEVEL), f"could not switch the calendar to {shown}")
        replay = daily.star_on(ui.screen_rgb(), now.day)[0]
        score = _play_offline(now.day, "today", True, c)
        star, gold = daily.star_on(ui.screen_rgb(), now.day)
        shot = c.shot(ui.shoot("DailyOfflineTodayStar"))
        ui.expect(star and gold, f"today has no gold star after the win (see {shot})")
        played.append((now.day, score, replay))
        c.note(f"offline on the dev build, today ({shown}) dealt a Daily game; Synthetic Win "
               f"completed it ({score:,}) and today shows the gold star"
               + (" (today was already won on this level earlier)" if replay else ""))
    past = _unplayed_past(ui.screen_rgb())
    if past is None:
        caselog.skip("DY-09", f"every earlier date this month is already played on {shown}"
                     if now.day > 1 else "today is the 1st — there is no earlier date")
    else:
        with caselog.case("DY-09") as c:
            score = _play_offline(past, "past date", False, c)
            star, _gold = daily.star_on(ui.screen_rgb(), past)
            shot = c.shot(ui.shoot("DailyOfflinePastStar"))
            ui.expect(star, f"the {past}th has no star after the win (see {shot})")
            played.append((past, score, False))
            summary = _popup(c, played, shot)
            c.note(f"offline on the dev build, the {past}th dealt a Daily game, Synthetic Win "
                   f"completed it ({score:,}) and it shows a star")
            c.note(f"score popup: {summary}")
    daily.save_wins(level, [score for _d, score, replay in played if not replay])
    ui.expect(daily.pick_level("standard", "medium"), "could not put the calendar back on "
                                                      "Standard Medium")


def _popup(c, played: list[tuple[int, int, bool]], calendar_shot: str) -> str:
    """Open the monthly score popup and check each played date's row against
    its Victory score; today's counts twice. A replay that scored lower is
    not counted, so its row keeps the earlier, higher score."""
    now = daily.today()
    monthly = daily.monthly_score(calendar_shot)
    top = daily.open_popup()
    ui.expect(top is not None, "tapping the monthly score did not open the score popup")
    shot = c.shot(ui.shoot("DailyScorePopup"))
    rows = daily.popup_scores(shot, top)
    for day, score, replay in played:
        row = rows.get(day)
        ui.expect(row, f"the popup lists no score for the {day}th (see {shot})")
        ui.expect(row[0] >= score if replay else row[0] == score,
                  f"the popup lists {row[0]:,} for the {day}th, Victory showed {score:,} "
                  f"(see {shot})")
        if day == now.day:
            ui.expect(2 * row[0] in row[1:], f"today's {row[0]:,} is not counted twice in the "
                                             f"popup (row reads {row}, see {shot})")
    if now.day < calendar.monthrange(now.year, now.month)[1]:
        ui.expect(now.day + 1 not in rows,
                  f"the popup lists a score for the {now.day + 1}th, a date not yet playable")
    summary = daily.check_popup(rows, monthly, shot)
    daily.close_popup()
    ui.expect(daily.on_calendar(4.0), "the score popup did not close back to the calendar")
    return summary


def run() -> None:
    fc.menu()
    if fc.dev_build():
        fc.ensure_qa()
    with caselog.case("DY-01") as c:
        ui.expect(ui.tap("menu_daily", settle=0.4), "Daily control not found on the menu")
        ui.expect(_opened(), "tapping Daily did not open the calendar")
        c.shot(ui.shoot("DailyCalendar"))
        c.note("Daily opened the calendar")
    _tips()
    _month()
    _levels()
    _future()
    _faq()
    if fc.dev_build():
        _offline_dev()
    else:
        _offline_prod()
    with caselog.case("DY-10") as c:
        daily.leave_calendar()
        c.note("back returned to the main menu")
    print("PASS: Daily calendar, tips, levels, FAQ and offline dates checked")


if __name__ == "__main__":
    fc.main(run)
