"""FreeCell's Daily mode, shared by verifyDaily and verifyDailyOnline.

The calendar, its tips, the score popup and the Daily stats are drawn
images with nothing in the accessibility tree, so screens are told apart
by pixels and templates (measured on the 1290x2796 iPhone) and scores are
read with macOS Vision (ocr.py).

Each level keeps its own calendar. The offline wins (verifyDaily, dev
build) are played on Standard Easy so that today on Standard Medium is
still unplayed when verifyDailyOnline wins it; WINS_PATH carries the
offline wins' scores over to the Daily stats check.
"""
from __future__ import annotations

import calendar
import datetime
import json
import time

import config
import fc
import freecell_ui as ui
import helpers
import ocr

LEVEL_BUTTON = (1000, 310)
LEVELS = {
    ("standard", "easy"): (1080, 593), ("standard", "medium"): (1025, 713),
    ("standard", "hard"): (1074, 834), ("standard", "expert"): (1047, 954),
    ("standard", "master"): (1039, 1071),
    ("relaxed", "easy"): (1080, 1304), ("relaxed", "medium"): (1025, 1421),
    ("relaxed", "hard"): (1074, 1539), ("relaxed", "expert"): (1047, 1662),
    ("relaxed", "master"): (1039, 1779),
}
LEVEL_LABEL = {("standard", "easy"): "daily_level_easy",
               ("standard", "medium"): "daily_level_medium",
               ("standard", "hard"): "daily_level_hard",
               ("relaxed", "easy"): "daily_level_easy_r"}
SCORE_BOX = (645, 697)
MONTHLY_BOX = (330, 600, 960, 760)  # "Tap on any date…" until a game is won
FAQ_LINK = (645, 2177)
ROW_STEP = 125
CALENDAR_BOX = (60, 1300, 1230, 1920)

# Tip outlines: red dashes round the level button (tip 1) or the dates (tip 2).
TIP1_OUTLINE = (650, 225, 1280, 380)
TIP2_OUTLINE = (70, 1180, 1220, 1950)
OUTLINE_MIN = 3000

# Date cells: past days are drawn bright, today orange, later days dimmed.
CELL_HALF = (45, 35)
PAST_INK = 200
TODAY_ORANGE = 300
FUTURE_INK = 30

# The table header's centre: "new" on Solo, a star on Daily (gold for today).
HEADER_STAR = (560, 290, 730, 400)
HEADER_STAR_MATCH = 0.80  # Daily ~1.0, Solo's "new" ~0.49
STAR_MATCH = 0.80
GOLD_SHARE = 0.5

# Score popup: rows 1..31 under the month name, "15: ★ 47,739x2 = 95,478"
# for a played date and a dash otherwise. The monthly score box and the
# calendar show dimmed through it; their text is taller or dimmer than a row's.
POPUP_ROW1 = 29          # row 1's centre below the daily_popup_days match top
POPUP_ROW_STEP = 44.2
POPUP_SCORE_X = (450, 960)  # past the "15:" label
POPUP_LINE_MAX = 60
POPUP_BRIGHT = 40

# Statistics → Daily: the tab label is white once selected. Below the totals
# come one section per level, Standard Easy first.
STATS_DAILY_LABEL = (850, 350, 1050, 415)
STATS_TAB_WHITE = 1500
STATS_BOX = (0, 450, 1290, 2400)
TOTALS, STANDARD_EASY, STANDARD_MEDIUM = 0, 1, 2

QA_DAILY_WIN = (686, 1746)
VICTORY_BACK = (140, 347)
WINS_PATH = config.LOG / "daily_wins.json"


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


def _box(img, centre, half):
    x, y = centre
    return img[y - half[1]:y + half[1], x - half[0]:x + half[0]]


def date_state(img, day: int) -> str:
    """'today' (orange or a star), 'past' (bright) or 'future' (dimmed)."""
    patch = _box(img, cell(day), CELL_HALF).astype(int)
    r, b = patch[:, :, 0], patch[:, :, 2]
    if int(((r > 200) & (r - b > 90)).sum()) >= TODAY_ORANGE:
        return "today"
    bright = int((patch.max(axis=2) > 205).sum())
    if bright >= PAST_INK:
        return "past"
    return "future" if bright < FUTURE_INK else "unclear"


def month_states(img) -> dict[int, str]:
    days = calendar.monthrange(today().year, today().month)[1]
    return {d: date_state(img, d) for d in range(1, days + 1)}


def check_month(img) -> str:
    """'' when today is orange, earlier days bright and later days dimmed."""
    now = today().day
    bad = []
    for d, state in month_states(img).items():
        want = "today" if d == now else "past" if d < now else "future"
        if state != want:
            bad.append(f"{d} reads {state}, expected {want}")
    return "; ".join(bad)


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


