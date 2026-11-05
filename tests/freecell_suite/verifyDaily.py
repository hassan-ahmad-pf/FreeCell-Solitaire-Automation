#!/usr/bin/env python3
"""FreeCell's Daily mode (FreeCell's own DY cases).

Standard Medium is finished first: today and a past date at 15%–30%,
then today again at 90%–99% for Victory +N, that past date again at
00%–15% for No improvement, then table Replay / No score recorded.
Relaxed Easy is only after that: today and a past date at 90%–99%.

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
Standard Medium first at 15%–30% (today, then a past date). Then Medium
today at 90%–99%: Victory +N is that score minus the earlier 15–30.
Then the same past date at 00%–15%: Victory shows No improvement
(clone: DailyImprovement ≤ 0). Then today's table menu Replay: Yes
deals the same game again, and Victory shows Replay / No score recorded
(clone: markAsReplayed). Every Daily Victory also checks current / rank /
best for score, time and moves (DY-65–71). Relaxed Easy is last: today
and a past date at 90%–99% only. DY-10 back returns to the main menu
DY-14  Statistics → Daily totals those six wins (Medium 4, Easy 2)

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
import datetime
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import config  # noqa: E402
import daily  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402
import ocr  # noqa: E402

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
        caselog.step("Check the first tip 'Tap on the Level Button…' shows, with the level "
                     "button outlined in red")
        ui.expect(ui.seen("daily_tip1", timeout=3.0),
                  "the first tip is not 'Tap on the Level Button to select your favorite level'")
        ring = daily.outline(ui.screen_rgb(), daily.TIP1_OUTLINE)
        ui.expect(ring >= daily.OUTLINE_MIN, f"the level button is not outlined ({ring} red px)")
        c.shot(ui.shoot("DailyTip1"))
        caselog.step("Tap the tip card to dismiss it")
        helpers.wda_tap(ui.DAILY_TIP, settle=1.6)
        c.note("first visit: 'Tap on the Level Button to select your favorite level', "
               "the level button outlined; a tap dismissed it")
    with caselog.case("DY-03") as c:
        caselog.step("Check the second tip 'Tap on any available date…' shows, with the dates "
                     "outlined in red")
        ui.expect(ui.seen("daily_tip2", timeout=4.0),
                  "the second tip is not 'Tap on any available date to play a game'")
        ring = daily.outline(ui.screen_rgb(), daily.TIP2_OUTLINE)
        ui.expect(ring >= daily.OUTLINE_MIN, f"the dates are not outlined ({ring} red px)")
        c.shot(ui.shoot("DailyTip2"))
        caselog.step("Tap the tip card to dismiss it")
        helpers.wda_tap(ui.DAILY_TIP, settle=1.6)
        caselog.step("Check the calendar shows with no tip left over it")
        ui.expect(not ui.wait_daily_tip(2.0), "a tip still covers the calendar after the second")
        ui.expect(daily.on_calendar(4.0), "the calendar is not showing after the tips")
        c.shot(ui.shoot("DailyAfterTips"))
        c.note("'Tap on any available date to play a game' outlined the dates; a tap "
               "dismissed it and the calendar shows with no tip")


def _levels() -> tuple[str, str] | None:
    level = None
    with caselog.case("DY-05") as c:
        level = daily.level_shown(c.shot(ui.shoot("DailyCalendarLevel")))
        ui.expect(level, "could not read the level on the level button")
        ui.expect(daily.open_levels(), "the level button did not open the level list "
                                       "(Standard and Relaxed, Easy to Master)")
        caselog.step("Check the list shows Standard and Relaxed, Easy to Master, with the "
                     "relaxed-rules note")
        ui.expect(ui.is_on("daily_relaxed_note"), "the relaxed-rules note is not beside the list")
        c.shot(ui.shoot("DailyLevels"))
        ui.expect(daily.close_levels(), "a tap beside the level list did not close it")
        after = daily.level_shown(c.shot(ui.shoot("DailyLevelsClosed")))
        caselog.step("Check the level did not change")
        ui.expect(after == level, f"closing the list changed the level from "
                                  f"{' '.join(level).title()} to {' '.join(after or ()).title()}")
        c.note(f"the level button ({' '.join(level).title()}) opened Standard and Relaxed "
               "Easy–Master; a tap beside the list closed it with the level unchanged")
    return level


def _rules_line(level: tuple[str, str]) -> str:
    return f"{level[1]} level • {level[0]} rules"


def _choose(want: tuple[str, str], cid: str, tag: str) -> tuple[str, str]:
    """Open the list and put *want* on the level button."""
    name = " ".join(want).title()
    with caselog.case(cid) as c:
        daily.ensure_calendar()
        shown = daily.level_shown(ui.shoot(f"Daily{tag}LevelBefore"))
        if shown != want:
            ui.expect(daily.open_levels(),
                      f"the level button did not open the level list to pick {name}")
            c.shot(ui.shoot(f"Daily{tag}LevelsPick"))
            caselog.step(f"Tap {want[1].title()} under {want[0].title()}")
            ui.expect(daily.pick_level(*want),
                      f"{want[1].title()} under {want[0].title()} could not be tapped")
        after = None
        path = ""
        for attempt in range(5):
            if attempt:
                time.sleep(0.7)
            path = ui.shoot(f"Daily{tag}Level")
            after = daily.level_shown(path)
            if after == want:
                break
        c.shot(path)
        caselog.step(f"Check the level button reads {name}")
        ui.expect(after == want, f"the level button reads "
                                 f"{' '.join(after or ()).title()}, not {name}")
        c.note(f"the level button reads {name}")
    return want


def _future() -> None:
    now = daily.today()
    if now.day == calendar.monthrange(now.year, now.month)[1]:
        caselog.skip("DY-07", "today is the last day of the month — there is no later date")
        return
    with caselog.case("DY-07") as c:
        before = ui.shoot("DailyBeforeFutureTap")
        daily.tap_date(now.day + 1, settle=2.5)
        caselog.step("Check nothing happens: no alert, and the calendar is unchanged")
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
            caselog.step("Tap the FAQ link on the calendar")
            helpers.wda_tap(daily.FAQ_LINK, settle=2.0)
        caselog.step("Check the FAQ opened on its Daily page")
        ui.expect(ui.seen("faq_daily_heading", timeout=6.0),
                  "the FAQ link did not open the FAQ on its Daily page")
        c.shot(ui.shoot("DailyFAQ"))
        ui.back()
        caselog.step("Check the calendar is showing again")
        ui.expect(daily.on_calendar(6.0), "FAQ back did not return to the calendar")
        c.note("the FAQ opened on 'What are Daily games?'; back returned to the calendar")


def _deal(day: int, name: str, level: tuple[str, str], c,
          when: datetime.date | None = None) -> tuple[str, bool, str]:
    """Tap *day*, check the Daily table, and play one card up to its
    foundation: the timer must start and the score count. Also True when an
    unfinished Daily game had to be abandoned first (it counts as played)."""
    daily.ensure_calendar()
    daily.tap_date(day, when=when)
    abandoned = ui.wait_prompt("abandon", timeout=2.0) and ui.answer_prompt("abandon")
    if abandoned:
        c.note("an unfinished Daily game from an earlier run was abandoned first")
    caselog.step("Check a Daily game is dealt")
    up, _live_gold = daily.on_daily_table(12.0)
    ui.expect(up, f"tapping the {daily.nth(day)} did not deal a Daily game")
    fresh = c.shot(ui.shoot(f"Daily{name}Table"))
    footer = (fc.table_footer(fresh) or [""])[0]
    low = footer.lower()
    caselog.step(f"Check the line under the cards names the {level[1].title()} level and "
                 f"{level[0]} rules")
    ui.expect(level[1] in low, f"the table reads {footer!r}, not the "
                               f"{level[1]} level on the button (see {fresh})")
    ui.expect(level[0] in low, f"the table reads {footer!r}, not {level[0]} "
                               f"rules (see {fresh})")
    timer0, score0 = fc.hud(fresh)
    _before, _after, card = fc.play_to_foundation()
    caselog.wait(TIMER_RUN, "for the timer to run")
    moved, timer1, score1 = fc.hud_after_move(f"Daily{name}CardUp")
    c.shot(moved)
    caselog.step("Check the timer started and the score went up")
    ui.expect(timer1 is not None and timer1 > (timer0 or 0),
              f"the timer did not start: {fc.mmss(timer0)} before the move, "
              f"{fc.mmss(timer1)} after (see {moved})")
    ui.expect(score1 is not None and score1 > (score0 or 0),
              f"the score did not count {card} going up: {daily.fmt(score0 or 0)} before, "
              f"{daily.fmt(score1)} after (see {moved})")
    return (f"'{footer.strip(' •')}'; {card} tapped up to its foundation: timer "
            f"{fc.mmss(timer0)} → {fc.mmss(timer1)}, score {score0 or 0:,} → {score1:,}",
            abandoned, fresh)


def _check_board_star(shot: str, gold: bool, day: int, c) -> None:
    want = daily.star_color(gold)
    caselog.step(f"Check the gameboard header star is {want}")
    present, shown_gold = daily.header_star(shot)
    shown = daily.star_color(shown_gold) if present else "no"
    ui.expect(present and shown_gold == gold,
              f"the {daily.nth(day)}'s gameboard header has a {shown} star, "
              f"expected {want} (see {shot})")
    c.shot(shot)
    c.note(f"gameboard header star is {want}")


def _check_victory_table(shot: str, current: int | None, c) -> dict:
    """Victory current / rank / best for score, time and moves.

    Clone uiEndFrame.mm + CLASSIC gameImports.uxf. Daily has no run
    (REF_20161210a). Rank is yellow; a first best is "-".
    """
    table = daily.check_victory_table(shot, current_score=current, daily_farm=True)
    score = table["score"]
    c.shot(shot)
    c.note(f"current {score['current']:,}  rank {score['rank']}  best {score['best']}; "
           f"time {table['time']['current']}  moves {table['moves']['current']}")
    return table


def _check_victory_settings(shot: str, when: datetime.date, level: tuple[str, str], c) -> str:
    shown = daily.date_line(when)
    caselog.step(f"Check Victory under leaderboards names {shown} and {_rules_line(level)}")
    footer = daily.check_victory_settings(shot, when, level)
    c.shot(shot)
    c.note(f"Victory settings: {footer}")
    return footer


def _check_no_improvement(shot: str, previous: int | None, current: int | None, c) -> None:
    """Victory shows No improvement when this score is not a new best.

    Clone uiEndFrame.mm: DailyImprovement = latest − previous best; when
    that is not > 0 (and not a first win / Replay) the line is
    {noImprovement}. A 00–15 replay after 15–30 is the lower score.
    """
    if current and previous:
        ui.expect(current < previous,
                  f"the 00-15 score {current:,} was not lower than the earlier "
                  f"15-30 score {previous:,} (see {shot})")
    caselog.step("Check Victory shows No improvement under the score")
    plus = daily.victory_improvement(shot) if shot else None
    shown = f"+{plus:,}" if plus is not None else "no +N"
    ui.expect(plus is None,
              f"Victory shows {shown}, expected No improvement (see {shot})")
    ui.expect(shot and daily.victory_no_improvement(shot),
              f"Victory does not show No improvement (see {shot})")
    c.shot(shot)
    c.note("Victory shows No improvement"
           + (f" ({current:,} < earlier {previous:,})" if current and previous else ""))


def _check_improvement(shot: str, previous: int | None, current: int | None, c) -> None:
    """Victory +N is the 90–99 score minus the earlier 15–30 score.

    Clone faTrail.getLastScoreDeltaFromPreviousBest: latest − previous
    best for that date. uiEndFrame shows '+' + that delta on Daily
    timespan when it is > 0 and not equal to current points (first win
    is ✥ because delta == current).
    """
    table = daily.victory_table_delta(shot) if shot else None
    if current and previous:
        want = current - previous
        ui.expect(current > previous,
                  f"the 90-99 score {current:,} was not higher than the earlier "
                  f"15-30 score {previous:,} (see {shot})")
        caselog.step(f"Check Victory shows +{want:,} under the score "
                     f"({current:,} − the earlier {previous:,})")
    else:
        want = table
        caselog.step("Check Victory +N equals current − best on the same table")
    shown = daily.victory_improvement(shot) if shot else None
    if shown is None or not (shown == want or daily.score_same(shown, want)):
        if table is not None:
            shown = table
    ui.expect(want, f"could not get the expected +improvement (see {shot})")
    ui.expect(shown is not None,
              f"Victory does not show +improvement under the score "
              f"(expected +{want:,}, see {shot})")
    ui.expect(shown == want or daily.score_same(shown, want),
              f"Victory shows +{shown:,}, expected +{want:,} "
              f"(see {shot})")
    c.shot(shot)
    c.note(f"Victory improvement +{shown:,}"
           + (f" = {current:,} − {previous:,}" if current and previous else
              " = current − best on the Victory table"))


def _popup(c, played: list[tuple[datetime.date, int, bool]], calendar_shot: str,
           name: str) -> str:
    """Each played date's row carries its Victory score (a lower replay is
    not counted, so its row keeps the earlier, higher one); today's counts
    twice; the rows add up to the monthly score."""
    now = daily.today()
    daily.ensure_calendar()
    monthly = daily.monthly_score(calendar_shot)
    top = daily.open_popup()
    ui.expect(top is not None, "tapping the monthly score did not open the score popup")
    shot = c.shot(ui.shoot(name))
    rows = daily.popup_scores(shot, top)
    try:
        caselog.step("Check each won date shows its Victory score, today's counts twice, and the "
                     "rows add up to the monthly score")
        for when, score, replay in played:
            if (when.year, when.month) != (now.year, now.month):
                continue
            day = when.day
            row = rows.get(day)
            ui.expect(row, f"the popup lists no score for the {daily.nth(day)} (see {shot})")
            shown = ocr.pick(row, score)
            ui.expect(shown is not None, f"the popup lists no score for the {daily.nth(day)} (see {shot})")
            ui.expect(shown >= score if replay else daily.score_same(shown, score),
                      f"the popup lists {shown:,} for the {daily.nth(day)}, Victory showed {score:,} "
                      f"(see {shot})")
            if when == now:
                doubled = 2 * (score if daily.score_same(shown, score) else shown)
                ui.expect(doubled in row[1:] or 2 * shown in row[1:],
                          f"today's {shown:,} is not counted twice in the "
                          f"popup (row reads {row}, see {shot})")
        if now.day < calendar.monthrange(now.year, now.month)[1]:
            ui.expect(now.day + 1 not in rows,
                      f"the popup lists a score for the {daily.nth(now.day + 1)}, a date not yet "
                      "playable")
        return daily.check_popup(rows, monthly, shot)
    finally:
        daily.close_popup()
        daily.ensure_calendar()


def _back_calendar_star(day: int, name: str, gold: bool, when: datetime.date | None,
                        c) -> None:
    if daily.back_to_calendar(f"the {daily.nth(day)}"):
        c.note("back on the calendar, FreeCell's one-time tip 'Tap on the monthly score to "
               "see its breakdown' came up; a tap dismissed it")
    want = daily.star_color(gold)
    caselog.step(f"Check the {daily.nth(day)} has a {want} star on the calendar")
    star, is_gold = daily.star_on(ui.screen_rgb(), day, when)
    shot = c.shot(ui.shoot(f"Daily{name}Star"))
    shown = daily.star_color(is_gold) if star else "no"
    ui.expect(star and is_gold == gold,
              f"the {daily.nth(day)} has a {shown} star after the win, expected {want} "
              f"(see {shot})")


def _play_level(level: tuple[str, str], ids: dict[str, str],
                band: tuple[int, int] = (15, 30),
                past_band: tuple[int, int] | None = None,
                previous: dict[datetime.date, int] | None = None) -> tuple[
        list[tuple[datetime.date, int, bool]], int]:
    """One Daily level: today, a past date, that level's monthly popup.

    *band* is today's Synthetic Win range (15, 30) on the first pass,
    (90, 99) on the Standard Medium today replay. *past_band* is the past
    date's range when it differs — (0, 15) so Victory shows No
    improvement. *previous* maps each date to its earlier 15–30 score;
    those same dates are replayed instead of picking a new unplayed day.
    """
    tag = ids["tag"]
    lo, hi = band
    past_lo, past_hi = past_band or band
    now = daily.today()
    played: list[tuple[datetime.date, int, bool]] = []
    abandoned = 0
    table = ""
    score = 0
    victory = ""
    _choose(level, ids["choose"], tag)
    if ids.get("deal_today"):
        replay = daily.star_on(ui.screen_rgb(), now.day)[0]
        with caselog.case(ids["deal_today"]) as c:
            dealt, gave_up, table = _deal(now.day, f"{tag}Today", level, c)
            abandoned += gave_up
            c.note(f"today ({' '.join(level).title()}) dealt a Daily table: {dealt}")
        with caselog.case(ids["board_today"]) as c:
            ui.expect(table, "no Daily table — today's deal did not finish")
            _check_board_star(table, True, now.day, c)
        with caselog.case(ids["victory_today"]) as c:
            ui.expect(table, "no Daily table — today's deal did not finish")
            score = daily.win_to_victory(f"{tag} today {now.day}", started=True, band=band)
            victory = c.shot(ui.shoot(f"Daily{tag}TodayVictory"))
            _check_victory_settings(victory, now, level, c)
        if ids.get("table_today"):
            with caselog.case(ids["table_today"]) as c:
                shot = victory or str(config.LOG / f"Daily{tag}TodayVictory.png")
                ui.expect(shot and os.path.exists(shot),
                          "no Victory screen — today's win did not finish")
                _check_victory_table(shot, score or None, c)
        if ids.get("improve_today"):
            with caselog.case(ids["improve_today"]) as c:
                shot = victory or str(config.LOG / f"Daily{tag}TodayVictory.png")
                ui.expect(shot and os.path.exists(shot),
                          "no Victory screen — today's win did not finish")
                prev = (previous or {}).get(now)
                _check_improvement(shot, prev, score or None, c)
        with caselog.case(ids["win_today"]) as c:
            ui.expect(table, "no Daily table — today's deal did not finish")
            _back_calendar_star(now.day, f"{tag}Today", True, None, c)
            played.append((now, score, replay))
            c.note(f"Synthetic Win {lo}% - {hi}% ({score:,}); today has the yellow star"
                   + (" (today was already won on this level earlier)" if replay else ""))
    past_when = now
    past_date = None
    if previous is not None:
        past_date = next((when for when in previous if when != now), None)
        past = past_date.day if past_date else None
        past_when = past_date or now
    else:
        past = daily.unplayed_past(ui.screen_rgb())
        if past is None and now.day > 1:
            past = now.day - 1
    skip_past = (ids.get("play_past"), ids.get("board_past"),
                 ids.get("victory_past"), ids.get("table_past"),
                 ids.get("improve_past"), ids.get("no_improve_past"),
                 ids.get("win_past"))
    ran_past = False
    if past is None and (previous is not None or not daily.month_arrow(True)):
        reason = ("no earlier date to replay at 00-15" if previous is not None
                  else "today is the 1st and the calendar has no previous-month arrow")
        for cid in skip_past:
            if cid:
                caselog.skip(cid, reason)
        if ids.get("popup") and not ids.get("deal_today"):
            caselog.skip(ids["popup"], reason)
    else:
        if past is None:
            past_when = now - datetime.timedelta(days=1)
            past = past_when.day
            daily.show_month(past_when)
        elif past_when.month != now.month:
            daily.show_month(past_when)
        replay = daily.star_on(ui.screen_rgb(), past, past_when)[0]
        label = (daily.nth(past) if past_when.month == now.month
                 else f"{daily.nth(past)} of {past_when.strftime('%B')}")
        past_date = past_when.replace(day=past)
        table = ""
        victory = ""
        with caselog.case(ids["play_past"]) as c:
            dealt, gave_up, table = _deal(past, f"{tag}Past", level, c, when=past_when)
            abandoned += gave_up
            c.note(f"the {label} dealt a Daily table: {dealt}")
        with caselog.case(ids["board_past"]) as c:
            ui.expect(table, "no Daily table — the past date's deal did not finish")
            _check_board_star(table, False, past, c)
        with caselog.case(ids["victory_past"]) as c:
            ui.expect(table, "no Daily table — the past date's deal did not finish")
            score = daily.win_to_victory(f"{tag} past {past}", started=True,
                                         band=(past_lo, past_hi))
            victory = c.shot(ui.shoot(f"Daily{tag}PastVictory"))
            _check_victory_settings(victory, past_date, level, c)
        if ids.get("table_past"):
            with caselog.case(ids["table_past"]) as c:
                shot = victory or str(config.LOG / f"Daily{tag}PastVictory.png")
                ui.expect(shot and os.path.exists(shot),
                          "no Victory screen — the past date's win did not finish")
                _check_victory_table(shot, score or None, c)
        if ids.get("improve_past"):
            with caselog.case(ids["improve_past"]) as c:
                shot = victory or str(config.LOG / f"Daily{tag}PastVictory.png")
                ui.expect(shot and os.path.exists(shot),
                          "no Victory screen — the past date's win did not finish")
                prev = (previous or {}).get(past_date) if past_date else None
                _check_improvement(shot, prev, score or None, c)
        if ids.get("no_improve_past"):
            with caselog.case(ids["no_improve_past"]) as c:
                shot = victory or str(config.LOG / f"Daily{tag}PastVictory.png")
                ui.expect(shot and os.path.exists(shot),
                          "no Victory screen — the past date's win did not finish")
                prev = (previous or {}).get(past_date) if past_date else None
                _check_no_improvement(shot, prev, score or None, c)
        with caselog.case(ids["win_past"]) as c:
            ui.expect(table, "no Daily table — the past date's deal did not finish")
            _back_calendar_star(past, f"{tag}Past", False, past_when, c)
            played.append((past_date, score, replay))
            if past_when.month != now.month:
                daily.show_month(now)
            c.note(f"Synthetic Win {past_lo}% - {past_hi}% ({score:,}); the {label} has a silver star"
                   + (" (already won on this level earlier)" if replay else ""))
        ran_past = True
    if ids.get("popup") and (ids.get("deal_today") or ran_past):
        with caselog.case(ids["popup"]) as c:
            c.note("score popup: " + _popup(c, played, ui.shoot(f"Daily{tag}CalendarAfterWins"),
                                            f"Daily{tag}ScorePopup"))
    return played, abandoned


def _clean_stats() -> str:
    """Daily statistics at 0 / none before Daily opens, so DY-14 can ask for
    exactly this run's games; earlier games are reset away first.
    A stats-only rerun leaves the first run's games in place."""
    only = caselog.rerun_ids()
    # Only a deal/win case rebuilds the games. A rerun of +N / popup / stats
    # must keep the first run's Daily scores — resetting them was wiping the
    # data those cases read, then SkipThisCase aborted the rest.
    deal = ("deal_today", "win_today", "play_past", "win_past")
    play = {ids[key] for ids in (STANDARD, RELAXED, IMPROVE) for key in deal
            if key in ids}
    if only is not None and not (only & play):
        return "Daily statistics kept from the first run (this rerun only checks them)"
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


