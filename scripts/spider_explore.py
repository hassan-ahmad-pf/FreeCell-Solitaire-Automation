#!/usr/bin/env python3
"""Device walks used to build the Spider-suite ports for FreeCell.

Each step drives FreeCell to one screen the Spider suite checks and saves
captures under log/spider_src/ for scripts/crop_spider_suite_assets.py.

    ./.venv/bin/python scripts/spider_explore.py menu-about
    ./.venv/bin/python scripts/spider_explore.py options
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import requests  # noqa: E402

import config  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402

SRC = config.LOG / "spider_src"


def save(name: str):
    SRC.mkdir(parents=True, exist_ok=True)
    path = SRC / f"{name}.png"
    path.write_bytes(helpers.grab_png())
    print(f"  saved {path}", flush=True)
    return path


def step_menu_about() -> None:
    """Crown logo -> About; FAQ back -> About; About back -> menu."""
    print("menu", ui.to_menu())
    helpers.wda_tap((628, 560), settle=2.5)
    print("crown opens About", ui.expect_screen("about", 5))
    ui.back()
    print("back to menu", ui.on_menu(5))


def step_options() -> None:
    """Options top and bottom, for Contact Us and the slider rows."""
    print("menu", ui.to_menu())
    print("options", ui.open_options())
    save("options_top")
    for n in range(3):
        ui.scroll(True)
        ui.settle(4.0)
        save(f"options_scroll{n + 1}")
    ui.scroll_to_end(False)
    ui.settle(4.0)
    save("options_back_top")


def step_tree() -> None:
    """Dump the accessibility tree of whatever is on screen."""
    sid = helpers.current_session()
    source = requests.get(f"{config.WDA_URL}/session/{sid}/source",
                          params={"format": "description"}, timeout=60).json()
    text = source.get("value") or ""
    out = SRC / f"tree_{sys.argv[2] if len(sys.argv) > 2 else 'now'}.txt"
    SRC.mkdir(parents=True, exist_ok=True)
    out.write_text(str(text), encoding="utf-8")
    print(f"  {len(str(text))} chars -> {out}")
    for line in str(text).splitlines():
        if any(k in line for k in ("Slider", "Switch", "Button", "Alert")):
            print("  " + line.strip()[:160])


def step_help() -> None:
    """Help top, then scrolled to its end."""
    print("menu", ui.to_menu())
    print("help", ui.tap("menu_help", settle=2.5) and ui.expect_screen("help", 6))
    save("help_top")
    ui.scroll_to_end(True, max_swipes=25)
    save("help_end")
    ui.back()
    print("menu", ui.on_menu(5))


def step_more_games() -> None:
    """More Games top, then one swipe up."""
    print("menu", ui.to_menu())
    print("more games", ui.tap("more_games", settle=2.5)
          and ui.expect_screen("more_games", 6))
    save("more_games_top")
    ui.scroll(True)
    ui.settle(4.0)
    save("more_games_swiped")
    ui.back()
    print("menu", ui.on_menu(5))


def step_table() -> None:
    """Easy table, its drawer, tap to lower, a card tap, undo."""
    print("menu", ui.to_menu())
    print("easy", ui.start_game("easy"))
    ui.start_deal()
    time.sleep(1.0)
    save("table")
    print("drawer", ui.open_table_drawer())
    save("table_drawer")
    ui.close_drawer()
    time.sleep(1.0)
    save("table_after_drawer")


def step_picker() -> None:
    """The picker with a paused game (Resume ribbon), and the abandon alert."""
    print("menu", ui.to_menu())
    print("play", ui.tap("menu_play", settle=2.5))
    save("picker_paused")
    print("easy", ui.tap("difficulty_easy", settle=2.0))
    print("alert", repr(helpers.alert_text()), helpers.alert_buttons())
    save("abandon_alert")
    print("No", helpers.answer_alert("No"))
    time.sleep(1.0)
    save("picker_after_no")


def step_play() -> None:
    """On the table: one move, undo, hints, lower / raise, read through the tree."""
    sys.path.insert(0, os.path.join(ROOT, "tests", "spider_suite"))
    import fc

    if not ui.at_table(timeout=2.0):
        print("menu", ui.to_menu())
        print("easy", ui.start_game("easy"))
    t = time.time()
    b0 = fc.settled_board()
    print(f"  board read in {time.time() - t:.1f}s: {len(b0)} cards, top_y {b0.top_y}")
    print("  " + b0.text())
    before, after, card = fc.play_one_move()
    print(f"  moved {card}: {before.moved(after)} -> {[after.cards[c] for c in before.moved(after)]}")
    save("play_moved")
    helpers.wda_tap((220, 2280), settle=1.5)
    undone = fc.settled_board()
    print(f"  undo restores the board: {undone == before}; diff {before.moved(undone)}")
    save("play_undone")
    helpers.wda_tap((1080, 2260), settle=0.4)
    save("play_hint_1")
    time.sleep(1.0)
    save("play_hint_2")
    hinted = fc.read_board()
    print(f"  hint changed the board: {hinted != undone}")
    helpers.wda_tap((645, 2150), settle=4.0)
    low = fc.read_board()
    print(f"  lower: top_y {undone.top_y} -> {low.top_y}")
    save("play_lowered")
    helpers.wda_tap((645, 2250), settle=4.0)
    up = fc.read_board()
    print(f"  raise: top_y -> {up.top_y}")
    save("play_raised")


def step_drawer_new() -> None:
    """Drawer New: what it asks, and whether the board changes."""
    sys.path.insert(0, os.path.join(ROOT, "tests", "spider_suite"))
    import fc

    b0 = fc.settled_board()
    print("drawer", ui.open_table_drawer())
    print("new", ui.tap("drawer_new", settle=2.0))
    print("alert", repr(helpers.alert_text()), helpers.alert_buttons())
    save("drawer_new_alert")
    ui.settle_prompts({"abandon": "Yes"})
    time.sleep(2.0)
    b1 = fc.settled_board()
    print("new board differs:", b1 != b0, "at table:", ui.at_table(3.0))
    save("drawer_new_after")


def _texts(limit: int = 25) -> None:
    sys.path.insert(0, os.path.join(ROOT, "tests", "spider_suite"))
    import fc

    seen = []
    for node in fc.nodes():
        kind = node.get("type")
        label = node.get("label") or node.get("name") or ""
        if kind in ("StaticText", "Button", "NavigationBar", "Link", "TextView",
                    "TextField", "WebView") and label and label not in seen:
            seen.append(label)
            print(f"    {kind}: {str(label)[:90]!r}")
            if len(seen) >= limit:
                break


def step_contact() -> None:
    """Options -> Contact Us: where it goes, then back."""
    print("menu", ui.to_menu())
    print("options", ui.open_options())
    print("contact us", ui.tap("contact_us", settle=5.0))
    print("  app", helpers.active_app(), "alert", repr(helpers.alert_text()),
          helpers.alert_buttons())
    save("contact_us_dest")
    _texts()


def step_about_links() -> None:
    """About: ad free version and submit feedback prompts (answered No / Cancel)."""
    print("menu", ui.to_menu())
    print("about", ui.tap("menu_about", settle=2.5) and ui.expect_screen("about", 6))
    print("ad free", ui.tap("about_adfree", settle=2.5))
    print("  alert", repr(helpers.alert_text()), helpers.alert_buttons())
    save("adfree_prompt")
    buttons = helpers.alert_buttons()
    if buttons:
        print("  answer", buttons[0], helpers.answer_alert(buttons[0]))
    print("  app", helpers.active_app(), "about", ui.expect_screen("about", 4))
    print("feedback", ui.tap("about_feedback", settle=2.5))
    print("  alert", repr(helpers.alert_text()), helpers.alert_buttons())
    save("feedback_prompt")
    buttons = helpers.alert_buttons()
    if buttons:
        print("  answer", buttons[0], helpers.answer_alert(buttons[0]))
    print("  app", helpers.active_app(), "about", ui.expect_screen("about", 4))


def _fc():
    sys.path.insert(0, os.path.join(ROOT, "tests", "spider_suite"))
    import fc
    return fc


def step_buttons() -> None:
    fc = _fc()
    want = sys.argv[2].lower() if len(sys.argv) > 2 else ""
    for node in fc.nodes():
        text = f"{node.get('name')} {node.get('label')}".lower()
        if want and want in text and "fa-images" not in text:
            print(f"    {node.get('type')} name={node.get('name')!r} label={node.get('label')!r} "
                  f"rect={node.get('rect')}")


def step_close_support() -> None:
    fc = _fc()
    print("close icon", fc.tap_named("Button", "close icon", settle=2.0))
    print("options", ui.expect_screen("options", 5))
    save("after_support_close")


def step_go_online() -> None:
    print("online", ui.online())
    os.environ["SKIP_OFFLINE"] = "1"
    helpers.launch_app(force=False, settle=4.0)
    ui.clear_overlays()
    print("app", helpers.active_app())


def step_go_offline() -> None:
    print("offline", ui.offline())


def step_contact_online() -> None:
    os.environ["SKIP_OFFLINE"] = "1"
    fc = _fc()
    print("menu", ui.to_menu())
    print("options", ui.open_options())
    print("contact us", ui.tap("contact_us", settle=8.0))
    print("  app", helpers.active_app())
    save("contact_us_online")
    _texts(40)
    print("close icon", fc.tap_named("Button", "close icon", settle=2.0))
    print("options", ui.expect_screen("options", 5))
    ui.back()
    print("menu", ui.on_menu(5))


def step_promo() -> None:
    os.environ["SKIP_OFFLINE"] = "1"
    print("menu", ui.to_menu())
    time.sleep(3.0)
    save("menu_promo")


def step_strip_test() -> None:
    """Does abandoning the paused game, or a fresh launch, draw the promo strip?"""
    os.environ["SKIP_OFFLINE"] = "1"
    print("menu", ui.to_menu())
    print("play", ui.tap("menu_play", settle=2.0), "resume", ui.tap("resume", settle=3.0))
    ui.settle_prompts()
    print("table", ui.at_table(5))
    print("drawer", ui.open_table_drawer(), "abandon", ui.tap("drawer_abandon", settle=2.0))
    print("  alert", repr(helpers.alert_text()), helpers.alert_buttons())
    save("abandon_drawer_alert")
    ui.settle_prompts({"abandon": "Yes"})
    time.sleep(3.0)
    print("  app", helpers.active_app(), "menu", ui.on_menu(5))
    save("strip_after_abandon")
    ui.close_app()
    helpers.launch_app(force=True, settle=6.0)
    ui.clear_overlays()
    print("  relaunched, menu", ui.on_menu(8))
    time.sleep(3.0)
    save("strip_after_relaunch")


def step_store_probe() -> None:
    """Tap a pixel point (argv[2], argv[3]) on the menu, read the App Store title."""
    os.environ["SKIP_OFFLINE"] = "1"
    fc = _fc()
    x, y = int(sys.argv[2]), int(sys.argv[3])
    helpers.wda_tap((x, y), settle=4.0)
    went = fc.left_app()
    print("  went to", went)
    if went == fc.APP_STORE:
        print("  title", repr(fc.store_title()))
        save(f"store_{x}_{y}")
        print("  back", fc.tap_back_to_app(), "menu", ui.on_menu(8))


def step_adfree_yes() -> None:
    os.environ["SKIP_OFFLINE"] = "1"
    fc = _fc()
    print("menu", ui.to_menu())
    print("about", ui.tap("menu_about", settle=2.5) and ui.expect_screen("about", 6))
    print("ad free", ui.tap("about_adfree", settle=2.5))
    print("  yes", helpers.answer_alert("Yes", settle=4.0))
    went = fc.left_app()
    print("  went to", went)
    print("  title", repr(fc.store_title()))
    save("adfree_store")
    print("  back", fc.tap_back_to_app(), "about", ui.expect_screen("about", 8))


def step_feedback_mail() -> None:
    os.environ["SKIP_OFFLINE"] = "1"
    fc = _fc()
    print("menu", ui.to_menu())
    print("about", ui.tap("menu_about", settle=2.5) and ui.expect_screen("about", 6))
    print("feedback", ui.tap("about_feedback", settle=2.5))
    print("  write", helpers.answer_alert("Write Email", settle=5.0))
    went = fc.left_app()
    print("  went to", went)
    draft = fc.mail_draft()
    print("  draft", draft)
    save("feedback_mail")
    print("  discard", fc.mail_discard())
    print("  back", fc.tap_back_to_app(), "about", ui.expect_screen("about", 6),
          "menu", ui.on_menu(3))


def step_ad_probe() -> None:
    """Table for 32 s, then drawer Help: capture whatever covers the screen."""
    os.environ["SKIP_OFFLINE"] = "1"
    fc = _fc()
    if not ui.at_table(timeout=2.0):
        print("menu", ui.to_menu())
        print("easy", ui.start_game("easy"))
        ui.start_deal()
    print("  waiting 32 s on the table")
    time.sleep(32)
    print("drawer", ui.open_table_drawer())
    print("help", ui.tap("drawer_help", settle=1.0))
    for n in range(12):
        time.sleep(2.0)
        up = fc.ad_up()
        print(f"  t+{2 * (n + 1)}s app {helpers.active_app()} ad_up {up}")
        if up:
            save(f"ad_{n}")
            _texts(30)
            break
    else:
        save("ad_none")


def step_ad_tree() -> None:
    """What WDA sees on an interstitial: every button, and anything top-left."""
    fc = _fc()
    print("app", helpers.active_app())
    save("ad_tree")
    for node in fc.nodes():
        r = node.get("rect") or {}
        kind = node.get("type")
        corner = r and r.get("x", 999) < 90 and r.get("y", 999) < 150 and r.get("width", 999) < 120
        if kind == "Button" or corner:
            print(f"    {kind} name={node.get('name')!r} label={node.get('label')!r} "
                  f"id={node.get('rawIdentifier')!r} rect={r}")


def step_kill() -> None:
    """Home, then terminate FreeCell (clears a stuck interstitial)."""
    ui.close_app()
    print("  state", helpers.app_state())


def step_close_ad() -> None:
    fc = _fc()
    print("ad up", fc.ad_up())
    print("closed", fc.close_ad("probe", budget=90))
    save("after_close_ad")


def step_about_resume() -> None:
    """About -> Home -> reopen: does FreeCell keep About, and is it still alive?"""
    os.environ["SKIP_OFFLINE"] = "1"
    print("menu", ui.to_menu())
    print("about", ui.tap("menu_about", settle=2.5) and ui.expect_screen("about", 6))
    print("home", helpers.home())
    for n in range(3):
        time.sleep(1.5)
        print(f"  state while away {helpers.app_state()}")
    helpers.launch_app(force=False, settle=3.0)
    print("  back: about", ui.expect_screen("about", 4), "menu", ui.on_menu(3))
    save("about_resume")


def step_shot() -> None:
    save(sys.argv[2] if len(sys.argv) > 2 else "now")


def step_qa_on() -> None:
    """Dev build: About → version → emblem burst → code, saving each screen."""
    print("menu", ui.to_menu())
    save("dev_menu_before")
    print("  watermark before", ui.is_on("qa_watermark"))
    print("about", ui.tap("menu_about", settle=2.5) and ui.expect_screen("about", 6))
    save("dev_about")
    print("version", ui.tap("about_version", settle=1.0))
    save("dev_about_version")
    point = ui.find("about_emblem")
    print("emblem", point)
    print("burst", helpers.rapid_tap(point, times=config.QA_TAPS))
    time.sleep(1.0)
    save("dev_about_burst")
    _texts(30)
    print("code", helpers.type_keys(config.QA_CODE))
    time.sleep(1.5)
    save("dev_about_code")
    _texts(30)
    ui.back()
    print("menu", ui.on_menu(6))
    time.sleep(1.0)
    save("dev_menu_after")
    print("  watermark after", ui.is_on("qa_watermark"))


KEYPAD = {"1": (219, 1965), "2": (642, 1965), "3": (1066, 1965),
          "4": (219, 2134), "5": (642, 2134), "6": (1066, 2134),
          "7": (219, 2304), "8": (642, 2304), "9": (1066, 2304),
          "0": (642, 2473)}


def step_qa_keypad() -> None:
    """About → version → burst, then press the code on the keypad one digit at a time."""
    print("menu", ui.to_menu())
    print("about", ui.tap("menu_about", settle=2.5) and ui.expect_screen("about", 6))
    print("version", ui.tap("about_version", settle=1.0))
    point = ui.find("about_emblem")
    print("burst", helpers.rapid_tap(point, times=config.QA_TAPS))
    time.sleep(1.0)
    for digit in config.QA_CODE:
        helpers.wda_tap(KEYPAD[digit], settle=0.4)
    time.sleep(0.6)
    save("dev_keypad_code")
    _texts(30)
    time.sleep(2.0)
    save("dev_keypad_code_2")


def step_qa_table() -> None:
    """Dev build: Easy, first move prompt cleared, the QA badge and its panel."""
    print("menu", ui.to_menu())
    print("easy", ui.start_game("easy"))
    ui.start_deal()
    time.sleep(1.0)
    save("dev_table")
    print("  badge", ui.is_on("qa_badge"))
    print("panel", ui.open_qa_panel())
    save("dev_qa_panel")
    _texts(40)


def step_qa_drawer() -> None:
    """Dev build: the table drawer, which carries a QA entry."""
    print("drawer", ui.open_table_drawer())
    save("dev_drawer")
    _texts(40)


def step_win() -> None:
    """Dev build: on the Synthetic Win panel pick 90-99 and WIN; capture Victory."""
    if not ui.is_on("qa_panel"):
        print("panel", ui.open_qa_panel())
    helpers.wda_tap(ui.QA_SELECT_90_99, settle=1.0)
    save("dev_qa_selected")
    helpers.wda_tap(ui.QA_WIN, settle=0.2)
    for n in range(4):
        time.sleep(1.5)
        save(f"dev_victory_{n}")
    print("  victory", ui.expect_screen("victory", 4))
    _texts(40)


def step_last_score() -> None:
    """Play → LAST SCORE."""
    print("menu", ui.to_menu())
    print("play", ui.tap("menu_play", settle=2.0))
    save("dev_picker")
    helpers.wda_tap(ui.LAST_SCORE, settle=3.0)
    save("dev_last_score")
    _texts(40)


def step_tap() -> None:
    """Tap pixel (argv[2], argv[3]) and save argv[4]."""
    x, y = int(sys.argv[2]), int(sys.argv[3])
    helpers.wda_tap((x, y), settle=float(sys.argv[5]) if len(sys.argv) > 5 else 2.0)
    save(sys.argv[4] if len(sys.argv) > 4 else f"tap_{x}_{y}")
    print("  app", helpers.active_app(), "alert", repr(helpers.alert_text()))


STEPS = {
    "menu-about": step_menu_about,
    "options": step_options,
    "tree": step_tree,
    "help": step_help,
    "more-games": step_more_games,
    "table": step_table,
    "picker": step_picker,
    "play": step_play,
    "drawer-new": step_drawer_new,
    "contact": step_contact,
    "about-links": step_about_links,
    "texts": _texts,
    "close-support": step_close_support,
    "buttons": step_buttons,
    "go-online": step_go_online,
    "go-offline": step_go_offline,
    "contact-online": step_contact_online,
    "promo": step_promo,
    "strip-test": step_strip_test,
    "store-probe": step_store_probe,
    "adfree-yes": step_adfree_yes,
    "feedback-mail": step_feedback_mail,
    "ad-probe": step_ad_probe,
    "about-resume": step_about_resume,
    "ad-tree": step_ad_tree,
    "close-ad": step_close_ad,
    "kill": step_kill,
    "shot": step_shot,
    "qa-on": step_qa_on,
    "qa-keypad": step_qa_keypad,
    "qa-table": step_qa_table,
    "qa-drawer": step_qa_drawer,
    "win": step_win,
    "last-score": step_last_score,
    "tap": step_tap,
}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in STEPS:
        print("steps: " + ", ".join(STEPS))
        sys.exit(2)
    STEPS[sys.argv[1]]()
