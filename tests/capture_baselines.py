#!/usr/bin/env python3
"""Capture every FreeCell Obj-C reference screen, three shots each.

Phase A runs on a FRESH install with QA still locked, so no screen carries
the QA watermark, Stats and Last Score are empty, the menu's More Games badge
still reads "1" and the Daily tips show. Phase B then unlocks QA, wins an
Easy game, captures Victory, turns QA off again and captures the menu and
Solo Statistics after the win (Solo is reset to none/0 afterwards).

Screens, their order and their masks live in ``visual.SCREENS``.

Output: ``log/objc_baselines/<Name>_<n>.png`` (the bytes WDA returned,
never re-encoded) and ``capture.json`` with the app / device identity.
Promote with ``scripts/update_baselines.py``.

Network, as in run_all: offline before FreeCell first runs; online only for
the Terms and Privacy pages, with FreeCell closed around each switch;
offline again right after the gates; online at the end with FreeCell closed.

Prereqs: fresh install of FreeCell 7.42.5 (279), AssistiveTouch OFF, WDA
started while the phone was online, phone unlocked, DEVICE_UDID set.

Run:
  DEVICE_UDID=... ./.venv/bin/python -u tests/capture_baselines.py
  ... --out log/objc_pass2            # the independent second pass
  ... --only HelpTop,HelpMid          # re-shoot screens that need no fresh install
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import requests  # noqa: E402

import config  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402
import visual  # noqa: E402
from tests import verifyFirstLaunch as first  # noqa: E402

SHOTS = 3
GAP = 0.7
STILL = 0.004        # share of pixels still moving in a settled frame
END_STILL = 0.03     # a swipe that moves less than this hit the end of the page

# Measured on the 1290x2796 Obj-C screens.
ABOUT_AD_FREE = (645, 1851)
ABOUT_FAQ = (645, 1963)
ABOUT_FEEDBACK = (645, 2190)
AD_FREE_NO = (424, 1584)
FEEDBACK_CANCEL = (424, 1715)
RESET_NO = (415, 1650)
ABANDON_YES = (866, 1543)
FAQ_TABS = {"FAQSolo": (648, 382), "FAQDaily": (1052, 382)}
LAST_SCORE = (365, 2270)
LAST_SCORE_CARD_OFF = (645, 1100)
DAILY_TIP = (645, 900)
DAILY_COLUMNS = (156, 317, 478, 637, 798, 957, 1118)  # S M T W T F S
DAILY_FIRST_ROW = 1357
DRAG_FROM, DRAG_TO = (645, 2000), (645, 1100)

POLICY_PAGES = (
    ("TermsPage", "tc_terms_link", "tc_terms_page", "Terms & Conditions"),
    ("PrivacyPage", "tc_privacy_link", "tc_privacy_page", "Privacy Policy"),
)


class Abort(RuntimeError):
    """Stop the whole pass — carrying on would record the wrong state."""


# ── frames ─────────────────────────────────────────────────────────
def _decode(png: bytes, flags=cv2.IMREAD_GRAYSCALE):
    return cv2.imdecode(np.frombuffer(png, np.uint8), flags)


def _grey_now():
    return _decode(helpers.grab_png())


def _moving(a, b) -> float:
    top = visual.STATUS_BAR[3]
    return float((cv2.absdiff(a[top:], b[top:]) > visual._PIXEL_TOL).mean())


def settle(timeout: float = 8.0, gap: float = 0.45) -> bool:
    """True once two frames *gap* apart agree; False if it never stopped."""
    prev = _grey_now()
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(gap)
        cur = _grey_now()
        if _moving(prev, cur) < STILL:
            return True
        prev = cur
    return False


def banner_drawn(bgr) -> bool:
    """True when the cross-promo banner, not bare wood, sits under the tray.

    Without it the menu, picker and table reflow ~120 px lower, so a tray
    screen captured before the banner arrives is a different layout.
    """
    roi = bgr[2450:2560, 100:1190].astype(int)
    b, g, r = roi[..., 0], roi[..., 1], roi[..., 2]
    wood = (r > g) & (g >= b - 5) & (r - b > 25) & (r < 170)
    return float(wood.mean()) < 0.4


def daily_tip_up() -> bool:
    """True while a white Daily tip card covers the calendar.

    The calendar's own "Tap on any date" box is still matchable for a moment
    before the card lands on it, so the card is looked for directly.
    """
    card = _decode(helpers.grab_png(), cv2.IMREAD_COLOR)[700:1080, 180:1110]
    return float((card.min(axis=2) > 235).mean()) > 0.6


def wait_daily_tip(timeout: float) -> bool:
    deadline = time.time() + timeout
    while True:
        if daily_tip_up():
            return True
        if time.time() > deadline:
            return False
        time.sleep(0.4)


def wait_banner(timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while True:
        if banner_drawn(_decode(helpers.grab_png(), cv2.IMREAD_COLOR)):
            return True
        if time.time() > deadline:
            return False
        time.sleep(0.6)


# ── gestures ───────────────────────────────────────────────────────
def drag_hold(start, end, move_ms: int = 1200, hold_ms: int = 700) -> None:
    """Drag and hold still before lifting, so the page does not fling."""
    sid = helpers.current_session()
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
    requests.post(f"{config.WDA_URL}/session/{sid}/actions", json=body,
                  timeout=30).raise_for_status()
    time.sleep(0.8)


def scroll_to_end(down: bool = True, max_swipes: int = 15) -> bool:
    """Swipe until a swipe no longer moves the page."""
    prev = _grey_now()
    for _ in range(max_swipes):
        ui.scroll(down)
        settle(5.0)
        cur = _grey_now()
        if _moving(prev, cur) < END_STILL:
            return True
        prev = cur
    return False


def answer_alert(label: str, fallback) -> None:
    """Press *label* on the current iOS alert, or tap where it is drawn."""
    if helpers.alert_text():
        sid = helpers.current_session()
        for verb in ("accept", "dismiss"):
            response = requests.post(
                f"{config.WDA_URL}/session/{sid}/alert/{verb}",
                json={"name": label}, timeout=8)
            if response.ok:
                time.sleep(1.2)
                return
    helpers.wda_tap(fallback, settle=1.2)


# ── identity ───────────────────────────────────────────────────────
def _run(cmd) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=90).stdout
    except Exception:  # noqa: BLE001
        return ""


def identity() -> dict:
    """Version / build from the installed app; model / iOS from the phone."""
    udid = config.DEVICE_UDID
    info = _run([sys.executable, "-m", "tidevice", "--udid", udid, "appinfo",
                 config.BUNDLE_ID])

    def plist(key):
        match = re.search(rf"'{key}': '([^']*)'", info)
        return match.group(1) if match else ""

    def device(key):
        return _run(["ideviceinfo", "-u", udid, "-k", key]).strip()

    return {
        "bundle_id": config.BUNDLE_ID,
        "name": plist("CFBundleDisplayName"),
        "version": plist("CFBundleShortVersionString"),
        "build": plist("CFBundleVersion"),
        "udid": udid,
        "model": device("ProductType"),
        "ios": device("ProductVersion"),
        "size": [visual.W, visual.H],
        "started": dt.datetime.now().isoformat(timespec="seconds"),
    }


# ── the pass ───────────────────────────────────────────────────────
class Pass:
    def __init__(self, out: Path, only: set, ident: dict):
        self.out = out
        self.only = only
        self.record = dict(ident, screens={}, missing={}, notes={})

    def wanted(self, name: str) -> bool:
        return not self.only or name in self.only

    def save(self) -> None:
        self.record["finished"] = dt.datetime.now().isoformat(timespec="seconds")
        (self.out / "capture.json").write_text(
            json.dumps(self.record, indent=2) + "\n")

    def note(self, key: str, value) -> None:
        self.record["notes"][key] = value
        self.save()

    def miss(self, name: str, reason: str) -> None:
        self.record["missing"][name] = reason
        print(f"  MISSING {name}: {reason}", flush=True)
        self.save()

    def discard(self, name: str, reason: str) -> None:
        """Withdraw a captured screen that turned out to be in the wrong state."""
        for shot in self.record["screens"].pop(name, {}).get("shots", []):
            (self.out / shot).unlink(missing_ok=True)
        self.miss(name, reason)

    def shoot(self, name: str, settle_for: float = 8.0) -> None:
        if not self.wanted(name):
            return
        screen = visual.SCREENS[name]
        banner = wait_banner() if screen.tray else None
        settled = settle(settle_for)
        for stale in visual.capture_shots(self.out, name):
            stale.unlink()
        shots = []
        first_png = None
        for index in range(1, SHOTS + 1):
            if index > 1:
                time.sleep(GAP)
            png = helpers.grab_png()
            first_png = first_png or png
            path = self.out / f"{name}_{index}.png"
            path.write_bytes(png)
            shots.append(path.name)
        at = visual.assistive_touch(_decode(first_png))
        if at and not self.record["screens"]:
            raise Abort("the iOS AssistiveTouch button is on screen — turn it "
                        "off (Settings → Accessibility → Touch → "
                        "AssistiveTouch); it is drawn into every screenshot")
        self.record["screens"][name] = {
            "shots": shots, "settled": settled, "banner": banner,
            "assistive_touch": [list(b) for b in at],
            "at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        self.record["missing"].pop(name, None)
        flags = [] if settled else ["still moving"]
        if banner is False:
            flags.append("NO BANNER")
        if at:
            flags.append(f"AssistiveTouch at {at[0][:2]}")
        print(f"  captured {name}" + (f" ({', '.join(flags)})" if flags else ""),
              flush=True)
        self.save()

    def group(self, title: str, names, step) -> None:
        names = [n for n in names if self.wanted(n)]
        if not names:
            return
        print(f"\n== {title}: {', '.join(names)}", flush=True)
        try:
            step(self)
        except Abort:
            raise
        except Exception as exc:  # noqa: BLE001
            failed = self.out / f"_failed_{title.replace(' ', '_')}.png"
            try:
                failed.write_bytes(helpers.grab_png())
            except Exception:  # noqa: BLE001
                pass
            for name in names:
                if name not in self.record["screens"]:
                    self.miss(name, f"{exc} (see {failed.name})")
            print(f"  {title} stopped: {exc}", flush=True)
            try:
                ui.to_menu()
            except Exception as again:  # noqa: BLE001
                print(f"  could not get back to the menu: {again}", flush=True)


# ── phase A ────────────────────────────────────────────────────────
def first_launch(p: Pass) -> None:
    first._start_without_clearing_overlays()
    if not first._reveal_terms_card():
        raise Abort("no Terms & Conditions card — FreeCell is not a fresh "
                    "install. Reinstall it, or pass --only with screens that "
                    "do not need one")
    p.shoot("FirstLaunchTerms")
    pages = [spec for spec in POLICY_PAGES if p.wanted(spec[0])]
    try:
        if pages:
            first._online_for_links()
        for name, link, page, label in pages:
            ui.answer_tracking()
            if not (ui.tap_policy_link(link)
                    or (ui.answer_tracking() and ui.tap_policy_link(link))):
                raise RuntimeError(f"could not tap the {label} link")
            if not ui.seen(page, timeout=12.0):
                raise RuntimeError(f"the {label} page did not open")
            p.shoot(name, settle_for=15.0)
            ui.close_web_page()
            if not ui.seen("tc_continue", timeout=8.0):
                raise RuntimeError(f"closing {label} did not return to the card")
    finally:
        if pages:
            first._answer_gates_then_offline()
        first._finish_on_menu()


def stats_empty(p: Pass) -> None:
    ui.expect(ui.open_stats(), "Stats did not open")
    ui.open_stats_tab("solo")
    ui.expect(ui.stats_are_default(),
              "Solo does not read none/0 — not a fresh install")
    p.shoot("StatsSoloEmpty")
    ui.expect(scroll_to_end(), "Solo never reached its end")
    p.shoot("StatsSoloBottom")
    if p.wanted("ResetSoloDialog"):
        ui.expect(ui.tap("reset_solo_stats", settle=1.8),
                  "Reset Solo Statistics not found")
        p.shoot("ResetSoloDialog", settle_for=4.0)
        answer_alert("No", RESET_NO)
        ui.expect(ui.expect_screen("stats", timeout=5.0),
                  "No on the reset prompt did not stay on Stats")
    ui.open_stats_tab("daily")
    scroll_to_end(down=False)
    p.shoot("StatsDailyEmpty")
    ui.expect(scroll_to_end(), "Daily never reached its end")
    p.shoot("StatsDailyBottom")
    ui.expect(ui.leave_stats() and ui.on_menu(6.0), "Stats did not close")


def main_menu(p: Pass) -> None:
    ui.expect(ui.on_menu(6.0), "not on the main menu")
    if not wait_banner(10.0):
        print("  no banner yet — Help and back once", flush=True)
        ui.tap("menu_help", settle=2.0)
        ui.to_menu()
    p.shoot("MainMenu")


def about(p: Pass) -> None:
    ui.expect(ui.tap("menu_about", settle=2.0) and ui.expect_screen("about"),
              "About did not open")
    p.shoot("AboutTop")
    for name, point, word, answer, fallback in (
            ("AdFreePrompt", ABOUT_AD_FREE, "ad free", "No", AD_FREE_NO),
            ("FeedbackAlert", ABOUT_FEEDBACK, "feedback", "Cancel",
             FEEDBACK_CANCEL)):
        if not p.wanted(name):
            continue
        helpers.wda_tap(point, settle=1.8)
        text = helpers.alert_text().lower()
        ui.expect(word in text, f"{name}: no alert about {word!r} ({text!r})")
        p.shoot(name, settle_for=4.0)
        answer_alert(answer, fallback)
        ui.expect(ui.expect_screen("about", timeout=5.0),
                  f"answering {name} did not return to About")
    if p.wanted("AboutVersion"):
        ui.expect(ui.tap("about_version", settle=1.5), "version line not found")
        p.shoot("AboutVersion")
    helpers.wda_tap(ABOUT_FAQ, settle=2.0)
    ui.expect(ui.seen("screen_faq", timeout=6.0), "FAQ did not open")
    p.shoot("FAQTop")
    if p.wanted("FAQBottom"):
        ui.expect(scroll_to_end(), "FAQ never reached its end")
        p.shoot("FAQBottom")
    for name, point in FAQ_TABS.items():
        if p.wanted(name):
            helpers.wda_tap(point, settle=1.5)
            scroll_to_end(down=False)
            p.shoot(name)
    ui.expect(ui.to_menu(), "could not get back to the menu from FAQ")


def page_with_mid(p: Pass, button: str, screen: str, prefix: str) -> None:
    ui.expect(ui.tap(button, settle=2.0) and ui.expect_screen(screen),
              f"{prefix} did not open")
    p.shoot(f"{prefix}Top")
    drag_hold(DRAG_FROM, DRAG_TO)
    p.shoot(f"{prefix}Mid")
    ui.expect(scroll_to_end(), f"{prefix} never reached its end")
    p.shoot(f"{prefix}Bottom")
    ui.expect(ui.to_menu(), f"could not get back to the menu from {prefix}")


def choose_look(p: Pass) -> None:
    ui.expect(ui.open_choose_look(), "Choose Look did not open")
    for tab, name in (("surface", "ChooseLookSurface"), ("cards", "ChooseLookCards")):
        ui.open_look_tab(tab)
        picked = ui.look_selected(tab)
        if picked != 1:
            p.note(f"look_{tab}", picked)
            print(f"  WARNING: {tab} palette {picked} is marked, not 1",
                  flush=True)
        p.shoot(name)
    ui.expect(ui.close_choose_look() and ui.on_menu(6.0),
              "Choose Look did not close")


def close_drawer() -> None:
    """Tap "menu" once more and wait for the drawer to slide away."""
    if not ui.tap("table_menu", settle=1.4):
        helpers.wda_tap(ui.TABLE_MENU, settle=1.4)
    deadline = time.time() + 3.0
    while ui.is_on("drawer_options") and time.time() < deadline:
        time.sleep(0.3)


def set_switch(setter, on: bool, title: str) -> None:
    ui.expect(ui.open_options(from_table=True), "table → options did not open")
    ui.expect(setter(on), f"could not turn {title} {'ON' if on else 'OFF'}")
    ui.back()
    ui.expect(ui.at_table(), "back from Options did not return to the table")


def play(p: Pass) -> None:
    ui.expect(ui.tap("menu_play", settle=2.0) and ui.expect_screen("play"),
              "Play did not open the picker")
    p.shoot("PlayPicker")
    if p.wanted("LastScoreNotice") or p.wanted("LastScore"):
        helpers.wda_tap(LAST_SCORE, settle=2.2)
        ui.expect(not ui.is_on("screen_play"), "LAST SCORE did not open")
        p.shoot("LastScoreNotice", settle_for=4.0)
        helpers.wda_tap(LAST_SCORE_CARD_OFF, settle=1.5)
        p.shoot("LastScore")
        ui.back()
        # Obj-C's Last Score "back" lands on the main menu, not the picker.
        if not ui.expect_screen("play", timeout=3.0):
            ui.expect(ui.on_menu(6.0) and ui.tap("menu_play", settle=2.0)
                      and ui.expect_screen("play"),
                      "back from Last Score reached neither the picker nor "
                      "the menu")
    ui.expect(ui.tap("difficulty_easy", settle=2.2), "Easy not found")
    helpers.accept_alert()
    ui.expect(ui.expect_screen("table", timeout=12.0), "Easy did not deal")
    p.shoot("TableDeal", settle_for=10.0)
    ui.expect(ui.open_table_drawer(), "the table drawer did not open")
    p.shoot("TableDrawer")
    close_drawer()
    ui.start_deal()
    ui.expect(ui.leave_table() and ui.on_menu(6.0), "could not leave the table")

    ui.expect(ui.tap("menu_play", settle=2.0) and ui.expect_screen("play"),
              "Play did not open the picker the second time")
    p.shoot("PlayPickerResume")
    ui.expect(ui.tap("difficulty_easy", settle=2.0), "Easy not found")
    text = helpers.alert_text().lower()
    if "abandon" in text:
        p.shoot("AbandonPrompt", settle_for=4.0)
        answer_alert("Yes", ABANDON_YES)
    else:
        reason = f"no abandon prompt, so no paused game ({text!r})"
        p.discard("PlayPickerResume", reason)
        p.miss("AbandonPrompt", reason)
    ui.expect(ui.expect_screen("table", timeout=12.0), "the new deal did not start")

    touched = []
    try:
        if p.wanted("TableRichOff"):
            touched.append("rich")
            set_switch(ui.set_rich_features, False, "Rich Features")
            p.shoot("TableRichOff", settle_for=10.0)
            set_switch(ui.set_rich_features, True, "Rich Features")
            touched.remove("rich")
        if p.wanted("TableRankStripOff"):
            touched.append("rank")
            set_switch(ui.set_rank_strip, False, "Rank Strip")
            p.shoot("TableRankStripOff", settle_for=10.0)
            set_switch(ui.set_rank_strip, True, "Rank Strip")
            touched.remove("rank")
    finally:
        if "rich" in touched:
            ui.restore_rich_features()
        if "rank" in touched:
            ui.restore_rank_strip()
    ui.expect(ui.to_menu(), "could not get back to the menu from the table")


def daily(p: Pass) -> None:
    ui.expect(ui.tap("menu_daily", settle=2.2), "Daily not found")
    tips = ("DailyTutorial1", "DailyTutorial2")
    for index, name in enumerate(tips):
        if not wait_daily_tip(6.0 if index == 0 else 4.0):
            break
        p.shoot(name, settle_for=5.0)
        helpers.wda_tap(DAILY_TIP, settle=1.2)
    for name in tips:
        if p.wanted(name) and name not in p.record["screens"]:
            p.miss(name, "no Daily tip card (already dismissed on this install)")
    extra = 0
    while extra < 3 and wait_daily_tip(2.0):
        extra += 1
        helpers.wda_tap(DAILY_TIP, settle=1.2)
    if extra:
        p.note("daily_extra_tips", extra)
    ui.expect(not daily_tip_up() and ui.seen("screen_daily", timeout=6.0),
              "the calendar did not show")
    p.shoot("DailyCalendar")
    if p.wanted("DailyTable"):
        today = dt.date.today()
        day1 = today.replace(day=1)
        column = (day1.weekday() + 1) % 7
        helpers.wda_tap((DAILY_COLUMNS[column], DAILY_FIRST_ROW), settle=2.5)
        ui.expect(ui.at_table(timeout=12.0), f"{day1} did not deal a table")
        p.note("daily_date", day1.isoformat())
        p.note("daily_level", "Medium")
        p.shoot("DailyTable", settle_for=10.0)
    ui.expect(ui.to_menu(), "could not get back to the menu from Daily")


def more_games(p: Pass) -> None:
    ui.expect(ui.tap("more_games", settle=2.2) and ui.expect_screen("more_games"),
              "More Games did not open")
    p.shoot("MoreGamesTop", settle_for=4.0)
    ui.expect(scroll_to_end(), "More Games never reached its end")
    p.shoot("MoreGamesScrolled", settle_for=4.0)
    ui.expect(ui.to_menu(), "could not get back to the menu from More Games")


# ── phase B ────────────────────────────────────────────────────────
def qa_off() -> bool:
    """Enter the QA code once more — it toggles — and confirm the watermark left."""
    if not ui.is_on("qa_watermark"):
        return True
    if not ui._enter_qa_code_on_about():
        return False
    if not ui.on_menu(2.0):
        ui.back()
    return ui.on_menu(6.0) and not ui.seen("qa_watermark", timeout=2.0)


def victory(p: Pass) -> None:
    ui.expect(ui.open_dev_panel(), "the QA unlock did not take")
    ui.expect(ui.start_game("easy"), "Easy did not deal")
    ui.expect(ui.complete_game(), "Complete Game did not reach Victory")
    p.shoot("Victory", settle_for=6.0)
    entry = p.record["screens"].get("Victory")
    if p.wanted("Victory") and entry:
        grey = _decode((p.out / entry["shots"][0]).read_bytes())
        x0, y0, x1, y1 = visual.VICTORY_MENU
        # back / menu are white on some runs and ~80% grey on others
        p.note("victory_buttons",
               "bright" if grey[y0:y1, x0:x1].max() >= 240 else "dim")
    ui.expect(ui.leave_victory(), "could not leave Victory for the menu")
    try:
        if qa_off():
            p.shoot("MainMenuAfterWin")
        else:
            p.miss("MainMenuAfterWin", "QA would not turn off — the overlay "
                   "would cover the crown")
        ui.expect(ui.open_stats(), "Stats did not open after the win")
        ui.open_stats_tab("solo")
        p.shoot("StatsSoloAfterWin")
    finally:
        if ui.expect_screen("stats", timeout=1.0) or ui.open_stats():
            if ui.reset_solo_stats():
                print("  Solo reset to none/0", flush=True)
        ui.to_menu()


GROUPS = (
    ("first launch", ("FirstLaunchTerms", "TermsPage", "PrivacyPage"), first_launch),
    ("stats empty", ("StatsSoloEmpty", "StatsSoloBottom", "ResetSoloDialog",
                     "StatsDailyEmpty", "StatsDailyBottom"), stats_empty),
    ("menu", ("MainMenu",), main_menu),
    ("about", ("AboutTop", "AdFreePrompt", "FeedbackAlert", "AboutVersion",
               "FAQTop", "FAQBottom", "FAQSolo", "FAQDaily"), about),
    ("help", ("HelpTop", "HelpMid", "HelpBottom"),
     lambda p: page_with_mid(p, "menu_help", "help", "Help")),
    ("options", ("OptionsTop", "OptionsMid", "OptionsBottom"),
     lambda p: page_with_mid(p, "menu_options", "options", "Options")),
    ("choose look", ("ChooseLookSurface", "ChooseLookCards"), choose_look),
    ("play", ("PlayPicker", "LastScoreNotice", "LastScore", "TableDeal",
              "TableDrawer", "PlayPickerResume", "AbandonPrompt",
              "TableRichOff", "TableRankStripOff"), play),
    ("daily", ("DailyTutorial1", "DailyTutorial2", "DailyCalendar",
               "DailyTable"), daily),
    ("more games", ("MoreGamesTop", "MoreGamesScrolled"), more_games),
    ("victory", ("Victory", "MainMenuAfterWin", "StatsSoloAfterWin"), victory),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(config.LOG / "objc_baselines"))
    parser.add_argument("--only", default="",
                        help="comma-separated screen names to (re)capture")
    args = parser.parse_args()

    grouped = [name for _, names, _ in GROUPS for name in names]
    assert grouped == list(visual.SCREENS), "GROUPS and visual.SCREENS disagree"
    only = {n.strip() for n in args.only.split(",") if n.strip()}
    unknown = only - set(visual.SCREENS)
    if unknown:
        print(f"unknown screens: {', '.join(sorted(unknown))}")
        return 2
    problems = config.validate()
    if problems:
        print("preflight failed:\n  - " + "\n  - ".join(problems))
        return 2
    try:
        helpers.wda_status()
    except Exception as exc:  # noqa: BLE001
        print(f"WDA is not reachable ({exc}) — start ./scripts/wda.sh while "
              "the phone is online and unlocked")
        return 2
    ident = identity()
    print(f"FreeCell {ident['version']} ({ident['build']}) on {ident['model']}, "
          f"iOS {ident['ios']}", flush=True)
    if (ident["version"], ident["build"]) != (config.OBJC_VERSION, config.OBJC_BUILD):
        print(f"this is not the Obj-C reference build "
              f"({config.OBJC_VERSION} / {config.OBJC_BUILD}) — refusing to "
              "capture baselines from it")
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    p = Pass(out, only, ident)
    prior = out / "capture.json"
    if only and prior.exists():
        old = json.loads(prior.read_text())
        if (old.get("version"), old.get("build")) != (ident["version"], ident["build"]):
            print(f"{prior} is from {old.get('version')} ({old.get('build')}) — "
                  "re-shoot into a fresh --out instead")
            return 2
        for key in ("screens", "missing", "notes"):
            p.record[key] = dict(old.get(key, {}))
        p.record["started"] = old.get("started", ident["started"])
        p.record["reshoots"] = old.get("reshoots", []) + [
            {"at": ident["started"], "only": sorted(only)}]
    p.save()
    online_at_end = os.environ.get("SKIP_OFFLINE") != "1"
    try:
        print("going offline before FreeCell runs…", flush=True)
        if not ui.ensure_offline():
            print("could not go offline — refusing to capture while ads can load")
            return 2
        for title, names, step in GROUPS:
            if title != "first launch" and not ui.on_menu(2.0):
                ui.expect(ui.launch_to_menu(), "could not reach the main menu")
            p.group(title, names, step)
    except Abort as exc:
        print(f"\nABORTED: {exc}", flush=True)
        p.note("aborted", str(exc))
        return 1
    finally:
        p.save()
        if online_at_end:
            print("closing FreeCell, then restoring Wi-Fi…", flush=True)
            ui.ensure_online()

    wanted = [n for n in visual.SCREENS if p.wanted(n)]
    got = [n for n in wanted if n in p.record["screens"]]
    print(f"\ncaptured {len(got)}/{len(wanted)} screens into {out}")
    for name in wanted:
        if name not in got:
            print(f"  missing {name}: {p.record['missing'].get(name, '?')}")
    unsettled = [n for n in got if not p.record["screens"][n]["settled"]]
    if unsettled:
        print(f"  never settled (animated — the volatile mask covers it): "
              f"{', '.join(unsettled)}")
    return 0 if len(got) == len(wanted) else 1


if __name__ == "__main__":
    sys.exit(main())
