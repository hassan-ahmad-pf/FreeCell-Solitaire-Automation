#!/usr/bin/env python3
"""Run the regression with a live console an audience can follow.

Runs tests/freecell_suite/run_all.py (arguments passed through) and turns its
output into a readable view: each test as a header followed by the list of
its cases in the order they run, then each case as it starts (▶ n/N), the
numbered steps it performs, and its end (PASS / FAIL / SKIP and its time),
with the runner's notes dimmed. A status bar kept at the bottom shows the
case running and its clock, the case up next, progress, passes and failures,
and the time left (estimated from the last run). A rerun of failed tests (the runner's default) shows as its own
section, and a case that passes there moves from failed to passed. The
plain output is saved to log/regression_<time>.log, and the HTML report
opens at the end (--no-open keeps it closed). Stopped midway, the report
of the cases run so far is written and opened at once.

Colours and the status bar need a terminal. Output to a pipe or an agent's
shell is plain unless FORCE_COLOR=1, which brings the colours back (the
status bar stays off there).

Run:  ./scripts/regression.sh   (starts WDA and keeps the Mac awake first)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "freecell_suite" / "run_all.py"
RESULTS = ROOT / "log" / "freecell_suite_results.json"
REPORT = ROOT / "scripts" / "gen_suite_report.py"
TTY = sys.stdout.isatty()
COLOR = TTY or os.environ.get("FORCE_COLOR", "") not in ("", "0")

# One calm palette: a steel-blue accent for structure, soft green / red / amber
# for verdicts only, greys for everything the eye can skip. 256-colour codes
# where the terminal has them (Terminal.app, iTerm), plain ANSI otherwise.
RICH = COLOR and ("256" in os.environ.get("TERM", "") or bool(os.environ.get("COLORTERM")))


def _c(code256: str, basic: str) -> str:
    return code256 if RICH else basic


ACCENT = _c("38;5;74", "36")          # headings, rules, the running case
GREEN = _c("38;5;78", "32")
RED = _c("38;5;203", "31")
YELLOW = _c("38;5;179", "33")
CYAN = ACCENT
TEXT = _c("38;5;253", "0")            # case titles
MUTED = _c("38;5;246", "2")           # step text, times
DIM = _c("38;5;242", "2")             # runner notes, details
BOLD = "1"
RULE = _c("38;5;238", "2")            # hairlines
BAR = _c("38;5;252;48;5;236", "7")    # status bar
BADGE = {                             # verdict chips
    "PASS": _c("1;38;5;232;48;5;78", "1;30;42"),
    "FAIL": _c("1;38;5;231;48;5;167", "1;37;41"),
    "SKIP": _c("1;38;5;232;48;5;179", "1;30;43"),
    "BLOCKED": _c("1;38;5;232;48;5;179", "1;30;43"),
    "ONLINE": _c("1;38;5;252;48;5;240", "7"),
}
MARKS = {"PASS": ("✓", "PASS", GREEN), "FAIL": ("✗", "FAIL", RED), "SKIP": ("–", "SKIP", YELLOW),
         "BLOCKED": ("!", "BLOCK", YELLOW), "ONLINE": ("~", "KEPT", DIM)}

PLAN = re.compile(r"^\s+(\d+)/(\d+)\s+(\S+)\s*(?:SKIP — (.*))?$")
CASES = re.compile(r"^cases:\s+(.*?) — (\d+) run")
TEST_START = re.compile(r"^>>> \[(\d+)/(\d+)\] (START|SKIP|RERUN)\s+(\S+)(?: — (.*))?$")
TEST_END = re.compile(r"^<<< \[(\d+)/(\d+)\] (PASS|FAIL|SKIP)\s+(\S+)(?:\s+\(\s*([\d.]+)s\))?")
CASE_RUN = re.compile(r"^\s+\[RUN \] (\S+) ?(.*)$")
CASE_LIST = re.compile(r"^\s+\[LIST\] (\d+|-)/(\d+) (\S+) (.+?)(?: \(not run here: (.*)\))?$")
STEP = re.compile(r"^\s+\[STEP\] (.*)$")
CASE_END = re.compile(r"^\s+\[(PASS|FAIL|SKIP|BLOCKED|ONLINE)\] (\S+) (.+?)"
                      r"(?: \((\d+(?:\.\d+)?)s\))?(?: — (.*))?$")
SUMMARY_TEST = re.compile(r"^  (PASS|FAIL|SKIP|STOP)  (\S+)\s+\((?:\s*([\d.]+)s|not started)\)"
                          r"(?:\s+\+ rerun ([\d.]+)s)?$")
RERUN_HEAD = re.compile(r"^  RERUN — (.*)$")
RERUN_ITEM = re.compile(r"^    (\S+) (.*)  \((\S+)\)$")
RERUN_CASE = re.compile(r"^\s+\[RERUN (PASS|FAIL)\] (\S+) (.*?) — (.*)$")
NOISE = re.compile(r"Warning|warnings\.warn")
ERROR = re.compile(r"^(Traceback|\s+File \"|\w+(Error|Exception)\b)")
DEV_SKIP = "needs the dev build"


def paint(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def badge(mark: str) -> str:
    """A verdict as a coloured chip: ' PASS ' on green, ' FAIL ' on red."""
    symbol, word, _code = MARKS[mark]
    return paint(BADGE[mark], f" {word:<5}") if COLOR else f"{symbol} {word:<5}"


def rule(char: str = "─", code: str = RULE, size: int = 0) -> str:
    return paint(code, char * (size or min(width() - 1, 86)))


def banner(con: "Console", lines: list[tuple[str, str]], code: str = ACCENT) -> None:
    """A boxed block: [(text, colour)] inside a rounded frame."""
    inner = min(width() - 3, 84)
    con.emit(paint(code, "╭" + "─" * inner + "╮"))
    for text, colour in lines:
        for cut in textwrap.wrap(text, inner - 2, drop_whitespace=False,
                                 break_on_hyphens=False) or [""]:
            con.emit(paint(code, "│") + " " + paint(colour, cut) + " " * (inner - 1 - len(cut))
                     + paint(code, "│"))
    con.emit(paint(code, "╰" + "─" * inner + "╯"))


def clock(seconds: float) -> str:
    s = int(max(seconds, 0))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def took(seconds: float) -> str:
    return f"{seconds:.1f}s" if seconds < 60 else f"{int(seconds // 60)}m {int(seconds % 60):02d}s"


def width() -> int:
    return shutil.get_terminal_size((110, 30)).columns or 110


class Console:
    """Lines print above a status bar that a ticker redraws every second."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.t0 = time.time()
        self.total = 0
        self.done = self.passed = self.failed = self.skipped = 0
        self.failures: list[str] = []
        self.plan: list[str] = []
        self.estimate: dict[str, float] = {}
        self.finished: set[str] = set()
        self.test = ""
        self.test_at = (0, 0)
        self.test_t0 = 0.0
        self.running = False
        self.case = ""
        self.case_t0 = 0.0
        self.case_pos = ""          # "2/5": the running case's place in its test's list
        self.listed: list[str] = []  # the running test's cases, in the order they run
        self.ended: set[str] = set()
        self.steps = 0
        self.bar = False
        self.closed = False
        self.paused = False
        self.summary = False
        self.summaries = 0
        self.rerun = False
        self.rescued: list[str] = []
        self.took: dict[str, float] = {}
        self.report = ""
        self.stopping = False
        self.stop_report = False
        self.open_report = True
        self.opened = False

    def emit(self, text: str = "") -> None:
        with self.lock:
            if self.bar:
                sys.stdout.write("\r\033[K")
            sys.stdout.write(text + "\n")
            self._draw()
            sys.stdout.flush()

    def wrap(self, text: str, indent: int, code: str) -> None:
        for line in textwrap.wrap(text, max(width() - indent - 1, 40)) or [""]:
            self.emit(paint(code, " " * indent + line))

    def left(self) -> float | None:
        known, total = False, 0.0
        for name in self.plan:
            if name in self.finished or name not in self.estimate:
                continue
            known = True
            est = self.estimate[name]
            if name == self.test and self.test_t0:
                est = max(est - (time.time() - self.test_t0), 0.0)
            total += est
        return total if known else None

    def _draw(self) -> None:
        if not TTY or self.closed or self.paused or not self.test:
            self.bar = False
            return
        now = time.time()
        parts = [f"elapsed {clock(now - self.t0)}",
                 f"{'rerun' if self.rerun else 'test'} {self.test_at[0]}/{self.test_at[1]} "
                 f"{self.test}"]
        if self.case:
            where = f"{self.case_pos} " if self.case_pos else ""
            parts.append(f"now {where}{self.case} {clock(now - self.case_t0)}")
        upcoming = self.next_case()
        if upcoming:
            parts.append(f"next {upcoming}")
        if self.total:
            parts.append(f"{self.done}/{self.total} cases")
        counts = [(f"✓ {self.passed} passed", GREEN),
                  (f"✗ {self.failed} failed", RED if self.failed else "")]
        left = self.left()
        tail = [f"~{clock(left)} left"] if left is not None else []
        plain = " " + "  ·  ".join(parts + [t for t, _c in counts] + tail) + " "
        if not COLOR or len(plain) > width() - 1:
            sys.stdout.write("\r\033[K" + paint(BAR, plain[:width() - 1]))
        else:
            # the counts keep the bar's background and only change their ink
            sep = paint(BAR, "  ·  ")
            pieces = [paint(BAR, p) for p in parts]
            pieces += [paint(f"{BAR};1;{code}" if code else BAR, t) for t, code in counts]
            pieces += [paint(BAR, t) for t in tail]
            fill = paint(BAR, " " * (width() - 1 - len(plain)))
            sys.stdout.write("\r\033[K" + paint(BAR, " ") + sep.join(pieces)
                             + paint(BAR, " ") + fill)
        self.bar = True

    def next_case(self) -> str:
        return next((c for c in self.listed if c not in self.ended and c != self.case), "")

    def tick(self) -> None:
        while not self.closed:
            time.sleep(1.0)
            with self.lock:
                if self.bar:
                    self._draw()
                    sys.stdout.flush()

    def pause(self, paused: bool = True) -> None:
        with self.lock:
            self.paused = paused
            if self.bar:
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()
            self.bar = False

    def close(self) -> None:
        self.pause()
        self.closed = True


