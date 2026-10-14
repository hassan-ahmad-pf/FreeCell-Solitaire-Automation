#!/usr/bin/env python3
"""FreeCell's Daily mode (FreeCell's own DY cases; Spider has no Daily).

Plays whatever level the level button shows; nothing is switched.

DY-01  Daily opens the calendar from the main menu
DY-02  first visit: tip 1 "Tap on the Level Button…" is dismissed
DY-03  tip 2 "Tap on any available date…" is dismissed; no tip is left
DY-05  the level button opens the level list; a tap beside it closes the
       list and the level stays
DY-07  a later date does nothing
DY-11  the FAQ link opens the FAQ on its Daily page; back returns
dev build — Daily plays offline there, and the wins come from Synthetic Win:
DY-12  today deals a Daily table for the level shown; a card tapped up to
       its foundation starts the timer and the score counts
DY-13  Synthetic Win, back to the calendar: today has the gold star
DY-15  an unplayed past date the same way; it gets a star
DY-16  the monthly score popup lists both games' Victory scores (today's
       x2) and they add up to the monthly score
DY-10  back returns to the main menu
DY-14  Statistics → Daily counts both wins and their best score

The tips show on the first Daily visit after a fresh install only (QA's
reset alerts does not bring them back), so a rerun skips DY-02 and DY-03.
A rerun also finds today already won: a replay that scores lower is not
counted, so the popup then shows at least the new score.

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
TIMER_RUN = 2.0


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
        helpers.wda_tap(ui.DAILY_TIP, settle=1.6)
        c.note("first visit: 'Tap on the Level Button to select your favorite level', "
               "the level button outlined; a tap dismissed it")
    with caselog.case("DY-03") as c:
        ui.expect(ui.seen("daily_tip2", timeout=4.0),
                  "the second tip is not 'Tap on any available date to play a game'")
        ring = daily.outline(ui.screen_rgb(), daily.TIP2_OUTLINE)
        ui.expect(ring >= daily.OUTLINE_MIN, f"the dates are not outlined ({ring} red px)")
        c.shot(ui.shoot("DailyTip2"))
        helpers.wda_tap(ui.DAILY_TIP, settle=1.6)
        ui.expect(not ui.wait_daily_tip(2.0), "a tip still covers the calendar after the second")
        ui.expect(daily.on_calendar(4.0), "the calendar is not showing after the tips")
        c.shot(ui.shoot("DailyAfterTips"))
        c.note("'Tap on any available date to play a game' outlined the dates; a tap "
               "dismissed it and the calendar shows with no tip")


def _levels() -> tuple[str, str]:
    with caselog.case("DY-05") as c:
        level = daily.level_shown(c.shot(ui.shoot("DailyCalendarLevel")))
        ui.expect(level, "could not read the level on the level button")
        ui.expect(daily.open_levels(), "the level button did not open the level list "
                                       "(Standard and Relaxed, Easy to Master)")
        ui.expect(ui.is_on("daily_relaxed_note"), "the relaxed-rules note is not beside the list")
        c.shot(ui.shoot("DailyLevels"))
        ui.expect(daily.close_levels(), "a tap beside the level list did not close it")
        after = daily.level_shown(c.shot(ui.shoot("DailyLevelsClosed")))
        ui.expect(after == level, f"closing the list changed the level from "
                                  f"{' '.join(level).title()} to {' '.join(after or ()).title()}")
        c.note(f"the level button ({' '.join(level).title()}) opened Standard and Relaxed "
               "Easy–Master; a tap beside the list closed it with the level unchanged")
    return level


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


def _deal(day: int, name: str, gold: bool, level: tuple[str, str], c) -> str:
    """Tap *day*, check the Daily table, and play one card up to its
    foundation: the timer must start and the score count."""
    daily.tap_date(day)
    up, is_gold = daily.on_daily_table(12.0)
    ui.expect(up, f"tapping the {day}th did not deal a Daily game")
    ui.expect(is_gold == gold, f"the {day}th's table has a {'gold' if is_gold else 'plain'} "
                               f"header star, expected {'gold' if gold else 'plain'}")
    fresh = c.shot(ui.shoot(f"Daily{name}Table"))
    footer = daily.table_footer(fresh)
    ui.expect(level[1] in footer.lower(), f"the table reads {footer!r}, not the "
                                          f"{level[1]} level on the button (see {fresh})")
    timer0, score0 = daily.hud(fresh)
    _before, _after, card = fc.play_to_foundation()
    time.sleep(TIMER_RUN)
    moved = c.shot(ui.shoot(f"Daily{name}CardUp"))
    timer1, score1 = daily.hud(moved)
    ui.expect(timer1 is not None and timer1 > (timer0 or 0),
              f"the timer did not start: {daily.mmss(timer0)} before the move, "
              f"{daily.mmss(timer1)} after (see {moved})")
    ui.expect(score1 is not None and score1 > (score0 or 0),
              f"the score did not count {card} going up: {daily.fmt(score0 or 0)} before, "
              f"{daily.fmt(score1)} after (see {moved})")
    return (f"'{footer.strip(' •')}'; {card} tapped up to its foundation: timer "
            f"{daily.mmss(timer0)} → {daily.mmss(timer1)}, score {score0 or 0:,} → {score1:,}")


def _win(day: int, name: str, c) -> int:
    score = daily.win_to_victory(f"{name.lower()} {day}", started=True)
    c.shot(ui.shoot(f"Daily{name}Victory"))
    daily.back_to_calendar(f"the {day}th")
    return score


def _popup(c, played: list[tuple[int, int, bool]], calendar_shot: str) -> str:
    """Each played date's row carries its Victory score (a lower replay is
    not counted, so its row keeps the earlier, higher one); today's counts
    twice; the rows add up to the monthly score."""
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


def _play(level: tuple[str, str]) -> list[tuple[int, int, bool]]:
    """DY-12, DY-13, DY-15 and DY-16 on the dev build."""
    now = daily.today()
    played: list[tuple[int, int, bool]] = []
    replay = daily.star_on(ui.screen_rgb(), now.day)[0]
    with caselog.case("DY-12") as c:
        c.note(f"today ({' '.join(level).title()}) dealt a Daily table: "
               + _deal(now.day, "Today", True, level, c))
    with caselog.case("DY-13") as c:
        score = _win(now.day, "Today", c)
        star, gold = daily.star_on(ui.screen_rgb(), now.day)
        shot = c.shot(ui.shoot("DailyTodayStar"))
        ui.expect(star and gold, f"today has no gold star after the win (see {shot})")
        played.append((now.day, score, replay))
        c.note(f"Synthetic Win ({score:,}); back on the calendar today has the gold star"
               + (" (today was already won on this level earlier)" if replay else ""))
    past = daily.unplayed_past(ui.screen_rgb())
    if past is None and now.day > 1:
        past = now.day - 1
    if past is None:
        caselog.skip("DY-15", "today is the 1st — there is no earlier date")
    else:
        replay = daily.star_on(ui.screen_rgb(), past)[0]
        with caselog.case("DY-15") as c:
            dealt = _deal(past, "Past", False, level, c)
            score = _win(past, "Past", c)
            star, _gold = daily.star_on(ui.screen_rgb(), past)
            shot = c.shot(ui.shoot("DailyPastStar"))
            ui.expect(star, f"the {past}th has no star after the win (see {shot})")
            played.append((past, score, replay))
            c.note(f"the {past}th dealt a Daily table: {dealt}")
            c.note(f"Synthetic Win ({score:,}); the {past}th has a star"
                   + (" (already won on this level earlier)" if replay else ""))
    with caselog.case("DY-16") as c:
        c.note("score popup: " + _popup(c, played, ui.shoot("DailyCalendarAfterWins")))
    return played


def _stats(before: list[dict], played: list[tuple[int, int, bool]],
           level: tuple[str, str]) -> None:
    with caselog.case("DY-14") as c:
        after, shot = daily.read_stats("DailyStatsAfter")
        c.shot(shot)
        wins, scores = len(played), [score for _d, score, _r in played]
        index = daily.stats_section(*level)
        checks = [(daily.TOTALS, "Daily")]
        if index < min(len(before), len(after)):
            checks.append((index, " ".join(level).title()))
        for key, name in checks:
            was, now_won = before[key]["won"] or 0, after[key]["won"]
            ui.expect(now_won == was + wins, f"{name} games won reads {daily.fmt(now_won)}, "
                                             f"expected {was + wins} after {wins} wins "
                                             f"(see {shot})")
            best = max([before[key]["best"] or 0] + scores)
            ui.expect(after[key]["best"] == best,
                      f"{name} best score reads {daily.fmt(after[key]['best'])}, expected "
                      f"{best:,} (see {shot})")
            c.note(f"{name}: games won {was} → {now_won}, best score {best:,}")


def run() -> None:
    dev = fc.dev_build()
    fc.menu()
    if dev:
        fc.ensure_qa()
        before, _shot = daily.read_stats("DailyStatsBefore")
    with caselog.case("DY-01") as c:
        ui.expect(ui.tap("menu_daily", settle=0.4), "Daily control not found on the menu")
        ui.expect(_opened(), "tapping Daily did not open the calendar")
        c.shot(ui.shoot("DailyCalendar"))
        c.note("Daily opened the calendar")
    _tips()
    level = _levels()
    _future()
    _faq()
    played = _play(level) if dev else []
    with caselog.case("DY-10") as c:
        daily.leave_calendar()
        c.note("back returned to the main menu")
    if dev:
        _stats(before, played, level)
    print("PASS: Daily opened, tips and level list checked"
          + (f", {len(played)} Daily games played, scored and counted" if dev else ""))


if __name__ == "__main__":
    fc.main(run)
