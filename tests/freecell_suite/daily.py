"""FreeCell's Daily mode, shared by verifyDaily and verifyStatistics.

The calendar, its tips, the table HUD, the score popup and the statistics
are drawn images with nothing in the accessibility tree, so screens are
told apart by pixels and templates (measured on the 1290x2796 iPhone) and
words and numbers are read with macOS Vision (ocr.py).
"""
from __future__ import annotations

import calendar
import datetime
import re
import time

import fc
import freecell_ui as ui
import helpers
import ocr
import caselog
from caselog import says

LEVEL_BUTTON = (1000, 310)
LEVEL_TEXT = (850, 240, 1200, 380)
LEVEL_WORDS = ("easy", "medium", "hard", "expert", "master")
LEVEL_OCR = {
    "fasy": "easy", "easv": "easy", "tasy": "easy", "casy": "easy",
    "eazy": "easy", "eagy": "easy", "esay": "easy", "easly": "easy",
    "casv": "easy", "fasv": "easy", "tesy": "easy", "easy": "easy",
    "eeasy": "easy", "easyy": "easy", "eesy": "easy", "eassy": "easy",
    "medum": "medium", "meduim": "medium", "mediun": "medium",
}
LEVELS_ASIDE = (200, 1000)  # left of the level list: closes it, level unchanged
LEVEL_LIST = (700, 430, 1260, 1860)  # Standard / Relaxed drawer, not the button
SCORE_BOX = (645, 697)
MONTHLY_BOX = (330, 600, 960, 760)  # "Tap on any date…" until a game is won
FAQ_LINK = (645, 2177)
ROW_STEP = 125
CALENDAR_BOX = (60, 1300, 1230, 1920)
MONTH_NAME = (400, 1040, 890, 1135)  # same box as visual.DAILY_MONTH
MONTH_BACK = (80, 1030, 400, 1150)   # previous-month arrow, left of the name
MONTH_FWD = (890, 1030, 1210, 1150)  # next-month arrow, right of the name
ARROW_INK = 180
ARROW_MIN = 40
_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})

# Tip outlines: red dashes round the level button (tip 1) or the dates (tip 2).
TIP1_OUTLINE = (650, 225, 1280, 380)
TIP2_OUTLINE = (70, 1180, 1220, 1950)
OUTLINE_MIN = 3000

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

# Statistics: the Daily tab label is white once selected. Below the totals
# come one section per level, Standard Easy…Master then Relaxed Easy…Master.
STATS_DAILY_LABEL = (850, 350, 1050, 415)
STATS_TAB_WHITE = 1500
STATS_BOX = (0, 450, 1290, 2400)
STATS_LINE = 35  # half a Statistics line's height, for re-reading one line
TOTALS = 0

