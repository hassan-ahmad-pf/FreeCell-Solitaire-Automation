"""FreeCell reads and gestures the FreeCell suite's tests share.

FreeCell is native UIKit, so rather than reading pixels this reads WDA's
accessibility tree:

* the table: every card is an Image named after its suit and rank
  (``card-a-heart-10-…``), and every empty slot is an Image too
  (``slot-…-aSymbol`` foundations, ``-thin`` free cells, ``-thick`` columns),
  so a board is an exact list of which card sits where;
* Options: the sliders and switches are UISlider / UISwitch with a value;
* the App Store page title, the Mail draft and support pages are other apps'
  native text.

Coordinates from the tree are WDA points; taps convert them to pixels.
"""
from __future__ import annotations

import fcntl
import heapq
import itertools
import os
import re
import sys
import time
from contextlib import contextmanager
from typing import NamedTuple

import requests

import caselog
import catalog
import config
import freecell_ui as ui
import helpers
import ocr
from caselog import says

APP_STORE = "com.apple.AppStore"
MAIL = "com.apple.mobilemail"

caselog.titles(catalog.TITLES)
caselog.on_fail(lambda cid: ui.shoot(f"FAIL_{cid}"))


_PHONE_LOCK = None


def hold_phone() -> None:
    """One test process drives the phone at a time: a second one closes the
    app and toggles the radios under the first, and both fail. Exits with 2
    while another process holds the phone; the lock goes with the process."""
    global _PHONE_LOCK
    if _PHONE_LOCK is not None:
        return
    config.LOG.mkdir(parents=True, exist_ok=True)
    lock = open(config.LOG / "phone.lock", "a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.seek(0)
        holder = lock.read().strip() or "another process"
        print(f"FAIL: a FreeCell test is already driving the phone ({holder}) — wait for it "
              "to finish, or stop it (./scripts/regression.sh stop ends a regression)",
              flush=True)
        sys.exit(2)
    lock.truncate(0)
    lock.write(f"pid {os.getpid()}, {os.path.basename(sys.argv[0])}\n")
    lock.flush()
    _PHONE_LOCK = lock


def main(run) -> None:
    """The ``__main__`` block every port shares: run, print FAIL, exit 1."""
    hold_phone()
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)


def dev_build() -> bool:
    """True on the dev build: run_all.py --dev, or FREECELL_SUITE_BUILD=dev
    for a port run on its own (the default, as the QA ports need it)."""
    return os.environ.get("FREECELL_SUITE_BUILD", "dev") == "dev"


# ── network ────────────────────────────────────────────────────────

def is_online() -> bool:
    return os.environ.get("FREECELL_SUITE_ONLINE") == "1"


def go_online() -> None:
    """Bring the phone online once per process. Later launches stay online:
    SKIP_OFFLINE stops launch_to_menu from taking it offline again."""
    if is_online():
        return
    ui.expect(ui.online(), "could not leave Airplane Mode / turn Wi-Fi on")
    os.environ["SKIP_OFFLINE"] = "1"
    os.environ["FREECELL_SUITE_ONLINE"] = "1"
    print("  device is online", flush=True)


def go_offline() -> None:
    """For a test that starts games: offline, no interstitial can cover them.
    A process that never went online is left to launch_to_menu's own switch."""
    if not is_online():
        return
    ui.expect(ui.offline(restore=False), "could not enable Airplane Mode / turn Wi-Fi off")
    os.environ.pop("SKIP_OFFLINE", None)
    os.environ["FREECELL_SUITE_ONLINE"] = "0"
    print("  device is offline", flush=True)


@says("Go to FreeCell's main menu")
def menu() -> None:
    """The main menu, closing an interstitial that covers FreeCell first."""
    if is_online():
        try:
            helpers.launch_app(force=False)
        except Exception:  # noqa: BLE001
            pass
        if helpers.in_app() and ad_up():
            close_ad("leftover")
    if ui.launch_to_menu():
        if wait_foreign_alert("FreeCell's main menu"):
            ui.expect(ui.on_menu(6.0), f"the main menu was gone after the alert closed "
                                       f"(see {ui.shoot('NoMenu')})")
        return
    if not (wait_foreign_alert("FreeCell") and ui.launch_to_menu()):
        raise AssertionError(f"could not reach the main menu (see {ui.shoot('NoMenu')})")


def wait_alert(phrase: str, timeout: float = 6.0) -> str:
    """Text of the native alert containing *phrase*, or "" if none came."""
    deadline = time.time() + timeout
    while True:
        text = helpers.alert_text()
        if phrase.lower() in text.lower():
            return text
        if time.time() >= deadline:
            return ""
        time.sleep(0.4)


def diff_frac(path_a, path_b, box=None, tol: int = 32) -> float:
    """Share of pixels that differ by more than *tol* inside *box* (x0, y0, x1, y1)."""
    import numpy as np

    a = ui.screen_rgb(path_a).astype(int)
    b = ui.screen_rgb(path_b).astype(int)
    if box:
        x0, y0, x1, y1 = box
        a, b = a[y0:y1, x0:x1], b[y0:y1, x0:x1]
    return float((np.abs(a - b).max(axis=2) > tol).mean())


# ── accessibility ──────────────────────────────────────────────────

SOURCE_BUILD = 5.0


def source() -> dict:
    """The foreground app's accessibility tree as WDA's JSON."""
    sid = helpers.current_session()
    for attempt in range(5):
        try:
            response = requests.get(f"{config.WDA_URL}/session/{sid}/source",
                                    params={"format": "json"}, timeout=90)
            break
        except (requests.ConnectionError, requests.exceptions.ChunkedEncodingError):
            if attempt == 4:
                raise
            # WDA keeps building a dropped read's tree (~3.5 s on the table);
            # a read on top of it stacks the work and can take the runner down.
            time.sleep(SOURCE_BUILD)
    response.raise_for_status()
    return response.json().get("value") or {}


def nodes(tree: dict | None = None):
    stack = [tree if tree is not None else source()]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.get("children") or []))


def _post(path: str, body: dict, timeout: float = 15.0):
    response = requests.post(f"{config.WDA_URL}{path}", json=body, timeout=timeout)
    return response.json().get("value") if response.ok else None


def _get(path: str, timeout: float = 10.0):
    response = requests.get(f"{config.WDA_URL}{path}", timeout=timeout)
    return response.json().get("value") if response.ok else None


def find_elements(predicate: str, timeout: float = 15.0) -> list[str]:
    """Element ids matching an NSPredicate in the foreground app."""
    sid = helpers.current_session()
    try:
        found = _post(f"/session/{sid}/elements",
                      {"using": "predicate string", "value": predicate},
                      timeout=timeout) or []
    except Exception:  # noqa: BLE001
        return []
    ids = []
    for element in found:
        eid = element.get("ELEMENT") or next(iter(element.values()), None)
        if eid:
            ids.append(eid)
    return ids


def element(predicate: str, timeout: float = 0.0) -> str | None:
    deadline = time.time() + timeout
    while True:
        ids = find_elements(predicate)
        if ids:
            return ids[0]
        if time.time() >= deadline:
            return None
        time.sleep(0.5)


def attr(eid: str, name: str):
    try:
        return _get(f"/session/{helpers.current_session()}/element/{eid}/attribute/{name}")
    except Exception:  # noqa: BLE001
        return None


def rect(eid: str) -> dict | None:
    try:
        return _get(f"/session/{helpers.current_session()}/element/{eid}/rect")
    except Exception:  # noqa: BLE001
        return None


def _quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def named(kind: str, name: str, timeout: float = 0.0) -> str | None:
    """First element of XCUIElementType*kind* whose name or label is *name*."""
    q = _quote(name)
    return element(f"type == 'XCUIElementType{kind}' AND (name == '{q}' OR label == '{q}')",
                   timeout=timeout)


def visible_rect(kind: str, name: str) -> dict | None:
    """Rect of the first *kind* element called *name* that is actually drawn.

    Native lists (MAX's debugger) keep off-screen rows in the tree with rects
    that cannot be tapped; only ``visible`` says a row is on screen.
    """
    q = _quote(name)
    for eid in find_elements(f"type == 'XCUIElementType{kind}' AND name == '{q}'"):
        if attr(eid, "visible") is True:
            return rect(eid)
    return None


