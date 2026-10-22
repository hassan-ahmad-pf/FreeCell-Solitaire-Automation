#!/usr/bin/env python3
"""FreeCell's Daily mode (FreeCell's own DY cases).

Plays whatever level the level button shows; nothing is switched.

DY-01  Daily opens the calendar from the main menu
DY-02  first visit: tip 1 "Tap on the Level Button…" is dismissed
DY-03  tip 2 "Tap on any available date…" is dismissed; no tip is left
DY-05  the level button opens the level list; a tap beside it closes the
       list and the level stays
DY-07  a later date does nothing
DY-11  the FAQ link opens the FAQ on its Daily page; back returns
dev build — Daily plays offline there, and the wins come from Synthetic Win.
Before Daily opens, Statistics → Daily must read 0 / none; if earlier games
show, Reset Daily Statistics clears them first.
DY-12  today deals a Daily table for the level shown; a card tapped up to
       its foundation starts the timer and the score counts
DY-13  Synthetic Win, back to the calendar: today has the gold star
DY-15  an unplayed past date the same way; it gets a star
DY-16  the monthly score popup lists both games' Victory scores (today's
       x2) and they add up to the monthly score
DY-10  back returns to the main menu
DY-14  Statistics → Daily shows exactly those games: played and won 2, best
       score the higher Victory score, in the totals and the level played

An unfinished Daily game left by an earlier failed run makes FreeCell ask
to abandon it when a date is tapped: it is abandoned, and counts as played.
After a past date is won, FreeCell shows the tip "Tap on the monthly score
to see its breakdown" once (after a fresh install); it is dismissed.

The tips show on the first Daily visit after a fresh install only (QA's
reset alerts does not bring them back), so a rerun skips DY-02 and DY-03.
Reset Daily Statistics leaves the calendar alone, so a rerun also finds
today already won: a replay that scores lower is not counted, and the
popup then shows at least the new score.

Run:  FREECELL_SUITE_BUILD=dev ./.venv/bin/python -u tests/freecell_suite/verifyDaily.py
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
        if daily.weekdays_on() or ui.daily_tip_up():
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
        c.note(f"tapping the {daily.nth(now.day + 1)} did nothing")


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


def _deal(day: int, name: str, gold: bool, level: tuple[str, str], c) -> tuple[str, bool]:
    """Tap *day*, check the Daily table, and play one card up to its
    foundation: the timer must start and the score count. Also True when an
    unfinished Daily game had to be abandoned first (it counts as played)."""
    daily.tap_date(day)
    abandoned = ui.wait_prompt("abandon", timeout=2.0) and ui.answer_prompt("abandon")
    if abandoned:
        c.note("an unfinished Daily game from an earlier run was abandoned first")
    up, is_gold = daily.on_daily_table(12.0)
    ui.expect(up, f"tapping the {daily.nth(day)} did not deal a Daily game")
    ui.expect(is_gold == gold, f"the {daily.nth(day)}'s table has a "
                               f"{'gold' if is_gold else 'plain'} header star, expected "
                               f"{'gold' if gold else 'plain'}")
    fresh = c.shot(ui.shoot(f"Daily{name}Table"))
    footer = (fc.table_footer(fresh) or [""])[0]
    ui.expect(level[1] in footer.lower(), f"the table reads {footer!r}, not the "
                                          f"{level[1]} level on the button (see {fresh})")
    timer0, score0 = fc.hud(fresh)
    _before, _after, card = fc.play_to_foundation()
    time.sleep(TIMER_RUN)
    moved, timer1, score1 = fc.hud_after_move(f"Daily{name}CardUp")
    c.shot(moved)
    ui.expect(timer1 is not None and timer1 > (timer0 or 0),
              f"the timer did not start: {fc.mmss(timer0)} before the move, "
              f"{fc.mmss(timer1)} after (see {moved})")
    ui.expect(score1 is not None and score1 > (score0 or 0),
              f"the score did not count {card} going up: {daily.fmt(score0 or 0)} before, "
              f"{daily.fmt(score1)} after (see {moved})")
    return (f"'{footer.strip(' •')}'; {card} tapped up to its foundation: timer "
            f"{fc.mmss(timer0)} → {fc.mmss(timer1)}, score {score0 or 0:,} → {score1:,}",
            abandoned)


def _win(day: int, name: str, c) -> int:
    score = daily.win_to_victory(f"{name.lower()} {day}", started=True)
    c.shot(ui.shoot(f"Daily{name}Victory"))
    if daily.back_to_calendar(f"the {daily.nth(day)}"):
        c.note("back on the calendar, FreeCell's one-time tip 'Tap on the monthly score to "
               "see its breakdown' came up; a tap dismissed it")
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
        ui.expect(row, f"the popup lists no score for the {daily.nth(day)} (see {shot})")
        ui.expect(row[0] >= score if replay else row[0] == score,
                  f"the popup lists {row[0]:,} for the {daily.nth(day)}, Victory showed {score:,} "
                  f"(see {shot})")
        if day == now.day:
            ui.expect(2 * row[0] in row[1:], f"today's {row[0]:,} is not counted twice in the "
                                             f"popup (row reads {row}, see {shot})")
    if now.day < calendar.monthrange(now.year, now.month)[1]:
        ui.expect(now.day + 1 not in rows,
                  f"the popup lists a score for the {daily.nth(now.day + 1)}, a date not yet "
                  "playable")
    summary = daily.check_popup(rows, monthly, shot)
    daily.close_popup()
    ui.expect(daily.on_calendar(4.0), "the score popup did not close back to the calendar")
    return summary


def _play(level: tuple[str, str]) -> tuple[list[tuple[int, int, bool]], int]:
    """DY-12, DY-13, DY-15 and DY-16 on the dev build: the games won, and
    how many unfinished ones were abandoned on the way."""
    now = daily.today()
    played: list[tuple[int, int, bool]] = []
    abandoned = 0
    replay = daily.star_on(ui.screen_rgb(), now.day)[0]
    with caselog.case("DY-12") as c:
        dealt, gave_up = _deal(now.day, "Today", True, level, c)
        abandoned += gave_up
        c.note(f"today ({' '.join(level).title()}) dealt a Daily table: {dealt}")
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
            dealt, gave_up = _deal(past, "Past", False, level, c)
            abandoned += gave_up
            score = _win(past, "Past", c)
            star, _gold = daily.star_on(ui.screen_rgb(), past)
            shot = c.shot(ui.shoot("DailyPastStar"))
            ui.expect(star, f"the {daily.nth(past)} has no star after the win (see {shot})")
            played.append((past, score, replay))
            c.note(f"the {daily.nth(past)} dealt a Daily table: {dealt}")
            c.note(f"Synthetic Win ({score:,}); the {daily.nth(past)} has a star"
                   + (" (already won on this level earlier)" if replay else ""))
    with caselog.case("DY-16") as c:
        c.note("score popup: " + _popup(c, played, ui.shoot("DailyCalendarAfterWins")))
    return played, abandoned


def _clean_stats() -> str:
    """Daily statistics at 0 / none before Daily opens, so DY-14 can ask for
    exactly this run's games; earlier games are reset away first."""
    before, shot = daily.read_stats("DailyStatsBefore")
    if daily.stats_empty(before):
        return "Daily statistics read 0 / none before the run"
    was = daily.stats_summary(before)
    daily.reset_stats()
    cleared, shot = daily.read_stats("DailyStatsCleared")
    ui.expect(daily.stats_empty(cleared), "Reset Daily Statistics did not bring Daily to 0 / none "
                                          f"before the run ({daily.stats_summary(cleared)}, "
                                          f"see {shot})")
    return f"Daily statistics were reset to 0 / none before the run (they read {was})"