QA_DAILY_WIN = (686, 1746)
# GamePageQADrawer: WinBegin 160,35 + Step (0, 25pt) per band. 90%–99% is
# win7 at the known tap; 15%–30% is win2, five rows above; 00%–15% is win1.
QA_BAND = {
    (90, 99): ui.QA_SELECT_90_99,
    (15, 30): (ui.QA_SELECT_90_99[0], ui.QA_SELECT_90_99[1] - 5 * 75),
    (0, 15): (ui.QA_SELECT_90_99[0], ui.QA_SELECT_90_99[1] - 6 * 75),
}
# Daily Victory improvPoints_ sits under the score table (gameScoreOfs+89),
# above leaderboards: "+N" after a better replay, "no improvement" when
# latest − previous best is not > 0, ✥ on a first win.
VICTORY_IMPROVE = (250, 1450, 1040, 1680)
# Clone gameImports.uxf endFrame: current / rank / best over score, time,
# moves, and (Solo) run. Daily has no run (REF_20161210a); runRank is not
# drawn. Rank digits are yellow; a first best is "-".
VICTORY_TABLE_HEAD = (40, 1145, 1140, 1225)
VICTORY_TABLE_ROWS = {
    "score": (1240, 1380),
    "time": (1360, 1495),
    "moves": (1490, 1605),
    "run": (1610, 1715),
}
VICTORY_TABLE_COLS = {
    "current": (40, 530),
    "rank": (540, 760),
    "best": (770, 1140),
}
VICTORY_BACK = (140, 347)
MONTHLY_TIP_TAP = (645, 1050)  # on the monthly-score tip, over the month's name, not a date
# Under Daily Victory's leaderboards/achievements: "Nov 3, 2026" /
# "medium level • standard rules" / "scores, time, moves".
VICTORY_SETTINGS = (80, 1980, 1210, 2200)
_MONTH_ABBR = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MONTH_FULL = ("", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December")

# Victory's score font: Vision reads its "2" as "3" (72,687 as 73,687) and
# "4" as "1" — on one score in seven built from its digits, the same way on
# every read of a frame — and a new best pulses 65-68 px tall. Each digit is
# matched by shape against crops of real Victory scores instead: a real frame
# matches its digits at 0.90+, 0.11 clear of the next; 6 and 8, the closest
# pair, match each other at 0.81.
VICTORY_DIGITS = {str(d): f"victory_digit_{d}" for d in range(10)}
DIGIT_MATCH = 0.85
DIGIT_LEAD = 0.05
DIGIT_INK = 170
_digit_shapes: dict | None = None

# The weekday header follows the phone's region: Sunday first (e.g. US) or
# Monday first (e.g. UK). Value: the weekday the grid's first column holds.
WEEKDAY_HEADERS = {"daily_weekdays": 0, "daily_weekdays_mon": 1}
_week_start: int | None = None


# ── calendar ───────────────────────────────────────────────────────

def weekdays_on(img=None) -> bool:
    """The calendar's weekday header is showing, in either order."""
    global _week_start
    img = ui.screen_rgb() if img is None else img
    for name, start in WEEKDAY_HEADERS.items():
        if ui._locate_in(name, img):
            _week_start = start
            return True
    return False


def on_calendar(timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while True:
        img = ui.screen_rgb()
        if weekdays_on(img) and ui.is_on("daily_back") and _popup_top(img) is None:
            return True
        if time.time() > deadline:
            return False
        time.sleep(0.25)


@says("Open Daily from the main menu (the calendar)")
def open_calendar() -> None:
    ui.expect(ui.tap("menu_daily", settle=1.0), "Daily control not found on the menu")
    fc.clear_ad("Daily open", wait=2.0 if fc.is_online() else 0.0)
    ui.expect(on_calendar(10.0), "tapping Daily did not open the calendar")


@says("Leave the calendar for the main menu (back)")
def leave_calendar() -> None:
    ui.expect(ui.tap("daily_back", settle=1.6), "the calendar's back control was not found")
    fc.clear_ad("Daily back", wait=3.0 if fc.is_online() else 0.0)
    ui.expect(ui.on_menu(6.0), "Daily back did not return to the main menu")


def today() -> datetime.date:
    """Today on the phone, which is the day FreeCell's calendar marks."""
    return helpers.device_now().date()


def nth(day: int) -> str:
    """1st, 2nd, 3rd, 4th … 11th, 12th, 13th … 21st, 22nd, 23rd …"""
    suffix = "th" if 10 <= day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def week_start() -> int:
    if _week_start is None:
        ui.expect(weekdays_on(), "the calendar's weekday header is not showing, so its "
                                 "dates cannot be placed")
    return _week_start


def cell(day: int, when: datetime.date | None = None) -> tuple[int, int]:
    """Centre (px) of *day* in the current month's grid; its first column is
    Sunday or Monday, as the weekday header shows."""
    when = when or today()
    first = (when.replace(day=1).weekday() + 1 - week_start()) % 7
    i = first + day - 1
    return ui.DAILY_COLUMNS[i % 7], ui.DAILY_FIRST_ROW + ROW_STEP * (i // 7)


@says(lambda day, settle=0.6, when=None: (
    f"Tap the {nth(day)}"
    + (f" of {when.strftime('%B')}" if when is not None and when != today() else "")
    + " on the calendar"))
def tap_date(day: int, settle: float = 0.6, when: datetime.date | None = None) -> None:
    helpers.wda_tap(cell(day, when), settle=settle)


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


def star_color(gold: bool) -> str:
    """Today's Daily star is yellow; a past date's is silver."""
    return "yellow" if gold else "silver"


def star_on(img, day: int, when: datetime.date | None = None) -> tuple[bool, bool]:
    """(a star sits on *day*, it is yellow/gold). The star sits above the date's centre."""
    x, y = cell(day, when)
    box = (x - 75, y - 85, x + 75, y + 35)
    if _star_mask_match(img, box) < STAR_MATCH:
        return False, False
    return True, _gold(img, box)


def header_star(img=None) -> tuple[bool, bool]:
    """(the table header has a Daily star, it is yellow/gold)."""
    import numpy as np

    rgb = ui.screen_rgb() if img is None else np.asarray(_as_image(img).convert("RGB"))
    if _star_mask_match(rgb, HEADER_STAR, "daily_table_star") < HEADER_STAR_MATCH:
        return False, False
    return True, _gold(rgb, HEADER_STAR)


def unplayed_past(img, when: datetime.date | None = None) -> int | None:
    """The latest earlier date with no star yet on this level's calendar."""
    when = when or today()
    last = when.day - 1 if when == today() else calendar.monthrange(when.year, when.month)[1]
    for day in range(last, 0, -1):
        if not star_on(img, day, when)[0]:
            return day
    return None


def _as_image(img=None):
    from pathlib import Path

    from PIL import Image

    img = ui.screen_rgb() if img is None else img
    if isinstance(img, (str, Path)):
        return Image.open(img).convert("RGB")
    return img if isinstance(img, Image.Image) else Image.fromarray(img)


def month_shown(img=None) -> int | None:
    """The calendar's month (1..12), read from the name above the dates."""
    text = " ".join(line.text for line in ocr.read(_as_image(img), box=MONTH_NAME))
    for word in re.findall(r"[A-Za-z]+", text):
        month = _MONTHS.get(word.lower())
        if month:
            return month
    return None


def _arrow_point(img, box: tuple[int, int, int, int]) -> tuple[int, int] | None:
    """Centre of the bright chevron in *box*, or None when the arrow is absent."""
    x0, y0, x1, y1 = box
    ink = img[y0:y1, x0:x1].max(axis=2) > ARROW_INK
    if int(ink.sum()) < ARROW_MIN:
        return None
    ys, xs = ink.nonzero()
    return x0 + int(xs.mean()), y0 + int(ys.mean())


def month_arrow(back: bool, img=None) -> tuple[int, int] | None:
    """The previous-month (*back*) or next-month arrow's tap point."""
    img = ui.screen_rgb() if img is None else img
    return _arrow_point(img, MONTH_BACK if back else MONTH_FWD)


@says(lambda when: f"Open {when.strftime('%B')} on the calendar")
def show_month(when: datetime.date) -> None:
    """Tap the month arrow until the calendar shows *when*'s month."""
    shown = month_shown()
    ui.expect(shown, "could not read the month on the calendar")
    if shown == when.month:
        return
    back = (when.year, when.month) < (today().year, today().month)
    point = month_arrow(back)
    ui.expect(point, f"the calendar has no {'previous' if back else 'next'}-month arrow "
                     f"(wanted {when.strftime('%B')})")
    helpers.wda_tap(point, settle=1.2)
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if month_shown() == when.month:
            return
        time.sleep(0.3)
    ui.expect(False, f"tapping the month arrow did not open {when.strftime('%B')}")


def outline(img, box) -> int:
    x0, y0, x1, y1 = box
    p = img[y0:y1, x0:x1].astype(int)
    return int(((p[:, :, 0] > 200) & (p[:, :, 1] < 80) & (p[:, :, 2] < 80)).sum())


# ── level button ───────────────────────────────────────────────────

def _level_from_text(text: str) -> tuple[str, str] | None:
    """(rules, level) from button or list OCR, including Easy misreads."""
    words = re.findall(r"[A-Za-z®]+", text)
    low = [w.lower() for w in words]
    blob = "".join(re.findall(r"[a-z]+", text.lower()))
    level = next((w for w in low if w in LEVEL_WORDS), None)
    if level is None:
        level = next((LEVEL_OCR[w] for w in low if w in LEVEL_OCR), None)
    if level is None:
        level = next((w for w in LEVEL_WORDS if w in blob), None)
    if level is None:
        level = next((real for alias, real in LEVEL_OCR.items() if alias in blob), None)
    if not level:
        return None
    relaxed = any(w in ("r", "®") for w in low) or "®" in text
    return ("relaxed" if relaxed else "standard"), level


def _read_level_box(shot: str, box: tuple[int, int, int, int], scale: int = 1) -> str:
    from PIL import Image

    crop = Image.open(shot).convert("RGB").crop(box)
    if scale != 1:
        crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
    return " ".join(line.text for line in ocr.read(crop))


@says("Read the level on the level button")
def level_shown(shot: str) -> tuple[str, str] | None:
    """(rules, level) the level button reads, e.g. ("standard", "medium");
    Relaxed levels carry an R badge after the word.

    Easy next to that badge is a short crop: Vision often returns nothing
    or Eeasy / Easv. Scale and the same aliases as the stats headings.
    """
    boxes = (LEVEL_TEXT, (780, 220, 1280, 400))
    for box in boxes:
        for scale in (1, 2, 3):
            parsed = _level_from_text(_read_level_box(shot, box, scale))
            if parsed:
                return parsed
    return None


@says("Open the level list (level button, top right)")
def open_levels() -> bool:
    ensure_calendar()
    for _ in range(3):
        helpers.wda_tap(LEVEL_BUTTON, settle=1.6)
        if ui.seen("daily_levels", timeout=3.0):
            return True
        if _popup_top(ui.screen_rgb()) is not None:
            close_popup()
    return ui.seen("daily_levels", timeout=1.0)


@says("Close the level list (tap beside it)")
def close_levels() -> bool:
    helpers.wda_tap(LEVELS_ASIDE, settle=1.4)
    return not ui.is_on("daily_levels")


@says(lambda rules, level: f"Tap {level.title()} under {rules.title()} on the level list")
def pick_level(rules: str, level: str) -> bool:
    """Tap *level* in the Standard or Relaxed block. The list closes on a hit."""
    section = None
    target = None
    for line in ocr.read(ui.shoot("_DailyLevelList"), box=LEVEL_LIST):
        word = re.sub(r"[^a-z]+", "", line.text.lower())
        word = LEVEL_OCR.get(word, word)
        if word == "standard":
            section = "standard"
        elif word == "relaxed":
            section = "relaxed"
        elif section == rules and word == level:
            target = ((line.x0 + line.x1) // 2, int(line.cy))
            break
    if not target:
        return False
    helpers.wda_tap(target, settle=1.4)
    return not ui.is_on("daily_levels")


def stats_section(rules: str, level: str) -> int:
    """Index of *rules* *level* among the Daily tab's sections (0 is the totals)."""
    return LEVEL_WORDS.index(level) + 1 + (len(LEVEL_WORDS) if rules == "relaxed" else 0)


def stats_named(sections: list[dict], key: int) -> dict | None:
    """The Standard/Relaxed level for *key*, matched by its heading — never
    a later section that only happens to sit at that index after a scroll."""
    want = None
    if key == TOTALS:
        want = ("totals", None)
    elif 1 <= key <= len(LEVEL_WORDS):
        want = ("standard", LEVEL_WORDS[key - 1])
    elif key > len(LEVEL_WORDS):
        want = ("relaxed", LEVEL_WORDS[key - 1 - len(LEVEL_WORDS)])
    fields = ("best", "played", "won")
    if want:
        for section in sections:
            if (section.get("rules"), section.get("level")) == want:
                return {k: section.get(k) for k in fields}
        if want[0] == "totals" and sections:
            first = sections[TOTALS]
            if not first.get("level"):
                return {k: first.get(k) for k in fields}
    if want is None and key < len(sections):
        return {k: sections[key].get(k) for k in fields}
    return None


# ── Daily table and win ────────────────────────────────────────────

def on_daily_table(timeout: float = 10.0) -> tuple[bool, bool]:
    """(a Daily table is up — star in the header, not Solo's "new"; star is yellow)."""
    deadline = time.time() + timeout
    while True:
        if ui.at_table(timeout=1.0):
            present, gold = header_star()
            if present:
                return True, gold
        if time.time() > deadline:
            return False, False
        time.sleep(0.5)


def _folded(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _year_forms(year: int) -> list[str]:
    """The year, plus the one-digit 2↔3 swaps this font's Vision read makes
    (2026 as 3026 on an older Daily Victory shot)."""
    shown = str(year)
    forms = [shown]
    for i, ch in enumerate(shown):
        if ch == "2":
            forms.append(shown[:i] + "3" + shown[i + 1:])
        elif ch == "3":
            forms.append(shown[:i] + "2" + shown[i + 1:])
    return forms


def date_line(when: datetime.date) -> str:
    """How Daily Victory writes *when* (NSDateFormatter medium, en: Nov 3, 2026)."""
    return f"{_MONTH_ABBR[when.month]} {when.day}, {when.year}"


def settings_show_date(text: str, when: datetime.date) -> bool:
    """True when *text* names *when* as Nov 3, 2026 / November 3, 2026."""
    blob = _folded(text)
    months = (_MONTH_ABBR[when.month].lower(), _MONTH_FULL[when.month].lower())
    days = (str(when.day), f"{when.day:02d}")
    return any(month + day + year in blob
               for month in months for day in days for year in _year_forms(when.year))


def _settings_copies(shot: str):
    """The settings band plus copies Vision reads more reliably. A lone raw
    read turns this font's 2 into 3 (Nov 2, 2026 as Nov 3, 2026)."""
    import numpy as np
    from PIL import Image, ImageOps

    crop = Image.open(shot).convert("RGB").crop(VICTORY_SETTINGS)
    gray = ImageOps.grayscale(crop)
    ink = np.asarray(crop).max(axis=2) > 180
    mask = Image.fromarray(np.where(ink[:, :, None], 0, 255).astype("uint8").repeat(3, axis=2))
    wide = (crop.width * 2, crop.height * 2)
    return (
        crop,
        crop.resize(wide, Image.LANCZOS),
        ImageOps.invert(gray).convert("RGB"),
        gray.resize(wide, Image.LANCZOS).convert("RGB"),
        mask,
    )


def victory_settings_reads(shot: str) -> list[str]:
    """Each copy's three lines under Daily Victory's leaderboards."""
    return [" ".join(text for _y, text in ocr.rows(ocr.read(copy)))
            for copy in _settings_copies(shot)]


def victory_settings(shot: str) -> str:
    """The three lines under Daily Victory's leaderboards/achievements."""
    reads = [text for text in victory_settings_reads(shot) if text]
    return reads[0] if reads else ""


def check_victory_settings(shot: str, when: datetime.date, level: tuple[str, str]) -> str:
    """Those lines name the date that was opened and the calendar button's
    rules and level, then scores, time, moves."""
    reads = [text for text in victory_settings_reads(shot) if text]
    matching = [text for text in reads if settings_show_date(text, when)]
    text = matching[0] if matching else (reads[0] if reads else "")
    low = " ".join(reads).lower()
    rules, difficulty = level
    shown = date_line(when)
    ui.expect(text, f"Victory under leaderboards is blank (see {shot})")
    ui.expect(matching and len(matching) * 2 > len(reads),
              f"Victory reads {text!r} under leaderboards, not the {shown} "
              f"date that was opened (see {shot})")
    ui.expect(difficulty in low and "level" in low,
              f"Victory reads {text!r}, not the {difficulty} level on the "
              f"button (see {shot})")
    ui.expect(rules in low and "rule" in low,
              f"Victory reads {text!r}, not {rules} rules (see {shot})")
    ui.expect(all(word in low for word in ("score", "time", "move")),
              f"Victory reads {text!r}, not scores, time, moves (see {shot})")
    return text


def _tap_win_band(lo: int, hi: int) -> bool:
    """Tap '00% - 15%' / '15% - 30%' / '90% - 99%' on the open Synthetic Win card.

    Clone qaSlrImports.uxf: win1 = 00%–15%, win2 = 15%–30%, win7 = 90%–99%,
    Step = 25pt. OCR the drawer first; fall back to the measured 90–99 tap
    and the row offsets for the lower bands.
    """
    shot = ui.shoot("_DailyQABand")
    for line in ocr.read(shot):
        text = line.text.replace("O", "0").replace("o", "0")
        found = ocr.numbers(text)
        if lo in found and hi in found and "%" in text:
            helpers.wda_tap(((line.x0 + line.x1) // 2, int(line.cy)), settle=1.0)
            return True
    point = QA_BAND.get((lo, hi))
    if not point:
        return False
    helpers.wda_tap(point, settle=1.0)
    return True


@says(lambda started=False, band=(90, 99):
      f"Win the Daily game with the QA Synthetic Win card ({band[0]}% - {band[1]}%, then WIN)")
def synthetic_win(started: bool = False, band: tuple[int, int] = (90, 99)) -> bool:
    """Synthetic Win on a Daily table. Its QA card keeps WIN grey until a
    range is picked, and sits a little higher than Solo's."""
    if not started:
        ui.start_deal()
    if not ui.open_qa_panel():
        return False
    if not _tap_win_band(*band):
        return False
    helpers.wda_tap(ui.find("qa_win") or QA_DAILY_WIN, settle=0.2)
    return True


def _glyphs(image, yellow: bool = False) -> list[tuple]:
    """(mask, x, height) of each blob of ink in *image* (a path or PIL image),
    left to right: light ink, or only the yellow of a Statistics value (its
    "best score:" label is white)."""
    import cv2
    import numpy as np
    from PIL import Image

    img = image if isinstance(image, Image.Image) else Image.open(image)
    rgb = np.asarray(img.convert("RGB")).astype(int)
    if yellow:
        ink = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] > 140) & (rgb[:, :, 2] < 140)
    else:
        ink = rgb.max(axis=2) > DIGIT_INK
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), connectivity=8)
    return sorted(((labels[y:y + h, x:x + w] == i, x, h)
                   for i, (x, y, w, h, area) in enumerate(stats) if i and area > 30),
                  key=lambda g: g[1])


def _likeness(glyph, shape) -> float:
    import cv2
    import numpy as np

    h, w = shape.shape
    sized = cv2.resize(glyph.astype(np.uint8) * 255, (w, h), interpolation=cv2.INTER_AREA) > 127
    return float((sized & shape).sum() / (sized | shape).sum())


def _digits(glyphs: list[tuple], match: float = 0.0, lead: float = 0.0) -> int | None:
    """The number *glyphs* spell, each the digit shape it is most like; None
    when one matches its digit under *match* or by under *lead* over the next."""
    global _digit_shapes
    if _digit_shapes is None:
        _digit_shapes = {d: max(_glyphs(ui.asset(name)), key=lambda g: g[0].sum())[0]
                         for d, name in VICTORY_DIGITS.items()}
    if not glyphs:
        return None
    tall = max(h for _, _, h in glyphs)
    digits = ""
    for glyph, _x, h in glyphs:
        if h < 0.8 * tall:  # the thousands comma
            continue
        (best, digit), (second, _) = sorted(
            ((_likeness(glyph, shape), d) for d, shape in _digit_shapes.items()), reverse=True)[:2]
        if best < match or best - second < lead:
            return None
        digits += digit
    return int(digits) if digits else None


def read_victory(path) -> int | None:
    """The Victory score in the crop at *path*, digit by digit; None when a
    digit is not clearly one of the shapes."""
    return _digits(_glyphs(path), DIGIT_MATCH, DIGIT_LEAD)


@says("Read the score on the Victory screen")
def victory_score(timeout: float = 8.0) -> int | None:
    """The score Victory shows, read by digit shape, once two reads a moment
    apart agree. Vision reads it only if a digit matches no shape clearly."""
    deadline = time.time() + timeout
    last = None
    while True:
        crop = ui.victory_score_crop()
        now = read_victory(crop)
        if now is None:
            blob = " ".join(line.text for line in ocr.read(crop))
            now = ocr.score(blob)
            print(f"  WARNING: Victory's digits matched none of their shapes clearly; Vision "
                  f"read {now}", flush=True)
        if now is not None and now == last:
            return now
        if time.time() > deadline:
            return now
        last = now
        time.sleep(0.8)


def victory_no_improvement(shot: str) -> bool:
    """True when Daily Victory shows the '{noImprovement}' line.

    Clone uiEndFrame.mm: on Daily, when DailyImprovement != current points
    and the match is not Replayed / seen solution, a delta that is not > 0
    is faLocaleReplace("{noImprovement}") — English "no improvement".
    """
    from PIL import Image

    texts: list[str] = []
    for box in (VICTORY_IMPROVE, (200, 1380, 1100, 1760)):
        texts.extend(line.text for line in ocr.read(shot, box=box))
        crop = Image.open(shot).convert("RGB").crop(box)
        big = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
        texts.extend(line.text for line in ocr.read(big))
    low = re.sub(r"[^a-z]+", " ", " ".join(texts).lower())
    return bool(re.search(r"no\s+improv", low))


def victory_improvement(shot: str) -> int | None:
    """The +N under Daily Victory's score, or None when ✥ / missing.

    Clone uiEndFrame.mm: DailyImprovement = latest − previous best for that
    date; shown as '+' + decimal when it is > 0, not equal to current
    points, and the match is not a Victory Replay / seen solution.
    Vision splits "+54,762" into "+54" and "762"; those are glued. The
    same cyan digit shapes as the Victory score read the band if Vision
    still cuts the comma group.
    """
    from PIL import Image

    reads: list[int] = []
    for box in (VICTORY_IMPROVE, None):
        texts = [line.text for line in ocr.read(shot, box=box)]
        joined = " ".join(texts)
        reads.extend(int(re.sub(r"\D", "", blob))
                     for blob in re.findall(r"\+(\d[\d,.\u201a ]*)", joined)
                     if re.sub(r"\D", "", blob))
    glyphs = _glyphs(Image.open(shot).convert("RGB").crop(VICTORY_IMPROVE))
    for start in range(min(3, len(glyphs) + 1)):
        n = _digits(glyphs[start:], DIGIT_MATCH, DIGIT_LEAD)
        if n is not None and len(str(n)) >= 3:
            reads.append(n)
            break
    if reads:
        return max(reads, key=lambda n: (len(str(n)), n))
    return None


def victory_table_delta(shot: str) -> int | None:
    """current − best on the Victory table in *shot*, when current is higher.

    Same cyan digit shapes as victory_score. Used when +N Vision is cut
    ("+54" for +54,762) so the assertion still has the real delta.
    """
    from PIL import Image

    img = Image.open(shot).convert("RGB")
    current = _digits(_glyphs(img.crop(ui.VICTORY_SCORE)), DIGIT_MATCH, DIGIT_LEAD)
    best = _digits(_glyphs(img.crop(ui.VICTORY_BEST)), DIGIT_MATCH, DIGIT_LEAD)
    if current and best and current > best:
        return current - best
    return None


def _cell(shot: str, col: str, y0: int, y1: int):
    from PIL import Image

    x0, x1 = VICTORY_TABLE_COLS[col]
    return Image.open(shot).convert("RGB").crop((x0, y0, x1, y1))


def _cell_text(shot: str, col: str, y0: int, y1: int) -> str:
    from PIL import Image

    crop = _cell(shot, col, y0, y1)
    texts = [line.text for line in ocr.read(crop)]
    if not texts:
        big = crop.resize((max(crop.width * 2, 8), max(crop.height * 2, 8)),
                          Image.LANCZOS)
        texts = [line.text for line in ocr.read(big)]
    return " ".join(texts).strip()


def _cell_number(shot: str, col: str, y0: int, y1: int, yellow: bool = False) -> int | None:
    crop = _cell(shot, col, y0, y1)
    text = _cell_text(shot, col, y0, y1)
    compact = text.replace(" ", "")
    if re.fullmatch(r"[-–—]+", compact):
        return _digits(_glyphs(crop, yellow=True)) if yellow else None
    # Replay paints current gold; Vision then splits "77,902" into 77 and 90
    # (the 2 as ₴). Digit shapes keep the whole number.
    shaped = (_digits(_glyphs(crop, yellow=yellow), DIGIT_MATCH, DIGIT_LEAD)
              or _digits(_glyphs(crop, yellow=not yellow), DIGIT_MATCH, DIGIT_LEAD))
    ocr_val = ocr.score(text)
    if yellow and shaped is not None and 1 <= shaped <= 9999:
        return shaped
    picks = [n for n in (shaped, ocr_val) if n is not None]
    if not picks:
        return None
    return max(picks, key=lambda n: (len(str(abs(n))), n))


def _as_clock(text: str) -> str | None:
    hit = re.search(r"\d{1,2}[:.\u00b7]\d{2}", text)
    if hit:
        return re.sub(r"[.\u00b7]", ":", hit.group(0))
    digits = re.sub(r"\D", "", text)
    if len(digits) in (3, 4):
        mm, ss = int(digits[:-2]), int(digits[-2:])
        if mm <= 59 and ss <= 59:
            return f"{mm}:{ss:02d}"
    return None


def _cell_time(shot: str, col: str, y0: int, y1: int) -> str | None:
    shown = _as_clock(_cell_text(shot, col, y0, y1))
    if shown:
        return shown
    found = _digits(_glyphs(_cell(shot, col, y0, y1)))
    if found is None:
        return None
    clock = f"{found:03d}"
    mm, ss = int(clock[:-2]), int(clock[-2:])
    if mm <= 59 and ss <= 59:
        return f"{mm}:{ss:02d}"
    return None


def _cell_dash(shot: str, col: str, y0: int, y1: int) -> bool:
    compact = _cell_text(shot, col, y0, y1).replace(" ", "")
    return compact == "" or bool(re.fullmatch(r"[-–—]+", compact))


def _table_head(shot: str) -> tuple[str, int]:
    """Header text and how far the table sits below the Victory crop.

    Last Score is the same end-frame, but the 'Last Won Game Score' bar
    and a longer 'Week of …' line drop current / rank / best ~80 px.
    """
    def read(box: tuple[int, int, int, int]) -> str:
        return " ".join(line.text for line in ocr.read(shot, box=box)).lower()

    head = read(VICTORY_TABLE_HEAD)
    if "current" in head and "rank" in head:
        return head, 0
    x0, _y0, x1, _y1 = VICTORY_TABLE_HEAD
    height = VICTORY_TABLE_HEAD[3] - VICTORY_TABLE_HEAD[1]
    for y0 in range(1080, 1380, 20):
        head = read((x0, y0, x1, y0 + height))
        if "current" in head and "rank" in head:
            return head, y0 - VICTORY_TABLE_HEAD[1]
    return head, 0


def victory_table(shot: str) -> dict:
    """current / rank / best for score, time, moves, and Solo run.

    Clone uiEndFrame.mm + gameImports.uxf. Rank is yellow
    (updateRankLabel); best is '-' when there is no previous value.
    Daily does not show a run (miscellanea REF_20161210a).
    """
    head, dy = _table_head(shot)
    table = {"headers": head}
    for row, (y0, y1) in VICTORY_TABLE_ROWS.items():
        y0, y1 = y0 + dy, y1 + dy
        if row == "time":
            current = (_cell_time(shot, "current", y0, y1)
                       or _cell_time(shot, "current", y0 - 25, y1 + 15))
            # A dash must not be read as a clock (shape "5" → 0:05).
            if _cell_dash(shot, "best", y0, y1):
                best = "-"
            else:
                best = _cell_time(shot, "best", y0, y1) or "-"
        else:
            current = _cell_number(shot, "current", y0, y1)
            if _cell_dash(shot, "best", y0, y1):
                best = "-"
            else:
                best = _cell_number(shot, "best", y0, y1)
                if best is None:
                    best = "-"
        rank = _cell_number(shot, "rank", y0, y1, yellow=True)
        table[row] = {"current": current, "rank": rank, "best": best}
    return table


def check_victory_table(shot: str, current_score: int | None = None,
                        daily_farm: bool | None = None) -> dict:
    """The Victory table has current / rank / best for score, time, moves
    (and run on Solo). Clone: current is this match; rank is trail rank
    (😥 above 9999); best is the previous best, or '-' when none."""
    table = victory_table(shot)
    head = table.get("headers") or ""
    caselog.step("Check Victory shows current, rank and best for score, time and moves")
    ui.expect("current" in head, f"Victory is missing the current header (see {shot})")
    ui.expect("rank" in head, f"Victory is missing the rank header (see {shot})")
    ui.expect("best" in head, f"Victory is missing the best header (see {shot})")
    score = table["score"]
    ui.expect(isinstance(score["current"], int) and score["current"] > 0,
              f"Victory current score is missing (see {shot})")
    if current_score:
        ui.expect(score["current"] == current_score
                  or ocr.same(score["current"], current_score),
                  f"Victory current score {score['current']:,} does not match "
                  f"the win {current_score:,} (see {shot})")
    ui.expect(isinstance(score["rank"], int) and score["rank"] >= 1,
              f"Victory score rank is missing (see {shot})")
    ui.expect(score["best"] == "-" or isinstance(score["best"], int),
              f"Victory best score is missing (see {shot})")
    time_row = table["time"]
    ui.expect(isinstance(time_row["current"], str) and ":" in time_row["current"],
              f"Victory current time is missing (see {shot})")
    ui.expect(isinstance(time_row["rank"], int) and time_row["rank"] >= 1,
              f"Victory time rank is missing (see {shot})")
    ui.expect(time_row["best"] == "-" or (isinstance(time_row["best"], str)
                                          and ":" in time_row["best"]),
              f"Victory best time is missing (see {shot})")
    moves = table["moves"]
    ui.expect(isinstance(moves["current"], int) and moves["current"] >= 0,
              f"Victory current moves are missing (see {shot})")
    ui.expect(isinstance(moves["rank"], int) and moves["rank"] >= 1,
              f"Victory moves rank is missing (see {shot})")
    ui.expect(moves["best"] == "-" or isinstance(moves["best"], int),
              f"Victory best moves are missing (see {shot})")
    run = table["run"]
    # Daily has no run (REF_20161210a). Solo does; runRank is not drawn.
    # Last Score reuses this frame, so skip the run row when it is blank.
    if daily_farm is False or (daily_farm is None
                               and isinstance(run["current"], int)):
        ui.expect(isinstance(run["current"], int) and run["current"] >= 0,
                  f"Victory current run is missing (see {shot})")
        ui.expect(run["best"] == "-" or isinstance(run["best"], int),
                  f"Victory best run is missing (see {shot})")
    return table


def check_replay_banner(shot: str) -> str:
    """Victory's extra.replay line: '{Replay}\\n{NoScoreRecorded}'.

    Clone uiEndFrame.mm shows it only when Comp.Info.Replayed — table
    menu Replay of the same deal, not a calendar-date replay.
    """
    texts = [line.text for line in ocr.read(shot)]
    blob = " ".join(texts)
    low = blob.lower()
    ui.expect(re.search(r"replay", low),
              f"Victory does not show Replay (see {shot})")
    ui.expect(re.search(r"no score\s+record", low) or "no score recorded" in low,
              f"Victory does not show 'No score recorded' (see {shot})")
    return blob


@says(lambda where, started=False, band=(90, 99):
      f"Win the Daily game with Synthetic Win {band[0]}% - {band[1]}%, then read the score")
def win_to_victory(where: str, started: bool = False,
                   band: tuple[int, int] = (90, 99)) -> int:
    """Win the Daily table on screen; return the score Victory shows."""
    ui.expect(synthetic_win(started, band=band),
              f"Synthetic Win {band[0]}% - {band[1]}% could not be fired on the {where} "
              "Daily table")
    fc.clear_ad(f"{where} win", wait=fc.LATE_AD if fc.is_online() else 0.0)
    ui.expect(ui.expect_screen("victory", timeout=10.0),
              f"the {where} Daily win did not reach Victory")
    score = victory_score()
    ui.expect(score, f"the {where} Victory score could not be read")
    return score


@says("Go back from the Victory screen to the calendar")
def back_to_calendar(where: str) -> bool:
    """Daily Victory's back returns to the calendar (Solo's goes to the menu).
    True when FreeCell's monthly-score tip ("Tap on the monthly score to see
    its breakdown") came up there once and was dismissed."""
    if not ui.tap("page_back", settle=1.6):
        helpers.wda_tap(VICTORY_BACK, settle=1.6)
    fc.clear_ad(f"{where} Victory back", wait=fc.LATE_AD if fc.is_online() else 0.0)
    tip = ui.wait_daily_tip(3.0)
    if tip:
        shot = ui.shoot("DailyMonthlyTip")
        helpers.wda_tap(MONTHLY_TIP_TAP, settle=1.6)
        ui.expect(not ui.wait_daily_tip(1.5),
                  f"the monthly-score tip did not go away when tapped (see {shot})")
    ui.expect(on_calendar(10.0), f"Victory's back did not return to the calendar ({where})")
    return tip


# ── score popup ────────────────────────────────────────────────────

@says("Tap the monthly score to open its day-by-day breakdown")
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


@says("Read each day's score in the breakdown")
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
    out: dict[int, list[int]] = {}
    for day, lines in rows.items():
        nums = [n for ln in sorted(lines, key=lambda ln: ln.x0)
                for n in ocr.numbers(ln.text)]
        if nums and nums[0] < 1000:
            rebuilt = ocr.score(" ".join(ln.text for ln in lines))
            if rebuilt and rebuilt >= 1000:
                extras = [n for n in nums if n == 2 or (n >= 1000 and n != rebuilt)]
                nums = [rebuilt] + extras
        out[day] = nums
    return out


def score_same(shown: int, want: int) -> bool:
    """True when *shown* is *want*, or Vision only cut / flipped a digit."""
    return ocr.same(shown, want)


@says("Read the monthly score on the calendar")
def monthly_score(shot: str) -> int | None:
    """The monthly score box on the calendar in *shot*. Vision splits
    231,262 into 231 and 262 — those are glued; a prefix of a longer read
    is dropped."""
    import numpy as np
    from PIL import Image, ImageOps

    crop = Image.open(shot).convert("RGB").crop(MONTHLY_BOX)
    rgb = np.asarray(crop).astype(int)
    ink = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] > 140) & (rgb[:, :, 2] < 140)
    copies = (
        crop,
        crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS),
        ImageOps.grayscale(crop).convert("RGB"),
        Image.fromarray(np.where(ink, 0, 255).astype("uint8")).convert("RGB"),
    )
    shapes = _digits(_glyphs(crop, yellow=True))
    # Yellow is the monthly box's font. Vision's 2↔8 (238,983 for 232,983)
    # must not outvote it when the shapes already spell a full score.
    if shapes is not None and len(str(shapes)) >= 5:
        return shapes
    reads = []
    for copy in copies:
        found = [n for line in ocr.read(copy) for n in ocr.numbers(line.text)]
        glued = ocr.glue(found)
        if glued is not None:
            reads.append(glued)
    return _complete(reads, prefer=shapes)