class Printer:
    """banner() target once the live console has closed."""

    @staticmethod
    def emit(text: str = "") -> None:
        print(text)


def last_durations() -> dict[str, float]:
    try:
        tests = json.loads(RESULTS.read_text(encoding="utf-8")).get("tests", [])
    except (OSError, ValueError):
        return {}
    return {t["name"]: float(t.get("estimate") or t.get("seconds") or 0.0)
            for t in tests if t.get("name")}


def handle(con: Console, raw: str) -> None:
    line = raw.rstrip("\n")
    if NOISE.search(line):
        return
    m = RERUN_HEAD.match(line)
    if m:
        rerun_start(con, m.group(1))
        return
    m = STEP.match(line)
    if m:
        step_line(con, m.group(1))
        return
    if con.summary:
        if not line.startswith("-" * 20):
            summary_line(con, line)
        return
    m = RERUN_ITEM.match(line) if con.rerun and not con.test else None
    if m:
        if m.group(3) not in con.plan:
            con.plan.append(m.group(3))
        con.emit(paint(RED, f"   {m.group(1):6} {m.group(2)}") + paint(DIM, f"  ({m.group(3)})"))
        return

    m = RERUN_CASE.match(line)
    if m:
        rerun_case(con, *m.groups())
        return

    m = CASE_LIST.match(line)
    if m:
        list_line(con, *m.groups())
        return

    m = CASE_RUN.match(line)
    if m:
        cid = m.group(1)
        con.case, con.case_t0, con.steps = cid, time.time(), 0
        con.case_pos = (f"{con.listed.index(cid) + 1}/{len(con.listed)}"
                        if cid in con.listed else "")
        where = paint(MUTED, f"{con.case_pos:>5}  ") if con.case_pos else ""
        con.emit("   " + paint(ACCENT, "▶ ") + where + paint(f"{BOLD};{ACCENT}", f"{cid:6} ")
                 + paint(f"{BOLD};{TEXT}", m.group(2)))
        return

    m = CASE_END.match(line)
    if m:
        case_line(con, *m.groups())
        return

    m = TEST_START.match(line)
    if m:
        test_start(con, int(m.group(1)), int(m.group(2)), m.group(3), m.group(4), m.group(5))
        return

    m = TEST_END.match(line)
    if m:
        verdict, name, secs = m.group(3), m.group(4), m.group(5)
        con.finished.add(name)
        con.case = ""
        if verdict != "SKIP":
            spent = float(secs) if secs else time.time() - con.test_t0
            if not con.rerun:
                con.took[name] = spent
            code = GREEN if verdict == "PASS" else RED
            word = "passed" if verdict == "PASS" else "failed"
            con.emit(paint(RULE, "   └─ ") + paint(TEXT, name) + "  "
                     + paint(f"{BOLD};{code}", f"{MARKS[verdict][0]} {word}")
                     + paint(MUTED, f" in {took(spent)}"))
        return

    if not con.test:
        header_line(con, line)
        return

    if line.startswith("=" * 20):
        con.summary = True
        con.summaries += 1
        con.pause()
        heading = ("SUMMARY SO FAR (stopped midway)" if con.stopping
                   else "FINAL SUMMARY (after the rerun)" if con.rerun else "SUMMARY")
        con.emit("")
        banner(con, [(heading, f"{BOLD};{TEXT}")])
        return

    if ERROR.match(line):
        con.emit(paint(RED, "      " + line))
    elif line.startswith("PASS: "):
        con.wrap(line[6:], 6, MUTED)
    elif line.startswith("FAIL: "):
        con.wrap("test failed: " + line[6:], 6, RED)
    elif line.strip().startswith("note:"):
        # bookkeeping (a rerun keeping a first-run pass): quiet, the word only in amber
        first, *rest = textwrap.wrap(line.strip()[5:].strip(), max(width() - 13, 40)) or [""]
        con.emit(paint(YELLOW, "      note  ") + paint(DIM, first))
        for more in rest:
            con.emit(paint(DIM, " " * 12 + more))
    elif line.startswith("WARNING"):
        con.wrap(line.strip(), 6, YELLOW)
    elif line.strip():
        con.wrap("· " + line.strip(), 6, DIM)


