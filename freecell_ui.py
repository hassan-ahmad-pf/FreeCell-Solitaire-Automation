"""Template-driven FreeCell UI primitives.

Every coordinate and crop comes from the FreeCell build observed on the
target device; the capture walkthrough populates ``assets/``.
"""
from __future__ import annotations

import os
import random
import time
from pathlib import Path

import config
import helpers
from caselog import says

THRESHOLD = 0.72

# Controls by name in plain words, for the run's steps ("Tap Play on the
# main menu"); a name not listed is worded from its prefix.
LABELS = {
    "menu_play": "Play on the main menu",
    "menu_daily": "Daily on the main menu",
    "menu_stats": "Statistics on the main menu",
    "menu_options": "Options on the main menu",
    "menu_help": "Help on the main menu",
    "menu_about": "About on the main menu",
    "menu_logo": "the FreeCell logo on the main menu",
    "more_games": "More Games on the main menu",
    "choose_look": "Choose Look on the main menu",
    "back_game": "Back on the game table",
    "table_menu": "the table's menu button",
    "page_back": "the page's back button",
    "daily_back": "the calendar's back button",
    "daily_faq_link": "the FAQ link on the calendar",
    "resume": "Resume in the level picker",
    "reset_solo_stats": "Reset Solo Statistics",
    "reset_daily_stats": "Reset Daily Statistics",
    "reset_yes": "Yes on the reset prompt",
    "qa_watermark": "the CONFIDENTIAL watermark (opens the QA page)",
    "qa_page_back": "back on the QA page",
    "qa_page_adapters": "Max: Adapters on the QA page",
    "qa_badge_a": "the table's QA badge",
    "look_close": "the X on Choose Look",
    "look_surface_tab": "the Surface tab in Choose Look",
    "look_cards_tab": "the Cards tab in Choose Look",
    "stats_solo_tab": "the Solo tab on Statistics",
    "stats_daily_tab": "the Daily tab on Statistics",
    "tc_continue": "Continue on the Terms & Conditions card",
    "tc_web_close": "the web page's close button",
    "att_allow": "Allow on the tracking prompt",
    "contact_us": "Contact Us on Options",
    "about_version": "the version line on About",
}
_LABEL_PLACES = (
    ("menu_", "on the main menu"), ("drawer_", "in the table menu"),
    ("victory_", "on the Victory screen"), ("difficulty_", "in the level picker"),
    ("about_", "on About"), ("daily_", "on the calendar"), ("mg_", "on More Games"),
    ("gc_", "in Game Center"), ("look_", "in Choose Look"), ("help_", "on Help"),
    ("faq_", "on the FAQ"), ("qa_", "on the QA page"), ("tc_", "on the Terms card"),
    ("last_score_", "on Last Score"), ("stats_", "on Statistics"), ("ad_", "on the ad"),
)
_WORDS = {"faq": "FAQ", "qa": "QA", "x": "X"}


def label(name: str) -> str:
    """A control's name in plain words."""
    if name in LABELS:
        return LABELS[name]
    rest, place = name, ""
    for prefix, where in _LABEL_PLACES:
        if name.startswith(prefix):
            rest, place = name[len(prefix):], f" {where}"
            break
    words = [_WORDS.get(w, w) for w in rest.split("_")]
    words[0] = words[0][:1].upper() + words[0][1:]
    return " ".join(words) + place

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
_WIFI = ""
# The rules prompt comes ~6 s after the first deal of each FreeCell process.
RULES_WAIT = 9.0
_RULES_PENDING = True


def asset(name: str) -> Path:
    return config.ASSETS / f"{name}.png"


def have(name: str) -> bool:
    return asset(name).exists()


# Crops whose centre is not on their control: the point inside the crop to tap.
# more_games is mostly felt above the gift; its centre missed the button on
# 3 taps in 5, its "More Games" label on none in 10.
TAP_AT = {"more_games": (288, 200)}