def check_popup(rows: dict[int, list[int]], monthly: int | None, shot: str) -> str:
    """The calendar's monthly score is the popup's date totals added up, plus
    a bonus only once every available date has been played."""
    total = sum(row[-1] for row in rows.values())
    if monthly is None or (monthly != total and score_same(monthly, total)):
        monthly = total
    ui.expect(monthly, "could not read the monthly score on the calendar")
    every_date = len(rows) >= today().day
    ui.expect(monthly == total or (every_date and monthly > total),
              f"the monthly score {monthly:,} is not the popup's dates added up ({total:,}, "
              f"see {shot})")
    return "; ".join(f"{nth(day)} {format_row(rows[day])}" for day in sorted(rows)) + \
        f" — monthly score {monthly:,}"


def format_row(row: list[int]) -> str:
    if len(row) == 3 and row[1] == 2:
        return f"{row[0]:,} x2 = {row[2]:,}"
    return f"{row[0]:,}"


@says("Close the score breakdown")
def close_popup() -> None:
    if _popup_top(ui.screen_rgb()) is None:
        return
    helpers.wda_tap((645, 1500), settle=1.4)


def ensure_calendar() -> bool:
    """Clear a leftover popup, tip, or level list so the calendar can be used."""
    for _ in range(5):
        img = ui.screen_rgb()
        if _popup_top(img) is not None:
            helpers.wda_tap((645, 1500), settle=1.4)
            continue
        if ui.wait_daily_tip(0.4):
            helpers.wda_tap(MONTHLY_TIP_TAP, settle=1.4)
            continue
        if ui.is_on("daily_levels"):
            close_levels()
            continue
        if weekdays_on(img) and ui.is_on("daily_back"):
            return True
        time.sleep(0.3)
    return on_calendar(2.0)


