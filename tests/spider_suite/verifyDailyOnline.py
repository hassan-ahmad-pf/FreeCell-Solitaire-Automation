#!/usr/bin/env python3
"""FreeCell's Daily game online, dev build (FreeCell's own DY cases; Spider has no Daily).

DY-12  online, today on Standard Medium deals a Daily table: a gold star in
       the header (Solo shows "new") and "medium level standard rules"
DY-13  Synthetic Win completes it; back on the calendar today has the gold
       star, and the monthly score popup lists Victory's score, counted twice
DY-14  Statistics → Daily after the win: games won up by one (in total and
       on Standard Medium), best scores take the win, and Standard Easy
       holds verifyDaily's offline wins

Today on Standard Medium is unplayed on a fresh install: verifyDaily plays
its offline games on Standard Easy, and each level keeps its own calendar.
A rerun on the same day finds today already won; a lower replay is not
counted, so the popup then shows at least the new score.

Run:  SPIDER_SUITE_BUILD=dev ./.venv/bin/python -u tests/spider_suite/verifyDailyOnline.py
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


def _stats(name: str) -> tuple[list[dict], str]:
    daily.open_daily_stats()
    shot = ui.shoot(name)
    ui.leave_stats()
    fc.clear_ad("Statistics back", wait=3.0)
    ui.expect(ui.on_menu(6.0) or ui.to_menu(), "Statistics back did not return to the menu")
    sections = daily.daily_stats(shot)
    ui.expect(len(sections) > daily.STANDARD_MEDIUM,
              f"could not read the Daily statistics (see {shot})")
    return sections, shot


def _fmt(value) -> str:
    return "none" if value is None else f"{value:,}"


def run() -> None:
    fc.go_online()
    fc.menu()
    fc.ensure_qa()
    before, _shot = _stats("DailyStatsBefore")
    daily.open_calendar()
    ui.expect(daily.pick_level("standard", "medium"),
              "could not switch the calendar to Standard Medium")
    now = daily.today()
    replay = daily.star_on(ui.screen_rgb(), now.day)[0]

    with caselog.case("DY-12") as c:
        daily.tap_date(now.day)
        fc.clear_ad("today's Daily deal", wait=fc.LATE_AD)
        up, gold = daily.on_daily_table(15.0)
        ui.expect(up, "tapping today did not deal a Daily game")
        ui.expect(gold, "today's Daily table has no gold star in its header")
        ui.expect(ui.is_on("daily_table_medium"),
                  "the table does not read 'medium level standard rules'")
        c.shot(ui.shoot("DailyTodayTable"))
        c.note("online, today dealt a Daily table: gold star in the header, "
               "'medium level standard rules'")

    with caselog.case("DY-13") as c:
        score = daily.win_to_victory("online today")
        c.shot(ui.shoot("DailyTodayVictory"))
        daily.back_to_calendar("online today")
        star, gold = daily.star_on(ui.screen_rgb(), now.day)
        shot = c.shot(ui.shoot("DailyTodayGoldStar"))
        ui.expect(star and gold, f"today has no gold star on the calendar after the win "
                                 f"(see {shot})")
        monthly = daily.monthly_score(shot)
        top = daily.open_popup()
        ui.expect(top is not None, "tapping the monthly score did not open the score popup")
        shot = c.shot(ui.shoot("DailyTodayScorePopup"))
        rows = daily.popup_scores(shot, top)
        row = rows.get(now.day)
        ui.expect(row, f"the score popup lists no score for today (see {shot})")
        ui.expect(row[0] >= score if replay else row[0] == score,
                  f"the popup lists {row[0]:,} for today, Victory showed {score:,} (see {shot})")
        ui.expect(2 * row[0] in row[1:], f"today's {row[0]:,} is not counted twice in the popup "
                                         f"(row reads {row}, see {shot})")
        summary = daily.check_popup(rows, monthly, shot)
        daily.close_popup()
        ui.expect(daily.on_calendar(4.0), "the score popup did not close back to the calendar")
        c.note(f"Synthetic Win completed today's game ({score:,}); today shows the gold star"
               + (" (today was already won on Standard Medium earlier)" if replay else ""))
        c.note(f"score popup: {summary}")
    daily.leave_calendar()

    with caselog.case("DY-14") as c:
        after, shot = _stats("DailyStatsAfter")
        c.shot(shot)
        for key, name in ((daily.TOTALS, "Daily"), (daily.STANDARD_MEDIUM, "Standard Medium")):
            was, now_won = before[key]["won"] or 0, after[key]["won"]
            ui.expect(now_won == was + 1, f"{name} games won reads {_fmt(now_won)}, expected "
                                          f"{was + 1} after the win (see {shot})")
            best = max(before[key]["best"] or 0, score)
            ui.expect(after[key]["best"] == best,
                      f"{name} best score reads {_fmt(after[key]['best'])}, expected {best:,} "
                      f"(see {shot})")
            c.note(f"{name}: games won {was} → {now_won}, best score {after[key]['best']:,}")
        wins = daily.load_wins()
        if wins.get("level") == "standard easy" and wins.get("scores"):
            easy = after[daily.STANDARD_EASY]
            top_win = max(wins["scores"])
            ui.expect((easy["best"] or 0) >= top_win,
                      f"Standard Easy best score reads {_fmt(easy['best'])}, below the offline "
                      f"win's {top_win:,} (see {shot})")
            ui.expect((easy["won"] or 0) >= len(wins["scores"]),
                      f"Standard Easy games won reads {_fmt(easy['won'])}, fewer than the "
                      f"{len(wins['scores'])} offline wins (see {shot})")
            c.note(f"Standard Easy (verifyDaily's offline wins "
                   f"{', '.join(f'{s:,}' for s in wins['scores'])}): games won {easy['won']}, "
                   f"best score {_fmt(easy['best'])}")
    print("PASS: today's Daily dealt online, won, starred and counted in Daily stats")


if __name__ == "__main__":
    fc.main(run)
