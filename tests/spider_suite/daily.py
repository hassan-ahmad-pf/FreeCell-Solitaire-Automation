"""FreeCell's Daily mode, shared by verifyDaily and resetDailyStats.

The calendar, its tips, the table HUD, the score popup and the statistics
are drawn images with nothing in the accessibility tree, so screens are
told apart by pixels and templates (measured on the 1290x2796 iPhone) and
words and numbers are read with macOS Vision (ocr.py).
"""
from __future__ import annotations

import datetime
import re
import time

import fc
import freecell_ui as ui
import helpers
import ocr

LEVEL_BUTTON = (1000, 310)
LEVEL_TEXT = (850, 240, 1200, 380)
LEVEL_WORDS = ("easy", "medium", "hard", "expert", "master")
LEVELS_ASIDE = (200, 1000)  # left of the level list: closes it, level unchanged
SCORE_BOX = (645, 697)
MONTHLY_BOX = (330, 600, 960, 760)  # "Tap on any date…" until a game is won
FAQ_LINK = (645, 2177)
ROW_STEP = 125
CALENDAR_BOX = (60, 1300, 1230, 1920)

# Tip outlines: red dashes round the level button (tip 1) or the dates (tip 2).
TIP1_OUTLINE = (650, 225, 1280, 380)
TIP2_OUTLINE = (70, 1180, 1220, 1950)
OUTLINE_MIN = 3000

# The table header's centre: "new" on Solo, a star on Daily (gold for today).
HEADER_STAR = (560, 290, 730, 400)
HEADER_STAR_MATCH = 0.80  # Daily ~1.0, Solo's "new" ~0.49
STAR_MATCH = 0.80
GOLD_SHARE = 0.5

# Table: "• medium level standard rules •" under the board; the HUD below
# it shows the score, then the timer and multiplier ("0:00 X158"). The HUD
# drops 132 px once the "tap to undo / lower / hints" captions go.
TABLE_FOOTER = (200, 1760, 1090, 1860)
HUD_BAND = (380, 2080, 900, 2480)
TIMER = re.compile(r"(\d+):(\d{2})")
SCORE_ONLY = re.compile(r"[\d,.\u201a ]+")

# Score popup: rows 1..31 under the month name, "15: ★ 47,739x2 = 95,478"
# for a played date and a dash otherwise. The monthly score box and the
# calendar show dimmed through it; their text is taller or dimmer than a row's.
POPUP_ROW1 = 29          # row 1's centre below the daily_popup_days match top
POPUP_ROW_STEP = 44.2
POPUP_SCORE_X = (450, 960)  # past the "15:" label
POPUP_LINE_MAX = 60
POPUP_BRIGHT = 40

# Statistics: the Daily tab label is white once selected. Below the totals
# come one section per level, Standard Easy…Master then Relaxed Easy…Master.
STATS_DAILY_LABEL = (850, 350, 1050, 415)
STATS_TAB_WHITE = 1500
STATS_BOX = (0, 450, 1290, 2400)
STATS_LINE = 35  # half a Statistics line's height, for re-reading one line
TOTALS = 0

QA_DAILY_WIN = (686, 1746)
VICTORY_BACK = (140, 347)


# ── calendar ───────────────────────────────────────────────────────

def on_calendar(timeout: float = 8.0) -> bool:
    return ui.seen("daily_weekdays", timeout=timeout) and ui.is_on("daily_back")


def open_calendar() -> None:
    ui.expect(ui.tap("menu_daily", settle=1.0), "Daily control not found on the menu")
    fc.clear_ad("Daily open", wait=2.0 if fc.is_online() else 0.0)
    ui.expect(on_calendar(10.0), "tapping Daily did not open the calendar")


def leave_calendar() -> None:
    ui.expect(ui.tap("daily_back", settle=1.6), "the calendar's back control was not found")
    fc.clear_ad("Daily back", wait=3.0 if fc.is_online() else 0.0)
    ui.expect(ui.on_menu(6.0), "Daily back did not return to the main menu")


def today() -> datetime.date:
    return datetime.date.today()