def tap_point(x: float, y: float, settle: float = 1.0) -> None:
    """Tap a WDA point (the tree's coordinate space)."""
    scale = helpers.pixel_scale()
    helpers.wda_tap((int(x * scale), int(y * scale)), settle=settle)


def tap_rect(r: dict, settle: float = 1.0) -> None:
    tap_point(r["x"] + r["width"] / 2, r["y"] + r["height"] / 2, settle=settle)


NAMED = {"BackButton": "Back", "close icon": "the close icon",
         "Mail.cancelSendButton": "Cancel in Mail",
         "Mail.compose.popoverAlert.deleteDraft": "Delete Draft"}


@says(lambda kind, name, settle=1.0, timeout=0.0: f"Tap {NAMED.get(name, name)}", done=True)
def tap_named(kind: str, name: str, settle: float = 1.0, timeout: float = 0.0) -> bool:
    eid = named(kind, name, timeout=timeout)
    r = rect(eid) if eid else None
    if not r:
        return False
    tap_rect(r, settle=settle)
    return True


def drag_points(start, end, move_ms: int = 600, hold_ms: int = 200) -> None:
    """Press, drag and lift in WDA points."""
    body = {"actions": [{
        "type": "pointer", "id": "freecell-suite-drag",
        "parameters": {"pointerType": "touch"},
        "actions": [
            {"type": "pointerMove", "duration": 0, "x": int(start[0]), "y": int(start[1])},
            {"type": "pointerDown", "button": 0},
            {"type": "pause", "duration": 150},
            {"type": "pointerMove", "duration": move_ms,
             "x": int(end[0]), "y": int(end[1])},
            {"type": "pause", "duration": hold_ms},
            {"type": "pointerUp", "button": 0},
        ],
    }]}
    helpers.post_gesture(body, "drag", helpers.TAP_PAUSE).raise_for_status()
    time.sleep(0.6)


# ── QA ─────────────────────────────────────────────────────────────

# The QA page's interstitial SHOW (pixels) is grey until an interstitial has
# loaded and black once one has; it updates while the page is open.
QA_SHOW = (290, 995, 470, 1065)


def inter_loaded() -> bool:
    """On the QA page: an interstitial is loaded and ready to show."""
    img = ui.screen_rgb()
    if not ui._locate_in("qa_page_adapters", img):
        return False
    x0, y0, x1, y1 = QA_SHOW
    return int((img[y0:y1, x0:x1].min(axis=2) < 90).sum()) > 500


def await_inter(timeout: float = 300.0) -> float:
    """On the QA page: wait until an interstitial is loaded. Seconds waited."""
    t0 = time.time()
    loaded = inter_loaded()
    while not loaded and time.time() - t0 < timeout:
        time.sleep(2.0)
        loaded = inter_loaded()
    ui.expect(loaded, f"no interstitial loaded within {timeout:.0f}s (the QA page's SHOW "
                      "stayed grey) — no ad fill, so the ad point cannot be measured")
    return time.time() - t0


@says("Open the QA page and wait until an ad has loaded")
def wait_inter_loaded(timeout: float = 300.0) -> float:
    """From the main menu: wait on the QA page until an interstitial is
    loaded, then return to the menu. Seconds waited."""
    ui.expect(ui.tap("qa_watermark", settle=1.5) and ui.seen("qa_page_adapters", 4.0),
              "the QA page did not open from the menu's CONFIDENTIAL watermark")
    try:
        return await_inter(timeout)
    finally:
        ui.tap("qa_page_back", settle=1.5)
        ui.expect(ui.on_menu(6.0), "back from the QA page did not reach the main menu")


@says(lambda deal: "Deal a new game: Play, Easy, Yes to abandon the old one" if deal
      else "Go back into the game: Play, then Resume")
def enter_from_menu(deal: bool) -> None:
    """Play, then Resume (or Easy and Yes to abandon when *deal*)."""
    ui.expect(ui.on_menu(4.0), "game entry did not start from the main menu")
    if not ui.tap("menu_play", settle=2.0):
        helpers.wda_tap(ui.MENU_PLAY, settle=2.0)
    ui.expect(ui.wait_for("difficulty_easy", timeout=6.0), "Play did not open the picker")
    if not deal and ui.is_on("resume"):
        ui.expect(ui.tap("resume", settle=1.0), "Resume could not be tapped")
        return
    ui.expect(ui.tap("difficulty_easy", settle=1.0), "Easy could not be tapped")
    if wait_alert("abandon", timeout=3.0):
        helpers.answer_alert("Yes", settle=1.0)


# FreeCell's ads can land ~10 s after their trigger.
LATE_AD = 12.0


@says(lambda label, ready_wait=300.0: "Get onto the game table with an ad loaded and ready "
                                      "(checked on the QA page)")
def loaded_table(label: str, ready_wait: float = 300.0) -> None:
    """Onto the table with an interstitial loaded and no cooldown running.

    FreeCell's ads do not always fill, so an ad point is measured only
    once the QA page shows one loaded: menu, QA page until
    SHOW, then Resume. An ad on the way in uses that one up, so the detour
    starts again.
    """
    for _ in range(3):
        if ui.at_table(timeout=1.0):
            ui.expect(ui.tap("back_game", settle=1.0), "the table's Back could not be tapped")
        clear_ad(f"{label} setup", wait=LATE_AD)
        if not ui.on_menu(3.0):
            menu()
        waited = wait_inter_loaded(ready_wait)
        enter_from_menu(deal=False)
        if clear_ad(f"{label} resume", wait=LATE_AD):
            print("  entering the game showed an ad, which used up the loaded one — "
                  "waiting for the next", flush=True)
            continue
        ui.settle_prompts()
        ui.expect(ui.at_table(timeout=8.0), "Resume did not reach the game table")
        print(f"  interstitial loaded (QA SHOW after {waited:.0f}s) — on the table for "
              f"{label}", flush=True)
        return
    raise AssertionError(f"could not reach the table with an interstitial loaded for {label}")


def ensure_qa() -> None:
    """QA on, from the main menu, without toggling it off when it already is."""
    if ui.qa_enabled():
        return
    print("  QA is off — unlocking it on About", flush=True)
    ui.expect(ui.open_dev_panel(), "could not turn QA on (About → version line → "
                                   "emblem taps → code)")
    ui.expect(ui.on_menu(4.0) or ui.to_menu(), "could not return to the menu after "
                                               "turning QA on")


# ── apps ───────────────────────────────────────────────────────────

