"""Per-case results: each automated test records the TestRail cases it covers.

    with case("OP-03") as c:
        c.shot(ui.shoot("OptionsApplause"))
        ui.expect(..., "Applause Volume did not reach the left end")

A passing case with no ``c.shot`` still photographs the screen so the
report never says a screenshot is missing.

A failed check records the case as ``fail``. In a suite or named-module
run the rest of the test carries on (it still ends FAIL); a module run
on its own still stops so the cases after it read ``not reached``. Pass
``soft=True`` / ``soft=False`` to force either. ``skip`` is for a case
this run cannot reach by design (no fresh install); ``block`` for one the
phone's setup prevents (no Mail account).

``tests/run_all.py`` calls ``begin()`` before every test and reads
``results()`` after it. A rerun sets ``rerun_only`` to the failed ids so
``case()`` skips every other case's body. A test run on its own prints
its cases at exit.

``step()`` says what the test is doing now, one line under the running case
(``[STEP] …``); helpers decorated with ``says()`` say it themselves.
``c.note()`` prints ``[NOTE]`` at once so findings show at runtime, not only
on the case's PASS line.
"""
from __future__ import annotations

import atexit
import functools
import os
import sys
import threading
import time
from contextlib import contextmanager


def _live_stdio() -> None:
    """Prints reach the presenter as they happen, not after a buffer fills."""
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True, write_through=True)
        except Exception:  # noqa: BLE001
            pass
        try:
            stream.flush()
        except Exception:  # noqa: BLE001
            pass


_live_stdio()

_TEST = ""
_RESULTS: list[dict] = []
_STANDALONE = True
_TITLES: dict[str, str] = {}
_ON_FAIL = None
_DEPTH = 0  # how many says() helpers are running: their inner steps stay quiet
_LAST_STEP = ""
_RERUN_ONLY: set[str] | None = None


class SkipThisCase(Exception):
    """Raised when a rerun should not execute this case's body."""


class _Case:
    def __init__(self, cid: str):
        self.cid = cid
        self.shots: list[str] = []
        self.notes: list[str] = []

    def shot(self, path):
        self.shots.append(str(path))
        step(f"Save the screenshot {os.path.basename(str(path))} as evidence")
        return path

    def note(self, text: str) -> None:
        self.notes.append(str(text))
        if text:
            print(f"      [NOTE] {text}", flush=True)


def begin(test: str) -> None:
    global _TEST, _STANDALONE, _LAST_STEP
    _TEST = test
    _STANDALONE = False
    _LAST_STEP = ""
    _RESULTS.clear()


def rerun_only(ids: list[str] | None) -> None:
    """On a rerun, only these case ids execute. None means run every case."""
    global _RERUN_ONLY
    _RERUN_ONLY = None if ids is None else set(ids)


def rerun_ids() -> set[str] | None:
    """The case ids a rerun is limited to, or None on a full run."""
    return None if _RERUN_ONLY is None else set(_RERUN_ONLY)


def step(text: str) -> None:
    """What the test is doing now, in plain words. Quiet inside a says()
    helper (its own step covers it) and when it repeats the step before."""
    global _LAST_STEP
    if _DEPTH or not text or text == _LAST_STEP:
        return
    _LAST_STEP = text
    print(f"      [STEP] {text}", flush=True)


def ticking(left: float, what: str = "", total: float = 0.0) -> None:
    """One countdown line: seconds left, a fill bar, and what the wait is for."""
    secs = _secs_left(left)
    whole = _secs_left(total) if total > 0 else 0
    extra = f"  {what}" if what else ""
    if whole:
        elapsed = min(whole, max(whole - secs, 0))
        print(f"      [WAIT] {secs}s left / {whole}s  {_bar(elapsed, whole)}{extra}",
              flush=True)
        return
    print(f"      [WAIT] {secs}s left{extra}", flush=True)


def _bar(elapsed: int, total: int, width: int = 20) -> str:
    """A 20-block bar that fills as the wait is used up."""
    if total <= 0:
        return ""
    filled = min(width, int(round(width * elapsed / total)))
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def _secs_left(left: float) -> int:
    """Whole seconds still to wait. Never higher than time left (2.2 → 2).
    The last second stays 1 until the wait ends."""
    if left <= 0:
        return 0
    whole = int(left)
    return whole if whole else 1


@contextmanager
def live(seconds: float, what: str = "", announce: bool | str = True):
    """Count down *seconds* live: a [WAIT] line every second, even while
    other work (play, polling) is running. Yields the deadline."""
    total = max(seconds, 0.0)
    deadline = time.time() + total
    if seconds <= 0:
        yield deadline
        return
    secs = _secs_left(seconds)
    if announce:
        text = (announce if isinstance(announce, str)
                else f"Wait {secs} s" + (f" {what}" if what else ""))
        step(text)
    shown = [None]
    stop = threading.Event()
    lock = threading.Lock()

    def pulse() -> bool:
        left = deadline - time.time()
        if left <= 0:
            return False
        tick = _secs_left(left)
        with lock:
            if tick != shown[0]:
                shown[0] = tick
                ticking(tick, what, total)
        return True

    pulse()
    worker = threading.Thread(target=lambda: _pulse_until(stop, pulse),
                              name="caselog-wait", daemon=True)
    worker.start()
    try:
        yield deadline
    finally:
        stop.set()
        worker.join(timeout=1.0)