def rerun_start(con: Console, what: str) -> None:
    con.summary, con.rerun = False, True
    con.test, con.case, con.running = "", "", False
    con.plan, con.finished, con.estimate = [], set(), dict(con.took)
    con.pause(False)
    con.emit("")
    banner(con, [("↻  RERUN OF FAILED TESTS", f"{BOLD};{YELLOW}"), (what, MUTED)], YELLOW)


def rerun_case(con: Console, verdict: str, cid: str, title: str, detail: str) -> None:
    if verdict == "PASS":
        con.passed += 1
        con.failed -= 1
        if cid in con.failures:
            con.failures.remove(cid)
        con.rescued.append(cid)
        con.emit("   " + badge("PASS") + paint(f"{BOLD};{GREEN}", " ↻ on rerun  ")
                 + paint(f"{BOLD};{TEXT}", f"{cid:6} ") + paint(TEXT, title))
        con.wrap(detail, 13, DIM)
    else:
        con.emit("   " + badge("FAIL") + paint(f"{BOLD};{RED}", " ↻ again     ")
                 + paint(f"{BOLD};{TEXT}", f"{cid:6} ") + paint(TEXT, title))
        con.wrap(detail, 13, RED)


def header_line(con: Console, line: str) -> None:
    m = PLAN.match(line)
    if m:
        name, reason = m.group(3), m.group(4)
        con.plan.append(name)
        est = con.estimate.get(name)
        when = f"~{took(est)}" if est and not reason else ""
        place = paint(DIM, f"   {int(m.group(1)):2}/{m.group(2)}  ")
        if reason:
            con.emit(place + paint(YELLOW, f"{name:26} ") + paint(DIM, f"skipped — {reason}"))
        else:
            con.emit(place + paint(TEXT, f"{name:26} ") + paint(MUTED, f"{when:>9}"))
        return
    m = CASES.match(line)
    if m:
        con.total = int(m.group(2))
        con.emit(paint(MUTED, f"   {'scope':9}") + paint(TEXT, m.group(1)))
        con.emit(paint(MUTED, f"   {'cases':9}") + paint(TEXT, line.split(' — ', 1)[1]))
        con.emit("")
        con.emit(paint(f"{BOLD};{ACCENT}", "   Tests in order") + paint(MUTED, "  (time on the last run)"))
        con.emit("   " + rule(size=min(width() - 4, 60)))
        return
    for key, label in (("device:", "device"), ("wda:", "driver"), ("build:", "build"),
                       ("network:", "network")):
        if line.startswith(key):
            if key == "network:" and "checking" in line:
                con.emit("")
            con.emit(paint(MUTED, f"   {label:9}") + paint(TEXT, line[len(key):].strip()))
            return
    if line.startswith("WARNING"):
        con.emit(paint(YELLOW, "   " + line))
    elif line.strip():
        con.emit(paint(RED if ERROR.match(line) or "fail" in line.lower() else DIM, "   " + line))


