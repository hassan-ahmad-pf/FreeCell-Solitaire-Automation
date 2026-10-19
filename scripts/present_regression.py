#!/usr/bin/env python3
"""Run the regression with a live console an audience can follow.

Runs tests/spider_suite/run_all.py (arguments passed through) and turns its
output into a readable view: each test as a header, each case when it starts
and when it ends (PASS / FAIL / SKIP and its time), the runner's step notes
dimmed, and a status bar kept at the bottom with the case running and its
clock, progress, passes and failures, and the time left (estimated from the
last run). The plain output is saved to log/regression_<time>.log, and the
HTML report opens at the end (--no-open keeps it closed).

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
RUNNER = ROOT / "tests" / "spider_suite" / "run_all.py"
RESULTS = ROOT / "log" / "spider_suite_results.json"
TTY = sys.stdout.isatty()

GREEN, RED, YELLOW, CYAN, DIM, BOLD, BAR = "1;32", "1;31", "1;33", "1;36", "2", "1", "7"
MARKS = {"PASS": ("✓ PASS ", GREEN), "FAIL": ("✗ FAIL ", RED), "SKIP": ("– SKIP ", YELLOW),
         "LATER": ("… LATER", YELLOW), "BLOCKED": ("! BLOCK", YELLOW), "ONLINE": ("~ KEPT ", DIM)}

PLAN = re.compile(r"^\s+(\d+)/(\d+)\s+(\S+)\s*(?:SKIP — (.*))?$")
CASES = re.compile(r"^cases:\s+(.*?) — (\d+) run")
TEST_START = re.compile(r"^>>> \[(\d+)/(\d+)\] (START|SKIP)\s+(\S+)(?: — (.*))?$")
TEST_END = re.compile(r"^<<< \[(\d+)/(\d+)\] (PASS|FAIL|SKIP)\s+(\S+)(?:\s+\(\s*([\d.]+)s\))?")
CASE_RUN = re.compile(r"^\s+\[RUN \] (\S+) ?(.*)$")
CASE_END = re.compile(r"^\s+\[(PASS|FAIL|SKIP|LATER|BLOCKED|ONLINE)\] (\S+) (.+?)"
                      r"(?: \((\d+(?:\.\d+)?)s\))?(?: — (.*))?$")
SUMMARY_TEST = re.compile(r"^  (PASS|FAIL|SKIP)  (\S+)\s+\(\s*([\d.]+)s\)$")
NOISE = re.compile(r"Warning|warnings\.warn")
ERROR = re.compile(r"^(Traceback|\s+File \"|\w+(Error|Exception)\b)")
DEV_SKIP = "needs the dev build"


def paint(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if TTY else text


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
        self.bar = False
        self.closed = False
        self.summary = False
        self.report = ""

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
        if not TTY or self.closed or not self.test:
            self.bar = False
            return
        now = time.time()
        parts = [f"elapsed {clock(now - self.t0)}",
                 f"test {self.test_at[0]}/{self.test_at[1]} {self.test}"]
        if self.case:
            parts.append(f"now {self.case} {clock(now - self.case_t0)}")
        if self.total:
            parts.append(f"{self.done}/{self.total} cases")
        parts.append(f"{self.passed} passed")
        parts.append(f"{self.failed} failed")
        left = self.left()
        if left is not None:
            parts.append(f"~{clock(left)} left")
        line = " " + "  ·  ".join(parts) + " "
        sys.stdout.write("\r\033[K" + paint(BAR + (";31" if self.failed else ""),
                                            line[:width() - 1]))
        self.bar = True

    def tick(self) -> None:
        while not self.closed:
            time.sleep(1.0)
            with self.lock:
                if self.bar:
                    self._draw()
                    sys.stdout.flush()

    def close(self) -> None:
        with self.lock:
            self.closed = True
            if self.bar:
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()
            self.bar = False


def last_durations() -> dict[str, float]:
    try:
        tests = json.loads(RESULTS.read_text(encoding="utf-8")).get("tests", [])
    except (OSError, ValueError):
        return {}
    return {t["name"]: float(t.get("seconds") or 0.0) for t in tests if t.get("name")}


def handle(con: Console, raw: str) -> None:
    line = raw.rstrip("\n")
    if NOISE.search(line):
        return
    if con.summary:
        summary_line(con, line)
        return

    m = CASE_RUN.match(line)
    if m:
        con.case, con.case_t0 = m.group(1), time.time()
        con.emit(paint(BOLD, f"   ▶ {m.group(1):6} {m.group(2)}"))
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
            code = GREEN if verdict == "PASS" else RED
            con.emit(paint(code, f"   ═ {name} {verdict} in {took(spent)}"))
        return

    if not con.test:
        header_line(con, line)
        return

    if line.startswith("=" * 20):
        con.summary = True
        con.close()
        con.emit("")
        con.emit(paint(CYAN, "━" * min(width() - 1, 78)))
        con.emit(paint(CYAN, "  SUMMARY"))
        con.emit(paint(CYAN, "━" * min(width() - 1, 78)))
        return

    if ERROR.match(line):
        con.emit(paint(RED, "      " + line))
    elif line.startswith("PASS: "):
        con.wrap(line[6:], 6, DIM)
    elif line.startswith("FAIL: "):
        con.wrap("test failed: " + line[6:], 6, RED)
    elif line.strip():
        con.wrap("· " + line.strip(), 6, DIM)


def header_line(con: Console, line: str) -> None:
    m = PLAN.match(line)
    if m:
        name, reason = m.group(3), m.group(4)
        con.plan.append(name)
        est = con.estimate.get(name)
        when = f"~{took(est)}" if est and not reason else ""
        text = f"   {int(m.group(1)):2}/{m.group(2)}  {name:26} {when:>9}"
        con.emit(paint(YELLOW, text + "  skipped: " + reason) if reason else text)
        return
    m = CASES.match(line)
    if m:
        con.total = int(m.group(2))
        con.emit(paint(BOLD, f"   scope    {m.group(1)}"))
        con.emit(paint(BOLD, f"   cases    {line.split(' — ', 1)[1]}"))
        con.emit("")
        con.emit(paint(BOLD, "   tests in order (time on the last run):"))
        return
    for key, label in (("device:", "device"), ("wda:", "driver"), ("build:", "build")):
        if line.startswith(key):
            con.emit(paint(BOLD, f"   {label:8} {line[len(key):].strip()}"))
            return
    if line.strip():
        con.emit(paint(RED if ERROR.match(line) or "fail" in line.lower() else DIM, "   " + line))


def test_start(con: Console, i: int, n: int, kind: str, name: str, reason: str | None) -> None:
    if not con.test:
        known = [con.estimate[t] for t in con.plan if t in con.estimate]
        if known:
            con.emit("")
            con.emit(paint(BOLD, f"   estimated time ~{clock(sum(known))} (from the last run)"))
    con.test, con.test_at, con.test_t0 = name, (i, n), time.time()
    con.running, con.case = kind == "START", ""
    stamp = clock(time.time() - con.t0)
    if kind == "SKIP":
        con.emit("")
        con.emit(paint(YELLOW, f"── [{i:2}/{n}] {name} — skipped: {reason or ''}"))
        return
    title = f"━━ [{i:2}/{n}] {name} "
    con.emit("")
    con.emit(paint(CYAN, title + "━" * max(min(width(), 80) - len(title) - len(stamp) - 2, 3)
                   + f" {stamp}"))


def case_line(con: Console, mark: str, cid: str, title: str, secs: str | None,
              detail: str | None) -> None:
    label, code = MARKS[mark]
    if mark == "PASS":
        con.passed += 1
        con.done += 1
    elif mark == "FAIL":
        con.failed += 1
        con.done += 1
        con.failures.append(cid)
    elif mark in ("SKIP", "BLOCKED") and con.running and not (detail or "").startswith(DEV_SKIP):
        con.skipped += 1
        con.done += 1
    if cid == con.case:
        con.case = ""
    when = f"  ({took(float(secs))})" if secs else ""
    con.emit(paint(code, f"   {label} {cid:6} {title}") + paint(BOLD, when))
    if detail:
        con.wrap(detail, 13, RED if mark == "FAIL" else DIM)


def summary_line(con: Console, line: str) -> None:
    m = SUMMARY_TEST.match(line)
    if m:
        verdict, name, secs = m.groups()
        code = {"PASS": GREEN, "FAIL": RED}.get(verdict, YELLOW)
        con.emit(paint(code, f"   {verdict}  {name:26} {took(float(secs)):>9}"))
        return
    if line.startswith("  report: "):
        con.report = line.split(": ", 1)[1].strip()
        return
    if "failed cases:" in line or line.startswith("    ") and con.failures:
        con.emit(paint(RED, line))
    elif line.strip().startswith("cases:"):
        con.emit(paint(BOLD, line))
    elif line.strip():
        con.emit(paint(DIM if "network" in line else BOLD, line))


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--no-open"]
    open_report = "--no-open" not in sys.argv[1:]
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    log_path = ROOT / "log" / f"regression_{stamp}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    con = Console()
    con.estimate = last_durations()
    rule = "═" * min(width() - 1, 78)
    con.emit(paint(CYAN, rule))
    con.emit(paint(CYAN, "   FreeCell Solitaire — automated regression"))
    con.emit(paint(CYAN, f"   started {datetime.now():%A %d %B %Y, %H:%M}"))
    con.emit(paint(CYAN, rule))

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
            stopped = True
            con.emit(paint(YELLOW, "   stopping — the runner is putting the network back on…"))
            try:
                pump()
            except KeyboardInterrupt:
                proc.kill()
    code = proc.wait()
    con.close()

    total = time.time() - con.t0
    executed = con.passed + con.failed
    print()
    print(paint(CYAN, rule))
    if stopped:
        code = 130
        print(paint(YELLOW, f"   STOPPED after {clock(total)} — {con.passed} passed, "
                            f"{con.failed} failed so far"))
    elif con.failed:
        print(paint(RED, f"   RESULT  ✗ {con.failed} of {executed} cases failed "
                         f"({', '.join(con.failures)})  ·  {clock(total)}"))
    elif executed:
        print(paint(GREEN, f"   RESULT  ✓ all {executed} cases passed  ·  {clock(total)}"))
    else:
        print(paint(RED, f"   the runner stopped before any case ran (exit {code}) — "
                         f"see {log_path}"))
    if con.skipped:
        print(paint(YELLOW, f"           {con.skipped} skipped on this install (not failures)"))
    if con.report:
        print(f"   report  {con.report}")
    print(f"   log     {log_path}")
    print(paint(CYAN, rule))
    if con.report and open_report and sys.platform == "darwin":
        subprocess.run(["open", con.report], check=False)
    return code


if __name__ == "__main__":
    sys.exit(main())