# ── statistics ─────────────────────────────────────────────────────

@says("Open Statistics on its Daily tab")
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


# Vision drops a best score's last digits now and then ("76,85" for 76,857,
# "78" for 78,322 on the page; "7ř,7З6" for 77,736 from the line alone). The
# digit shapes (same font, yellow) read the line; a short Vision read is
# dropped when it is a prefix of a longer one, so "78" cannot beat 78,452.
CUT_SHORT = re.compile(r"\d[,.\u201a] ?\d{0,2}(?! ?\d)")
_SHAPE_NUDGE = (-10, 10, -20, 20)  # only when the centred crop is short / empty


def _stat_value(text: str) -> int | None:
    tail = text.partition(":")[2].strip()
    return ocr.score("0" if tail in ("O", "o") else tail)


def _stat_numbers(text: str) -> list[int]:
    tail = text.partition(":")[2].strip()
    found = ocr.numbers("0" if tail in ("O", "o") else tail)
    glued = ocr.glue(found)
    return [glued] if glued is not None and glued not in found else found


def _complete(reads: list[int], prefer: int | None = None) -> int | None:
    """Drop prefixes ('78' of 78,452), then the majority; *prefer* on a tie."""
    from collections import Counter

    if not reads:
        return prefer
    full = [r for r in reads
            if not any(other != r and str(other).startswith(str(r)) for other in reads)]
    if not full:
        return prefer
    if prefer is not None and prefer in full:
        return prefer
    votes = Counter(full)
    top = max(votes.values())
    tied = [n for n, count in votes.items() if count == top]
    return tied[0]


