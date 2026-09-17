"""Template-driven FreeCell UI primitives.

This module intentionally starts with no Spider coordinates or crops. The
capture walkthrough populates ``assets/`` after the FreeCell build is observed
on the target device.
"""
from __future__ import annotations

import time
from pathlib import Path

from airtest.core.api import exists, text, touch
from airtest.core.cv import Template

import config
import helpers


THRESHOLD = 0.72

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
    "table": "screen_table",
    "victory": "screen_victory",
}


def asset(name: str) -> Path:
    return config.ASSETS / f"{name}.png"


def find(name: str):
    path = asset(name)
    if not path.exists():
        raise FileNotFoundError(
            f"missing FreeCell asset {path}; capture and crop the FreeCell screen first"
        )
    return exists(Template(str(path), threshold=THRESHOLD))


def is_on(name: str) -> bool:
    return bool(find(name))


def wait_for(name: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_on(name):
            return True
        time.sleep(0.25)
    return False


def tap(name: str, settle: float = 1.0) -> bool:
    path = asset(name)
    if not path.exists():
        raise FileNotFoundError(path)
    point = find(name)
    if not point:
        return False
    helpers.tap(point, settle=settle)
    return True


def expect_screen(screen: str, timeout: float = 15.0) -> bool:
    return wait_for(SCREENS[screen], timeout)


def launch_to_menu(force: bool = False) -> bool:
    helpers.connect()
    helpers.launch_app(force=force)
    if expect_screen("menu", timeout=3.0):
        return True
    if is_on("back_game"):
        tap("back_game")
    if expect_screen("menu", timeout=4.0):
        return True
    # Leaving a table can open a cross-promo ad. Relaunching FreeCell is the
    # deterministic recovery path; it does not alter QA state.
    helpers.launch_app(force=True)
    return expect_screen("menu", timeout=8.0)


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
    return wait_for("qa_enabled")


def enter_qa_code() -> bool:
    """Enter the configured QA code using named keypad crops."""
    for digit in config.QA_CODE:
        if not tap(f"qa_digit_{digit}", settle=0.1):
            return False
    return wait_for("qa_panel")


def complete_game() -> bool:
    """Complete the active table through the Synthetic Win panel."""
    if not tap("qa_badge", settle=1.0) or not wait_for("qa_panel"):
        return False
    # The panel rows are wide, but the matched crop's centre falls between
    # controls on this device. These points are re-measured from the captured
    # 1290x2796 panel and are kept separate from the template assertions.
    if not is_on("qa_90_99") or not is_on("qa_win"):
        return False
    helpers.tap((1030, 1765), settle=0.5)
    helpers.tap((680, 1747), settle=4.0)
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