def _pulse_until(stop: threading.Event, pulse) -> None:
    while not stop.wait(0.25):
        if not pulse():
            break


def wait(seconds: float, what: str = "") -> None:
    """Sleep *seconds* and count down in the log so the next step is visible."""
    if seconds <= 0:
        return
    with live(seconds, what) as deadline:
        left = deadline - time.time()
        if left > 0:
            time.sleep(left)


def says(describe, done: bool = False):
    """Decorator: each call of the helper is one step, worded by *describe*
    (a string, or a function of the call's arguments returning one or None).
    *done*: said after the call, and only when it returned something true
    (a tap that found its control)."""
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            global _DEPTH
            text = None
            if not _DEPTH:
                try:
                    text = describe(*args, **kwargs) if callable(describe) else describe
                except Exception:  # noqa: BLE001
                    text = None
                if text and not done:
                    step(text)
            _DEPTH += 1
            try:
                result = fn(*args, **kwargs)
            finally:
                _DEPTH -= 1
            if text and done and result:
                step(text)
            return result
        return inner
    return wrap


def titles(mapping: dict[str, str]) -> None:
    """Print each case's title after its id."""
    _TITLES.update(mapping)


def on_fail(capture) -> None:
    """*capture(case_id)* saves the screen as a failed case leaves it and
    returns the path; it becomes the case's last screenshot."""
    global _ON_FAIL
    _ON_FAIL = capture


def _capture(rec: _Case, grab, kind: str) -> None:
    if grab is None:
        return
    try:
        path = grab(rec.cid)
    except Exception as exc:  # noqa: BLE001
        print(f"  (no {kind} screenshot for {rec.cid}: {exc})", flush=True)
        return
    if path:
        rec.shot(path)


def _failure_shot(rec: _Case) -> None:
    _capture(rec, _ON_FAIL, "failure")


def _ensure_shot(rec: _Case) -> None:
    """Every passing case must have evidence. Take the screen if none was saved."""
    if rec.shots:
        return
    try:
        import helpers
        rec.shot(helpers.screenshot(rec.cid))
    except Exception as exc:  # noqa: BLE001
        print(f"  (no screenshot for {rec.cid}: {exc})", flush=True)


def results() -> list[dict]:
    return [dict(r) for r in _RESULTS]


def failed() -> list[str]:
    return [r["id"] for r in _RESULTS if r["status"] == "fail"]


def _record(cid: str, status: str, detail: str = "", rec: _Case | None = None,
            elapsed: float = 0.0, quiet: bool = False) -> None:
    for old in [r for r in _RESULTS if r["id"] == cid]:
        _RESULTS.remove(old)
    _RESULTS.append({
        "id": cid, "status": status, "detail": detail,
        "shots": rec.shots if rec else [], "notes": rec.notes if rec else [],
        "test": _TEST, "seconds": round(elapsed, 1),
    })
    if quiet:
        return
    mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "block": "BLOCKED"}[status]
    took = f" ({elapsed:.1f}s)" if status in ("pass", "fail") else ""
    # Pass notes were already printed live as [NOTE]; only fail/skip/block
    # still carry their reason on this line.
    shown = detail if status != "pass" else ""
    print(f"    [{mark}] {cid}{_title(cid)}{took}" + (f" — {shown}" if shown else ""),
          flush=True)


def _title(cid: str) -> str:
    return f" {_TITLES[cid]}" if cid in _TITLES else ""


@contextmanager
def case(cid: str, soft: bool | None = None):
    global _LAST_STEP
    if _RERUN_ONLY is not None and cid not in _RERUN_ONLY:
        print(f"    [KEEP] {cid}{_title(cid)}", flush=True)
        _record(cid, "pass", "kept first-run pass", quiet=True)
        raise SkipThisCase()
    if soft is None:
        soft = not _STANDALONE
    rec = _Case(cid)
    _LAST_STEP = ""
    print(f"    [RUN ] {cid}{_title(cid)}", flush=True)
    start = time.time()
    try:
        yield rec
    except Exception as exc:  # noqa: BLE001
        elapsed = time.time() - start
        _failure_shot(rec)
        _record(cid, "fail", str(exc) or type(exc).__name__, rec, elapsed)
        if not soft:
            raise
    else:
        _ensure_shot(rec)
        _record(cid, "pass", "; ".join(rec.notes), rec, time.time() - start)


def skip(cid: str, reason: str) -> None:
    _record(cid, "skip", reason)


def block(cid: str, reason: str) -> None:
    _record(cid, "block", reason)


def raise_if_failed() -> None:
    """End a test FAIL when a soft case failed, even though nothing raised."""
    bad = failed()
    if bad:
        raise AssertionError("failed cases: " + ", ".join(bad))


@atexit.register
def _print_standalone() -> None:
    if not _STANDALONE or not _RESULTS:
        return
    counts: dict[str, int] = {}
    for r in _RESULTS:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("  cases: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