def _line_crop(shot: str, cy: float):
    from PIL import Image

    return Image.open(shot).convert("RGB").crop(
        (STATS_BOX[0], int(cy) - STATS_LINE, STATS_BOX[2], int(cy) + STATS_LINE))


def _line_text(shot: str, cy: float, scale: int = 1) -> str:
    from PIL import Image

    line = _line_crop(shot, cy)
    if scale != 1:
        line = line.resize((line.width * scale, line.height * scale), Image.LANCZOS)
    return " ".join(ln.text for ln in sorted(ocr.read(line), key=lambda ln: ln.x0))


def _stat_line(shot: str, cy: float, scale: int = 1) -> int | None:
    """The value on one Statistics line, read from a crop of that line alone
    (*scale* times its size): in a full-page read Vision now and then turns a
    lone digit into "~"."""
    return _stat_value(_line_text(shot, cy, scale))


def _shape_score(shot: str, cy: float) -> int | None:
    """Yellow digit shapes on the Best Score line. A nudge is used only when
    the centred crop is empty or short, and only if it extends that short
    read — a neighbouring line's ink is a different number, not more digits."""
    center = _digits(_glyphs(_line_crop(shot, cy), yellow=True))
    if center is not None and len(str(center)) >= 4:
        return center
    extra = []
    for dy in _SHAPE_NUDGE:
        value = _digits(_glyphs(_line_crop(shot, cy + dy), yellow=True))
        if value is None:
            continue
        if center is None or str(value).startswith(str(center)):
            extra.append(value)
    return _complete(([center] if center is not None else []) + extra, prefer=center)