def left_app(timeout: float = 10.0) -> str:
    """Wait for a hand-off out of FreeCell; the bundle id we landed in."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not helpers.in_app():
            break
        time.sleep(1.0)
    time.sleep(0.5)
    return helpers.active_app()


@says("Bring FreeCell back to the front")
def resume(settle: float = 2.5) -> bool:
    """Foreground FreeCell without restarting it."""
    helpers.launch_app(force=False, settle=settle)
    return helpers.in_app()


# Where iOS draws the "◀ FreeCell" crumb, as a share of the frame. The crumb
# is drawn by SpringBoard, so no app's accessibility tree carries it.
_CRUMB = (0.055, 0.042)


@says("Return to FreeCell with the '◀ FreeCell' link at the top left")
def tap_back_to_app(settle: float = 3.0, timeout: float = 10.0) -> bool:
    """Return through the status-bar crumb. Refuses when FreeCell is in front:
    the crumb names the app you came from and would send you out."""
    if helpers.in_app():
        return True
    tap_point(430 * _CRUMB[0], 932 * _CRUMB[1], settle=settle)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if helpers.in_app():
            return True
        time.sleep(1.0)
    return helpers.in_app()


_STORE_MARK = "▻"
_STORE_LOADING = ("loading…", "loading...", "loading")


@says("Read the app name on the App Store page")
def store_title(timeout: float = 30.0) -> str:
    """App name on the App Store product page in front, or "".

    The store injects '▻' inside the title and draws the previous page while
    it loads, so the glyph is stripped and two equal reads are required. Its
    "Loading…" spinner text is not a title; on a slow connection it can stay
    up for well over ten seconds.
    """
    def once() -> str:
        for eid in find_elements("type == 'XCUIElementTypeStaticText'", timeout=10):
            value = attr(eid, "value") or attr(eid, "label")
            text = " ".join(str(value or "").replace(_STORE_MARK, " ").split())
            if text and text.lower() not in _STORE_LOADING:
                return text
        return ""

    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        now = once()
        if now and now == last:
            return now
        last = now
        time.sleep(1.0)
    return last


@says("Read the Mail draft's subject and recipient")
def mail_draft(timeout: float = 15.0) -> dict:
    """{"subject", "to"} of the Mail compose sheet in front; "" when unreadable."""
    deadline = time.time() + timeout
    draft = {"subject": "", "to": ""}
    while time.time() < deadline:
        subject = element("name == 'subjectField'")
        if subject:
            draft["subject"] = str(attr(subject, "value") or "").strip()
        to = element("name == 'toField'")
        if to:
            raw = str(attr(to, "value") or "")
            raw = raw.replace("\u200e", "").replace("\ufffc", "")
            draft["to"] = raw.split("To:", 1)[-1].strip()
        if draft["subject"]:
            return draft
        time.sleep(1.0)
    return draft


@says("Delete the Mail draft without sending it (Cancel, then Delete Draft)")
def mail_discard(timeout: float = 12.0) -> bool:
    """Cancel the draft and Delete it. Never sends. True once it is gone."""
    if not tap_named("Button", "Mail.cancelSendButton", settle=2.0):
        return not mail_draft(timeout=2.0)["subject"]
    tap_named("Button", "Mail.compose.popoverAlert.deleteDraft", settle=1.5) or \
        tap_named("Button", "Delete Draft", settle=1.5)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not element("name == 'subjectField'"):
            return True
        time.sleep(1.0)
    return False


# ── the table ──────────────────────────────────────────────────────

_CARD = re.compile(r"card-[a-z]+-([a-z]+)-(\d+)-")


def _images(tree: dict) -> list[tuple[str, dict]]:
    out = []
    for node in nodes(tree):
        if node.get("type") == "Image":
            ident = node.get("rawIdentifier") or node.get("name") or ""
            if ident:
                out.append((ident.rsplit("/", 1)[-1], node.get("rect") or {}))
    return out


def _centre(r: dict) -> tuple[float, float]:
    return r["x"] + r["width"] / 2, r["y"] + r["height"] / 2


class Board:
    """Which card sits where, read from the tree.

    ``cards`` maps "heart-10" to (area, index, depth): area F (foundation),
    C (free cell) or T (tableau column), index from the left, depth from the
    top of a column (0 for F and C). ``top_y`` is the foundation row's y in
    points, which moves when the playfield is lowered. ``places`` holds the
    centres of the empty-slot images by area, left to right.
    """

    def __init__(self, cards: dict, top_y: float, rects: dict, places: dict | None = None):
        self.cards = cards
        self.top_y = top_y
        self.rects = rects
        self.places = places or {}

    def __eq__(self, other) -> bool:
        return isinstance(other, Board) and self.cards == other.cards

    def __len__(self) -> int:
        return len(self.cards)

    def column(self, index: int) -> list[str]:
        mine = [(d, c) for c, (a, i, d) in self.cards.items() if a == "T" and i == index]
        return [c for _, c in sorted(mine)]

    def columns(self) -> int:
        return 1 + max((i for a, i, _ in self.cards.values() if a == "T"), default=-1)

    def bottom(self, index: int) -> str | None:
        col = self.column(index)
        return col[-1] if col else None

    def moved(self, other: "Board") -> list[str]:
        return sorted(c for c in self.cards if other.cards.get(c) != self.cards[c])

    def text(self) -> str:
        cols = [" ".join(self.column(i)) for i in range(self.columns())]
        return " | ".join(cols)


def board(tree: dict | None = None) -> Board | None:
    """The board on screen, or None when no table is showing."""
    images = _images(tree if tree is not None else source())
    slots = [(name, r) for name, r in images if name.startswith("slot-")]
    found = [(name, r) for name, r in images if _CARD.match(name)]
    if not found or not slots:
        return None
    foundations = sorted(_centre(r) for n, r in slots if "aSymbol" in n)
    cells = sorted(_centre(r) for n, r in slots if "-thin-" in n)
    columns = sorted(_centre(r) for n, r in slots if "-thick" in n)
    if not columns:
        return None
    top_y = min((y for _, y in foundations + cells), default=columns[0][1])
    tab_y = columns[0][1]
    split = (top_y + tab_y) / 2
    top = [("F", i, x) for i, (x, _) in enumerate(foundations)] + \
          [("C", i, x) for i, (x, _) in enumerate(cells)]
    cards, rects, per_column = {}, {}, {}
    for name, r in found:
        suit, rank = _CARD.match(name).groups()
        key = f"{suit}-{rank}"
        cx, cy = _centre(r)
        rects[key] = r
        if cy < split and top:
            area, index, _ = min(top, key=lambda t: abs(t[2] - cx))
            cards[key] = (area, index, 0)
        else:
            index = min(range(len(columns)), key=lambda i: abs(columns[i][0] - cx))
            per_column.setdefault(index, []).append((cy, key))
    for index, stack in per_column.items():
        for depth, (_, key) in enumerate(sorted(stack)):
            cards[key] = ("T", index, depth)
    return Board(cards, top_y, rects, {"F": foundations, "C": cells, "T": columns})


def read_board(timeout: float = 8.0) -> Board | None:
    deadline = time.time() + timeout
    while True:
        try:
            got = board()
        except Exception:  # noqa: BLE001
            got = None
        if got is not None and len(got) == 52:
            return got
        if time.time() >= deadline:
            return got
        time.sleep(0.6)


def settled_board(timeout: float = 10.0) -> Board | None:
    """The board once two reads agree — a card move animates."""
    prev = read_board()
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.8)
        now = read_board()
        if now is not None and prev is not None and now == prev:
            return now
        prev = now
    return prev


def tap_card(b: Board, card: str, settle: float = 1.5) -> None:
    tap_rect(b.rects[card], settle=settle)


@says("Play a move: tap bottom cards left to right until one moves")
def play_one_move(tag: str = "") -> tuple[Board, Board, str]:
    """Tap bottom cards left to right until one moves.

    FreeCell moves a tapped card to a legal place by itself (a column first,
    then a free cell), so the first bottom card that can go anywhere moves.
    Returns (before, after, card).
    """
    before = settled_board()
    ui.expect(before is not None and len(before) == 52,
              f"could not read the 52 cards off the table{tag}")
    for index in range(before.columns()):
        card = before.bottom(index)
        if not card:
            continue
        tap_card(before, card, settle=1.6)
        ui.answer_prompt("tip")
        after = settled_board()
        if after is not None and after != before:
            return before, after, card
        before = after or before
    raise AssertionError("no bottom card had a legal move — every tap left the board alone")


def _next_up(b: Board) -> list[str]:
    """Each suit's next card for its foundation (its Ace while it is empty)."""
    top: dict[str, int] = {}
    for card, (area, _index, _depth) in b.cards.items():
        suit, rank = card.rsplit("-", 1)
        top[suit] = max(top.get(suit, 0), int(rank) if area == "F" else 0)
    return [f"{suit}-{rank + 1}" for suit, rank in top.items() if rank < 13]


def _covering(b: Board, card: str) -> list[str]:
    """The cards lying on *card* in its column, the bottom one first."""
    area, index, depth = b.cards[card]
    return list(reversed(b.column(index)[depth + 1:])) if area == "T" else []


def _up(b: Board) -> int:
    return sum(1 for area, _i, _d in b.cards.values() if area == "F")