def _stats(start: str, runs: list[tuple[tuple[str, str],
                                        list[tuple[datetime.date, int, bool]], int]]) -> None:
    """From 0 / none, the totals and each level played show exactly this
    run's games — an abandoned leftover counts as played, not won; every
    other level on screen stays none."""
    words = {"best": "best score", "played": "games played", "won": "games won"}
    with caselog.case("DY-14") as c:
        c.note(start)
        after, shot = daily.read_stats(
            "DailyStatsAfter",
            until=(("standard", "medium"), ("relaxed", "easy")),
        )
        c.shot(shot)
        caselog.step("Check the Daily totals, Standard Medium, and Relaxed Easy each count "
                     "exactly this run's games, and every other level reads none")
        all_played = [hand for _level, played, _a in runs for hand in played]
        abandoned = sum(a for _level, _p, a in runs)
        wins = len(all_played)
        totals = {"best": max((score for _d, score, _r in all_played), default=None),
                  "played": wins + abandoned, "won": wins}
        games = f"{wins} wins" + (f" and {abandoned} abandoned" if abandoned else "")
        ui.expect(set(words) <= set(after[daily.TOTALS]),
                  f"could not find the Daily totals' lines (see {shot})")
        watched = {daily.TOTALS}
        watched_named = {("totals", None)}
        for key, label, want in (
            [(daily.TOTALS, "Daily", totals)]
            + [(daily.stats_section(*level), " ".join(level).title(),
                {"best": max((score for _d, score, _r in played), default=None),
                 "played": len(played) + gave_up, "won": len(played)})
               for level, played, gave_up in runs]
        ):
            section = daily.stats_named(after, key) if key != daily.TOTALS else after[daily.TOTALS]
            watched.add(key)
            ui.expect(section, f"{label} is not on the Daily statistics page (see {shot})")
            for field in words:
                value = section.get(field)
                expect = want[field]
                if field in ("played", "won"):
                    value, expect = value or 0, expect or 0
                ui.expect(value == expect or (field == "best" and value and expect
                                              and daily.score_same(value, expect)),
                          f"{label} {words[field]} reads {daily.fmt(value)},"
                          f" expected {daily.fmt(expect)} after {games} "
                          f"(see {shot})")
            c.note(f"{label}: " + ", ".join(f"{words[f]} {daily.fmt(section.get(f))}"
                                             for f in words))
            if key != daily.TOTALS:
                watched_named.add((
                    "relaxed" if "Relaxed" in label else "standard",
                    label.split()[-1].lower(),
                ))
        others = [s for i, s in enumerate(after)
                  if i not in watched
                  and (s.get("rules"), s.get("level")) not in watched_named]
        ui.expect(all(s["best"] is None and not s.get("won") for s in others),
                  f"a level not played this run shows a score (see {shot})")
        if others:
            c.note("the other levels on screen read none")


