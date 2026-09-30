"""Masked exact-pixel comparison against the FreeCell Obj-C baselines.

``baselines/`` holds one screenshot per screen of the Obj-C build (7.42.5,
build 279) on the iPhone 15 Pro Max, portrait, 1290x2796. They are the
reference for the Unity port and are never re-baselined to Unity: a large
diff is the finding, not a reason to overwrite the reference.

A pixel differs when any colour channel moves more than ``_PIXEL_TOL``.
Three things are left out so run-to-run churn is not reported as a UI change:

  1. chrome — the iOS status bar on every screen; the cross-promo banner and
     the wood below it on screens that have the wood tray;
  2. each screen's ``ignore`` boxes in ``SCREENS`` (dealt cards, dates,
     scores, QA marks on the few screens captured after the QA unlock);
  3. a learned volatile mask, ``baselines/<Name>.volatile.png`` — pixels that
     changed across the three shots of one capture (menu sparkles, smileys;
     More Games pools the shots of both Obj-C passes).

A screen fails when the share of compared pixels that differ exceeds its
``max_diff``, or when any one changed region is larger than ``max_region``
(a missing label is too small to move the share but is one solid blob).

The iOS AssistiveTouch button is not app UI and moves between screens. It is
found by its ring profile and masked in both images when present; captures
should still be taken with AssistiveTouch off.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

import config

W, H = 1290, 2796
BASELINES = config.BASELINES

# ── masks, (x0, y0, x1, y1) in 1290x2796 screenshot pixels ─────────
STATUS_BAR = (0, 0, W, 150)          # clock, radios, battery, "◀ app" crumb
BANNER = (0, 2420, W, H)             # rotating house banner + wood below it
PAGE = (STATUS_BAR,)                 # full-page screens (Stats, Options, Help, …)
TRAY = (STATUS_BAR, BANNER)          # screens drawn above the wood tray

# QA chrome — only after the QA unlock, so only on phase B screens.
QA_BRACKETS = (30, 2115, 120, 2195)  # "[ ]" above the wood
QA_RECYCLE = (1170, 2105, 1270, 2205)
QA_BADGE = (1155, 2230, 1285, 2315)
TEST_BANNER = (925, 2350, W, 2500)   # red "Test Banner" over the tray
QA_TRAY = (QA_BRACKETS, QA_RECYCLE, QA_BADGE, TEST_BANNER)
QA_STATS = ((30, 475, 125, 550), (1175, 530, 1270, 630), TEST_BANNER)

# App content that changes between runs.
TABLEAU = (0, 800, W, 1470)          # the eight dealt columns (Easy)
DRAWER_BANNER = (0, 2380, W, H)      # the drawer's banner starts above BANNER
DAILY_MONTH = (400, 1040, 890, 1135)  # month name ("September" is the widest)
DAILY_DAYS = (70, 1290, 1220, 2010)   # day grid, room for a sixth row + today's gold date
DAILY_STAR = (560, 280, 730, 420)    # table's date star, gold only when dealt on the day
DAILY_TABLEAU = (0, 800, W, 1510)    # Daily's dealt columns (Medium runs longer than Easy)
PICKER_FAN = (240, 1660, 490, 1840)  # picker's card fan: rides the rules block's hop (y 1674-1700)
VICTORY_WON = (370, 1010, 920, 1085)  # "won 1 ✣ 0 abandoned"
VICTORY_NUMBERS = (100, 1235, 1210, 1715)  # current / rank / best columns
STATS_TOTALS = (725, 535, 1075, 830)  # best score … playtime values
STATS_EASY = (725, 995, 1075, 1435)   # Standard · Easy values

# The menu / picker labels hop one after another in a near-continuous wave,
# the "standard rules" block hops with a crown shimmer every ~4 s, sparkles
# linger, and Daily's level button / FAQ and Victory's "menu" hop too. A
# comparison takes the per-pixel median of its shots, which absorbs most of
# it; what is left shows as small blobs on those labels.
VICTORY_MENU = (1000, 290, 1290, 410)  # dim on 3 of 4 Obj-C runs, white on one

# A pixel differs if any channel of |now - base| exceeds this (0-255).
_PIXEL_TOL = 32
# Looser when learning the volatile mask, so it does not over-mask.
_VOLATILE_TOL = 22
# Changed blobs smaller than this are not boxed in the diff image.
_MIN_REGION_AREA = 120

MAX_DIFF = 0.005      # static screens
MAX_DIFF_ANIM = 0.010  # screens with sparkles / smileys / glints
MAX_REGION = 2500     # px² of one changed blob; "ABOUT" alone is ~6000


@dataclass(frozen=True)
class Screen:
    phase: str                 # "A": fresh install, QA locked; "B": after the QA win
    how: str                   # how the capture pass reaches it
    state: str                 # the app state it must be in
    tray: bool = True          # drawn above the wood tray + banner
    ignore: tuple = ()
    max_diff: float = MAX_DIFF
    max_region: int = MAX_REGION
    animated: bool = False     # long, separate loops: see build_volatile_mask
    note: str = ""             # why a mask exists, for MANIFEST.md and the report


_FRESH = "fresh install, offline, QA locked"

# In capture order. The order is load-bearing: Stats and Last Score must be
# empty, the menu's More Games badge must still read "1", and the Daily tips
# only show on the first visit.
SCREENS: dict[str, Screen] = {
    "FirstLaunchTerms": Screen(
        "A", "cold launch of a fresh install, offline",
        "Terms & Conditions card over the first menu (no banner yet)",
        tray=False, ignore=(STATUS_BAR,), max_diff=MAX_DIFF_ANIM,
        note="Menu sparkles behind the card are volatile."),
    "TermsPage": Screen(
        "A", "Terms card → \"Terms & Conditions\" link (online, pages only)",
        "in-app web view of the Terms page, top", tray=False,
        max_diff=0.02, max_region=40000,
        note="Live web content: a changed policy page is not a port bug."),
    "PrivacyPage": Screen(
        "A", "Terms card → \"Privacy Policy\" link (online, pages only)",
        "in-app web view of the Privacy page, top", tray=False,
        max_diff=0.02, max_region=40000,
        note="Live web content: a changed policy page is not a port bug."),
    "StatsSoloEmpty": Screen(
        "A", "menu → Stats", f"Solo tab, top, every value none/0 ({_FRESH})",
        tray=False),
    "StatsSoloBottom": Screen(
        "A", "Stats Solo → scrolled to the end", "Solo tab, bottom (Reset link)",
        tray=False),
    "ResetSoloDialog": Screen(
        "A", "Stats Solo bottom → Reset Solo Statistics",
        "first reset confirmation (answered No)", tray=False),
    "StatsDailyEmpty": Screen(
        "A", "Stats → Daily tab", "Daily tab, top, every value none/0",
        tray=False),
    "StatsDailyBottom": Screen(
        "A", "Stats Daily → scrolled to the end",
        "Daily tab, bottom (Reset link)", tray=False),
    "MainMenu": Screen(
        "A", "back to the menu, banner drawn",
        "menu before More Games is visited (badge \"1\") and before any win",
        max_diff=MAX_DIFF_ANIM, note="Sparkle glints are volatile."),
    "AboutTop": Screen(
        "A", "menu → ABOUT", "About, version 7.42.5 (the page does not scroll)",
        tray=False),
    "AdFreePrompt": Screen(
        "A", "About → ad free version", "iOS alert No / Yes (answered No)",
        tray=False),
    "FeedbackAlert": Screen(
        "A", "About → submit feedback",
        "iOS alert Cancel / Write Email (answered Cancel)", tray=False),
    "AboutVersion": Screen(
        "A", "About → tap the version line",
        "About with \"279 build 60706F\" in place of the version", tray=False),
    "FAQTop": Screen(
        "A", "About → frequently asked questions", "FAQ, General tab, top",
        tray=False),
    "FAQBottom": Screen(
        "A", "FAQ → scrolled to the end", "FAQ, General tab, bottom",
        tray=False),
    "FAQSolo": Screen(
        "A", "FAQ → Solo tab", "FAQ, Solo tab, top", tray=False),
    "FAQDaily": Screen(
        "A", "FAQ → Daily tab", "FAQ, Daily tab, top", tray=False),
    "HelpTop": Screen("A", "menu → Help", "Help, top", tray=False),
    "HelpMid": Screen(
        "A", "Help → one slow 900 px drag", "Help, part way down", tray=False,
        note="Offset set by a slow drag without a fling."),
    "HelpBottom": Screen(
        "A", "Help → scrolled to the end", "Help, bottom", tray=False),
    "OptionsTop": Screen(
        "A", "menu → Options", "Options, top, defaults", tray=False),
    "OptionsMid": Screen(
        "A", "Options → one slow 900 px drag", "Options, part way down",
        tray=False, note="Offset set by a slow drag without a fling."),
    "OptionsBottom": Screen(
        "A", "Options → scrolled to the end", "Options, bottom", tray=False),
    "ChooseLookSurface": Screen(
        "A", "menu → Choose Look", "Surface tab, default look (1 / 1)",
        max_diff=MAX_DIFF_ANIM),
    "ChooseLookCards": Screen(
        "A", "Choose Look → Cards tab", "Cards tab, default look (1 / 1)",
        max_diff=MAX_DIFF_ANIM),
    "PlayPicker": Screen(
        "A", "menu → Play", "difficulty picker, no paused game (no Resume)",
        ignore=(PICKER_FAN,), max_diff=MAX_DIFF_ANIM,
        note="The card fan hops with the rules block; it is masked. The "
        "difficulty spades hop with their labels (a small box there is Obj-C "
        "motion)."),
    "LastScoreNotice": Screen(
        "A", "Play → LAST SCORE", "\"No game has been completed yet\" card",
        tray=False, max_diff=MAX_DIFF_ANIM),
    "LastScore": Screen(
        "A", "Last Score → dismiss the card",
        "Last Won Game Score, empty (Week of Jan 1, 1970)", tray=False,
        max_diff=MAX_DIFF_ANIM, note="Thumbs-up sparkle is volatile. The two "
        "period arrows slide (a small box on either is Obj-C motion)."),
    "TableDeal": Screen(
        "A", "Play → Easy", "fresh Easy table, untouched (tap a card to start, "
        "0:00, X98), Rich Features + Rank Strip on", ignore=(TABLEAU,),
        max_diff=MAX_DIFF_ANIM, note="Dealt cards masked; foundations (3s) and "
        "HUD are deterministic."),
    "TableDrawer": Screen(
        "A", "table → menu", "table drawer open", ignore=(TABLEAU, DRAWER_BANNER),
        max_diff=MAX_DIFF_ANIM, note="Dealt cards and the drawer banner masked."),
    "PlayPickerResume": Screen(
        "A", "table → back → Play", "picker with the Resume ribbon (paused game)",
        ignore=(PICKER_FAN,), max_diff=MAX_DIFF_ANIM,
        note="The card fan hops with the rules block; it is masked."),
    "AbandonPrompt": Screen(
        "A", "picker with a paused game → Easy",
        "iOS alert: abandon the paused game? (answered Yes)",
        ignore=(PICKER_FAN,), max_diff=MAX_DIFF_ANIM,
        note="The card fan hops with the rules block; it is masked."),
    "TableRichOff": Screen(
        "A", "table → menu → options → Rich Features OFF → back",
        "Easy table without timer / score / multiplier / moves",
        ignore=(TABLEAU,), max_diff=MAX_DIFF_ANIM),
    "TableRankStripOff": Screen(
        "A", "table → menu → options → Rank Strip OFF → back",
        "Easy table without the rank strip (Rich Features back on)",
        ignore=(TABLEAU,), max_diff=MAX_DIFF_ANIM),
    "DailyTutorial1": Screen(
        "A", "menu → Daily (first visit)", "first Daily tip over the calendar",
        ignore=(DAILY_MONTH, DAILY_DAYS), max_diff=MAX_DIFF_ANIM,
        note="Calendar dates masked."),
    "DailyTutorial2": Screen(
        "A", "Daily tip 1 → tap", "second Daily tip over the calendar",
        ignore=(DAILY_MONTH, DAILY_DAYS), max_diff=MAX_DIFF_ANIM,
        note="Calendar dates masked."),
    "DailyCalendar": Screen(
        "A", "Daily tip 2 → tap", "Daily calendar, Medium",
        ignore=(DAILY_MONTH, DAILY_DAYS), max_diff=MAX_DIFF_ANIM,
        note="Month and dates masked."),
    "DailyTable": Screen(
        "A", "Daily calendar → day 1 of the month (date in capture.json)",
        "untouched Daily table for that date, Medium",
        ignore=(DAILY_TABLEAU, DAILY_STAR), max_diff=MAX_DIFF_ANIM,
        note="Cards masked: the same date and level dealt different cards on "
        "two installs. The star is masked: it is gold only when that date is "
        "today."),
    "MoreGamesTop": Screen(
        "A", "menu → More Games", "More Games stage, top", tray=False,
        max_diff=MAX_DIFF_ANIM, animated=True,
        note="Game items animate on long, separate loops; their mask is "
        "learned from every shot of both Obj-C passes."),
    "MoreGamesScrolled": Screen(
        "A", "More Games → scrolled to the end", "More Games stage, bottom",
        tray=False, max_diff=MAX_DIFF_ANIM, animated=True,
        note="Game items animate on long, separate loops; their mask is "
        "learned from every shot of both Obj-C passes."),
    "Victory": Screen(
        "B", "QA unlock → Play → Easy → Complete Game (90-99)",
        "victory / ranking for This Week",
        ignore=(VICTORY_WON, VICTORY_NUMBERS) + QA_TRAY,
        max_diff=MAX_DIFF_ANIM,
        note="Score, time, moves, rank and QA marks masked. back / menu were "
        "dim on 3 of 4 Obj-C runs and white on one (cause unknown), so a "
        "brightness-only change to those two is not by itself a port bug. "
        "The thumbs-up bounces (a small box on it is Obj-C motion)."),
    "MainMenuAfterWin": Screen(
        "B", "victory → back, QA turned off again",
        "menu after a completed game (promo icons, no badge)",
        max_diff=MAX_DIFF_ANIM, note="Sparkle glints are volatile."),
    "StatsSoloAfterWin": Screen(
        "B", "menu → Stats", "Solo tab, top, one Easy win", tray=False,
        ignore=(STATS_TOTALS, STATS_EASY) + QA_STATS,
        note="Values masked (they follow the synthetic win)."),
}


def exclusions(name: str) -> tuple:
    screen = SCREENS[name]
    chrome = TRAY if screen.tray else PAGE
    return tuple(chrome) + tuple(screen.ignore)


# ── AssistiveTouch ─────────────────────────────────────────────────
# Measured on this phone: a disc of radius ~43 with ring edges at ~55, ~65 and
# ~90. Each ring is darker than the one inside it, whatever the background.
_AT_BOX = 100


def _ring(grey, cx, cy, r0, r1):
    values = []
    for r in range(r0, r1 + 1):
        angles = np.linspace(0, 2 * np.pi, max(24, int(2 * np.pi * r / 3)),
                             endpoint=False)
        xs = np.round(cx + r * np.cos(angles)).astype(int)
        ys = np.round(cy + r * np.sin(angles)).astype(int)
        ok = (xs >= 0) & (xs < grey.shape[1]) & (ys >= 0) & (ys < grey.shape[0])
        values.append(grey[ys[ok], xs[ok]])
    v = np.concatenate(values)
    return float(v.mean()), float(v.std())


def assistive_touch(grey) -> list:
    """Boxes around every AssistiveTouch button found in a greyscale frame."""
    blurred = cv2.medianBlur(grey, 5)
    circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=60,
                               param1=40, param2=14, minRadius=38, maxRadius=48)
    if circles is None:
        return []
    g = grey.astype(np.float32)
    boxes = []
    for x, y, _r in circles[0]:
        x, y = int(x), int(y)
        disc, spread = _ring(g, x, y, 5, 36)
        ring1, _ = _ring(g, x, y, 47, 52)
        ring2, _ = _ring(g, x, y, 58, 62)
        ring3, _ = _ring(g, x, y, 70, 84)
        if (spread < 6 and 28 <= disc - ring1 <= 52
                and 10 <= ring1 - ring2 <= 26 and 8 <= ring2 - ring3 <= 32):
            boxes.append((x - _AT_BOX, y - _AT_BOX, x + _AT_BOX, y + _AT_BOX))
    return boxes


# ── engine ─────────────────────────────────────────────────────────
def grey(path):
    if not Path(path).is_file():
        return None
    img = cv2.imread(str(path))
    return None if img is None else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def mask(shape, ignore) -> np.ndarray:
    """True where pixels are compared."""
    m = np.ones(shape[:2], dtype=bool)
    h, w = shape[:2]
    for x0, y0, x1, y1 in ignore:
        m[max(0, y0):min(h, y1), max(0, x0):min(w, x1)] = False
    return m


def volatile_path(name: str, base_dir: Path = None) -> Path:
    return Path(base_dir or BASELINES) / f"{name}.volatile.png"


def load_volatile(name: str, shape, base_dir: Path = None) -> np.ndarray:
    path = volatile_path(name, base_dir)
    v = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE) if path.exists() else None
    if v is None:
        return np.zeros(shape[:2], dtype=bool)
    if v.shape != shape[:2]:
        v = cv2.resize(v, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return v > 127


def _grey_stack(shots):
    greys = [g for g in (grey(s) for s in shots) if g is not None]
    if len(greys) < 2 or any(g.shape != greys[0].shape for g in greys):
        return None
    return np.stack(greys).astype("int16")


def typical_shot(shots) -> int:
    """Index of the shot closest to the per-pixel median of all *shots*.

    A glint or the tail of a transition shows in one shot only, so this is
    the shot with the least of either in it.
    """
    stack = _grey_stack(shots)
    if stack is None:
        return 0
    med = np.median(stack, axis=0)
    return int(np.argmin(np.abs(stack - med).sum(axis=(1, 2))))


def build_volatile_mask(shots, pick: int = None, span: bool = False):
    """Pixels a comparison must not trust, learned from several shots.

    Motion that shows in most shots (bouncing smileys) is a pixel off the
    per-pixel median in at least two shots; to that is added whatever glint
    is baked into the picked baseline shot itself. A glint in one other shot
    is neither: the median of the capture under test drops it just as the
    median here does, so it must not mask a label it crossed.

    ``span`` masks every pixel that differs anywhere across *shots* — for
    screens whose items loop so slowly that three shots of one pass see a
    single phase of each (More Games); pass it shots from several passes.
    """
    stack = _grey_stack(shots)
    if stack is None:
        return None
    if span:
        vol = (stack.max(axis=0) - stack.min(axis=0)) > _VOLATILE_TOL
    else:
        off = np.abs(stack - np.median(stack, axis=0)) > _VOLATILE_TOL
        vol = off.sum(axis=0) >= 2
        if pick is not None:
            vol |= off[pick]
    return _dilate(vol)


def _dilate(vol):
    vol = vol.astype("uint8") * 255
    return cv2.dilate(vol, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))


def changed_map(cur, base, compared):
    diff = cv2.absdiff(cur, base)
    if diff.ndim == 3:
        # per channel: a label tinted blue barely moves its grey value
        diff = diff.max(axis=2)
    changed = ((diff > _PIXEL_TOL) & compared).astype("uint8") * 255
    # 2x2, not 3x3: a label moved 2 px changes only 2 px strips along its
    # edges, and a 3x3 opening erased them all
    changed = cv2.morphologyEx(changed, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
    return cv2.morphologyEx(changed, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))


def regions(changed, min_area=_MIN_REGION_AREA):
    """[(area, (x, y, w, h))] of changed blobs, largest first."""
    contours, _ = cv2.findContours(changed, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    boxes = [(cv2.contourArea(c), cv2.boundingRect(c)) for c in contours]
    return sorted([b for b in boxes if b[0] >= min_area],
                  key=lambda b: b[0], reverse=True)


def capture_shots(capture_dir: Path, name: str, shot: int = None) -> list:
    """[<Name>.png], or every <Name>_<n>.png of a multi-shot capture folder."""
    capture_dir = Path(capture_dir)
    if shot:
        return [capture_dir / f"{name}_{shot}.png"]
    plain = capture_dir / f"{name}.png"
    if plain.exists():
        return [plain]
    numbered = [p for p in capture_dir.glob(f"{name}_*.png")
                if p.stem[len(name) + 1:].isdigit()]
    return sorted(numbered, key=lambda p: int(p.stem[len(name) + 1:]))


def load_capture(shots):
    """The BGR frame to compare: the per-pixel median of several shots, so a
    glint or a late transition in one of them is not reported as a change."""
    imgs = [cv2.imread(str(s)) for s in shots if Path(s).is_file()]
    imgs = [i for i in imgs if i is not None]
    if not imgs:
        return None
    if len(imgs) < 3 or any(i.shape != imgs[0].shape for i in imgs):
        return imgs[len(imgs) // 2]
    return np.median(np.stack(imgs), axis=0).astype("uint8")


def compare(name: str, capture, base_dir: Path = None,
            extra_ignore=(), diff_dir: Path = None, label: str = "capture"):
    """Compare one capture (a PNG, or a list of shots) with its baseline.

    Writes the diff image when asked. status: ok | no-capture | no-baseline |
    size. ``passed`` is only set when status is ok.
    """
    base_dir = Path(base_dir or BASELINES)
    screen = SCREENS[name]
    shots = [capture] if isinstance(capture, (str, Path)) else list(capture)
    result = {"name": name, "status": "ok", "diff_pct": None, "passed": None,
              "max_diff_pct": screen.max_diff * 100,
              "max_region": screen.max_region, "shots": len(shots),
              "capture": str(shots[len(shots) // 2]) if shots else ""}
    frame = load_capture(shots)
    cur = None if frame is None else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    base = grey(base_dir / f"{name}.png")
    if cur is None:
        result["status"] = "no-capture"
        return result
    if base is None:
        result["status"] = "no-baseline"
        return result
    if cur.shape != base.shape:
        result["status"] = "size"
        result["sizes"] = (cur.shape[::-1], base.shape[::-1])
        return result

    at = assistive_touch(cur) + assistive_touch(base)
    compared = mask(cur.shape, exclusions(name) + tuple(extra_ignore) + tuple(at))
    compared &= ~load_volatile(name, cur.shape, base_dir)
    changed = changed_map(frame, cv2.imread(str(base_dir / f"{name}.png")),
                          compared)
    total = int(compared.sum())
    changed_px = int((changed > 0).sum())
    frac = changed_px / total if total else 0.0
    blobs = regions(changed)
    largest = int(blobs[0][0]) if blobs else 0
    result.update({
        "diff_pct": frac * 100,
        "largest_region": largest,
        "regions": len(blobs),
        "assistive_touch": [list(b) for b in at],
        "has_volatile": volatile_path(name, base_dir).exists(),
        "passed": frac <= screen.max_diff and largest <= screen.max_region,
    })
    if diff_dir:
        result["diff"] = str(write_diff(name, frame, base_dir, changed,
                                        compared, frac, Path(diff_dir), label))
    return result


def _label(img, line1, line2=""):
    bar = np.full((110, img.shape[1], 3), 30, dtype="uint8")
    cv2.putText(bar, line1, (28, 46), cv2.FONT_HERSHEY_SIMPLEX, 1.3,
                (255, 255, 255), 3, cv2.LINE_AA)
    if line2:
        cv2.putText(bar, line2, (28, 92), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (120, 220, 255), 2, cv2.LINE_AA)
    return np.vstack([bar, img])


def write_diff(name, cur, base_dir, changed, compared, frac, diff_dir,
               label="capture") -> Path:
    """diff_<Name>.png: baseline | capture with changed pixels red and boxed.

    *cur* is the BGR frame that was compared. Areas that were not compared
    are dimmed on both halves.
    """
    base = cv2.imread(str(Path(base_dir) / f"{name}.png"))
    vis = cv2.dilate(changed, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    annotated = cur.copy()
    red = annotated.copy()
    red[vis > 0] = (0, 0, 255)
    annotated = cv2.addWeighted(red, 0.55, annotated, 0.45, 0)
    for _area, (x, y, w, h) in regions(changed):
        cv2.rectangle(annotated, (x - 3, y - 3), (x + w + 3, y + h + 3),
                      (0, 255, 255), 4)
    annotated[~compared] = (annotated[~compared] * 0.55).astype("uint8")
    shaded = base.copy()
    shaded[~compared] = (shaded[~compared] * 0.55).astype("uint8")
    combo = np.hstack([
        _label(shaded, f"Obj-C {config.OBJC_VERSION} baseline", name),
        _label(annotated, label, f"{frac * 100:.2f}% of compared pixels differ"),
    ])
    diff_dir.mkdir(parents=True, exist_ok=True)
    out = diff_dir / f"diff_{name}.png"
    cv2.imwrite(str(out), combo)
    return out


def exit_if_nothing_compared(results, capture_dir, how: str) -> None:
    """Exit 2 with the reason when no screen could be compared at all."""
    if any(r["status"] == "ok" for r in results):
        return
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    reason = max(counts, key=counts.get) if counts else "no-capture"
    print("\n  NOTHING WAS COMPARED — this run proved nothing.\n")
    if reason == "size":
        print(f"  Every capture in\n      {capture_dir}\n  is a different pixel "
              f"size from its baseline ({W}x{H}). Capture on an iPhone 15 Pro "
              "Max in portrait;\n  screenshots are never rescaled to fit.")
    elif reason == "no-baseline":
        print(f"  The baselines are missing from\n      {BASELINES}\n  They are "
              "committed to this repo — the checkout is incomplete, or BASELINES "
              "points elsewhere.")
    else:
        print(f"  No captures were found in:\n      {capture_dir}\n")
        print("  Captures are shot from the device into log/, which is "
              "git-ignored.\n")
        print(f"  To make them:\n      {how}")
    sys.exit(2)