def test_start(con: Console, i: int, n: int, kind: str, name: str, reason: str | None) -> None:
    if not con.test:
        known = [con.estimate[t] for t in con.plan if t in con.estimate]
        if sum(known) >= 1:
            source = "the first run" if con.rerun else "the last run"
            con.emit("")
            con.emit(paint(MUTED, f"   {'estimate':9}") + paint(f"{BOLD};{TEXT}", f"~{clock(sum(known))}")
                     + paint(MUTED, f"  (from {source})"))
    con.test, con.test_at, con.test_t0 = name, (i, n), time.time()
    con.running, con.case, con.case_pos = kind != "SKIP", "", ""
    con.listed, con.ended = [], set()
    stamp = clock(time.time() - con.t0)
    place = f"{i:02}/{n}"
    if kind == "SKIP":
        con.emit("")
        con.emit(paint(YELLOW, "▌ ") + paint(DIM, f"{place}  ") + paint(YELLOW, name)
                 + paint(DIM, f"  — skipped: {reason or ''}"))
        return
    code = YELLOW if kind == "RERUN" else ACCENT
    label = f"{place}  {'↻ ' if kind == 'RERUN' else ''}{name}"
    fill = max(min(width() - 1, 86) - len(label) - len(stamp) - 5, 3)
    con.emit("")
    con.emit(paint(code, "▌ ") + paint(MUTED, f"{place}  ")
             + paint(f"{BOLD};{code}", label[len(place) + 2:]) + " "
             + paint(RULE, "─" * fill) + " " + paint(MUTED, stamp))


