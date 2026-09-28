"""Template-driven FreeCell UI primitives.

This module intentionally starts with no Spider coordinates or crops. The
capture walkthrough populates ``assets/`` after the FreeCell build is observed
on the target device.
"""
from __future__ import annotations

import os
import random
import time
from pathlib import Path

from airtest.core.api import exists, text
from airtest.core.cv import Template
from airtest.core.settings import Settings as ST

import config
import helpers

# Template-only matching. SIFT/BRISK is slow and false-matches About's emblem
# to the menu crown.
ST.CVSTRATEGY = ["tpl"]
ST.FIND_TIMEOUT_TMP = 0.5

THRESHOLD = 0.72

MENU_ITEMS = (
    "menu_play",
    "menu_daily",
    "menu_stats",
    "menu_options",
    "menu_help",
    "menu_about",
    "more_games",
    "choose_look",
)
DIFFICULTIES = ("easy", "medium", "hard", "expert", "master")

# Names are semantic FreeCell controls. Their PNGs are created only from
# FreeCell captures; a missing crop is an explicit setup failure.
SCREENS = {
    "menu": "screen_menu",
    "play": "screen_play",
    "stats": "screen_stats",
    "options": "screen_options",
    "help": "screen_help",
    "about": "screen_about",
    "more_games": "screen_more_games",
    "choose_look": "screen_choose_look",
    "daily": "screen_daily",
    "table": "screen_table",
    "victory": "screen_victory",
}


FIRST_LAUNCH_GATES = (
    "terms & conditions",
    "terms and conditions",
    "must agree",
    "privacy policy",
)

# Screenshot-pixel targets on the 1290x2796 Synthetic Win panel.
QA_SELECT_90_99 = (1080, 1760)
QA_WIN = (685, 1770)

_OFFLINE: bool | None = None


def asset(name: str) -> Path:
    return config.ASSETS / f"{name}.png"


def have(name: str) -> bool:
    return asset(name).exists()


def find(name: str):
    path = asset(name)
    if not path.exists():
        raise FileNotFoundError(
            f"missing FreeCell asset {path}; capture and crop the FreeCell screen first"
        )
    return exists(Template(str(path), threshold=THRESHOLD))


def is_on(name: str) -> bool:
    if not have(name):
        return False
    return bool(find(name))


def wait_for(name: str, timeout: float = 15.0) -> bool:
    return seen(name, timeout=timeout)