@says("Play a card up onto its foundation pile (the move that scores)")
def play_to_foundation(max_cover: int = 4) -> tuple[Board, Board, str]:
    """Put one card up on its foundation, the only move FreeCell scores.

    Picks the next card a suit needs with the fewest cards on it and taps
    those away first (each goes to a legal column or free cell by itself).
    Returns (before, after, the card tapped last).
    """
    start = settled_board()
    ui.expect(start is not None and len(start) == 52, "could not read the 52 cards off the table")
    b = start
    for target in sorted((c for c in _next_up(b) if c in b.cards),
                         key=lambda c: len(_covering(b, c))):
        cover = _covering(b, target)
        if len(cover) > max_cover:
            continue
        for card in cover + [target]:
            tap_card(b, card, settle=1.6)
            ui.answer_prompt("tip")
            after = settled_board()
            if after is None:
                break
            if _up(after) > _up(start):
                return start, after, card
            stuck = after.cards.get(card) == b.cards.get(card)
            b = after
            if stuck:
                break
    raise AssertionError("no card could be put up on a foundation within "
                         f"{max_cover} taps (board: {b.text()})")


# ── stuck cards ────────────────────────────────────────────────────

TABLEAU = 8
CANNOT_ATTACH = re.compile(r"cannot\s+attach|attach\s+anywhere", re.I)


def _red(card: str) -> bool:
    return card.startswith(("heart", "diamond"))


def _rank(card: str) -> int:
    return int(card.rsplit("-", 1)[1])


def _fits_column(b: Board, card: str, empty: bool = True) -> bool:
    """True when *card* could go onto another column: one whose bottom card is
    one rank higher in the other colour, or (with *empty*) an empty one."""
    own = b.cards[card][1]
    for index in range(TABLEAU):
        bottom = b.bottom(index)
        if index == own:
            continue
        if bottom is None:
            if empty:
                return True
        elif _red(bottom) != _red(card) and _rank(bottom) == _rank(card) + 1:
            return True
    return False


def cells_used(b: Board) -> int:
    return sum(1 for area, _i, _d in b.cards.values() if area == "C")


def empty_columns(b: Board) -> int:
    return sum(1 for i in range(TABLEAU) if b.bottom(i) is None)


def homeless(b: Board) -> list[str]:
    """Bottom cards that can go neither up to a foundation nor onto a column:
    a tap parks one in a free cell, or does nothing once the cells are full."""
    up = set(_next_up(b))
    return [card for card in (b.bottom(i) for i in range(TABLEAU))
            if card and card not in up and not _fits_column(b, card)]


def _parkable(b: Board) -> list[str]:
    """Bottom cards with nowhere to go but a free cell or an empty column, from
    columns they would not leave empty."""
    up = set(_next_up(b))
    return [card for card in (b.bottom(i) for i in range(TABLEAU))
            if card and card not in up and not _fits_column(b, card, empty=False)
            and len(b.column(b.cards[card][1])) > 1]


@says("Fill all four free cells and every column: tap bottom cards that have nowhere else to go")
def fill_free_cells(max_taps: int = 16) -> Board:
    """Tap bottom cards until all four free cells hold a card, no column is
    empty (an empty column takes any card) and some bottom card is stuck.

    Each tap parks a card that has nowhere else to go, which fills a free cell
    or an empty column; when there is none, any legal move changes the board.
    """
    b = settled_board()
    ui.expect(b is not None and len(b) == 52, "could not read the 52 cards off the table")
    for _ in range(max_taps):
        if cells_used(b) >= 4 and not empty_columns(b) and homeless(b):
            return b
        spare = _parkable(b)
        if spare:
            tap_card(b, spare[0], settle=1.6)
            ui.answer_prompt("tip")
            b = settled_board() or b
        else:
            b = play_one_move()[1]
    ui.expect(cells_used(b) >= 4 and not empty_columns(b),
              f"the free cells and columns are not all full after {max_taps} taps "
              f"(board: {b.text()})")
    return b


@contextmanager
def no_idle_wait():
    """Taps return as soon as WDA has played them, with no pause for the
    app's animations to settle."""
    with helpers.no_gesture_pause():
        yield


@says(lambda b, card, name, seconds=2.0: f"Tap {card}, which has nowhere to go, and capture "
                                         f"the screen as fast as possible for {seconds:.0f} s")
def tap_and_watch(b: Board, card: str, name: str, seconds: float = 2.0) -> list[tuple[float, str]]:
    """Tap *card* and grab frames back to back for *seconds*. A card message
    shows for under a second, and the usual pause for the animations to
    settle after a tap would outlast it. (seconds after the tap, path) per frame."""
    grabbed = []
    with no_idle_wait():
        t0 = time.time()
        tap_card(b, card, settle=0.0)
        print(f"  the tap returned after {time.time() - t0:.2f} s", flush=True)
        while time.time() - t0 < seconds:
            grabbed.append((time.time() - t0, helpers.grab_png()))
    frames = []
    for n, (at, png) in enumerate(grabbed):
        path = config.LOG / f"{name}{n}.png"
        path.write_bytes(png)
        frames.append((at, str(path)))
    return frames


@says("Read every captured frame for the 'this card cannot attach anywhere' note")
def card_message(frames: list[tuple[float, str]]) -> tuple[float, str, str] | None:
    """(seconds after the tap, path, text) of the first frame showing the note."""
    for at, path in frames:
        for line in ocr.read(path):
            if CANNOT_ATTACH.search(line.text):
                return at, path, line.text
    return None


# ── long piles ─────────────────────────────────────────────────────
# Maintain Card Spacing keeps at least 24 pt between a column's cards; a pile
# that does not fit that way has its top cards tucked under the next one and
# an arrow over it. That takes 15 cards with the playfield raised, 12 lowered.
# A card less than FOLDED_GAP above the next has its rank hidden (OFF squeezes
# a 13-card pile to 21 pt, tucked cards sit 0 or less apart).

_SUITS = ("heart", "diamond", "club", "spade")
FOLDED_GAP = 15.0
_PLAN_NODES = 100_000
_PLAN_COST = 1.5


def _code(card: str) -> int:
    suit, rank = card.rsplit("-", 1)
    return _SUITS.index(suit) * 16 + int(rank)


def _named(code: int) -> str:
    return f"{_SUITS[code >> 4]}-{code & 15}"


def _goes_on(card: int, onto: int) -> bool:
    """One rank lower and the other colour (hearts and diamonds are 0-31)."""
    return (card >> 5) != (onto >> 5) and (onto & 15) == (card & 15) + 1


def _pile_moves(state):
    """(card, from, to) for each single-card move; places are ("T", i),
    ("C", None) and ("F", None)."""
    cols, cells, up = state
    empty = next((j for j, col in enumerate(cols) if not col), None)
    sources = [(col[-1], ("T", i)) for i, col in enumerate(cols) if col]
    sources += [(card, ("C", None)) for card in cells]
    for card, src in sources:
        if up[card >> 4] + 1 == card & 15:
            yield card, src, ("F", None)
        for j, col in enumerate(cols):
            if col and src != ("T", j) and _goes_on(card, col[-1]):
                yield card, src, ("T", j)
        if empty is not None and (src[0] == "C" or len(cols[src[1]]) > 1):
            yield card, src, ("T", empty)
        if src[0] == "T" and len(cells) < 4:
            yield card, src, ("C", None)


def _pile_apply(state, move):
    cols, cells, up = state
    card, (src, i), (dst, j) = move
    cols, cells, up = list(cols), list(cells), list(up)
    if src == "T":
        cols[i] = cols[i][:-1]
    else:
        cells.remove(card)
    if dst == "T":
        cols[j] = cols[j] + (card,)
    elif dst == "C":
        cells.append(card)
    else:
        up[card >> 4] += 1
    return tuple(cols), tuple(sorted(cells)), tuple(up)