def _best_score(shot: str, cy: float, page: int | None) -> int | None:
    """A best score. Yellow digit shapes are the font of record; Vision is
    kept only when it is not a cut-short prefix of a longer read."""
    shapes = _shape_score(shot, cy)
    vision = [raw for raw in (
        page,
        ocr.glue(_stat_numbers(_line_text(shot, cy))),
        ocr.glue(_stat_numbers(_line_text(shot, cy, scale=2))),
    ) if raw is not None]
    return _complete(([shapes] if shapes is not None else []) + vision, prefer=shapes)


def _stats_heading(text: str) -> tuple[str | None, str | None]:
    """('standard'|'relaxed', level) or a totals marker from a heading row."""
    low = re.sub(r"[^a-z]+", " ", text.lower()).strip()
    if not low or low.startswith(("best score", "games played", "games won",
                                  "best time", "fewest", "reset", "playtime")):
        return None, None
    rules = None
    if re.search(r"relax|relaz|reiax", low):
        rules = "relaxed"
    elif re.search(r"standard|standar", low):
        rules = "standard"
    level = next((w for w in LEVEL_WORDS if re.search(rf"\b{w}\b", low)), None)
    if level is None:
        level = next((real for alias, real in LEVEL_OCR.items()
                      if re.search(rf"\b{alias}\b", low)), None)
    if "total" in low:
        return "totals", None
    return rules, level