def star_on(img, day: int) -> tuple[bool, bool]:
    """(a star sits on *day*, it is gold). The star sits above the date's centre."""
    x, y = cell(day)
    box = (x - 75, y - 85, x + 75, y + 35)
    if _star_mask_match(img, box) < STAR_MATCH:
        return False, False
    patch = img[box[1]:box[3], box[0]:box[2]].astype(int)
    ink = patch.max(axis=2) > 200
    gold = ink & (patch[:, :, 2] < 140)
    return True, bool(ink.sum()) and gold.sum() / ink.sum() > GOLD_SHARE


def outline(img, box) -> int:
    x0, y0, x1, y1 = box
    p = img[y0:y1, x0:x1].astype(int)
    return int(((p[:, :, 0] > 200) & (p[:, :, 1] < 80) & (p[:, :, 2] < 80)).sum())


# ── levels ─────────────────────────────────────────────────────────

def open_levels() -> bool:
    helpers.wda_tap(LEVEL_BUTTON, settle=1.6)
    return ui.seen("daily_levels", timeout=4.0)


def reads_level(rules: str, level: str) -> bool:
    """The level button (list closed: its items use the same lettering) reads
    *rules* *level*. "Easy" alone also matches inside Relaxed's "Easy R"."""
    if ui.is_on("daily_levels") or not ui.is_on(LEVEL_LABEL[(rules, level)]):
        return False
    return (rules, level) != ("standard", "easy") or not ui.is_on("daily_level_easy_r")


def pick_level(rules: str, level: str) -> bool:
    """Choose *rules* *level* and confirm the level button reads it."""
    if reads_level(rules, level):
        return True
    if not ui.is_on("daily_levels") and not open_levels():
        return False
    helpers.wda_tap(LEVELS[(rules, level)], settle=1.6)
    deadline = time.time() + 4.0
    while not reads_level(rules, level):
        if time.time() > deadline:
            return False
        time.sleep(0.3)
    return True


# ── Daily table and win ────────────────────────────────────────────

def on_daily_table(timeout: float = 10.0) -> tuple[bool, bool]:
    """(a Daily table is up — star in the header, not Solo's "new"; star is gold)."""
    deadline = time.time() + timeout
    while True:
        if ui.at_table(timeout=1.0):
            img = ui.screen_rgb()
            x0, y0, x1, y1 = HEADER_STAR
            if _star_mask_match(img, HEADER_STAR, "daily_table_star") >= HEADER_STAR_MATCH:
                patch = img[y0:y1, x0:x1].astype(int)
                ink = patch.max(axis=2) > 200
                gold = ink & (patch[:, :, 2] < 140)
                return True, bool(ink.sum()) and gold.sum() / ink.sum() > GOLD_SHARE
        if time.time() > deadline:
            return False, False
        time.sleep(0.5)


def synthetic_win() -> bool:
    """Synthetic Win on a Daily table. Its QA card keeps WIN grey until a
    range is picked, and sits a little higher than Solo's."""
    ui.start_deal()
    if not ui.open_qa_panel():
        return False
    helpers.wda_tap(ui.QA_SELECT_90_99, settle=1.0)
    helpers.wda_tap(ui.find("qa_win") or QA_DAILY_WIN, settle=0.2)
    return True


def victory_score() -> int | None:
    found = [n for line in ocr.read(ui.victory_score_crop()) for n in ocr.numbers(line.text)]
    return found[0] if found else None


def win_to_victory(where: str) -> int:
    """Win the Daily table on screen; return the score Victory shows."""
    ui.expect(synthetic_win(), f"Synthetic Win could not be fired on the {where} Daily table")
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


def daily_stats(shot: str) -> list[dict]:
    """Statistics → Daily in *shot*, one dict per section (TOTALS, STANDARD_EASY,
    STANDARD_MEDIUM, …) with "best", "played" and "won"; None where blank."""
    sections: list[dict] = []
    for _y, text in ocr.rows(ocr.read(shot, box=STATS_BOX)):
        low = text.lower()
        tail = text.partition(":")[2].strip()
        found = ocr.numbers("0" if tail in ("O", "o") else tail)  # this font's 0 reads as O
        value = found[0] if found else None
        if low.startswith("best score"):
            sections.append({"best": value, "played": None, "won": None})
        elif sections and low.startswith("games played"):
            sections[-1]["played"] = value
        elif sections and low.startswith("games won"):
            sections[-1]["won"] = value
    return sections


# ── offline wins handed to verifyDailyOnline ───────────────────────

def save_wins(level: str, scores: list[int]) -> None:
    WINS_PATH.write_text(json.dumps({"date": today().isoformat(), "level": level,
                                     "scores": scores}, indent=2) + "\n", encoding="utf-8")


def load_wins() -> dict:
    try:
        data = json.loads(WINS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if data.get("date") == today().isoformat() else {}