def plan_pile(b: Board, target: int) -> list[tuple[str, tuple]] | None:
    """The fewest single-card moves found that leave one column *target*
    cards long: [(card, ("T", column) / ("C", None) / ("F", None))], or None.
    A best-first search on how far the longest column is from *target* and
    how many free cells are taken, plus the moves made so far."""
    up = [0] * 4
    for card, (area, _i, _d) in b.cards.items():
        if area == "F":
            up[_code(card) >> 4] = max(up[_code(card) >> 4], _code(card) & 15)
    start = (tuple(tuple(_code(c) for c in b.column(i)) for i in range(TABLEAU)),
             tuple(sorted(_code(c) for c, (a, _i, _d) in b.cards.items() if a == "C")),
             tuple(up))

    def short(state) -> float:
        return 3 * max(0, target - max(len(col) for col in state[0])) + len(state[1])

    came = {start: None}
    order = itertools.count()
    queue = [(short(start), next(order), 0, start)]
    while queue and len(came) < _PLAN_NODES:
        _f, _n, made, state = heapq.heappop(queue)
        if max(len(col) for col in state[0]) >= target:
            path = []
            while came[state] is not None:
                state, (card, _src, dst) = came[state]
                path.append((_named(card), dst))
            return path[::-1]
        for move in _pile_moves(state):
            nxt = _pile_apply(state, move)
            if nxt not in came:
                came[nxt] = (state, move)
                heapq.heappush(queue, (short(nxt) + _PLAN_COST * (made + 1), next(order),
                                       made + 1, nxt))
    return None


def move_card(b: Board, card: str, dest: tuple) -> None:
    """Drag *card* onto a column or into a free cell; tap it up to its foundation."""
    if dest[0] == "F":
        tap_card(b, card, settle=0.8)
        return
    if dest[0] == "T":
        bottom = b.bottom(dest[1])
        end = _centre(b.rects[bottom]) if bottom else b.places["T"][dest[1]]
    else:
        used = {i for _c, (a, i, _d) in b.cards.items() if a == "C"}
        end = b.places["C"][next(i for i in range(4) if i not in used)]
    drag_points(_centre(b.rects[card]), end)


def _landed(b: Board | None, card: str, dest: tuple) -> bool:
    got = b.cards.get(card) if b else None
    return bool(got) and got[0] == dest[0] and (dest[0] != "T" or got[1] == dest[1])


@says("Deal a new game: menu, New, Yes")
def new_deal() -> Board:
    ui.expect(ui.open_table_drawer(), "the in-game menu did not open for New")
    ui.expect(ui.tap("drawer_new", settle=2.0), "New could not be tapped")
    if wait_alert("abandon", timeout=2.0):
        helpers.answer_alert("Yes", settle=1.5)
    ui.settle_prompts()
    ui.expect(ui.at_table(timeout=8.0), "New did not leave a game table")
    b = settled_board()
    ui.expect(b is not None and len(b) == 52, "could not read the 52 cards off the new deal")
    return b


@says(lambda target=13, max_moves=24, deals=6: f"Build a {target}-card pile in one column: "
      f"plan legal moves, then drag the cards one by one")
def build_long_pile(target: int = 13, max_moves: int = 24, deals: int = 6) -> tuple[Board, list[str]]:
    """Play this deal until one column holds *target* cards; a deal with no
    plan of *max_moves* or fewer is swapped for a new one. Run with the
    playfield raised, where the pile still fits. (board, the pile top first)."""
    b = settled_board()
    ui.expect(b is not None and len(b) == 52, "could not read the 52 cards off the table")
    path = None
    for deal in range(deals):
        path = plan_pile(b, target)
        if path and len(path) <= max_moves:
            break
        print(f"  this deal has no {target}-card pile within {max_moves} moves"
              + (" — dealing another" if deal + 1 < deals else ""), flush=True)
        path = None
        if deal + 1 < deals:
            b = new_deal()
    ui.expect(path, f"none of {deals} deals had a {target}-card pile within {max_moves} moves")
    print(f"  {len(path)} moves to a {target}-card pile", flush=True)
    made = replans = 0
    while path:
        card, dest = path.pop(0)
        move_card(b, card, dest)
        ui.answer_prompt("tip")
        made += 1
        after = read_board()
        if not _landed(after, card, dest):
            after = settled_board()
        if not _landed(after, card, dest) or len(b.moved(after)) != 1:
            replans += 1
            ui.expect(after is not None and replans <= 3,
                      f"move {made} ({card} to {dest}) did not go as planned "
                      f"(board: {after.text() if after else 'unreadable'})")
            path = plan_pile(after, target)
            ui.expect(path, f"no {target}-card pile left after move {made} went off plan "
                            f"(board: {after.text()})")
            print(f"  move {made} ({card}) went off plan — {len(path)} new moves", flush=True)
        b = after
    b = settled_board() or b
    col = max(range(TABLEAU), key=lambda i: len(b.column(i)))
    pile = b.column(col)
    ui.expect(len(pile) >= target, f"the longest column has {len(pile)} cards after {made} "
                                   f"moves, not {target} (board: {b.text()})")
    print(f"  column {col + 1} holds {len(pile)} cards after {made} moves", flush=True)
    return b, pile


def pile_gaps(b: Board, pile: list[str]) -> list[float]:
    """Points from each card's top to the next one's, top of the pile first."""
    ys = [b.rects[card]["y"] for card in pile]
    return [below - above for above, below in zip(ys, ys[1:])]


def folded(b: Board, pile: list[str]) -> list[str]:
    """The pile's cards drawn too close to the next one to show their rank.

    Read by name: while a pile is folded its column's empty-slot image
    leaves the tree, so Board's columns are off by one there."""
    return [card for card, gap in zip(pile, pile_gaps(b, pile)) if gap < FOLDED_GAP]


# ── Auto Hint ──────────────────────────────────────────────────────
# Auto Hint (ships OFF) shows the next card to play once the table is left
# alone: about 8.6 s after the last tap that card starts to pulse, growing
# with a golden glow and shrinking back every ~1.2 s, so 1.5-3 % of the
# playfield changes from one frame to the next. OFF, nothing on an idle
# table changes a pixel once the tapped card has landed (~2 s). The pulse
# is not in the tree: the cards keep their rects.

AUTO_HINT = "Auto Hint"
HINT_BAND = (0, 500, 1290, 1750)   # px: free cells, foundations, columns (raised)
HINT_WATCH = 15.0
HINT_LANDED = 3.0
HINT_QUIET = 4.0
HINT_PULSE = 0.01


class IdleWatch(NamedTuple):
    start: float | None        # seconds after the tap the pulse began
    box: tuple | None          # pixel box the pulse covered
    peak: float                # most of HINT_BAND changed between two frames
    last: float                # seconds after the tap of the last frame
    still: bytes               # the last frame before the pulse
    popped: bytes | None       # the pulse frame furthest from ``still``


def movable(b: Board) -> str | None:
    """A bottom card a tap moves: up to its foundation, onto another column,
    or into a free cell."""
    bottoms = [card for card in (b.bottom(i) for i in range(TABLEAU)) if card]
    up = set(_next_up(b))
    return (next((card for card in bottoms if card in up), None)
            or next((card for card in bottoms if _fits_column(b, card, empty=False)), None)
            or (bottoms[0] if bottoms and cells_used(b) < 4 else None))


@says(lambda b, card, seconds=HINT_WATCH: f"Tap {card}, then leave the table alone for "
                                          f"{seconds:.0f} s, capturing it all along")
def tap_and_idle(b: Board, card: str, seconds: float = HINT_WATCH) -> list[tuple[float, bytes]]:
    """(seconds after the tap, PNG) per frame, back to back."""
    frames = []
    with no_idle_wait():
        t0 = time.time()
        tap_card(b, card, settle=0.0)
        while time.time() - t0 < seconds:
            frames.append((time.time() - t0, helpers.grab_png()))
    return frames


def idle_after_move(b: Board) -> tuple[str, list[tuple[float, bytes]]]:
    """(card tapped, frames) for a move and the idle stretch after it. A tip
    alert over the table spoils the frames, so the move is made again."""
    for attempt in (1, 2):
        card = movable(b)
        ui.expect(card, f"no bottom card has a move (board: {b.text()})")
        frames = tap_and_idle(b, card)
        if not ui.settle_prompts() or attempt == 2:
            break
        print("  an alert came up while the table sat idle — moving again", flush=True)
        b = settled_board() or b
    return card, frames


