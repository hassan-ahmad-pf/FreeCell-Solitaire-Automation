"""FreeCell's Daily mode, shared by verifyDaily and verifyStatistics.

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
from caselog import says

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
MONTHLY_TIP_TAP = (645, 1050)  # on the monthly-score tip, over the month's name, not a date

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
        if weekdays_on() and ui.is_on("daily_back"):
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


@says(lambda day, settle=0.6: f"Tap the {nth(day)} on the calendar")
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

@says("Read the level on the level button")
def level_shown(shot: str) -> tuple[str, str] | None:
    """(rules, level) the level button reads, e.g. ("standard", "medium");
    Relaxed levels carry an R badge after the word."""
    text = " ".join(line.text for line in ocr.read(shot, box=LEVEL_TEXT))
    words = re.findall(r"[A-Za-z®]+", text)
    level = next((w.lower() for w in words if w.lower() in LEVEL_WORDS), None)
    if not level:
        return None
    return ("relaxed" if any(w in ("R", "®") for w in words) else "standard"), level


@says("Open the level list (level button, top right)")
def open_levels() -> bool:
    helpers.wda_tap(LEVEL_BUTTON, settle=1.6)
    return ui.seen("daily_levels", timeout=4.0)


@says("Close the level list (tap beside it)")
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


@says("Win the Daily game with the QA Synthetic Win card (90% - 99%, then WIN)")
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
            found = [n for line in ocr.read(crop) for n in ocr.numbers(line.text)]
            now = found[0] if found else None
            print(f"  WARNING: Victory's digits matched none of their shapes clearly; Vision "
                  f"read {now}", flush=True)
        if now is not None and now == last:
            return now
        if time.time() > deadline:
            return now
        last = now
        time.sleep(0.8)


@says("Win the Daily game with Synthetic Win, then read the score on the Victory screen")
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


@says("Go back from the Victory screen to the calendar")
def back_to_calendar(where: str) -> bool:
    """Daily Victory's back returns to the calendar (Solo's goes to the menu).
    True when FreeCell's monthly-score tip ("Tap on the monthly score to see
    its breakdown") came up there once and was dismissed."""
    if not ui.tap("page_back", settle=1.6):
        helpers.wda_tap(VICTORY_BACK, settle=1.6)
    fc.clear_ad(f"{where} Victory back", wait=fc.LATE_AD if fc.is_online() else 2.0)
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
    return {day: [n for ln in sorted(lines, key=lambda ln: ln.x0) for n in ocr.numbers(ln.text)]
            for day, lines in rows.items()}


@says("Read the monthly score on the calendar")
def monthly_score(shot: str) -> int | None:
    """The monthly score box on the calendar in *shot*. Vision now and then
    reads this font's "2" as "8", so a grey and a black-on-white copy are
    read as well and the majority wins."""
    from collections import Counter

    import numpy as np
    from PIL import Image, ImageOps

    crop = Image.open(shot).convert("RGB").crop(MONTHLY_BOX)
    rgb = np.asarray(crop).astype(int)
    ink = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] > 140) & (rgb[:, :, 2] < 140)
    copies = (crop, ImageOps.grayscale(crop).convert("RGB"),
              Image.fromarray(np.where(ink, 0, 255).astype("uint8")).convert("RGB"))
    reads = []
    for copy in copies:
        found = [n for line in ocr.read(copy) for n in ocr.numbers(line.text)]
        if found:
            reads.append(found[0])
    return Counter(reads).most_common(1)[0][0] if reads else None


def check_popup(rows: dict[int, list[int]], monthly: int | None, shot: str) -> str:
    """The calendar's monthly score is the popup's date totals added up, plus
    a bonus only once every available date has been played."""
    ui.expect(monthly, "could not read the monthly score on the calendar")
    total = sum(row[-1] for row in rows.values())
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
    helpers.wda_tap((645, 1500), settle=1.4)


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
# digit shapes (same font, yellow) read every saved Statistics line right.
CUT_SHORT = re.compile(r"\d[,.\u201a] ?\d{0,2}(?! ?\d)")


def _stat_value(text: str) -> int | None:
    tail = text.partition(":")[2].strip()
    found = ocr.numbers("0" if tail in ("O", "o") else tail)  # this font's 0 reads as O
    return found[0] if found else None


def _line_crop(shot: str, cy: float):
    from PIL import Image

    return Image.open(shot).convert("RGB").crop(
        (STATS_BOX[0], int(cy) - STATS_LINE, STATS_BOX[2], int(cy) + STATS_LINE))


def _stat_line(shot: str, cy: float, scale: int = 1) -> int | None:
    """The value on one Statistics line, read from a crop of that line alone
    (*scale* times its size): in a full-page read Vision now and then turns a
    lone digit into "~"."""
    from PIL import Image

    line = _line_crop(shot, cy)
    if scale != 1:
        line = line.resize((line.width * scale, line.height * scale), Image.LANCZOS)
    lines = ocr.read(line)
    return _stat_value(" ".join(ln.text for ln in sorted(lines, key=lambda ln: ln.x0)))


def _best_score(shot: str, cy: float, page: int | None) -> int | None:
    """A best score: Vision's page read once the digit shapes agree with it;
    otherwise Vision reads the line alone, as is and at twice the size, and
    the most common read wins (the shapes on a tie)."""
    from collections import Counter

    shapes = _digits(_glyphs(_line_crop(shot, cy), yellow=True))
    if shapes == page:
        return page
    reads = [r for r in (shapes, page, _stat_line(shot, cy), _stat_line(shot, cy, scale=2))
             if r is not None]
    value, votes = Counter(reads).most_common(1)[0] if reads else (None, 0)
    return value if votes >= 2 else shapes


def stats_sections(shot: str) -> list[dict]:
    """A Statistics tab in *shot*, one dict per section (TOTALS first, then
    each level on screen) with "best", "played" and "won"; None where blank.
    A level cut off by the bottom of the screen lacks the lines below it."""
    sections: list[dict] = []
    for cy, text in ocr.rows(ocr.read(shot, box=STATS_BOX)):
        low = text.lower()
        value = _stat_value(text)
        if low.startswith("best score") and "none" not in low:
            value = _best_score(shot, cy, None if CUT_SHORT.search(text) else value)
        elif ((value is None or CUT_SHORT.search(text))
                and low.startswith(("games played", "games won")) and "none" not in low):
            value = _stat_line(shot, cy)
        if low.startswith("best score"):
            sections.append({"best": value})
        elif sections and low.startswith("games played"):
            sections[-1]["played"] = value
        elif sections and low.startswith("games won"):
            sections[-1]["won"] = value
    return sections


@says(lambda name, tab="daily": f"Open Statistics, read the {tab.title()} tab, then go back "
                                "to the main menu")
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