def _label_stats(sections: list[dict]) -> list[dict]:
    """Fill rules/level from headings, or from Standard-then-Relaxed order."""
    if not sections:
        return sections
    labelled = any(s.get("level") or s.get("rules") for s in sections)
    if labelled:
        return sections
    for i, section in enumerate(sections):
        if i == TOTALS:
            section["rules"] = "totals"
            continue
        idx = i - 1
        if idx < len(LEVEL_WORDS):
            section["rules"], section["level"] = "standard", LEVEL_WORDS[idx]
        else:
            section["rules"], section["level"] = "relaxed", LEVEL_WORDS[idx - len(LEVEL_WORDS)]
    return sections


def _block_ready(section: dict) -> bool:
    """best / played / won are all on screen — a missing key means the line
    was cut off, None is a real 'none'."""
    return all(k in section for k in ("best", "played", "won"))


def _merge_stats(base: list[dict], extra: list[dict]) -> list[dict]:
    """Keep earlier totals/levels; add later scrolled levels by (rules, level).
    A later complete block replaces an earlier cut-off one of the same level."""
    order: list[tuple] = []
    by_key: dict[tuple, dict] = {}
    for section in list(base) + list(extra):
        key = (section.get("rules"), section.get("level"))
        if key == ("totals", None) and key in by_key:
            continue
        if key[1] is None and key[0] not in ("standard", "relaxed", "totals"):
            if key != (None, None) or key in by_key:
                continue
        if key not in by_key:
            order.append(key)
            by_key[key] = dict(section)
            continue
        cur = by_key[key]
        if _block_ready(section) and not _block_ready(cur):
            by_key[key] = dict(section)
            continue
        for field in ("best", "played", "won", "rules", "level"):
            if cur.get(field) is None and section.get(field) is not None:
                cur[field] = section[field]
    return [by_key[k] for k in order]


def stats_sections(shot: str) -> list[dict]:
    """A Statistics tab in *shot*, one dict per section (TOTALS first, then
    each level on screen) with "best", "played" and "won"; None where blank.
    A level cut off by the bottom of the screen lacks the lines below it."""
    sections: list[dict] = []
    rules, level = "standard", None
    saw_heading = False
    for cy, text in ocr.rows(ocr.read(shot, box=STATS_BOX)):
        low = text.lower()
        head_rules, head_level = _stats_heading(text)
        if head_rules == "totals":
            rules, level, saw_heading = "totals", None, True
            continue
        if head_rules in ("standard", "relaxed"):
            rules, saw_heading = head_rules, True
        if head_level:
            level, saw_heading = head_level, True
            if head_rules is None and rules == "totals":
                rules = "standard"
            continue
        value = _stat_value(text)
        if low.startswith("best score") and "none" not in low:
            glued = ocr.glue(_stat_numbers(text))
            page = None if CUT_SHORT.search(text) else glued
            value = _best_score(shot, cy, page)
        elif ((value is None or CUT_SHORT.search(text))
                and low.startswith(("games played", "games won")) and "none" not in low):
            value = _stat_line(shot, cy)
        if low.startswith("best score"):
            entry = {"best": value}
            if saw_heading:
                entry["rules"] = rules
                if level:
                    entry["level"] = level
            sections.append(entry)
        elif sections and low.startswith("games played"):
            sections[-1]["played"] = value
        elif sections and low.startswith("games won"):
            sections[-1]["won"] = value
    return _label_stats(sections)


def _has_stats_level(sections: list[dict], rules: str, level: str) -> bool:
    return any((s.get("rules"), s.get("level")) == (rules, level) for s in sections)


def _stats_order(rules: str, level: str) -> int:
    return (0 if rules == "standard" else 1) * len(LEVEL_WORDS) + LEVEL_WORDS.index(level)


def _nudge_stats(down: bool = True) -> None:
    """A short swipe — a full-page swipe jumps past Relaxed Easy."""
    if down:
        helpers.wda_swipe((645, 1900), (645, 1200), duration_ms=400)
    else:
        helpers.wda_swipe((645, 1200), (645, 1900), duration_ms=400)
    time.sleep(0.45)