@says("Compare the frames from the card landing on: does a card pulse as the hint?")
def idle_pulse(frames: list[tuple[float, bytes]]) -> IdleWatch:
    import io

    import numpy as np

    x0, y0, x1, y1 = HINT_BAND

    def band(png):
        return ui.screen_rgb(io.BytesIO(png))[y0:y1, x0:x1].astype(np.int16)

    after = [(at, png) for at, png in frames if at >= HINT_LANDED]
    ui.expect(len(after) >= 2, f"only {len(after)} frames after {HINT_LANDED:.0f} s")
    prev, still = band(after[0][1]), after[0][1]
    start, union, peak, pulsing = None, None, 0.0, []
    for at, png in after[1:]:
        cur = band(png)
        mask = np.abs(cur - prev).max(axis=2) > 32
        frac = float(mask.mean())
        peak = max(peak, frac)
        if frac >= HINT_PULSE:
            start = at if start is None else start
            union = mask if union is None else union | mask
        if start is None:
            still = png
        else:
            pulsing.append(png)
        prev = cur
    box = popped = None
    if union is not None:
        ys, xs = np.nonzero(union)
        box = (int(xs.min()) + x0, int(ys.min()) + y0, int(xs.max()) + x0, int(ys.max()) + y0)
        base = band(still)
        popped = max(pulsing, key=lambda png: int((np.abs(band(png) - base).max(axis=2) > 32).sum()))
    return IdleWatch(start, box, peak, after[-1][0], still, popped)


def card_at(b: Board, box: tuple) -> str | None:
    """The card drawn on top at the centre of pixel *box*."""
    scale = helpers.pixel_scale()
    cx, cy = (box[0] + box[2]) / 2 / scale, (box[1] + box[3]) / 2 / scale
    hits = [(depth, card) for card, (_area, _index, depth) in b.cards.items()
            if b.rects[card]["x"] <= cx <= b.rects[card]["x"] + b.rects[card]["width"]
            and b.rects[card]["y"] <= cy <= b.rects[card]["y"] + b.rects[card]["height"]]
    return max(hits)[1] if hits else None


def save_png(png: bytes, name: str) -> str:
    path = config.LOG / f"{name}.png"
    path.write_bytes(png)
    return str(path)


# ── Rank Strip ─────────────────────────────────────────────────────
# Rank Strip (ships ON) draws A…K under the cards, with ♠♣ and ♥♦ at its
# ends. In the tree the ranks are an Other 279 x 54 pt cut into 13 slots, A
# first, holding an element for each rank still in play: a rank whose four
# cards are all up is left blank. The suits are two 49 pt Others. Touching a
# rank lights its four cards gold; touching a suit lights the next three of
# that suit to go up. The light stays until the strip is touched again. OFF,
# the strip is not drawn and its elements sit below the screen (y 3312 pt).

RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
STRIP_SUITS = ("spade", "club", "heart", "diamond")
STRIP_SYMBOLS = {"spade": "♠", "club": "♣", "heart": "♥", "diamond": "♦"}
STRIP_FROM_Y, STRIP_TO_Y = 500, 880
LIT = 0.15   # gold share of a card's visible part: lit 0.20-0.27, unlit at most 0.08


class Strip(NamedTuple):
    row: dict          # the 13 rank slots
    shown: list[str]   # ranks drawn on it
    pairs: list[dict]  # ♠♣ then ♥♦


def rank_strip(tree: dict | None = None) -> Strip | None:
    """The rank strip as the tree has it, or None when it is not on screen."""
    row, pairs, slots = None, [], []
    for node in nodes(tree if tree is not None else source()):
        r = node.get("rect") or {}
        if node.get("type") not in ("Other", "XCUIElementTypeOther") or not r \
                or not STRIP_FROM_Y <= r["y"] <= STRIP_TO_Y or not 50 <= r["height"] <= 60:
            continue
        if 250 <= r["width"] <= 300:
            row = r
        elif 44 <= r["width"] <= 54:
            pairs.append(r)
        elif 18 <= r["width"] <= 26:
            slots.append(r)
    if row is None or len(pairs) != 2:
        return None
    step = row["width"] / len(RANKS)
    shown = sorted({round((s["x"] - row["x"]) / step) for s in slots
                    if row["x"] - 2 <= s["x"] < row["x"] + row["width"]})
    return Strip(row, [RANKS[i] for i in shown if 0 <= i < len(RANKS)],
                 sorted(pairs, key=lambda r: r["x"]))


def strip_rank(strip: Strip, rank: str) -> tuple[float, float]:
    step = strip.row["width"] / len(RANKS)
    return (strip.row["x"] + (RANKS.index(rank) + 0.5) * step,
            strip.row["y"] + strip.row["height"] / 2)


