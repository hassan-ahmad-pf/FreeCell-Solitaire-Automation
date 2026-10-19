"""Per-case results: each automated test records the TestRail cases it covers.

    with case("OP-03") as c:
        c.shot(ui.shoot("OptionsApplause"))
        ui.expect(..., "Applause Volume did not reach the left end")

A failed check raises out of the block, which records the case as ``fail``
and stops the test, so the cases after it read ``not reached``. Pass
``soft=True`` when the next cases do not depend on this one: the failure is
recorded and the test carries on (it still ends FAIL). ``skip`` is for a case
this run cannot reach by design (no fresh install); ``block`` for one the
phone's setup prevents (no Mail account).

``tests/run_all.py`` calls ``begin()`` before every test and reads
``results()`` after it. A test run on its own prints its cases at exit.
"""
from __future__ import annotations

import atexit
import time
from contextlib import contextmanager

_TEST = ""
_RESULTS: list[dict] = []
_STANDALONE = True
_TITLES: dict[str, str] = {}


class _Case:
    def __init__(self, cid: str):
        self.cid = cid
        self.shots: list[str] = []
        self.notes: list[str] = []

    def shot(self, path):
        self.shots.append(str(path))
        return path

    def note(self, text: str) -> None:
        self.notes.append(str(text))


def begin(test: str) -> None:
    global _TEST, _STANDALONE
    _TEST = test
    _STANDALONE = False
    _RESULTS.clear()


def titles(mapping: dict[str, str]) -> None:
    """Print each case's title after its id."""
    _TITLES.update(mapping)


def results() -> list[dict]:
    return [dict(r) for r in _RESULTS]


def failed() -> list[str]:
    return [r["id"] for r in _RESULTS if r["status"] == "fail"]


def _record(cid: str, status: str, detail: str = "", rec: _Case | None = None,
            elapsed: float = 0.0) -> None:
    for old in [r for r in _RESULTS if r["id"] == cid]:
        _RESULTS.remove(old)
    _RESULTS.append({
        "id": cid, "status": status, "detail": detail,
        "shots": rec.shots if rec else [], "notes": rec.notes if rec else [],
        "test": _TEST, "seconds": round(elapsed, 1),
    })
    mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "block": "BLOCKED"}[status]
    took = f" ({elapsed:.1f}s)" if status in ("pass", "fail") else ""
    print(f"    [{mark}] {cid}{_title(cid)}{took}" + (f" — {detail}" if detail else ""),
          flush=True)


def _title(cid: str) -> str:
    return f" {_TITLES[cid]}" if cid in _TITLES else ""


@contextmanager
def case(cid: str, soft: bool = False):
    rec = _Case(cid)
    print(f"    [RUN ] {cid}{_title(cid)}", flush=True)
    start = time.time()
    try:
        yield rec
    except Exception as exc:  # noqa: BLE001
        _record(cid, "fail", str(exc) or type(exc).__name__, rec, time.time() - start)
        if not soft:
            raise
    else:
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