STANDARD = {
    "tag": "SM",
    "choose": "DY-22",
    "deal_today": "DY-12",
    "board_today": "DY-24",
    "victory_today": "DY-26",
    "table_today": "DY-65",
    "win_today": "DY-13",
    "play_past": "DY-15",
    "board_past": "DY-28",
    "victory_past": "DY-29",
    "table_past": "DY-66",
    "win_past": "DY-43",
    "popup": "DY-16",
}
RELAXED = {
    "tag": "RE",
    "choose": "DY-17",
    "deal_today": "DY-23",
    "board_today": "DY-18",
    "victory_today": "DY-19",
    "table_today": "DY-69",
    "win_today": "DY-25",
    "play_past": "DY-27",
    "board_past": "DY-20",
    "victory_past": "DY-21",
    "table_past": "DY-70",
    "win_past": "DY-40",
    "popup": "DY-41",
}
IMPROVE = {
    "tag": "SMHigh",
    "choose": "DY-44",
    "deal_today": "DY-45",
    "board_today": "DY-46",
    "victory_today": "DY-47",
    "table_today": "DY-67",
    "improve_today": "DY-48",
    "win_today": "DY-49",
    "play_past": "DY-50",
    "board_past": "DY-51",
    "victory_past": "DY-52",
    "table_past": "DY-68",
    "no_improve_past": "DY-53",
    "win_past": "DY-54",
    "popup": "DY-55",
}
TABLE_REPLAY = {
    "ask": "DY-56",
    "banner": "DY-57",
    "table": "DY-71",
}