def list_line(con: Console, pos: str, total: str, cid: str, title: str,
              why: str | None) -> None:
    """The test's cases before it starts: numbered in the order they run,
    then the ones it leaves out."""
    if pos == "1":
        con.emit(paint(MUTED, f"   {total} case{'' if total == '1' else 's'}, "
                              "in the order they run"))
    if pos != "-":
        con.listed.append(cid)
        con.emit(paint(DIM, f"     {pos:>2}  ") + paint(MUTED, f"{cid:6} ") + paint(TEXT, title))
    else:
        con.emit(paint(DIM, "      –  ") + paint(YELLOW, f"{cid:6} {title}")
                 + paint(DIM, f"  (not run here: {why})"))


def step_line(con: Console, text: str) -> None:
    """What the running case is doing now, numbered within the case; a step
    between cases (setup, cleanup) is not numbered."""
    if con.case:
        con.steps += 1
        con.emit(paint(DIM, f"         {con.steps:>2}  ") + paint(MUTED, text))
    else:
        con.emit(paint(DIM, "          ·  ") + paint(MUTED, text))


def case_line(con: Console, mark: str, cid: str, title: str, secs: str | None,
              detail: str | None) -> None:
    code = MARKS[mark][2]
    if con.rerun:
        pass  # a rerun is counted from the runner's [RERUN PASS] / [RERUN FAIL] lines
    elif mark == "PASS":
        con.passed += 1
        con.done += 1
    elif mark == "FAIL":
        con.failed += 1
        con.done += 1
        con.failures.append(cid)
    elif mark in ("SKIP", "BLOCKED") and con.running and not (detail or "").startswith(DEV_SKIP):
        con.skipped += 1
        con.done += 1
    con.ended.add(cid)
    if cid == con.case:
        con.case, con.case_pos = "", ""
    when = f"  {took(float(secs))}" if secs else ""
    ink = f"{BOLD};{RED}" if mark == "FAIL" else TEXT
    con.emit("   " + badge(mark) + "  " + paint(f"{BOLD};{code}", f"{cid:6} ")
             + paint(ink, title) + paint(MUTED, when))
    if detail:
        con.wrap(detail, 14, RED if mark == "FAIL" else DIM)