def _stats(start: str, played: list[tuple[int, int, bool]], level: tuple[str, str],
           abandoned: int = 0) -> None:
    """From 0 / none, the totals and the level played show exactly this
    run's games — an abandoned leftover counts as played, not won; every
    other level on screen stays none."""
    words = {"best": "best score", "played": "games played", "won": "games won"}
    with caselog.case("DY-14") as c:
        c.note(start)
        after, shot = daily.read_stats("DailyStatsAfter")
        c.shot(shot)
        wins = len(played)
        want = {"best": max(score for _d, score, _r in played), "played": wins + abandoned,
                "won": wins}
        games = f"{wins} wins" + (f" and {abandoned} abandoned" if abandoned else "")
        index = daily.stats_section(*level)
        name = " ".join(level).title()
        ui.expect(set(words) <= set(after[daily.TOTALS]),
                  f"could not find the Daily totals' lines (see {shot})")
        for key, label in ((daily.TOTALS, "Daily"), (index, name)):
            if key >= len(after):
                c.note(f"{label} is below the screen; the totals cover it")
                continue
            for field, value in after[key].items():
                ui.expect(value == want[field], f"{label} {words[field]} reads {daily.fmt(value)},"
                                                f" expected {want[field]:,} after {games} "
                                                f"(see {shot})")
            c.note(f"{label}: " + ", ".join(f"{words[f]} {daily.fmt(v)}"
                                             for f, v in after[key].items()))
        others = [s for key, s in enumerate(after) if key not in (daily.TOTALS, index)]
        ui.expect(all(s["best"] is None and not s.get("won") for s in others),
                  f"a level not played this run shows a score (see {shot})")
        if others:
            c.note("the other levels on screen read none")


def run() -> None:
    dev = fc.dev_build()
    fc.menu()
    if dev:
        fc.ensure_qa()
        start = _clean_stats()
    with caselog.case("DY-01") as c:
        ui.expect(ui.tap("menu_daily", settle=0.4), "Daily control not found on the menu")
        ui.expect(_opened(), "tapping Daily did not open the calendar")
        c.shot(ui.shoot("DailyCalendar"))
        c.note("Daily opened the calendar")
    _tips()
    level = _levels()
    _future()
    _faq()
    played, abandoned = _play(level) if dev else ([], 0)
    with caselog.case("DY-10") as c:
        daily.leave_calendar()
        c.note("back returned to the main menu")
    if dev:
        _stats(start, played, level, abandoned)
    print("PASS: Daily opened, tips and level list checked"
          + (f", {len(played)} Daily games played, scored and counted" if dev else ""))


if __name__ == "__main__":
    fc.main(run)