def _table_replay() -> None:
    """Table menu Replay of the same Daily deal — not a calendar-date replay.

    Clone cmdReplayGame: an unfinished Daily game asks first
    (replayGame-message-noRun); Yes marks the match Replayed / DoNotRecord.
    Victory then shows Replay / No score recorded (uiEndFrame extra.replay).
    Zero moves before Replay so the unfinished game is not stored as
    abandoned (addScoreInternal skips a 0-move match).
    """
    now = daily.today()
    daily.ensure_calendar()
    with caselog.case(TABLE_REPLAY["ask"]) as c:
        daily.tap_date(now.day)
        if ui.wait_prompt("abandon", timeout=2.0) and ui.answer_prompt("abandon"):
            c.note("an unfinished Daily game from an earlier run was abandoned first")
            daily.tap_date(now.day)
        up, _gold = daily.on_daily_table(12.0)
        ui.expect(up, "tapping today did not deal a Daily game for table Replay")
        c.shot(ui.shoot("DailyTableReplayDealt"))
        caselog.step("Open the table menu and tap replay")
        ui.expect(ui.open_table_drawer(), "the table menu did not open")
        c.shot(ui.shoot("DailyTableReplayDrawer"))
        ui.expect(ui.tap("drawer_replay", settle=1.0), "replay is not on the table menu")
        caselog.step("Check FreeCell asks to play this game again, and that the "
                     "replay will not be recorded")
        ui.expect(ui.wait_prompt("replay", timeout=6.0),
                  "replay did not ask 'Are you sure you want to play this game again?'")
        alert = helpers.alert_text()
        c.shot(ui.shoot("DailyTableReplayAsk"))
        low = alert.lower()
        ui.expect("play this game again" in low, f"the alert reads {alert!r}")
        ui.expect("not be recorded" in low,
                  f"the alert does not say the replay score is not recorded: {alert!r}")
        ui.expect(ui.answer_prompt("replay", "Yes"), "Yes did not confirm replay")
        up, _gold = daily.on_daily_table(12.0)
        ui.expect(up, "Replay Yes did not deal the same Daily game again")
        c.shot(ui.shoot("DailyTableReplayAgain"))
        c.note("table Replay Yes: same Daily game dealt again; the alert said "
               "the replay is not recorded")
    score = 0
    victory = ""
    with caselog.case(TABLE_REPLAY["banner"]) as c:
        score = daily.win_to_victory("table Replay", started=True, band=(90, 99))
        victory = c.shot(ui.shoot("DailyTableReplayVictory"))
        caselog.step("Check Victory shows Replay / No score recorded")
        daily.check_replay_banner(victory)
        ui.expect(daily.victory_improvement(victory) is None,
                  f"Victory shows +improvement on a table Replay "
                  f"(clone: Replayed suppresses +N, see {victory})")
        c.note(f"Victory shows Replay / No score recorded "
               f"(Synthetic Win {score:,} was not recorded)")
    with caselog.case(TABLE_REPLAY["table"]) as c:
        shot = victory or str(config.LOG / "DailyTableReplayVictory.png")
        ui.expect(shot and os.path.exists(shot),
                  "no Victory screen — table Replay did not finish")
        _check_victory_table(shot, score or None, c)
    daily.back_to_calendar("table Replay")