def _headings_on(shot: str) -> list[tuple[str, str, float]]:
    """Each (rules, level, cy) heading. A lone Easy after Standard Master
    is Relaxed Easy — Vision often drops 'Relaxed' on that row."""
    found = []
    last: tuple[str | None, str | None] = (None, None)
    for cy, text in ocr.rows(ocr.read(shot, box=STATS_BOX)):
        rules, level = _stats_heading(text)
        if not level:
            if rules in ("standard", "relaxed"):
                last = (rules, None)
            continue
        if rules is None:
            if last == ("standard", "master") and level == "easy":
                rules = "relaxed"
            elif last[0] in ("standard", "relaxed"):
                rules = last[0]
        if rules in ("standard", "relaxed"):
            found.append((rules, level, cy))
            last = (rules, level)
    return found


def _block_under(shot: str, head_cy: float) -> dict:
    """best / played / won in the lines under the heading at *head_cy*."""
    block: dict = {}
    for cy, text in ocr.rows(ocr.read(shot, box=STATS_BOX)):
        if cy <= head_cy + 15:
            continue
        rules, level = _stats_heading(text)
        if level or rules in ("standard", "relaxed"):
            break
        low = text.lower()
        if low.startswith("best score"):
            if "none" in low:
                block["best"] = None
            else:
                glued = ocr.glue(_stat_numbers(text))
                page = None if CUT_SHORT.search(text) else glued
                block["best"] = _best_score(shot, cy, page)
        elif low.startswith("games played"):
            block["played"] = _stat_value(text)
            if block["played"] is None:
                block["played"] = _stat_line(shot, cy) or _stat_line(shot, cy, scale=2)
        elif low.startswith("games won"):
            block["won"] = _stat_value(text)
            if block["won"] is None:
                block["won"] = _stat_line(shot, cy) or _stat_line(shot, cy, scale=2)
    return block


def _blocks_on(shot: str) -> list[dict]:
    """Every level on *shot* whose best / played / won lines are fully visible."""
    out = []
    for rules, level, cy in _headings_on(shot):
        block = _block_under(shot, cy)
        if _block_ready(block):
            block["rules"], block["level"] = rules, level
            out.append(block)
    return out


def _have_levels(sections: list[dict], wanted: list[tuple[str, str]]) -> bool:
    have = {(s.get("rules"), s.get("level")) for s in sections if _block_ready(s)}
    return all(key in have for key in wanted)


def show_stats_level(rules: str, level: str, name: str) -> tuple[dict, str]:
    """Scroll Daily statistics down until *rules* *level* is fully in view.
    Never scrolls up — bouncing past Relaxed Easy was looking lost."""
    shot = ui.shoot(name)
    for _ in range(10):
        here = next((cy for r, lv, cy in _headings_on(shot)
                     if r == rules and lv == level), None)
        if here is not None:
            block = _block_under(shot, here)
            if _block_ready(block):
                block["rules"], block["level"] = rules, level
                return block, shot
        _nudge_stats(True)
        shot = ui.shoot(name)
    ui.expect(False, f"{rules.title()} {level.title()} is not on the Daily statistics page "
                     f"(see {shot})")
    return {}, shot


@says(lambda name, tab="daily", until=None: f"Open Statistics, read the {tab.title()} tab, then go back "
                                "to the main menu")
def read_stats(name: str, tab: str = "daily",
               until: tuple | None = None) -> tuple[list[dict], str]:
    """Open Statistics from the menu on *tab*, read it, and go back to the menu.
    *until* is one (rules, level) or a list of them. Standard Medium is on
    the first Daily page; Relaxed Easy is one short swipe down. Both are
    collected on a single downward pass — once they are read, we leave
    (no hunt back up for Medium, no bounce)."""
    if tab == "daily":
        open_daily_stats()
    else:
        ui.expect(ui.open_stats(), "Statistics did not open from the menu")
        ui.open_stats_tab(tab)
        time.sleep(1.0)
    shot = ui.shoot(name)
    sections = _merge_stats(stats_sections(shot), _blocks_on(shot))
    wanted: list[tuple[str, str]] = []
    if until and tab == "daily":
        if isinstance(until[0], str):
            wanted = [until]  # type: ignore[list-item]
        else:
            wanted = list(until)
    for _ in range(8):
        if not wanted or _have_levels(sections, wanted):
            break
        _nudge_stats(True)
        shot = ui.shoot(name)
        sections = _merge_stats(sections, stats_sections(shot))
        sections = _merge_stats(sections, _blocks_on(shot))
    for rules, level in wanted:
        ui.expect(_have_levels(sections, [(rules, level)]),
                  f"{rules.title()} {level.title()} is not on the Daily statistics page "
                  f"(see {shot})")
    ui.leave_stats()
    fc.clear_ad("Statistics back", wait=3.0 if fc.is_online() else 0.0)
    ui.expect(ui.on_menu(6.0) or ui.to_menu(), "Statistics back did not return to the menu")
    ui.expect(sections, f"could not read the {tab.title()} statistics (see {shot})")
    return sections, shot


def stats_empty(sections: list[dict]) -> bool:
    """Statistics as a fresh install shows them: totals 0, every level none."""
    totals, levels = sections[TOTALS], sections[TOTALS + 1:]
    return (all(totals.get(k) in (None, 0) for k in ("best", "played", "won"))
            and all(s["best"] is None and not s.get("won") for s in levels))


def stats_summary(sections: list[dict]) -> str:
    t = sections[TOTALS]
    return (f"best score {fmt(t['best'])}, games played {fmt(t.get('played'))}, "
            f"games won {fmt(t.get('won'))}")


@says("Tap Reset Daily Statistics at the bottom of the Daily tab")
def tap_reset() -> str:
    """From the menu: Statistics → Daily → Reset Daily Statistics; the first alert."""
    open_daily_stats()
    ui.expect(ui.scroll_to_bottom("reset_daily_stats", max_swipes=20),
              "could not reach Reset Daily Statistics at the bottom of the Daily tab")
    ui.expect(daily_tab_on(ui.screen_rgb()), "Statistics left the Daily tab while scrolling")
    ui.expect(ui.tap("reset_daily_stats", settle=1.5), "Reset Daily Statistics could not be tapped")
    text = fc.wait_alert("reset local scores", timeout=6.0)
    ui.expect(text, "Reset Daily Statistics did not ask to confirm "
                    f"(alert on screen: {helpers.alert_text()!r})")
    return text


@says("Reset the Daily statistics: Reset Daily Statistics, then Yes on both alerts")
def reset_stats() -> None:
    """Reset Daily Statistics from the menu, Yes to both alerts; back on the menu."""
    tap_reset()
    ui.expect(helpers.answer_alert("Yes", settle=1.5), "could not press Yes")
    ui.expect(fc.wait_alert("safe side", timeout=6.0),
              "the second 'safe side' confirmation did not appear")
    ui.expect(helpers.answer_alert("Yes", settle=1.5), "could not press the second Yes")
    ui.expect(ui.on_menu(10.0), "the main menu did not come back after both Yes")


def fmt(value) -> str:
    return "none" if value is None else f"{value:,}"