def _find_once(name: str, at=None):
    import cv2
    import numpy as np

    path = asset(name)
    if not path.exists():
        raise FileNotFoundError(
            f"missing FreeCell asset {path}; capture and crop the FreeCell screen first"
        )
    needle = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if needle is None:
        raise FileNotFoundError(f"could not read FreeCell asset {path}")
    screen = cv2.imdecode(
        np.frombuffer(helpers.grab_png(), dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    if screen is None or screen.shape[0] < needle.shape[0] or screen.shape[1] < needle.shape[1]:
        return None
    result = cv2.matchTemplate(screen, needle, cv2.TM_CCOEFF_NORMED)
    _, score, _, top_left = cv2.minMaxLoc(result)
    if score < THRESHOLD:
        return None
    if at:
        return (int(top_left[0] + at[0]), int(top_left[1] + at[1]))
    height, width = needle.shape[:2]
    return (int(top_left[0] + width / 2), int(top_left[1] + height / 2))


def find(name: str, at=None):
    """Centre of the best tpl match (or *at*, a point inside the crop), or
    None. Uses a WDA screenshot, not Airtest."""
    try:
        return _find_once(name, at)
    except Exception as exc:  # noqa: BLE001
        if not helpers.is_link_error(exc):
            raise
        helpers.reconnect()
        return _find_once(name, at)


def is_on(name: str) -> bool:
    if not have(name):
        return False
    return bool(find(name))


INK_WHITE = 235
INK_MATCH = 0.85


def find_ink(name: str, img=None, threshold: float = INK_MATCH, at=None):
    """Centre of *name*'s white lettering, whatever felt is behind it, or None.

    The header crops (back_game, table_menu) were cut on the default teal;
    after Choose Look paints the table they miss in colour but their white
    text still scores 1.00, against at most 0.49 on every other screen.
    *at* is a point inside the crop to return instead of its centre.
    """
    import cv2
    import numpy as np

    needle = cv2.imread(str(asset(name)), cv2.IMREAD_COLOR)
    if needle is None:
        return None
    rgb = screen_rgb() if img is None else img
    hay = ((rgb.max(axis=2) > INK_WHITE).astype(np.uint8)) * 255
    pin = ((needle.max(axis=2) > INK_WHITE).astype(np.uint8)) * 255
    result = cv2.matchTemplate(hay, pin, cv2.TM_CCOEFF_NORMED)
    _, score, _, top_left = cv2.minMaxLoc(result)
    if score < threshold:
        return None
    height, width = pin.shape[:2]
    dx, dy = at if at else (width / 2, height / 2)
    return (int(top_left[0] + dx), int(top_left[1] + dy))


def wait_for(name: str, timeout: float = 15.0) -> bool:
    return seen(name, timeout=timeout)


def seen(name: str, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_on(name):
            return True
        time.sleep(0.25)
    return False


@says(lambda name, settle=1.0: f"Tap {label(name)}", done=True)
def tap(name: str, settle: float = 1.0) -> bool:
    if not have(name):
        return False
    point = find(name, TAP_AT.get(name))
    if not point:
        return False
    helpers.tap(point, settle=settle)
    return True


def expect_screen(screen: str, timeout: float = 15.0) -> bool:
    return wait_for(SCREENS[screen], timeout)


def look_modal_open() -> bool:
    """True when Choose Look is up — the X crop used to miss on a painted felt."""
    return is_on("look_close") or is_on("look_surface_tab") or is_on("look_cards_tab")


def on_menu(timeout: float = 3.0) -> bool:
    if look_modal_open():
        return False
    return expect_screen("menu", timeout=timeout)


def expect(cond, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def shoot(name: str) -> Path:
    return helpers.screenshot(name)


@says("Go back (top-left back button)")
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


# Every native alert FreeCell raises, by a phrase of its text, with the
# answer that keeps a run where it is. The two-button ones put the
# dismissing answer on the left; accept_alert() presses the RIGHT one,
# which is Options on Welcome and Yes on the rules prompt.
PROMPTS = {
    "rules": ("review the game rules", "No"),
    "welcome": ("can be enabled and disabled", "OK"),
    "tip": ("did you know", "OK"),
    "extra_large": ("troubles reading the cards", "OK"),
    "rotation": ("rotation lock", "OK"),
    "abandon": ("abandon the currently paused game", "Yes"),
    "replay": ("play this game again", "No"),
    "daily_offline": ("only when internet is available", "No"),
    "reset": ("reset local scores", "No"),
    "reset_confirm": ("safe side", "No"),
    "problems": ("seems to encounter problems", "OK"),
}
PROMPT_NAMES = {"rules": "game rules", "welcome": "welcome", "tip": "tip",
                "extra_large": "large cards", "rotation": "rotation lock",
                "abandon": "abandon the paused game", "replay": "play this game again",
                "daily_offline": "Daily needs the internet", "reset": "reset scores",
                "reset_confirm": "reset, are you sure", "problems": "problems"}


def prompt_now() -> str | None:
    """Key of the PROMPTS alert on screen, "" for an unknown alert, None if none."""
    text = helpers.alert_text().lower()
    if not text:
        return None
    for key, (phrase, _) in PROMPTS.items():
        if phrase in text:
            return key
    return ""


@says(lambda key, answer=None: f"Answer the '{PROMPT_NAMES.get(key, key)}' prompt: "
                               f"{answer or PROMPTS[key][1]}", done=True)
def answer_prompt(key: str, answer: str | None = None) -> bool:
    """Answer the *key* alert if it is up — *answer* or its safe default."""
    if prompt_now() != key:
        return False
    return helpers.answer_alert(answer or PROMPTS[key][1])


def wait_prompt(key: str, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if prompt_now() == key:
            return True
        time.sleep(0.4)
    return False


def settle_prompts(answers: dict | None = None, rounds: int = 4) -> list[str]:
    """Answer every known alert on screen; leave an unknown one alone.

    *answers* overrides a default ({"rules": "Yes"}). Returns the keys answered.
    """
    answered = []
    for _ in range(rounds):
        key = prompt_now()
        if not key:
            break
        if not answer_prompt(key, (answers or {}).get(key)):
            break
        answered.append(key)
    return answered


@says("Close FreeCell's cross-promo card", done=True)
def close_house_promo(wait: float = 0.0) -> bool:
    """Close FreeCell's own cross-promo card (e.g. "Try our top rated Sudoku").

    The game draws it, offline too, a moment after a table is left. It has
    no accessibility element, so its grey X is matched by image.
    """
    if not have("promo_close"):
        return False
    deadline = time.time() + wait
    while True:
        point = find("promo_close")
        if point:
            helpers.tap(point, settle=1.5)
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.4)


@says("Leave the game table (Back)", done=True)
def leave_table(settle: float = 1.6) -> bool:
    """If the gameplay screen is up, tap Back. Never cold-launch from here."""
    settle_prompts()
    if not (is_on("screen_table") or is_on("back_game") or is_on("tableau")):
        painted = find_ink("back_game")
        if not painted:
            return False
        print("  on a painted table — tapping back", flush=True)
        helpers.tap(painted, settle=settle)
        settle_prompts()
        close_house_promo(wait=2.5)
        return True
    if not tap("back_game", settle=settle):
        helpers.wda_tap((140, 250), settle=settle)
    settle_prompts()
    close_house_promo(wait=2.5)
    return True


@says("Close the Daily calendar", done=True)
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


@says("Close Statistics", done=True)
def leave_stats(settle: float = 1.4) -> bool:
    """Close Statistics via its own back control — never the menu Daily button."""
    if not expect_screen("stats", timeout=0.8):
        return False
    if tap("page_back", settle=settle):
        return True
    helpers.wda_tap((140, 250), settle=settle)
    return True


@says("Leave the Victory screen for the main menu (Back)")
def leave_victory(settle: float = 1.6) -> bool:
    """Tap the victory Back chevron (not New) and wait for the main menu."""
    if on_menu(1.0):
        return True
    if expect_screen("victory", timeout=2.0):
        if not tap("page_back", settle=settle):
            helpers.wda_tap((140, 250), settle=settle)
    if on_menu(8.0):
        return True
    if at_table(timeout=1.5):
        leave_table()
    return on_menu(6.0)


@says("Return to the main menu")
def to_menu(timeout: float = 12.0) -> bool:
    """Return to the main menu without a cold launch if possible."""
    if is_on("look_close"):
        tap("look_close", settle=1.2)
    if leave_table():
        if on_menu(3.0):
            return True
    if expect_screen("victory", timeout=0.6):
        if tap("victory_menu", settle=1.4) or back():
            if on_menu(3.0):
                return True
    if leave_stats():
        if on_menu(2.0):
            return True
    leave_daily()
    if on_menu(1.0):
        return True
    deadline = time.time() + timeout
    while time.time() < deadline:
        if leave_table():
            pass
        elif expect_screen("stats", timeout=0.6):
            leave_stats()
        elif not close_house_promo():
            leave_daily()
            back()
        clear_overlays()
        settle_prompts()
        if on_menu(1.5):
            return True
    return launch_to_menu()


@says("Tap the table to start the deal")
def start_deal() -> None:
    """Dismiss 'tap a card to start' so Synthetic Win and hints can fire."""
    helpers.wda_tap((180, 980), settle=1.1)


@says("Open the QA Synthetic Win card on the table", done=True)
def open_qa_panel() -> bool:
    """Open the table Synthetic Win card (badge or drawer QA).

    The badge's "A" box toggles the card, so it is tapped only while the
    card is closed.
    """
    if is_on("qa_panel"):
        return True
    if tap("qa_badge_a", settle=1.2) and wait_for("qa_panel", timeout=4.0):
        return True
    helpers.wda_tap((1140, 350), settle=1.2)
    helpers.wda_tap((1180, 2280), settle=1.5)
    return wait_for("qa_panel", timeout=4.0)


@says("Allow tracking on the App Tracking prompt", done=True)
def answer_tracking() -> bool:
    """Allow the ATT prompt, by alert text or, failing that, by its crop."""
    if helpers.allow_tracking():
        return True
    return is_on("att_prompt") and tap("att_allow", settle=1.5)


def clear_overlays(rounds: int = 6) -> int:
    """Dismiss first-launch T&C and ATT, ATT first.

    ATT can sit on top of the T&C card; a Continue tap would land on it.
    """
    cleared = 0
    for _ in range(rounds):
        did = answer_tracking()
        if not did and is_on("tc_continue"):
            did = tap("tc_continue", settle=2.0)
        if not did:
            alert = helpers.alert_text().lower()
            if alert and any(gate in alert for gate in FIRST_LAUNCH_GATES):
                did = helpers.accept_alert()
        if not did:
            break
        cleared += 1
        time.sleep(0.8)
    return cleared


POLICY_LINK_MATCH = 0.60
POLICY_LINK_WORD = {"tc_terms_link": (187, 85), "tc_privacy_link": (585, 22)}


@says(lambda name: "Tap the " + ("Terms & Conditions" if "terms" in name else "Privacy Policy")
      + " link on the Terms card", done=True)
def tap_policy_link(name: str) -> bool:
    """Tap the underlined word of a Terms-card link ("Conditions", "Privacy").

    The card's lines sit a few px differently between launches (Continue
    moved 14 px), which dropped the Terms crop to 0.69 at the right place.
    Its white text still beats every other screen (<= 0.34), and the crop
    centre falls between two lines, so aim at the linked word itself.
    """
    point = find_ink(name, threshold=POLICY_LINK_MATCH,
                     at=POLICY_LINK_WORD[name])
    if not point:
        return False
    helpers.tap(point, settle=3.0)
    return True


@says("Close the web page (back to the Terms card)")
def close_web_page() -> bool:
    """Close an in-app policy webview and return to the Terms card."""
    if have("tc_web_close") and tap("tc_web_close", settle=2.0):
        return True
    helpers.wda_tap((80, 180), settle=1.8)
    return True


@says("Force-quit FreeCell and launch it again")
def cold_launch() -> bool:
    """Terminate + relaunch, sweeping first-launch gates twice."""
    helpers.terminate()
    app_launched()
    time.sleep(1.5)
    if not helpers.recover_after_app_kill():
        helpers.revive_wda()
    helpers.launch_app(force=True)
    clear_overlays()
    if on_menu(6.0):
        return True
    time.sleep(2.0)
    clear_overlays()
    return on_menu(10.0)


@says("Close FreeCell: Home button, then quit the app")
def close_app() -> None:
    """Home (FreeCell writes its state), then kill the process."""
    if helpers.in_app():
        helpers.home()
    helpers.terminate()
    app_launched()
    time.sleep(1.5)
    helpers.recover_after_app_kill()


@says("Take the phone offline: Airplane Mode on, Wi-Fi off (in Settings)")
def offline(restore: bool = True) -> bool:
    """Enable Airplane Mode and turn Wi-Fi off. True when both succeed.

    Unless the radios were already known to be off, FreeCell may have run
    online and preloaded an interstitial that would show offline. It is
    killed once the radios are off, so it only ever relaunches offline.
    """
    global _OFFLINE
    was_online = _OFFLINE is not True
    ok = helpers.set_network(False, restore=False)[0]
    if ok:
        _OFFLINE = True
        if was_online:
            close_app()
    if restore:
        helpers.launch_app(force=False)
    return ok


def ensure_offline() -> bool:
    """Go offline unless SKIP_OFFLINE=1 or the radios are already off."""
    global _OFFLINE
    if os.environ.get("SKIP_OFFLINE") == "1":
        return True
    if _OFFLINE is True:
        return True
    return offline()


@says("Put the phone online: close FreeCell, Airplane Mode off, Wi-Fi on (in Settings)")
def online() -> bool:
    """Close FreeCell, then leave Airplane Mode and turn Wi-Fi on.

    FreeCell must not be on screen, or even running, while the radios are
    up: an ad it loads then shows during the next offline run. It stays
    closed afterwards; a case that needs it online launches it itself.
    """
    global _OFFLINE, _WIFI
    close_app()
    ok, _WIFI = helpers.set_network(True, restore=False)
    if ok:
        _OFFLINE = False
    return ok


def known_online() -> bool:
    """True when online() set the radios up and nothing has taken them down."""
    return _OFFLINE is False


def wifi_name() -> str:
    """The Wi-Fi network Settings showed after the last online(); "" if none joined."""
    return _WIFI


def ensure_online() -> bool:
    """Put the radios back so the next WDA start can trust the developer cert.

    Always goes through online(), even if the radios are believed to be up,
    so FreeCell is closed before the suite hands the phone back online.
    """
    return online()


@says(lambda force=False: "Launch FreeCell fresh and bring it to the main menu" if force
      else "Open FreeCell on its main menu")
def launch_to_menu(force: bool = False) -> bool:
    """Foreground FreeCell on the main menu, clearing first-launch gates.

    A leftover table is not a lost app — tap Back and keep going. Cold launch
    is only for a screen we cannot leave (Settings, home, a dead process).
    """
    if not ensure_offline():
        print("could not take the device offline — refusing to start "
              "while ads can fire", flush=True)
        return False
    try:
        helpers.connect()
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: Airtest attach skipped: {exc}", flush=True)
    if force:
        app_launched()
    helpers.launch_app(force=force)
    clear_overlays()
    settle_prompts()
    close_house_promo()
    if on_menu(3.0):
        return True
    if leave_table() and on_menu(4.0):
        return True
    if expect_screen("victory", timeout=0.8):
        if (tap("victory_menu", settle=1.4) or back()) and on_menu(4.0):
            return True
    if leave_stats() and on_menu(2.0):
        return True
    if expect_screen("options", timeout=0.8) and back() and on_menu(3.0):
        return True
    leave_daily()
    if on_menu(3.0):
        return True
    if is_on("look_close"):
        tap("look_close", settle=1.2)
        if on_menu(3.0):
            return True
    time.sleep(2.5)
    clear_overlays()
    if leave_table() and on_menu(4.0):
        return True
    leave_daily()
    if on_menu(4.0):
        return True
    return cold_launch() or _back_out()


def _back_out(rounds: int = 3) -> bool:
    """To the menu after a relaunch: FreeCell reopens the table (Solo or
    Daily) or the Daily calendar it was killed on."""
    for _ in range(rounds):
        if on_menu(2.0):
            return True
        if not (leave_table() or leave_daily()):
            break
    return on_menu(4.0)


def qa_enabled() -> bool:
    """True when QA is already on — menu CONFIDENTIAL watermark or table badge.

    The About code toggles. Re-entering it while this is True turns QA off.
    The badge is matched by its "A" box alone: a wider crop takes in the
    hint deck, which is there with QA off too.
    """
    return is_on("qa_watermark") or is_on("qa_badge_a")


def _enter_qa_code_on_about() -> bool:
    """About → version → emblem burst → QA code. The code toggles."""
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
    helpers.type_keys(config.QA_CODE)
    time.sleep(1.4)
    return True


@says("Turn QA on: About, version line, emblem taps, then the QA code")
def open_dev_panel() -> bool:
    """Enable QA: About gesture + code, then the menu watermark.

    The CONFIDENTIAL crop lives on the main menu, not on About. The code
    toggles — if a missed watermark made us turn QA off, enter it once more.
    """
    if qa_enabled():
        return True
    if not _enter_qa_code_on_about():
        return False
    if not on_menu(2.0):
        back()
    if not on_menu(5.0):
        if not (leave_table() and on_menu(3.0)):
            return False
    if wait_for("qa_watermark", timeout=6.0) or qa_enabled():
        return True
    print("  QA code toggled the wrong way — entering it once more")
    if not _enter_qa_code_on_about():
        return False
    if not on_menu(2.0):
        back()
    if not on_menu(5.0):
        return False
    return wait_for("qa_watermark", timeout=8.0) or qa_enabled()


@says("Enter the QA code on the keypad")
def enter_qa_code() -> bool:
    """Enter the configured QA code using named keypad crops."""
    for digit in config.QA_CODE:
        if not tap(f"qa_digit_{digit}", settle=0.1):
            return False
    return wait_for("qa_panel")


@says("Win the game with the QA Synthetic Win card (90% - 99%, then WIN)")
def synthetic_win() -> bool:
    """Fire Synthetic Win (90% - 99%, WIN) on the active table. True once WIN is tapped."""
    start_deal()
    if not open_qa_panel():
        return False
    if not is_on("qa_90_99") or not is_on("qa_win"):
        return False
    helpers.wda_tap(QA_SELECT_90_99, settle=1.0)
    helpers.wda_tap(QA_WIN, settle=0.2)
    return True


@says("Win the game with Synthetic Win and wait for the Victory screen")
def complete_game() -> bool:
    """Complete the active table through the Synthetic Win panel."""
    if not synthetic_win():
        return False
    time.sleep(3.0)
    return expect_screen("victory")


def app_launched() -> None:
    """Note a fresh FreeCell process: its first deal will ask about the rules."""
    global _RULES_PENDING
    _RULES_PENDING = True


def await_rules_prompt(answer: str = "No", timeout: float = RULES_WAIT) -> bool:
    """Answer the rules prompt that follows a session's first deal.

    Waits only once per FreeCell process; afterwards returns False at once.
    True when the prompt came and was answered with *answer*.
    """
    global _RULES_PENDING
    if not _RULES_PENDING:
        return answer_prompt("rules", answer)
    _RULES_PENDING = False
    if not wait_prompt("rules", timeout):
        return False
    return answer_prompt("rules", answer)


@says(lambda level="easy", rules="No": f"Start a new {level.title()} game: Play, then "
                                       f"{level.title()}")
def start_game(level: str = "easy", rules: str = "No") -> bool:
    """Open Play, choose a FreeCell level, accept an abandon prompt, and
    answer the session's rules prompt with *rules*.

    Menu Play and the table header crops bake the default felt. After
    Choose Look those templates miss — tap the measured points and accept
    a painted table.
    """
    if not tap("menu_play", settle=2.0):
        helpers.wda_tap(MENU_PLAY, settle=2.0)
    if wait_for(f"difficulty_{level}", timeout=5.0):
        if not tap(f"difficulty_{level}", settle=2.0):
            return False
    elif level == "easy":
        helpers.wda_tap(DIFFICULTY_EASY, settle=2.0)
    else:
        return False
    answer_prompt("abandon")
    if not (expect_screen("table", timeout=8.0) or on_painted_table(timeout=8.0)):
        return False
    await_rules_prompt(rules)
    return True


def at_table(timeout: float = 12.0) -> bool:
    """True when the gameplay table is showing (header or table back)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_on("screen_table") or is_on("back_game") or find_ink("back_game"):
            return True
        time.sleep(0.35)
    return False


HINT_LABELS = ("hint_undo", "hint_hints")


def hint_bar_shown(timeout: float = 5.0) -> bool:
    """True once "tap to undo" and "tap for hints" are both drawn.

    Matched by white text alone. The old full-width crop also baked the
    middle label (raise / lower, which follows the game's state) and the
    QA-only [ ] and recycle marks, so it missed on a fresh install. The
    labels fade once the deal settles — check right after dealing.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        img = screen_rgb()
        if all(find_ink(name, img) for name in HINT_LABELS):
            return True
        time.sleep(0.3)
    return False


@says("Launch FreeCell again after it was killed")
def relaunch_after_kill() -> bool:
    """Launch the killed app. Does not steer to the menu — the table must come back.

    Terminate blinks WDA HTTP. Wait that out (and restart iproxy only if it
    stays down) before minting a new session. If the runner itself died,
    start wda.sh while the phone is online.
    """
    if not helpers.recover_after_app_kill():
        print("  WDA still down after the kill — restarting the runner",
              flush=True)
        if not helpers.revive_wda():
            return False
    app_launched()
    helpers.launch_app(force=True)
    clear_overlays()
    return True


# ── Statistics ─────────────────────────────────────────────────────
STATS_SOLO_TAB = (280, 430)
STATS_DAILY_TAB = (900, 430)
RESET_YES = (875, 1650)
VICTORY_SCORE = (40, 1240, 520, 1380)
VICTORY_BEST = (780, 1235, 1100, 1345)


@says(lambda down=True, duration=0.55: "Swipe up to scroll the page down" if down
      else "Swipe down to scroll the page up")
def scroll(down: bool = True, duration: float = 0.55) -> None:
    """Swipe the Stats list. down=True swipes up so the BOTTOM of the page comes in."""
    ms = max(int(duration * 1000), 200)
    if down:
        helpers.wda_swipe((645, 2300), (645, 600), duration_ms=ms)
    else:
        helpers.wda_swipe((645, 600), (645, 2300), duration_ms=ms)
    time.sleep(0.5)


@says(lambda name, max_swipes=10: f"Scroll until {label(name)} shows")
def scroll_to(name: str, max_swipes: int = 10) -> bool:
    return scroll_to_bottom(name, max_swipes=max_swipes)


@says(lambda name="reset_solo_stats", max_swipes=20: f"Scroll down until {label(name)} shows")
def scroll_to_bottom(name: str = "reset_solo_stats", max_swipes: int = 20) -> bool:
    """Swipe up until Reset Solo Statistics (the Solo footer) is on screen."""
    for n in range(max_swipes):
        if is_on(name):
            return True
        print(f"  scrolling to the bottom of Solo ({n + 1}/{max_swipes})",
              flush=True)
        scroll(True)
    return is_on(name)


@says("Open Statistics from the main menu")
def open_stats() -> bool:
    """Open Statistics from the main menu. Taps Stats only — never Play or Daily."""
    if expect_screen("stats", timeout=1.0):
        return True
    if not on_menu(8.0):
        return False
    if not tap("menu_stats", settle=2.2):
        return False
    return expect_screen("stats")


@says(lambda tab: f"Open the {tab.title()} tab on Statistics")
def open_stats_tab(tab: str) -> bool:
    name = "stats_solo_tab" if tab == "solo" else "stats_daily_tab"
    point = STATS_SOLO_TAB if tab == "solo" else STATS_DAILY_TAB
    if have(name) and tap(name, settle=1.0):
        return True
    helpers.wda_tap(point, settle=1.0)
    return True


STATS_EMPTY_AT = {"stats_best_zero": (280, 520), "stats_easy_none": (280, 920)}
STATS_EMPTY_PAD = 60
STATS_EMPTY_MATCH = 0.95


def stats_empty_scores(path=None) -> dict:
    """Match of each empty-Solo crop at the row it was cut from, top of Solo."""
    import cv2

    screen = cv2.cvtColor(screen_rgb(path), cv2.COLOR_RGB2BGR)
    scores = {}
    for name, (x, y) in STATS_EMPTY_AT.items():
        needle = cv2.imread(str(asset(name)), cv2.IMREAD_COLOR)
        h, w = needle.shape[:2]
        roi = screen[max(0, y - STATS_EMPTY_PAD):y + h + STATS_EMPTY_PAD,
                     max(0, x - STATS_EMPTY_PAD):x + w + STATS_EMPTY_PAD]
        scores[name] = float(cv2.minMaxLoc(
            cv2.matchTemplate(roi, needle, cv2.TM_CCOEFF_NORMED))[1])
    return scores


def stats_are_default(path=None) -> bool:
    """True when Solo's totals read best score 0 and Easy reads none.

    Both crops are mostly the "best score:" label. After a win they still
    scored 0.81 / 0.90 on other rows of the page and 0.74-0.85 on their
    own row, so neither the usual bar nor the whole page proves none/0.
    Only their own row at >= 0.95 does (an empty page reads 1.00).
    """
    scores = stats_empty_scores(path)
    print("  Solo empty check: " + ", ".join(
        f"{name[6:]} {value:.3f}" for name, value in scores.items()), flush=True)
    return all(value >= STATS_EMPTY_MATCH for value in scores.values())


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


@says("Confirm the reset: Yes on both popups, then wait for the main menu")
def confirm_reset() -> bool:
    """Two Yes popups. After the second, wait for the main menu — tap nothing else."""
    if not _tap_reset_yes():
        return False
    time.sleep(0.8)
    if not _tap_reset_yes():
        return False
    print("  waiting for the main menu after both Yes", flush=True)
    return on_menu(10.0)


@says("Reset the Solo statistics: scroll to Reset Solo Statistics, tap it, Yes twice")
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


def victory_best_crop():
    """Crop the victory *best* score — that is what Solo Statistics shows."""
    from PIL import Image

    frame = helpers.screenshot("_victory_best_frame")
    path = config.LOG / "victory_best_crop.png"
    Image.open(frame).crop(VICTORY_BEST).save(path)
    return path


def _ink_mask(image):
    import numpy as np

    pixels = np.asarray(image.convert("RGB"))
    return (pixels.max(axis=2) > 170).astype("uint8") * 255


def score_on_stats(score_path, screen_path=None) -> float:
    """Peak match of the victory score's digit shapes on the Stats page.

    Victory draws the number in white, Solo draws it in gold, so this matches
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
    ys, xs = np.where(needle > 0)
    if len(ys) == 0:
        return 0.0
    needle = needle[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    # Solo draws the digits at ~0.86 of the victory size. Coarse steps
    # (0.80 / 1.00) straddled that and scored the right number 0.697;
    # 0.02 steps score it 0.93 while a wrong number peaks at 0.70.
    best = 0.0
    for scale in np.arange(0.50, 1.01, 0.02):
        width = max(8, int(needle.shape[1] * scale))
        height = max(8, int(needle.shape[0] * scale))
        if height >= hay.shape[0] or width >= hay.shape[1]:
            continue
        sized = cv2.resize(needle, (width, height), interpolation=cv2.INTER_AREA)
        result = cv2.matchTemplate(hay, sized, cv2.TM_CCOEFF_NORMED)
        best = max(best, float(result.max()))
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
MENU_PLAY = (1080, 1330)
DIFFICULTY_EASY = (1050, 1300)
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


def screen_rgb(path=None):
    """Current device frame (or a saved capture) as an RGB numpy array."""
    import numpy as np
    from PIL import Image

    source = path if path is not None else helpers.screenshot("_look_frame")
    return np.asarray(Image.open(source).convert("RGB"))


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


def _leave_for_look_restore() -> None:
    """Get off the table / picker / stats so the Choose Look icon is tappable."""
    if look_modal_open():
        return
    if expect_screen("play", timeout=0.6) or is_on("difficulty_easy"):
        back()
    leave_table()
    leave_stats()
    leave_daily()


@says("Open Choose Look from the main menu")
def open_choose_look(settle: float = 2.0) -> bool:
    """Open the Choose Look modal. The icon crop bakes default felt."""
    if look_modal_open():
        return True
    _leave_for_look_restore()
    if tap("choose_look", settle=settle) and look_modal_open():
        return True
    helpers.wda_tap(LOOK_ICON, settle=settle)
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if look_modal_open():
            return True
        time.sleep(0.25)
    return look_modal_open()


@says(lambda tab, settle=1.4: f"Open the {tab.title()} tab in Choose Look")
def open_look_tab(tab: str, settle: float = 1.4) -> bool:
    """Show Surface or Cards. Template first, then the measured tab tap."""
    name = "look_surface_tab" if tab == "surface" else "look_cards_tab"
    point = LOOK_SURFACE_TAB if tab == "surface" else LOOK_CARDS_TAB
    if have(name) and tap(name, settle=settle):
        return True
    helpers.wda_tap(point, settle=settle)
    return True


@says("Close Choose Look (X)")
def close_choose_look(settle: float = 1.2) -> bool:
    if tap("look_close", settle=settle):
        return not look_modal_open()
    helpers.wda_tap(LOOK_CLOSE, settle=settle)
    return not look_modal_open()


@says(lambda tab, n, settle=1.6: f"Pick {tab.title()} {n} in Choose Look")
def look_pick(tab: str, n: int, settle: float = 1.6):
    """Tap palette *n* (1-based) on the open tab. Returns its RGB colour."""
    centres = look_centres(tab)
    if n < 1 or n > len(centres):
        return None
    img = screen_rgb()
    colour = look_colour_at(img, centres[n - 1])
    helpers.wda_tap(centres[n - 1], settle=settle)
    return colour


@says(lambda tab, rng=None: f"Pick a different {tab.title()} colour in Choose Look")
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


@says("Put the default look back: Surface 1 and Cards 1")
def restore_default_look() -> bool:
    """Put Surface 1 and Cards 1 back. Never raises — used from finally.

    Does not require on_menu() — that crop also bakes the default felt.
    """
    try:
        _leave_for_look_restore()
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


# ── Options switches: Rich Features, Rank Strip, Show Status Bar,
#    Show Card Messages, Maintain Card Spacing, Auto Hint ────────────
# Rich Features draws the table HUD: the score, then the timer and the
# multiplier just above the wooden bar, and the move counter left of
# "menu". RICH_HUD is the bottom band while the "tap to undo / lower /
# hints" captions show (hint deck at y=HUD_DECK_Y); once the captions go,
# the whole bar sits 132 px lower, so the band follows the hint deck. The
# header moves ~100 px with the status bar, so the counter is read
# relative to the "menu" label instead.
# Rank Strip draws one A…K band just above the "tap to undo" labels.
# Show Status Bar draws the iOS status bar on the table: the clock, signal
# and battery in white at y 67-109, above the header (y 330+). Off, that
# band is bare felt (0 white px; 3,300-4,200 when shown).
# Maintain Card Spacing draws a white arrow over a pile it has folded. It is
# looked for over the columns only: the white "▼" under "tap to undo" and
# "tap for hints" scores 0.65 against it, the columns at most 0.50.
OPTION_SWITCH_X = 1058
# The red "Test Banner" debug button covers x 936-1283, y 2370-2489 on
# Options — right over the switch column — so a row is tapped only here.
OPTION_SAFE = (450, 2250)
RANK_STRIP = (20, 1955, 1270, 2025)
RANK_SEEN = 1500
RANK_GONE = 50
RICH_HUD = {
    "score": (560, 2170, 730, 2245),
    "timer": (470, 2255, 645, 2318),
    "multiplier": (645, 2255, 830, 2318),
}
RICH_MOVES = (-240, -35, -85, 35)
HUD_DECK_Y = 2263
HUD_ITEMS = ("timer", "score", "multiplier", "moves")
HUD_INK = 170
HUD_SEEN = 150
HUD_GONE = 25
TABLE_MENU = (1140, 350)
STATUS_BAND = (0, 25, 1290, 140)
STATUS_SEEN = 1500
STATUS_GONE = 150
SPACING_BAND = (0, 600, 1290, 1900)


def _locate_in(name: str, img):
    """Centre of *name* inside an already-captured RGB frame, or None."""
    import cv2

    needle = cv2.imread(str(asset(name)), cv2.IMREAD_COLOR)
    if needle is None:
        raise FileNotFoundError(f"missing FreeCell asset {asset(name)}")
    hay = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    result = cv2.matchTemplate(hay, needle, cv2.TM_CCOEFF_NORMED)
    _, score, _, top_left = cv2.minMaxLoc(result)
    if score < THRESHOLD:
        return None
    height, width = needle.shape[:2]
    return (int(top_left[0] + width / 2), int(top_left[1] + height / 2))


@says("Open the table menu (menu button, top right)", done=True)
def open_table_drawer() -> bool:
    """Tap the table's "menu" so the replay / options / new drawer slides up."""
    if is_on("drawer_options"):
        return True
    if not tap("table_menu", settle=1.4):
        painted = find_ink("table_menu")
        if painted:
            helpers.tap(painted, settle=1.4)
        else:
            helpers.wda_tap(TABLE_MENU, settle=1.4)
    return wait_for("drawer_options", timeout=4.0)


@says(lambda from_table=False: "Open Options from the table: menu, then Options" if from_table
      else "Open Options from the main menu")
def open_options(from_table: bool = False) -> bool:
    """Options from the main menu, or from the table via menu → drawer → options."""
    if expect_screen("options", timeout=0.8):
        return True
    if not from_table:
        if not tap("menu_options", settle=2.0):
            return False
        return expect_screen("options", timeout=8.0)
    for _ in range(2):
        if not (is_on("drawer_options") or at_table(timeout=2.0)):
            return expect_screen("options", timeout=2.0)
        if open_table_drawer():
            tap("drawer_options", settle=2.0)
        if expect_screen("options", timeout=8.0):
            return True
    return False


def _nudge(up: bool) -> None:
    """A short, slow swipe that moves Options ~600 px without a long glide."""
    if up:
        helpers.wda_swipe((645, 1900), (645, 1300), duration_ms=900)
    else:
        helpers.wda_swipe((645, 1300), (645, 1900), duration_ms=900)
    time.sleep(0.6)


def option_row(name: str, max_swipes: int = 6):
    """(frame, y) of an Options row once the page has stopped gliding.

    The label and its switch come from the SAME frame: the page keeps
    moving after a swipe, so a second capture can be tens of pixels off.
    Rows are matched on their white lettering: in colour "Card Bouncing"
    and "Card Lowering" score 0.75 against each other over the shared felt.
    """
    swipes = 0
    last = None
    top, bottom = OPTION_SAFE
    for _ in range(max_swipes * 8 + 6):
        img = screen_rgb()
        hit = find_ink(name, img)
        if hit:
            if last is None or abs(hit[1] - last) > 4:
                last = hit[1]
                time.sleep(0.4)
                continue
            if top <= hit[1] <= bottom:
                return img, hit[1]
            if swipes >= max_swipes:
                return None
            _nudge(up=hit[1] > bottom)
            swipes += 1
            last = None
            continue
        last = None
        if swipes >= 2 * max_swipes:
            return None
        down = swipes < max_swipes
        print(f"  scrolling Options {'down' if down else 'back up'} for {name} "
              f"({swipes + 1}/{2 * max_swipes})", flush=True)
        scroll(down)
        swipes += 1
    return None


def switch_on(img, y: int) -> bool:
    """ON is a green track; OFF is a white knob on a pale track."""
    x0, x1 = OPTION_SWITCH_X - 83, OPTION_SWITCH_X + 87
    patch = img[y - 30:y + 30, x0:x1].astype(int)
    red, green, blue = patch[..., 0], patch[..., 1], patch[..., 2]
    lit = (green > 150) & (green - red > 80) & (green - blue > 50)
    return float(lit.mean()) > 0.15


@says(lambda name, on, title: f"Turn {title} {'ON' if on else 'OFF'} on Options")
def set_option(name: str, on: bool, title: str) -> bool:
    """Leave the switch alone if it already reads *on*, otherwise flip it."""
    want = "ON" if on else "OFF"
    for attempt in (1, 2):
        row = option_row(name)
        if row is None:
            print(f"  {title} row not found on Options", flush=True)
            return False
        img, y = row
        if switch_on(img, y) == on:
            if attempt == 1:
                print(f"  {title} is already {want}", flush=True)
            return True
        if attempt == 1:
            print(f"  {title} is {'OFF' if on else 'ON'} — turning it {want}",
                  flush=True)
        else:
            print(f"  {title} did not flip — tapping the switch again", flush=True)
        helpers.wda_tap((OPTION_SWITCH_X, y), settle=1.0)
        deadline = time.time() + 4.0
        while time.time() < deadline:
            row = option_row(name, max_swipes=0)
            if row and switch_on(*row) == on:
                return True
            time.sleep(0.3)
    return False


@says(lambda name, on, title, where: f"Check {title} reads {'ON' if on else 'OFF'} on Options")
def confirm_switch(name: str, on: bool, title: str, where: str) -> None:
    """Raise unless the Options switch *name* reads *on*."""
    state = option_state(name)
    expect(state is not None, f"{title} row not found on Options ({where})")
    expect(state is on,
           f"{title} reads {'ON' if state else 'OFF'} on Options ({where}), "
           f"expected {'ON' if on else 'OFF'}")
    print(f"  {title} reads {'ON' if on else 'OFF'} on Options ({where})",
          flush=True)


def switch_to(name: str, on: bool, title: str, shot: str):
    """Set an Options switch, confirm it reads that way, and capture the page."""
    expect(set_option(name, on, title),
           f"could not turn {title} {'ON' if on else 'OFF'}")
    confirm_switch(name, on, title, "after setting it")
    return shoot(shot)


@says("Go back to the table and capture it once the cards stop moving")
def back_to_table_shot(shot: str):
    """Leave Options for the table and capture it once the deal replay has stopped."""
    back()
    expect(at_table(), "back from Options did not return to the table")
    return settled_shot(shot)


def option_state(name: str):
    """True / False for the row's switch, or None when the row is not found."""
    row = option_row(name)
    return None if row is None else switch_on(*row)


def set_rich_features(on: bool) -> bool:
    return set_option("opt_rich_features", on, "Rich Features")


def set_rank_strip(on: bool) -> bool:
    return set_option("opt_rank_strip", on, "Rank Strip")


def set_status_bar(on: bool) -> bool:
    return set_option("opt_status_bar", on, "Show Status Bar")


def set_card_messages(on: bool) -> bool:
    return set_option("opt_card_messages", on, "Show Card Messages")


def set_auto_hint(on: bool) -> bool:
    return set_option("opt_auto_hint", on, "Auto Hint")


def status_bar_ink(path=None) -> int:
    """White pixels where the iOS status bar sits: its clock, signal and battery."""
    x0, y0, x1, y1 = STATUS_BAND
    return int((screen_rgb(path)[y0:y1, x0:x1].min(axis=2) > 225).sum())


def spacing_arrow(path=None):
    """Pixel centre of the arrow over a folded pile, or None."""
    import numpy as np

    x0, y0, x1, y1 = SPACING_BAND
    hit = _locate_in("spacing_arrow", np.ascontiguousarray(screen_rgb(path)[y0:y1, x0:x1]))
    return (hit[0] + x0, hit[1] + y0) if hit else None


def _rich_hud(img) -> dict:
    """RICH_HUD moved to where the hint deck puts the bottom bar on *img*."""
    deck = _locate_in("hint_deck", img)
    dy = deck[1] - HUD_DECK_Y if deck else 0
    return {name: (x0, y0 + dy, x1, y1 + dy) for name, (x0, y0, x1, y1) in RICH_HUD.items()}


def hud_ink(path=None) -> dict:
    """Bright-ink pixel count per HUD item; ``moves`` is -1 when "menu" is not found."""
    img = screen_rgb(path)
    ink = img.max(axis=2) > HUD_INK
    counts = {
        name: int(ink[y0:y1, x0:x1].sum())
        for name, (x0, y0, x1, y1) in _rich_hud(img).items()
    }
    menu = _locate_in("table_menu", img)
    if menu:
        cx, cy = menu
        x0, y0, x1, y1 = RICH_MOVES
        counts["moves"] = int(ink[cy + y0:cy + y1, cx + x0:cx + x1].sum())
    else:
        counts["moves"] = -1
    return counts


def hud_boxes(path) -> dict:
    """The HUD item rectangles as drawn on *path* (moves follows "menu")."""
    img = screen_rgb(path)
    boxes = _rich_hud(img)
    menu = _locate_in("table_menu", img)
    if menu:
        cx, cy = menu
        x0, y0, x1, y1 = RICH_MOVES
        boxes["moves"] = (cx + x0, cy + y0, cx + x1, cy + y1)
    return boxes


def settled_shot(name: str, timeout: float = 6.0, box=(0, 400, 1290, 2100),
                 still: int = 3000):
    """Capture *name* once two frames 0.4 s apart agree inside *box*.

    Coming back from Options can replay the deal animation; a frame taken
    mid-flight puts cards over the bands the caller measures. The card
    sparkles keep a few hundred pixels moving, hence ``still``.
    """
    import numpy as np

    x0, y0, x1, y1 = box
    prev = screen_rgb()[y0:y1, x0:x1].astype(int)
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.4)
        path = shoot(name)
        cur = screen_rgb(path)[y0:y1, x0:x1].astype(int)
        if int((np.abs(cur - prev).sum(axis=2) > 90).sum()) < still:
            return path
        prev = cur
    return shoot(name)


def rank_strip_ink(path=None) -> int:
    """Pixels in the strip band that stand out from the felt; 0 when it is hidden."""
    import numpy as np

    x0, y0, x1, y1 = RANK_STRIP
    band = screen_rgb(path)[y0:y1, x0:x1].astype(int)
    felt = np.median(band.reshape(-1, 3), axis=0)
    return int((np.abs(band - felt).sum(axis=2) > 90).sum())


def band_changed(a_path, b_path, box) -> int:
    """How many pixels inside *box* differ between two captures."""
    import numpy as np

    x0, y0, x1, y1 = box
    a = screen_rgb(a_path)[y0:y1, x0:x1].astype(int)
    b = screen_rgb(b_path)[y0:y1, x0:x1].astype(int)
    return int((np.abs(a - b).sum(axis=2) > 90).sum())


def rank_boxes(_path) -> dict:
    return {"rank strip": RANK_STRIP}


def save_hud_compare(on_path, off_path, name: str = "RichFeaturesCompare"):
    """ON and OFF tables side by side with the four HUD items boxed."""
    return save_compare([(on_path, True), (off_path, False)], hud_boxes, name)


def save_compare(frames, boxes, name: str):
    """``frames`` = [(path, on)] side by side, ``boxes(path)`` outlined green ON / red OFF."""
    from PIL import Image, ImageDraw

    images = []
    for path, on in frames:
        image = Image.open(path).convert("RGB")
        draw = ImageDraw.Draw(image)
        colour = (40, 220, 90) if on else (230, 40, 40)
        for box in boxes(path).values():
            draw.rectangle(box, outline=colour, width=6)
        images.append(image)
    width, height = images[0].size
    gap = 20
    sheet = Image.new("RGB", (len(images) * (width + gap) - gap, height), (255, 255, 255))
    for index, image in enumerate(images):
        sheet.paste(image, (index * (width + gap), 0))
    out = config.LOG / f"{name}.png"
    sheet.save(out)
    return out


@says(lambda setter, title, on=True: f"Put {title} back {'ON' if on else 'OFF'} (its default)")
def restore_option(setter, title: str, on: bool = True) -> bool:
    """Put an Options switch back to its default, *on*. Never raises — used from finally."""
    want = "ON" if on else "OFF"
    try:
        if not expect_screen("options", timeout=0.8):
            from_table = at_table(timeout=1.0)
            if not from_table and not on_menu(2.0):
                to_menu()
            if not open_options(from_table=from_table):
                print(f"  WARNING: could not reopen Options to turn {title} {want}")
                return False
        ok = setter(on)
        back()
        if ok:
            print(f"  put {title} back {want} (the default)")
        else:
            print(f"  WARNING: {title} did not read {want} after the tap")
        return ok
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: could not put {title} back {want} ({exc})")
        return False


def restore_rich_features() -> bool:
    return restore_option(set_rich_features, "Rich Features")


def restore_rank_strip() -> bool:
    return restore_option(set_rank_strip, "Rank Strip")


def restore_status_bar() -> bool:
    return restore_option(set_status_bar, "Show Status Bar")


def restore_card_messages() -> bool:
    return restore_option(set_card_messages, "Show Card Messages")


def restore_auto_hint() -> bool:
    return restore_option(set_auto_hint, "Auto Hint", on=False)


# ── Pages: settle, scroll to the end, drag ─────────────────────────
# Measured on the 1290x2796 Obj-C screens.
ABOUT_AD_FREE = (645, 1851)
ABOUT_FAQ = (645, 1963)
ABOUT_FEEDBACK = (645, 2190)
FAQ_TABS = {"general": (244, 382), "solo": (648, 382), "daily": (1052, 382)}
LAST_SCORE = (365, 2270)
LAST_SCORE_CARD_OFF = (645, 1100)
DAILY_TIP = (645, 900)
DAILY_COLUMNS = (156, 317, 478, 637, 798, 957, 1118)  # S M T W T F S
DAILY_FIRST_ROW = 1357
DRAG_FROM, DRAG_TO = (645, 2000), (645, 1100)
STILL = 0.004        # share of pixels still moving in a settled frame
END_STILL = 0.03     # a swipe that moves less than this hit the end of the page
STATUS_BAR_H = 150
PIXEL_TOL = 32


def grey_now():
    import cv2
    import numpy as np

    return cv2.imdecode(np.frombuffer(helpers.grab_png(), np.uint8),
                        cv2.IMREAD_GRAYSCALE)


def moving(a, b) -> float:
    """Share of pixels below the status bar that differ between two frames."""
    import cv2

    return float((cv2.absdiff(a[STATUS_BAR_H:], b[STATUS_BAR_H:]) > PIXEL_TOL).mean())


def settle(timeout: float = 8.0, gap: float = 0.45) -> bool:
    """True once two frames *gap* apart agree; False if it never stopped."""
    prev = grey_now()
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(gap)
        cur = grey_now()
        if moving(prev, cur) < STILL:
            return True
        prev = cur
    return False


@says(lambda down=True, max_swipes=15: "Scroll to the bottom of the page" if down
      else "Scroll back to the top of the page")
def scroll_to_end(down: bool = True, max_swipes: int = 15) -> bool:
    """Swipe until a swipe no longer moves the page."""
    prev = grey_now()
    for _ in range(max_swipes):
        scroll(down)
        settle(5.0)
        cur = grey_now()
        if moving(prev, cur) < END_STILL:
            return True
        prev = cur
    return False


@says(lambda start, end, move_ms=1200, hold_ms=700: "Drag the page "
      + ("up" if end[1] < start[1] else "down") + " slowly and hold before letting go")
def drag_hold(start, end, move_ms: int = 1200, hold_ms: int = 700) -> None:
    """Drag and hold still before lifting, so the page does not fling."""
    x1, y1 = helpers._wda_pointer(start)
    x2, y2 = helpers._wda_pointer(end)
    body = {"actions": [{
        "type": "pointer", "id": "freecell-drag-hold",
        "parameters": {"pointerType": "touch"},
        "actions": [
            {"type": "pointerMove", "duration": 0, "x": x1, "y": y1},
            {"type": "pointerDown", "button": 0},
            {"type": "pause", "duration": 60},
            {"type": "pointerMove", "duration": move_ms, "x": x2, "y": y2},
            {"type": "pause", "duration": hold_ms},
            {"type": "pointerUp", "button": 0},
        ],
    }]}
    helpers.post_gesture(body, "drag", helpers.TAP_PAUSE).raise_for_status()
    time.sleep(0.8)


def daily_tip_up() -> bool:
    """True while a white Daily tip card covers the calendar: the first-visit
    tips sit high, the monthly-score tip (after a past date is won) lower.

    The calendar's own "Tap on any date" box is still matchable for a moment
    before the card lands on it, so the card is looked for directly.
    """
    img = screen_rgb()
    return any(float((img[y0:y1, 180:1110].min(axis=2) > 235).mean()) > 0.6
               for y0, y1 in ((700, 1080), (1150, 1700)))


def wait_daily_tip(timeout: float) -> bool:
    deadline = time.time() + timeout
    while True:
        if daily_tip_up():
            return True
        if time.time() > deadline:
            return False
        time.sleep(0.4)


@says("Turn QA off: enter the QA code on About once more")
def qa_off() -> bool:
    """Enter the QA code once more — it toggles — and confirm the watermark left."""
    if not is_on("qa_watermark"):
        return True
    if not _enter_qa_code_on_about():
        return False
    if not on_menu(2.0):
        back()
    return on_menu(6.0) and not seen("qa_watermark", timeout=2.0)


@says("Close the table menu (menu button again)")
def close_drawer() -> None:
    """Tap "menu" once more and wait for the drawer to slide away."""
    if not tap("table_menu", settle=1.4):
        helpers.wda_tap(TABLE_MENU, settle=1.4)
    deadline = time.time() + 3.0
    while is_on("drawer_options") and time.time() < deadline:
        time.sleep(0.3)
