"""Template-driven FreeCell UI primitives.

This module intentionally starts with no Spider coordinates or crops. The
capture walkthrough populates ``assets/`` after the FreeCell build is observed
on the target device.
"""
from __future__ import annotations

import time
from pathlib import Path

from airtest.core.api import exists, touch
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
    return expect_screen("menu")


def open_dev_panel() -> bool:
    """Perform the confirmed FreeCell QA gesture once crops are available."""
    if is_on("qa_badge"):
        return True
    if not is_on("about_emblem"):
        if not tap("menu_about"):
            return False
        if not expect_screen("about"):
            return False
    point = find("about_emblem")
    if not point:
        return False
    for _ in range(config.QA_TAPS):
        touch(point)
        time.sleep(0.08)
    return wait_for("qa_badge")


def enter_qa_code() -> bool:
    """Enter the configured QA code using named keypad crops."""
    for digit in config.QA_CODE:
        if not tap(f"qa_digit_{digit}", settle=0.1):
            return False
    return wait_for("qa_panel")


def complete_game() -> bool:
    if not is_on("qa_panel"):
        return False
    return tap("qa_complete_game", settle=3.0) and expect_screen("victory")