def cell(day: int, when: datetime.date | None = None) -> tuple[int, int]:
    """Centre (px) of *day* in the current month's grid (Sunday first)."""
    when = when or today()
    first = (when.replace(day=1).weekday() + 1) % 7
    i = first + day - 1
    return ui.DAILY_COLUMNS[i % 7], ui.DAILY_FIRST_ROW + ROW_STEP * (i // 7)


def tap_date(day: int, settle: float = 0.6) -> None:
    helpers.wda_tap(cell(day), settle=settle)


def _star_mask_match(img, box, name: str = "daily_gold_star") -> float:
    """Star shape (any colour) inside *box*: ink-mask match of template *name*."""
    import cv2
    import numpy as np

    star = cv2.imread(str(ui.asset(name)), cv2.IMREAD_COLOR)
    pin = ((star.max(axis=2) > 200).astype(np.uint8)) * 255
    x0, y0, x1, y1 = box
    hay = ((img[y0:y1, x0:x1].max(axis=2) > 200).astype(np.uint8)) * 255
    return float(cv2.matchTemplate(hay, pin, cv2.TM_CCOEFF_NORMED).max())


def _gold(img, box) -> bool:
    x0, y0, x1, y1 = box
    patch = img[y0:y1, x0:x1].astype(int)
    ink = patch.max(axis=2) > 200
    gold = ink & (patch[:, :, 2] < 140)
    return bool(ink.sum()) and gold.sum() / ink.sum() > GOLD_SHARE


def star_on(img, day: int) -> tuple[bool, bool]:
    """(a star sits on *day*, it is gold). The star sits above the date's centre."""
    x, y = cell(day)
    box = (x - 75, y - 85, x + 75, y + 35)
    if _star_mask_match(img, box) < STAR_MATCH:
        return False, False
    return True, _gold(img, box)


def unplayed_past(img) -> int | None:
    """The latest earlier date with no star yet on this level's calendar."""
    for day in range(today().day - 1, 0, -1):
        if not star_on(img, day)[0]:
            return day
    return None


def outline(img, box) -> int:
    x0, y0, x1, y1 = box
    p = img[y0:y1, x0:x1].astype(int)
    return int(((p[:, :, 0] > 200) & (p[:, :, 1] < 80) & (p[:, :, 2] < 80)).sum())


# ── level button ───────────────────────────────────────────────────

def level_shown(shot: str) -> tuple[str, str] | None:
    """(rules, level) the level button reads, e.g. ("standard", "medium");
    Relaxed levels carry an R badge after the word."""
    text = " ".join(line.text for line in ocr.read(shot, box=LEVEL_TEXT))
    words = re.findall(r"[A-Za-z®]+", text)
    level = next((w.lower() for w in words if w.lower() in LEVEL_WORDS), None)
    if not level:
        return None
    return ("relaxed" if any(w in ("R", "®") for w in words) else "standard"), level


def open_levels() -> bool:
    helpers.wda_tap(LEVEL_BUTTON, settle=1.6)
    return ui.seen("daily_levels", timeout=4.0)


def close_levels() -> bool:
    helpers.wda_tap(LEVELS_ASIDE, settle=1.4)
    return not ui.is_on("daily_levels")


def stats_section(rules: str, level: str) -> int:
    """Index of *rules* *level* among the Daily tab's sections (0 is the totals)."""
    return LEVEL_WORDS.index(level) + 1 + (len(LEVEL_WORDS) if rules == "relaxed" else 0)


# ── Daily table and win ────────────────────────────────────────────

def on_daily_table(timeout: float = 10.0) -> tuple[bool, bool]:
    """(a Daily table is up — star in the header, not Solo's "new"; star is gold)."""
    deadline = time.time() + timeout
    while True:
        if ui.at_table(timeout=1.0):
            img = ui.screen_rgb()
            if _star_mask_match(img, HEADER_STAR, "daily_table_star") >= HEADER_STAR_MATCH:
                return True, _gold(img, HEADER_STAR)
        if time.time() > deadline:
            return False, False
        time.sleep(0.5)


def table_footer(shot: str) -> str:
    return " ".join(line.text for line in ocr.read(shot, box=TABLE_FOOTER))


def hud(shot: str) -> tuple[int | None, int | None]:
    """(timer in seconds, score) under the board. A lone "0" score is too
    small for Vision, so None stands for 0 before anything is scored."""
    timer = score = None
    for _y, text in ocr.rows(ocr.read(shot, box=HUD_BAND)):
        match = TIMER.search(text)
        if match:
            timer = int(match.group(1)) * 60 + int(match.group(2))
        elif score is None and SCORE_ONLY.fullmatch(text.strip()):
            found = ocr.numbers(text)
            score = found[0] if found else None
    return timer, score


def mmss(seconds: int | None) -> str:
    return "?" if seconds is None else f"{seconds // 60}:{seconds % 60:02d}"


def synthetic_win(started: bool = False) -> bool:
    """Synthetic Win on a Daily table. Its QA card keeps WIN grey until a
    range is picked, and sits a little higher than Solo's."""
    if not started:
        ui.start_deal()
    if not ui.open_qa_panel():
        return False
    helpers.wda_tap(ui.QA_SELECT_90_99, settle=1.0)
    helpers.wda_tap(ui.find("qa_win") or QA_DAILY_WIN, settle=0.2)
    return True


def victory_score() -> int | None:
    found = [n for line in ocr.read(ui.victory_score_crop()) for n in ocr.numbers(line.text)]
    return found[0] if found else None


def win_to_victory(where: str, started: bool = False) -> int:
    """Win the Daily table on screen; return the score Victory shows."""
    ui.expect(synthetic_win(started), f"Synthetic Win could not be fired on the {where} "
                                      "Daily table")
    fc.clear_ad(f"{where} win", wait=fc.LATE_AD if fc.is_online() else 3.0)
    ui.expect(ui.expect_screen("victory", timeout=10.0),
              f"the {where} Daily win did not reach Victory")
    score = victory_score()
    ui.expect(score, f"the {where} Victory score could not be read")
    return score


def back_to_calendar(where: str) -> None:
    """Daily Victory's back returns to the calendar (Solo's goes to the menu)."""
    if not ui.tap("page_back", settle=1.6):
        helpers.wda_tap(VICTORY_BACK, settle=1.6)
    fc.clear_ad(f"{where} Victory back", wait=fc.LATE_AD if fc.is_online() else 2.0)
    ui.expect(on_calendar(10.0), f"Victory's back did not return to the calendar ({where})")


# ── score popup ────────────────────────────────────────────────────

def open_popup() -> int | None:
    """Tap the monthly score; the y (px) of the popup's first row, or None."""
    helpers.wda_tap(SCORE_BOX, settle=1.6)
    deadline = time.time() + 4.0
    while time.time() < deadline:
        top = _popup_top(ui.screen_rgb())
        if top is not None:
            return top
        time.sleep(0.4)
    return None


def _popup_top(img) -> int | None:
    import cv2

    needle = cv2.imread(str(ui.asset("daily_popup_days")), cv2.IMREAD_COLOR)
    hay = cv2.cvtColor(img.astype("uint8"), cv2.COLOR_RGB2BGR)
    result = cv2.matchTemplate(hay, needle, cv2.TM_CCOEFF_NORMED)
    _, score, _, top_left = cv2.minMaxLoc(result)
    return int(top_left[1]) if score >= ui.THRESHOLD else None


def popup_scores(shot: str, top: int) -> dict[int, list[int]]:
    """Numbers on each date's row of the score popup in *shot*, left to right:
    [score, total] for a past date, [score, 2, total] for today's (x2)."""
    import numpy as np
    from PIL import Image

    img = np.asarray(Image.open(shot).convert("RGB")).astype(int)
    box = (POPUP_SCORE_X[0], top, POPUP_SCORE_X[1], int(top + POPUP_ROW1 + 31 * POPUP_ROW_STEP))
    rows: dict[int, list] = {}
    for line in ocr.read(shot, box=box):
        patch = img[line.y0:line.y1, line.x0:line.x1]
        if line.y1 - line.y0 > POPUP_LINE_MAX or int((patch.max(axis=2) > 220).sum()) < POPUP_BRIGHT:
            continue
        day = round((line.cy - top - POPUP_ROW1) / POPUP_ROW_STEP) + 1
        if 1 <= day <= 31:
            rows.setdefault(day, []).append(line)
    return {day: [n for ln in sorted(lines, key=lambda ln: ln.x0) for n in ocr.numbers(ln.text)]
            for day, lines in rows.items()}


def monthly_score(shot: str) -> int | None:
    """The monthly score box on the calendar in *shot*."""
    found = [n for line in ocr.read(shot, box=MONTHLY_BOX) for n in ocr.numbers(line.text)]
    return found[0] if found else None


def check_popup(rows: dict[int, list[int]], monthly: int | None, shot: str) -> str:
    """The calendar's monthly score is the popup's date totals added up, plus
    a bonus only once every available date has been played."""
    ui.expect(monthly, "could not read the monthly score on the calendar")
    total = sum(row[-1] for row in rows.values())
    every_date = len(rows) >= today().day
    ui.expect(monthly == total or (every_date and monthly > total),
              f"the monthly score {monthly:,} is not the popup's dates added up ({total:,}, "
              f"see {shot})")
    return "; ".join(f"{day}th {format_row(rows[day])}" for day in sorted(rows)) + \
        f" — monthly score {monthly:,}"


def format_row(row: list[int]) -> str:
    if len(row) == 3 and row[1] == 2:
        return f"{row[0]:,} x2 = {row[2]:,}"
    return f"{row[0]:,}"


def close_popup() -> None:
    helpers.wda_tap((645, 1500), settle=1.4)


# ── statistics ─────────────────────────────────────────────────────

def open_daily_stats() -> None:
    ui.expect(ui.open_stats(), "Statistics did not open from the menu")
    fc.clear_ad("Statistics", wait=2.0 if fc.is_online() else 0.0)
    for _ in range(3):
        time.sleep(1.0)
        helpers.wda_tap(ui.STATS_DAILY_TAB, settle=1.4)
        if daily_tab_on(ui.screen_rgb()):
            return
    ui.expect(False, "the Daily tab of Statistics could not be selected")


def daily_tab_on(img) -> bool:
    x0, y0, x1, y1 = STATS_DAILY_LABEL
    return int((img[y0:y1, x0:x1].min(axis=2) > 220).sum()) >= STATS_TAB_WHITE


def _stat_value(text: str) -> int | None:
    tail = text.partition(":")[2].strip()
    found = ocr.numbers("0" if tail in ("O", "o") else tail)  # this font's 0 reads as O
    return found[0] if found else None


def _stat_line(shot: str, cy: float) -> int | None:
    """The value on one Statistics line, read from a crop of that line alone:
    in a full-page read Vision now and then turns a lone digit into "~"."""
    lines = ocr.read(shot, box=(STATS_BOX[0], int(cy) - STATS_LINE, STATS_BOX[2],
                                int(cy) + STATS_LINE))
    return _stat_value(" ".join(ln.text for ln in sorted(lines, key=lambda ln: ln.x0)))


def stats_sections(shot: str) -> list[dict]:
    """A Statistics tab in *shot*, one dict per section (TOTALS first, then
    each level on screen) with "best", "played" and "won"; None where blank."""
    sections: list[dict] = []
    for cy, text in ocr.rows(ocr.read(shot, box=STATS_BOX)):
        low = text.lower()
        value = _stat_value(text)
        if (value is None and low.startswith(("best score", "games played", "games won"))
                and "none" not in low):
            value = _stat_line(shot, cy)
        if low.startswith("best score"):
            sections.append({"best": value, "played": None, "won": None})
        elif sections and low.startswith("games played"):
            sections[-1]["played"] = value
        elif sections and low.startswith("games won"):
            sections[-1]["won"] = value
    return sections


def read_stats(name: str, tab: str = "daily") -> tuple[list[dict], str]:
    """Open Statistics from the menu on *tab*, read it, and go back to the menu."""
    if tab == "daily":
        open_daily_stats()
    else:
        ui.expect(ui.open_stats(), "Statistics did not open from the menu")
        ui.open_stats_tab(tab)
        time.sleep(1.0)
    shot = ui.shoot(name)
    ui.leave_stats()
    fc.clear_ad("Statistics back", wait=3.0 if fc.is_online() else 0.0)
    ui.expect(ui.on_menu(6.0) or ui.to_menu(), "Statistics back did not return to the menu")
    sections = stats_sections(shot)
    ui.expect(sections, f"could not read the {tab.title()} statistics (see {shot})")
    return sections, shot


def fmt(value) -> str:
    return "none" if value is None else f"{value:,}"