def summary_line(con: Console, line: str) -> None:
    m = SUMMARY_TEST.match(line)
    if m:
        verdict, name, secs, again = m.groups()
        spent = took(float(secs)) if secs else "not run"
        chip = badge(verdict) if verdict in MARKS else paint(BADGE["SKIP"], f" {verdict:<5}")
        ink = f"{BOLD};{RED}" if verdict == "FAIL" else TEXT if verdict == "PASS" else DIM
        text = "   " + chip + "  " + paint(ink, f"{name:26}") + paint(MUTED, f" {spent:>9}")
        if again:
            text += paint(YELLOW, f"   + rerun {took(float(again))}")
        con.emit(text)
        return
    if line.startswith("  report: "):
        con.report = line.split(": ", 1)[1].strip()
        if con.stopping:
            con.stop_report = True
            con.emit(paint(YELLOW, f"   report of the cases run so far: {con.report}"))
            show_report(con)
        elif not con.rerun:
            con.emit(paint(DIM, f"   report written: {con.report}"))
        return
    if line.strip().startswith("passed on the rerun:"):
        con.emit(paint(f"{BOLD};{GREEN}", line))
    elif "failed cases:" in line:
        con.emit(paint(f"{BOLD};{RED}", line))
    elif line.startswith("    ") and con.failures:
        # "    MG-01 title — why — rerun fail: why": the case on one line, why under it
        head, _sep, why = line.strip().partition(" — ")
        cid, _sp, title = head.partition(" ")
        con.emit("    " + paint(f"{BOLD};{RED}", f"✗ {cid:6} ") + paint(TEXT, title))
        if why:
            con.wrap(why, 13, DIM)
    elif line.strip().startswith("cases:"):
        con.emit("")
        con.emit(paint(f"{BOLD};{TEXT}", line))
    elif line.strip():
        con.emit(paint(DIM if "network" in line else MUTED, line))


def show_report(con: Console) -> None:
    if con.report and con.open_report and not con.opened and sys.platform == "darwin":
        subprocess.run(["open", con.report], check=False)
        con.opened = True