def strip_suit(strip: Strip, suit: str) -> tuple[float, float]:
    k = STRIP_SUITS.index(suit)
    pair = strip.pairs[k // 2]
    return pair["x"] + (k % 2 + 0.5) * pair["width"] / 2, pair["y"] + pair["height"] / 2


def ranks_in_play(b: Board) -> list[str]:
    """Ranks with a card that is not up on its foundation, A first."""
    return [RANKS[rank - 1] for rank in range(1, 14)
            if any(b.cards.get(f"{suit}-{rank}", ("F",))[0] != "F" for suit in _SUITS)]


def of_rank(b: Board, rank: str) -> list[str]:
    return sorted(card for card, (area, _i, _d) in b.cards.items()
                  if area != "F" and _rank(card) == RANKS.index(rank) + 1)


def next_of_suit(b: Board, suit: str, count: int = 3) -> list[str]:
    """The *count* lowest cards of *suit* not yet up."""
    off = sorted((_rank(card), card) for card, (area, _i, _d) in b.cards.items()
                 if area != "F" and card.startswith(f"{suit}-"))
    return sorted(card for _, card in off[:count])


def lit_cards(b: Board, path) -> list[str]:
    """Cards off the foundations drawn with the gold light on *path*. Only
    the part of a column card that the next card leaves showing is read."""
    img = ui.screen_rgb(path).astype(int)
    scale = helpers.pixel_scale()
    lit = []
    for card, (area, index, depth) in b.cards.items():
        if area == "F":
            continue
        r = b.rects[card]
        bottom = r["y"] + r["height"]
        if area == "T":
            col = b.column(index)
            if depth + 1 < len(col):
                bottom = b.rects[col[depth + 1]]["y"]
        patch = img[int(r["y"] * scale) + 4:int(bottom * scale) - 4,
                    int(r["x"] * scale) + 4:int((r["x"] + r["width"]) * scale) - 4]
        if not patch.size:
            continue
        red, green, blue = patch[..., 0], patch[..., 1], patch[..., 2]
        gold = (red > 200) & (green > 160) & (blue < 170) & (red - blue > 60)
        if float(gold.mean()) >= LIT:
            lit.append(card)
    return sorted(lit)


@says(lambda point, what, name: f"Touch {what} on the rank strip")
def touch_strip(point: tuple[float, float], what: str, name: str) -> str:
    """Tap *point* (WDA points) and capture the table once the light is drawn."""
    tap_point(*point, settle=1.2)
    return str(ui.shoot(name))


# Under the board, Solo and Daily alike: the level line, then "tap a card to
# start" until the first move. Lower down the score, then "0:00 X98" (timer
# and multiplier); they sit lower once the tap-to captions go.
TABLE_FOOTER = (200, 1760, 1090, 1920)
HUD_BAND = (380, 2080, 900, 2480)
TIMER = re.compile(r"(\d+):(\d{2})")
SCORE_ONLY = re.compile(r"[\d,.\u201a ]+")


@says("Read the text under the cards (level line and captions)")
def table_footer(shot: str) -> list[str]:
    """The footer's lines, top first."""
    return [text for _y, text in ocr.rows(ocr.read(shot, box=TABLE_FOOTER))]


@says("Read the timer and the score under the cards")
def hud(shot: str) -> tuple[int | None, int | None]:
    """(timer in seconds, score) under the board. A lone "0" score is too
    small for Vision, so None stands for 0 before anything is scored."""
    timer = score = None
    for _y, text in ocr.rows(ocr.read(shot, box=HUD_BAND)):
        match = TIMER.search(text)
        if match:
            timer = int(match.group(1)) * 60 + int(match.group(2))
        elif score is None and SCORE_ONLY.fullmatch(text.strip()):
            found = ocr.numbers(text)
            score = found[0] if found else None
    return timer, score


@says("Read the timer and the score under the cards")
def hud_after_move(name: str, tries: int = 6, wait: float = 1.2) -> tuple[str, int | None, int | None]:
    """(shot, timer, score) once both read. A card going up floats a large
    "X156" multiplier across the HUD for a few seconds, and Vision cannot
    read the timer or score under it."""
    for attempt in range(tries):
        shot = ui.shoot(name)
        timer, score = hud(shot)
        if timer is not None and score is not None:
            break
        if attempt + 1 < tries:
            print(f"  the timer or score is unreadable ({mmss(timer)}, {score}) — "
                  "reading again once the multiplier has floated off", flush=True)
            time.sleep(wait)
    return shot, timer, score


def mmss(seconds: int | None) -> str:
    return "?" if seconds is None else f"{seconds // 60}:{seconds % 60:02d}"


# ── Options controls ───────────────────────────────────────────────

SLIDERS = {
    "Applause Volume": "p.table._tit2.slider",
    "Effects Volume": "p.table._tit3.slider",
    "Card Lowering": "p.table._tit13.slider",
    "UI Brightness": "p.table._tit16.slider",
}
SWITCHES = {
    "Auto Mute Sounds": "p.table._tit4",
    "Maintain Card Spacing": "p.table._tit9",
    "Card Bouncing": "p.table._tit10",
    "Game Center": "p.table._tit30",
}
_KNOB = 15.5   # UISlider thumb half-width in points


def _control(kind: str, label: str) -> str | None:
    return element(f"type == 'XCUIElementType{kind}' AND label == '{_quote(label)}'")


def _on_screen(r: dict | None) -> bool:
    return bool(r) and r["x"] >= 0 and 60 <= r["y"] <= 850


def control_rect(kind: str, label: str, max_swipes: int = 6) -> tuple[str, dict] | None:
    """(id, rect) of an Options control once it is on screen."""
    for attempt in range(max_swipes * 2 + 1):
        eid = _control(kind, label)
        r = rect(eid) if eid else None
        if eid and _on_screen(r):
            return eid, r
        down = attempt < max_swipes and not (r and r["y"] < 60)
        ui._nudge(up=down)
    return None


def slider_value(human: str) -> float | None:
    eid = _control("Slider", SLIDERS[human])
    value = attr(eid, "value") if eid else None
    try:
        return float(str(value).strip().rstrip("%")) / 100.0
    except (TypeError, ValueError):
        return None


@says(lambda human, target: f"Drag the {human} slider to {target:.0%}")
def slider_drag(human: str, target: float) -> float | None:
    """Drag the knob to *target* (0..1); the ends overshoot the track."""
    found = control_rect("Slider", SLIDERS[human])
    if not found:
        return None
    _, r = found
    now = slider_value(human)
    if now is None:
        return None
    span = r["width"] - 2 * _KNOB
    y = r["y"] + r["height"] / 2
    x_from = r["x"] + _KNOB + now * span
    if target <= 0.0:
        x_to = r["x"] - 30
    elif target >= 1.0:
        x_to = r["x"] + r["width"] + 30
    else:
        x_to = r["x"] + _KNOB + target * span
    drag_points((x_from, y), (x_to, y))
    time.sleep(0.4)
    return slider_value(human)


def slider_adjust(human: str, target: float) -> float | None:
    """XCTest's adjustToNormalizedSliderPosition, which drags the real thumb."""
    found = control_rect("Slider", SLIDERS[human])
    if not found:
        return None
    text = f"{min(max(target, 0.0), 1.0):.3f}"
    try:
        _post(f"/session/{helpers.current_session()}/element/{found[0]}/value",
              {"value": [text], "text": text}, timeout=30)
    except Exception:  # noqa: BLE001
        return None
    helpers.gesture_pause()
    time.sleep(0.4)
    return slider_value(human)


@says(lambda human, target, tol=0.04, tries=8: f"Move the {human} slider to {target:.0%}")
def slider_set(human: str, target: float, tol: float = 0.04, tries: int = 8) -> float | None:
    """Bisect the thumb position until the slider reads *target*.

    FreeCell's sliders do not read back the position they were dragged to
    (50% reads 33%), so each drag is corrected from the value it produced.
    A slider that ignores a few adjusts throws the bisection off, so a miss
    starts it over once.
    """
    got = slider_value(human)
    if got is not None and abs(got - target) <= tol:
        return got
    for _round in range(2):
        lo, hi, pos = 0.0, 1.0, target
        for _ in range(tries):
            got = slider_adjust(human, pos)
            if got is None:
                return slider_drag(human, target)
            if abs(got - target) <= tol:
                return got
            lo, hi = (pos, hi) if got < target else (lo, pos)
            pos = (lo + hi) / 2
    return got


def switch_state(human: str) -> bool | None:
    eid = _control("Switch", SWITCHES[human])
    value = attr(eid, "value") if eid else None
    if value is None:
        return None
    return str(value).strip() in ("1", "true", "True")


@says(lambda human: f"Tap the {human} switch")
def switch_tap(human: str) -> bool | None:
    found = control_rect("Switch", SWITCHES[human])
    if not found:
        return None
    tap_rect(found[1], settle=1.0)
    return switch_state(human)


@says(lambda human, on: f"Turn the {human} switch {'ON' if on else 'OFF'}")
def switch_set(human: str, on: bool) -> bool | None:
    state = switch_state(human)
    if state is None or state == on:
        return state
    return switch_tap(human)


SPACING = "Maintain Card Spacing"


@says(lambda on, where: f"Check {SPACING} reads {'ON' if on else 'OFF'} on Options")
def confirm_spacing(on: bool, where: str) -> None:
    state = switch_state(SPACING) if control_rect("Switch", SWITCHES[SPACING]) else None
    ui.expect(state is not None, f"{SPACING} switch not found on Options ({where})")
    ui.expect(state is on, f"{SPACING} reads {'ON' if state else 'OFF'} on Options ({where}), "
                           f"expected {'ON' if on else 'OFF'}")
    print(f"  {SPACING} reads {'ON' if on else 'OFF'} on Options ({where})", flush=True)


def set_spacing(on: bool) -> bool:
    return switch_set(SPACING, on) is on


def restore_spacing() -> bool:
    return ui.restore_option(set_spacing, SPACING)


@says("Scroll back to the top of Options")
def options_top() -> None:
    ui.scroll_to_end(False, max_swipes=6)


@says("Make sure Game Center is switched on in Options")
def game_center_on() -> None:
    """From the main menu: Options' Game Center switch on, then back to the menu.

    FreeCell turns the switch off when its first Game Center sign-in does not
    finish, e.g. when the phone goes offline straight after the first launch.
    While it is off, Victory and Last Score draw suit symbols where their
    leaderboards and achievements links belong.
    """
    ui.expect(ui.open_options(), "Options did not open from the menu")
    clear_ad("Options", wait=2.0 if is_online() else 0.0)
    found = control_rect("Switch", SWITCHES["Game Center"], max_swipes=8)
    ui.expect(found, "Options' Game Center switch was not found at the bottom of the page")
    if switch_state("Game Center") is not True:
        r = found[1]
        # The last row sits under the test banner's button: tap the switch's lower edge.
        tap_point(r["x"] + r["width"] * 0.3, r["y"] + r["height"] * 0.85, settle=1.5)
        if not helpers.in_app():
            tap_back_to_app() or resume()
        ui.expect(switch_state("Game Center") is True, "Options' Game Center switch would "
                  f"not turn on (see {ui.shoot('GameCenterOff')})")
        print("  Options' Game Center switch was off — turned it on", flush=True)
    ui.back()
    ui.expect(ui.on_menu(6.0) or ui.to_menu(), "Options back did not return to the main menu")


# ── interstitials ──────────────────────────────────────────────────

# Every FreeCell screen a run can stand on has one of these.
LANDMARKS = ("menu_play", "back_game", "page_back", "daily_back", "screen_play",
             "difficulty_easy", "look_close", "screen_options", "contact_us",
             "drawer_options", "table_menu", "screen_about", "screen_help",
             "screen_faq", "screen_stats", "screen_more_games", "screen_table",
             "tableau", "hint_hints", "hint_undo", "screen_choose_look",
             "screen_victory", "screen_last_score")
CLOSE_NAMES = ("Close", "close", "Close Advertisement", "Close ad", "Dismiss",
               "Skip", "skip", "Done", "closeButton", "close button", "X")
MANUAL_WAIT = 300.0
MANUAL_CLOSES: set[str] = set()


def freecell_ui_showing() -> bool:
    img = ui.screen_rgb()
    for name in LANDMARKS:
        if ui.have(name) and ui._locate_in(name, img):
            return True
    if ui.find_ink("back_game", img) or ui.find_ink("table_menu", img):
        return True
    return bool(helpers.alert_text())


def ad_up() -> bool:
    """True when FreeCell is in front but none of its own screens is showing,
    twice a second apart (a screen transition shows no landmark either)."""
    if not helpers.in_app() or freecell_ui_showing():
        return False
    time.sleep(1.0)
    return helpers.in_app() and not freecell_ui_showing()


@says(lambda timeout=20.0: f"Wait up to {timeout:.0f} s for an ad to appear")
def wait_ad(timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not helpers.in_app():
            return False
        if ad_up():
            return True
        time.sleep(1.0)
    return False


# The creatives' X is drawn, not published in the tree: ad_close is its white
# glyph, matched only in the top corners (pixels) so ad artwork elsewhere
# cannot be mistaken for it. AD_X_POINTS are measured X centres (points),
# tapped only after the glyph has had time to appear.
AD_CORNERS = ((0, 0, 400, 600), (890, 0, 1290, 600))
AD_X_POINTS = ((29, 83),)
AD_X_AFTER = 20.0
# Some playable end cards draw no X until their App Store sheet has been
# opened and closed. A tap shows an "Open Store" pill (top-left, pixels) for
# about a second only, so it is pressed straight off the next screenshot.
STORE_PILL = (0, 150, 500, 400)


def _tap_close_control() -> str:
    names = ", ".join(f"'{_quote(n)}'" for n in CLOSE_NAMES)
    eid = element("(type == 'XCUIElementTypeButton' OR type == 'XCUIElementTypeImage' "
                  "OR type == 'XCUIElementTypeOther') AND "
                  f"(name IN {{{names}}} OR label IN {{{names}}})")
    r = rect(eid) if eid else None
    if not r or r.get("width", 0) <= 0:
        return ""
    tap_rect(r, settle=2.0)
    return f"named {attr(eid, 'name') or attr(eid, 'label') or 'close'!r}"


def _tap_ad_x() -> str:
    if not ui.have("ad_close"):
        return ""
    img = ui.screen_rgb()
    for x0, y0, x1, y1 in AD_CORNERS:
        hit = ui.find_ink("ad_close", img[y0:y1, x0:x1])
        if hit:
            point = (x0 + hit[0], y0 + hit[1])
            helpers.tap(point, settle=2.0)
            return f"ad_close at {point}"
    return ""


def _tap_open_store() -> str:
    if not ui.have("ad_open_store"):
        return ""
    x0, y0, x1, y1 = STORE_PILL
    hit = ui.find_ink("ad_open_store", ui.screen_rgb()[y0:y1, x0:x1])
    if not hit:
        return ""
    point = (x0 + hit[0], y0 + hit[1])
    helpers.tap(point, settle=2.5)
    return f"Open Store at {point}"


@says(lambda where, budget=150.0: f"Close the ad ({where}) with its X / close buttons")
def close_ad(where: str, budget: float = 150.0) -> bool:
    """Close an interstitial chain (video, store sheet, playable) by its
    close controls until FreeCell's own UI is back."""
    deadline = time.time() + budget
    started = time.time()
    last_measured = 0.0
    taps = []
    while time.time() < deadline:
        if not helpers.in_app():
            print(f"  the {where} ad left FreeCell for {helpers.active_app()} — "
                  "coming back", flush=True)
            tap_back_to_app() or resume()
            continue
        if freecell_ui_showing():
            if taps:
                print(f"  closed the {where} ad ({', '.join(taps)})", flush=True)
            return True
        hit = _tap_close_control() or _tap_ad_x()
        if hit:
            taps.append(hit)
            continue
        now = time.time()
        if now - started >= AD_X_AFTER and now - last_measured >= AD_X_AFTER:
            for x, y in AD_X_POINTS:
                tap_point(x, y, settle=0.2)
            last_measured = now
            taps.append("measured X")
            store = _tap_open_store()
            if store:
                taps.append(store)
            else:
                time.sleep(1.8)
            continue
        time.sleep(2.0)
    shot = ui.shoot(f"ad_unclosed_{re.sub(r'[^a-z0-9]+', '_', where.lower())}")
    print(f"  could not close the {where} ad within {budget:.0f}s — see {shot}",
          flush=True)
    return False


@says(lambda where, wait=3.0: f"An ad came up ({where}) — close it", done=True)
def clear_ad(where: str, wait: float = 3.0) -> bool:
    """Close an ad if one shows within *wait* seconds. True when one closed."""
    if wait_ad(timeout=wait):
        return close_or_wait(where)
    return False


@says(lambda where, budget=150.0: f"Close the ad ({where}) with its X / close buttons")
def close_or_wait(where: str, budget: float = 150.0) -> bool:
    """close_ad, then the fallback: ask for a hand close and wait for it.
    A hand close is remembered in MANUAL_CLOSES so the case can say so."""
    if close_ad(where, budget=budget):
        return True
    print("Manual effort required at this step", flush=True)
    print(f"  Close the {where} ad on the phone; the test continues when "
          "FreeCell's own screen is back.", flush=True)
    deadline = time.time() + MANUAL_WAIT
    while time.time() < deadline:
        if not helpers.in_app():
            tap_back_to_app() or resume()
        elif freecell_ui_showing():
            MANUAL_CLOSES.add(where)
            print(f"  {where} ad closed by hand — continuing", flush=True)
            return True
        time.sleep(1.5)
    raise AssertionError(f"the {where} ad was still up after {MANUAL_WAIT:.0f}s "
                         "of waiting for a hand close")


def wait_foreign_alert(where: str) -> bool:
    """An alert that is none of FreeCell's own prompts (iOS's "Device Added to
    Your Account", say) is never answered by the suite: ask for a hand close
    and wait for it. Only its first line is printed — the rest can name the
    Apple account. True when one was up and went."""
    if ui.prompt_now() != "" or ui.clear_overlays():
        return False
    text = helpers.alert_text().strip()
    if not text:
        return False
    title = text.splitlines()[0]
    print("Manual effort required at this step", flush=True)
    print(f"  An alert FreeCell did not raise covers {where}: '{title}'. Close it on the "
          "phone; the test continues when it is gone.", flush=True)
    deadline = time.time() + MANUAL_WAIT
    while time.time() < deadline:
        if not helpers.alert_text():
            print("  the alert was closed by hand — continuing", flush=True)
            time.sleep(1.0)
            return True
        time.sleep(1.5)
    raise AssertionError(f"the alert '{title}' covered {where} for {MANUAL_WAIT:.0f}s "
                         "and was not closed by hand")


@says(lambda level="easy", attempts=3: f"Start a new {level.title()} game: Play, then "
                                       f"{level.title()}")
def enter_game(level: str = "easy", attempts: int = 3) -> None:
    """Play → *level* onto a table, closing any ad that comes first."""
    for _ in range(attempts):
        if ui.start_game(level):
            return
        if is_online() and helpers.in_app() and ad_up():
            close_or_wait(f"{level} deal")
            ui.answer_prompt("abandon")
            if ui.at_table(timeout=4.0):
                ui.await_rules_prompt()
                return
        if not ui.on_menu(2.0):
            menu()
    raise AssertionError(f"{level.title()} did not reach the game table")


# ── support page ───────────────────────────────────────────────────

SUPPORT_TITLES = ("PeopleFun Support", "Helpshift")


@says("Wait for the support page to load and read its title")
def support_title(timeout: float = 24.0) -> str:
    """The loaded support page's header, or "" if it never appeared."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for title in SUPPORT_TITLES:
            q = _quote(title)
            if element(f"label CONTAINS '{q}' OR name CONTAINS '{q}' "
                       f"OR value CONTAINS '{q}'"):
                return title
        time.sleep(1.0)
    return ""