def run() -> None:
    dev = fc.dev_build()
    fc.menu()
    if dev:
        fc.ensure_qa()
        start = _clean_stats()
    with caselog.case("DY-01") as c:
        ui.expect(ui.tap("menu_daily", settle=0.4), "Daily control not found on the menu")
        caselog.step("Check the Daily calendar opened")
        ui.expect(_opened(), "tapping Daily did not open the calendar")
        c.shot(ui.shoot("DailyCalendar"))
        c.note("Daily opened the calendar")
    _tips()
    _levels()
    _future()
    _faq()
    runs: list[tuple[tuple[str, str], list[tuple[datetime.date, int, bool]], int]] = []
    if dev:
        medium, medium_abandoned = _play_level(("standard", "medium"), STANDARD,
                                               band=(15, 30))
        lows = {when: score for when, score, _r in medium}
        high, high_abandoned = _play_level(("standard", "medium"), IMPROVE,
                                           band=(90, 99), past_band=(0, 15),
                                           previous=lows)
        runs.append((("standard", "medium"), medium + high,
                     medium_abandoned + high_abandoned))
        _table_replay()
        easy, easy_abandoned = _play_level(("relaxed", "easy"), RELAXED,
                                           band=(90, 99))
        runs.append((("relaxed", "easy"), easy, easy_abandoned))
    with caselog.case("DY-10") as c:
        daily.leave_calendar()
        caselog.step("Check the main menu is showing")
        ui.expect(ui.on_menu(6.0), "Daily back did not return to the main menu")
        c.shot(ui.shoot("DailyBack"))
        c.note("back returned to the main menu")
    if dev:
        _stats(start, runs)
    n = sum(len(played) for _level, played, _a in runs)
    print("PASS: Daily opened, tips and level list checked"
          + (f", {n} Daily games played (Medium 15-30 / +N / No improvement, "
             f"then Easy 90-99)" if dev else ""))


if __name__ == "__main__":
    fc.main(run)