def seen(name: str, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_on(name):
            return True
        time.sleep(0.25)
    return False


def tap(name: str, settle: float = 1.0) -> bool:
    if not have(name):
        return False
    point = find(name)
    if not point:
        return False
    helpers.tap(point, settle=settle)
    return True


def expect_screen(screen: str, timeout: float = 15.0) -> bool:
    return wait_for(SCREENS[screen], timeout)


def on_menu(timeout: float = 3.0) -> bool:
    if is_on("look_close"):
        return False
    return expect_screen("menu", timeout=timeout)


def expect(cond, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def shoot(name: str) -> Path:
    return helpers.screenshot(name)


def back(settle: float = 1.4) -> bool:
    """Leave the current page via the top-left back control."""
    if tap("daily_back", settle=settle):
        return True
    if tap("page_back", settle=settle):
        return True
    if tap("back_game", settle=settle):
        return True
    helpers.wda_tap((140, 250), settle=settle)
    return True


def leave_daily(settle: float = 1.6) -> bool:
    """Close the Daily calendar if it is up."""
    if not (is_on("screen_daily") or is_on("daily_back")):
        return False
    if tap("daily_back", settle=settle):
        return True
    if tap("page_back", settle=settle):
        return True
    helpers.wda_tap((140, 250), settle=settle)
    return True


def leave_stats(settle: float = 1.4) -> bool:
    """Close Statistics via its own back control — never the menu Daily button."""
    if not expect_screen("stats", timeout=0.8):
        return False
    if tap("page_back", settle=settle):
        return True
    helpers.wda_tap((140, 250), settle=settle)
    return True


def to_menu(timeout: float = 12.0) -> bool:
    """Return to the main menu without a cold launch if possible."""
    if is_on("look_close"):
        tap("look_close", settle=1.2)
    if leave_stats():
        if on_menu(2.0):
            return True
    leave_daily()
    if on_menu(1.0):
        return True
    deadline = time.time() + timeout
    while time.time() < deadline:
        if expect_screen("stats", timeout=0.6):
            leave_stats()
        else:
            leave_daily()
            back()
        clear_overlays()
        if on_menu(1.5):
            return True
    return launch_to_menu()


def start_deal() -> None:
    """Dismiss 'tap a card to start' so Synthetic Win and hints can fire."""
    helpers.wda_tap((180, 980), settle=1.1)


def open_qa_panel() -> bool:
    """Open the table Synthetic Win card (badge or drawer QA)."""
    if is_on("qa_panel"):
        return True
    if tap("qa_badge", settle=1.2) and wait_for("qa_panel", timeout=4.0):
        return True
    helpers.wda_tap((1140, 350), settle=1.2)
    helpers.wda_tap((1180, 2280), settle=1.5)
    return wait_for("qa_panel", timeout=4.0)


def clear_overlays(rounds: int = 6) -> int:
    """Dismiss first-launch T&C then ATT. Gates arrive in sequence."""
    cleared = 0
    for _ in range(rounds):
        did = False
        if is_on("tc_continue"):
            did = tap("tc_continue", settle=2.0)
        if not did and is_on("att_prompt"):
            did = tap("att_allow", settle=1.5)
        if not did:
            alert = helpers.alert_text().lower()
            if alert and any(gate in alert for gate in FIRST_LAUNCH_GATES):
                did = helpers.accept_alert()
        if not did:
            break
        cleared += 1
        time.sleep(0.8)
    return cleared


def close_web_page() -> bool:
    """Close an in-app policy webview and return to the Terms card."""
    if have("tc_web_close") and tap("tc_web_close", settle=2.0):
        return True
    helpers.wda_tap((80, 180), settle=1.8)
    return True


def cold_launch() -> bool:
    """Terminate + relaunch, sweeping first-launch gates twice."""
    helpers.terminate()
    time.sleep(1.5)
    helpers.connect()
    helpers.launch_app(force=True)
    clear_overlays()
    if on_menu(6.0):
        return True
    time.sleep(2.0)
    clear_overlays()
    return on_menu(10.0)


def offline(restore: bool = True) -> bool:
    """Enable Airplane Mode and turn Wi-Fi off. True when both succeed."""
    global _OFFLINE
    ok = helpers.set_network(False, restore=restore)[0]
    if ok:
        _OFFLINE = True
    return ok


def ensure_offline() -> bool:
    """Go offline unless SKIP_OFFLINE=1 or the radios are already off."""
    global _OFFLINE
    if os.environ.get("SKIP_OFFLINE") == "1":
        return True
    if _OFFLINE is True:
        return True
    return offline()


def launch_to_menu(force: bool = False) -> bool:
    """Foreground FreeCell on the main menu, clearing first-launch gates."""
    if not ensure_offline():
        print("could not take the device offline — refusing to start "
              "while ads can fire", flush=True)
        return False
    helpers.connect()
    helpers.launch_app(force=force)
    clear_overlays()
    if on_menu(3.0):
        return True
    leave_daily()
    if on_menu(3.0):
        return True
    if is_on("back_game"):
        tap("back_game")
        if on_menu(4.0):
            return True
    time.sleep(2.5)
    clear_overlays()
    leave_daily()
    if on_menu(4.0):
        return True
    return cold_launch()


def open_dev_panel() -> bool:
    """Enable QA mode through FreeCell's confirmed hidden flow."""
    if is_on("qa_watermark"):
        return True
    if not is_on("about_emblem"):
        if not tap("menu_about"):
            return False
        if not expect_screen("about"):
            return False
    if not tap("about_version"):
        return False
    point = find("about_emblem")
    if not point:
        return False
    helpers.rapid_tap(point, times=config.QA_TAPS)
    text(config.QA_CODE, enter=False)
    return wait_for("qa_watermark")


def enter_qa_code() -> bool:
    """Enter the configured QA code using named keypad crops."""
    for digit in config.QA_CODE:
        if not tap(f"qa_digit_{digit}", settle=0.1):
            return False
    return wait_for("qa_panel")


def complete_game() -> bool:
    """Complete the active table through the Synthetic Win panel."""
    start_deal()
    if not open_qa_panel():
        return False
    if not is_on("qa_90_99") or not is_on("qa_win"):
        return False
    helpers.wda_tap(QA_SELECT_90_99, settle=1.0)
    helpers.wda_tap(QA_WIN, settle=0.2)
    time.sleep(3.0)
    return expect_screen("victory")


def start_game(level: str = "easy") -> bool:
    """Open Play, choose a FreeCell level, and accept an abandon prompt."""
    if not tap("menu_play"):
        return False
    if not wait_for(f"difficulty_{level}"):
        return False
    if not tap(f"difficulty_{level}", settle=2.0):
        return False
    helpers.accept_alert()
    return expect_screen("table", timeout=12.0)


def at_table(timeout: float = 12.0) -> bool:
    """True when the gameplay table is showing (header or table back)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_on("screen_table") or is_on("back_game"):
            return True
        time.sleep(0.35)
    return False


def relaunch_after_kill() -> bool:
    """Launch the killed app. Does not steer to the menu — the table must come back."""
    helpers.connect()
    helpers.launch_app(force=True)
    clear_overlays()
    return True


# ── Statistics ─────────────────────────────────────────────────────
STATS_SOLO_TAB = (280, 430)
STATS_DAILY_TAB = (900, 430)
RESET_YES = (875, 1650)
VICTORY_SCORE = (40, 1240, 520, 1380)


def scroll(down: bool = True, duration: float = 0.55) -> None:
    """Swipe the Stats list. down=True swipes up so the BOTTOM of the page comes in."""
    from airtest.core.api import swipe

    if down:
        swipe((645, 2300), (645, 600), duration=duration)
    else:
        swipe((645, 600), (645, 2300), duration=duration)
    time.sleep(0.5)


def scroll_to(name: str, max_swipes: int = 10) -> bool:
    return scroll_to_bottom(name, max_swipes=max_swipes)


def scroll_to_bottom(name: str = "reset_solo_stats", max_swipes: int = 20) -> bool:
    """Swipe up until Reset Solo Statistics (the Solo footer) is on screen."""
    for n in range(max_swipes):
        if is_on(name):
            return True
        print(f"  scrolling to the bottom of Solo ({n + 1}/{max_swipes})",
              flush=True)
        scroll(True)
    return is_on(name)


def open_stats() -> bool:
    """Open Statistics from the main menu. Taps Stats only — never Play or Daily."""
    if expect_screen("stats", timeout=1.0):
        return True
    if not on_menu(8.0):
        return False
    if not tap("menu_stats", settle=2.2):
        return False
    return expect_screen("stats")


def open_stats_tab(tab: str) -> bool:
    name = "stats_solo_tab" if tab == "solo" else "stats_daily_tab"
    point = STATS_SOLO_TAB if tab == "solo" else STATS_DAILY_TAB
    if have(name) and tap(name, settle=1.0):
        return True
    helpers.wda_tap(point, settle=1.0)
    return True


def stats_are_default() -> bool:
    """True when Solo shows the empty totals and Easy has no best score."""
    return is_on("stats_best_zero") and is_on("stats_easy_none")


def _tap_reset_yes() -> bool:
    """Tap Yes on the current reset popup. Never the main-menu Daily button."""
    time.sleep(0.5)
    if have("reset_yes") and tap("reset_yes", settle=1.6):
        return True
    alert = helpers.alert_text().lower()
    if alert:
        helpers.accept_alert()
        time.sleep(0.8)
        return True
    helpers.wda_tap(RESET_YES, settle=1.6)
    return True


def confirm_reset() -> bool:
    """Two Yes popups. After the second, wait for the main menu — tap nothing else."""
    if not _tap_reset_yes():
        return False
    time.sleep(0.8)
    if not _tap_reset_yes():
        return False
    print("  waiting for the main menu after both Yes", flush=True)
    return on_menu(10.0)


def reset_solo_stats() -> bool:
    """Swipe up to Reset Solo Statistics, Yes both popups, wait for the menu.

    Does not tap Play, Daily, or Stats — the caller opens Stats from the menu.
    """
    if not expect_screen("stats", timeout=1.5):
        return False
    open_stats_tab("solo")
    if not scroll_to_bottom("reset_solo_stats", max_swipes=20):
        return False
    if not tap("reset_solo_stats", settle=1.5):
        return False
    return confirm_reset()


def victory_score_crop():
    """Crop the victory screen's current-score digits (same run, not a fixed number)."""
    from PIL import Image

    frame = helpers.screenshot("_victory_frame")
    path = config.LOG / "victory_score_crop.png"
    Image.open(frame).crop(VICTORY_SCORE).save(path)
    return path


def _ink_mask(image):
    import numpy as np

    pixels = np.asarray(image.convert("RGB"))
    return (pixels.max(axis=2) > 170).astype("uint8") * 255


def score_on_stats(score_path, screen_path=None, threshold: float = 0.72) -> float:
    """How well the victory score's digit shapes appear on the Stats page.

    Victory draws the number in cyan, Solo draws it in gold, so this matches
    the ink mask at several scales rather than the raw colour.
    """
    import cv2
    import numpy as np
    from PIL import Image

    needle = _ink_mask(Image.open(score_path))
    hay_img = Image.open(screen_path) if screen_path else Image.open(
        helpers.screenshot("_stats_frame")
    )
    hay = _ink_mask(hay_img)
    if needle.size == 0 or hay.size == 0:
        return 0.0
    best = 0.0
    for scale in (0.38, 0.44, 0.50, 0.56, 0.62, 0.70, 0.80, 1.00):
        width = max(8, int(needle.shape[1] * scale))
        height = max(8, int(needle.shape[0] * scale))
        if height >= hay.shape[0] or width >= hay.shape[1]:
            continue
        sized = cv2.resize(needle, (width, height), interpolation=cv2.INTER_NEAREST)
        result = cv2.matchTemplate(hay, sized, cv2.TM_CCOEFF_NORMED)
        best = max(best, float(result.max()))
        if best >= threshold:
            return best
    return best


# ── Choose Look ────────────────────────────────────────────────────
# Measured on the 1290x2796 iPhone. Surface is 3x3, Cards is 2x3. The
# selected swatch draws a white rounded frame, which is how "current"
# is read. Pattern-only neighbours (teal vs teal-diamond) are almost
# the same colour, so a random pick also requires a colour gap.
LOOK_SURFACE_TAB = (280, 780)
LOOK_CARDS_TAB = (900, 780)
LOOK_CLOSE = (1180, 760)
LOOK_ICON = (210, 1930)
LOOK_SURFACE = (
    (210, 1040), (560, 1040), (920, 1040),
    (210, 1240), (560, 1240), (920, 1240),
    (210, 1400), (560, 1400), (920, 1400),
)
LOOK_CARDS = (
    (210, 1080), (560, 1080), (920, 1080),
    (210, 1380), (560, 1380), (920, 1380),
)
LOOK_PICK_MIN = 0.12
_LOOK_FLAT = 25
_FELT_BANDS = (0.58, 0.62, 0.52, 0.68)
_FELT_H = 0.05
_FELT_X = (0.12, 0.88)
_HINT_BACK = (1020, 2280)


def screen_rgb():
    """Current device frame as an RGB numpy array."""
    import numpy as np
    from PIL import Image

    return np.asarray(Image.open(helpers.screenshot("_look_frame")).convert("RGB"))


def colour_dist(a, b) -> float:
    """Hue distance after brightness is divided out."""
    sa, sb = float(sum(a)) or 1.0, float(sum(b)) or 1.0
    return float(sum(abs(float(x) / sa - float(y) / sb) for x, y in zip(a, b)))


def colour_text(c) -> str:
    return "[" + " ".join(f"{int(round(v)):3d}" for v in c) + "]"


def _patch(img, y0, y1, x0, x1, flat: float | None = None):
    import numpy as np

    h, w = img.shape[:2]
    y0, y1 = max(0, y0), min(h, y1)
    x0, x1 = max(0, x0), min(w, x1)
    if y1 <= y0 or x1 <= x0:
        return None
    pixels = np.asarray(img[y0:y1, x0:x1], dtype=float).reshape(-1, 3)
    if pixels.size == 0:
        return None
    if flat is not None and pixels.std(axis=0).max() > flat:
        return None
    return pixels.mean(axis=0)


def look_centres(tab: str):
    return LOOK_SURFACE if tab == "surface" else LOOK_CARDS


def look_colour_at(img, centre, radius: int = 28):
    cx, cy = centre
    return _patch(img, cy - radius, cy + radius, cx - radius, cx + radius)


def look_selected(tab: str, img=None) -> int:
    """1-based index of the white-framed palette, or 0 if none is marked."""
    img = screen_rgb() if img is None else img
    offsets = ((0, -56), (0, 72), (-130, 0), (130, 0)) if tab == "surface" else (
        (0, -100), (0, 110), (-90, 0), (90, 0),
    )
    h, w = img.shape[:2]
    for index, (cx, cy) in enumerate(look_centres(tab), 1):
        hits = 0
        for dx, dy in offsets:
            x, y = cx + dx, cy + dy
            if 0 <= y < h and 0 <= x < w and float(img[y, x].mean()) > 210:
                hits += 1
        if hits >= 2:
            return index
    return 0


def open_choose_look(settle: float = 2.0) -> bool:
    """Open the Choose Look modal. Falls back to the icon coordinate."""
    if is_on("look_close"):
        return True
    if tap("choose_look", settle=settle) and seen("look_close", timeout=5.0):
        return True
    helpers.wda_tap(LOOK_ICON, settle=settle)
    return seen("look_close", timeout=5.0)


def open_look_tab(tab: str, settle: float = 1.4) -> bool:
    """Show Surface or Cards. Template first, then the measured tab tap."""
    name = "look_surface_tab" if tab == "surface" else "look_cards_tab"
    point = LOOK_SURFACE_TAB if tab == "surface" else LOOK_CARDS_TAB
    if have(name) and tap(name, settle=settle):
        return True
    helpers.wda_tap(point, settle=settle)
    return True


def close_choose_look(settle: float = 1.2) -> bool:
    if tap("look_close", settle=settle):
        return True
    helpers.wda_tap(LOOK_CLOSE, settle=settle)
    return not is_on("look_close")


def look_pick(tab: str, n: int, settle: float = 1.6):
    """Tap palette *n* (1-based) on the open tab. Returns its RGB colour."""
    centres = look_centres(tab)
    if n < 1 or n > len(centres):
        return None
    img = screen_rgb()
    colour = look_colour_at(img, centres[n - 1])
    helpers.wda_tap(centres[n - 1], settle=settle)
    return colour


def look_pick_other(tab: str, rng: random.Random | None = None):
    """Tap a random palette that is not the current one, and not the same colour.

    Returns (tapped_index, current_colour, new_colour). Current is the
    white-framed swatch when that ring is visible, otherwise the first.
    """
    rng = rng or random.Random()
    img = screen_rgb()
    centres = look_centres(tab)
    colours = [look_colour_at(img, centre) for centre in centres]
    current = look_selected(tab, img)
    if current < 1:
        current = 1
    current_colour = colours[current - 1]
    choices = [
        index
        for index, colour in enumerate(colours, 1)
        if index != current
        and colour is not None
        and current_colour is not None
        and colour_dist(colour, current_colour) >= LOOK_PICK_MIN
    ]
    if not choices:
        choices = [index for index in range(1, len(centres) + 1) if index != current]
    if not choices:
        return None
    picked = rng.choice(choices)
    helpers.wda_tap(centres[picked - 1], settle=1.6)
    return picked, current_colour, colours[picked - 1]


def menu_felt(img=None):
    """Surface colour as the main menu draws it."""
    img = screen_rgb() if img is None else img
    h, w = img.shape[:2]
    return _patch(img, int(h * 0.48), int(h * 0.56), int(w * 0.04), int(w * 0.28),
                  flat=_LOOK_FLAT)


def felt_colour(img=None):
    """A flat band of table felt, or None when every band has cards in it."""
    img = screen_rgb() if img is None else img
    h, w = img.shape[:2]
    x0, x1 = int(w * _FELT_X[0]), int(w * _FELT_X[1])
    for top in _FELT_BANDS:
        got = _patch(
            img, int(h * top), int(h * (top + _FELT_H)), x0, x1, flat=_LOOK_FLAT,
        )
        if got is not None:
            return got
    return None


def back_colour(img=None):
    """Card-back colour from the 'tap for hints' stack, not the tableau."""
    img = screen_rgb() if img is None else img
    cx, cy = _HINT_BACK
    return _patch(img, cy - 28, cy + 28, cx - 36, cx + 36)


def on_painted_table(timeout: float = 12.0) -> bool:
    """True on the table even when the default-felt header crop misses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_on("screen_table") or is_on("back_game") or felt_colour() is not None:
            return True
        time.sleep(0.3)
    return False


def restore_default_look() -> bool:
    """Put Surface 1 and Cards 1 back. Never raises — used from finally."""
    try:
        if not to_menu():
            print("  WARNING: could not reach the menu to restore the look")
            return False
        if not open_choose_look():
            print("  WARNING: could not reopen Choose Look to restore the look")
            return False
        if not open_look_tab("surface"):
            print("  WARNING: could not open Surface to restore it")
            return False
        if look_pick("surface", 1) is None:
            print("  WARNING: could not select Surface 1")
            return False
        if not open_look_tab("cards"):
            print("  WARNING: could not open Cards to restore it")
            return False
        if look_pick("cards", 1) is None:
            print("  WARNING: could not select Cards 1")
            return False
        close_choose_look()
        if not on_menu(6.0):
            print("  WARNING: Choose Look would not close after restore")
            return False
        print("  put the default look back (Surface 1, Cards 1)")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: could not put the default look back ({exc})")
        return False
