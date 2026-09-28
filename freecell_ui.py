"""Template-driven FreeCell UI primitives.

This module intentionally starts with no Spider coordinates or crops. The
capture walkthrough populates ``assets/`` after the FreeCell build is observed
on the target device.
"""
from __future__ import annotations

import os
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


def to_menu(timeout: float = 12.0) -> bool:
    """Return to the main menu without a cold launch if possible."""
    if is_on("look_close"):
        tap("look_close", settle=1.2)
    leave_daily()
    if on_menu(1.0):
        return True
    deadline = time.time() + timeout
    while time.time() < deadline:
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