def report_now(con: Console) -> None:
    """The runner was killed before it wrote its report: write one from the
    results it saved after each finished test."""
    out = ROOT / "log" / "freecell_suite_report.html"
    con.emit(paint(YELLOW, "   writing the report of the tests finished so far…"))
    try:
        proc = subprocess.run([sys.executable, str(REPORT), "--results", str(RESULTS),
                               "--out", str(out), "--stopped"],
                              capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError, KeyboardInterrupt) as exc:
        con.emit(paint(RED, f"   no report: {exc or 'interrupted'}"))
        return
    if proc.returncode:
        con.emit(paint(RED, f"   no report: {proc.stderr.strip()[-300:]}"))
        return
    con.report = str(out)


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--no-open"]
    open_report = "--no-open" not in sys.argv[1:]
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    log_path = ROOT / "log" / f"regression_{stamp}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    con = Console()
    con.open_report = open_report
    con.estimate = last_durations()
    banner(con, [("FreeCell Solitaire  ·  automated regression", f"{BOLD};{TEXT}"),
                 (f"started {datetime.now():%A %d %B %Y, %H:%M}", MUTED)])
    con.emit("")

    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONWARNINGS="ignore")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(ROOT), env.get("PYTHONPATH"))))
    proc = subprocess.Popen([sys.executable, "-u", "-W", "ignore", str(RUNNER), *args],
                            cwd=ROOT, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", bufsize=1)
    threading.Thread(target=con.tick, daemon=True).start()
    stopped = False
    with open(log_path, "w", encoding="utf-8") as log:
        def pump() -> None:
            for raw in proc.stdout:
                log.write(raw)
                log.flush()
                handle(con, raw)
        try:
            pump()
        except KeyboardInterrupt:
            stopped = con.stopping = True
            con.emit(paint(YELLOW, "   stopping — writing the report of the cases run so far, "
                                   "then putting the network back on…"))
            try:
                pump()
            except KeyboardInterrupt:
                proc.kill()
    code = proc.wait()
    if stopped and not con.stop_report:
        report_now(con)
        show_report(con)
    con.close()

    total = time.time() - con.t0
    executed = con.passed + con.failed
    lines: list[tuple[str, str]] = []
    if stopped:
        code = 130
        frame = YELLOW
        lines.append((f"STOPPED after {clock(total)}  ·  {con.passed} passed, "
                      f"{con.failed} failed so far", f"{BOLD};{YELLOW}"))
    elif con.failed:
        frame = RED
        lines.append((f"✗  RESULT  {con.failed} of {executed} cases failed"
                      f"{' after a rerun' if con.rerun else ''}  ·  {clock(total)}",
                      f"{BOLD};{RED}"))
        lines.append((f"   {', '.join(con.failures)}", RED))
    elif executed:
        frame = GREEN
        lines.append((f"✓  RESULT  all {executed} cases passed  ·  {clock(total)}",
                      f"{BOLD};{GREEN}"))
    else:
        frame = RED
        lines.append((f"the runner stopped before any case ran (exit {code})", f"{BOLD};{RED}"))
    if con.rescued and not stopped:
        lines.append((f"   {len(con.rescued)} passed on the rerun after failing the first "
                      f"time: {', '.join(con.rescued)}", GREEN))
    if con.skipped:
        lines.append((f"   {con.skipped} skipped on this install (not failures)", YELLOW))
    lines.append(("", MUTED))

    def short(path: str | Path) -> str:
        try:
            return str(Path(path).resolve().relative_to(ROOT))
        except ValueError:
            return str(path)

    if con.report:
        lines.append((f"report  {short(con.report)}", MUTED))
    lines.append((f"log     {short(log_path)}", MUTED))
    print()
    banner(Printer(), lines, frame)
    show_report(con)
    return code


if __name__ == "__main__":
    sys.exit(main())
