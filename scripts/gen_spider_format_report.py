#!/usr/bin/env python3
"""Generate the FreeCell regression report in Spider's report format.

Spider's scripts/gen_regression_report.py layout — header, pass-rate donut,
run chips, filters, "Needs attention", then every TestRail case grouped by
section with its screenshots — fed by tests/spider_suite/run_all.py's
log/spider_suite_results.json. Each case carries its own status and
evidence; dev-build and later cases show as skipped with the reason.

Run:  ./.venv/bin/python scripts/gen_spider_format_report.py
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import math
import os
import sys
from collections import OrderedDict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "tests", "spider_suite"), ROOT]

from PIL import Image  # noqa: E402

import catalog  # noqa: E402
import config  # noqa: E402

HEADER_LOGO = os.path.join(ROOT, "assets", "report_icon.png")  # the App Store icon
DISPLAY_FONT = os.path.join(ROOT, "assets", "report_font_outfit.woff2")  # SIL OFL, see *_OFL.txt
DEFAULT_RESULTS = os.path.join(config.LOG, "spider_suite_results.json")
DEFAULT_OUT = os.path.join(config.LOG, "freecell_spider_regression.html")

CSS = r"""
:root { color-scheme: light;
  --blue-light:#54a4f6; --blue:#316edc; --blue-deep:#1e4cc5;
  --ink:#12305f; --muted:#5a6f95; --line:#d9e4f6; --page:#f3f7fe; --tint:#eef5ff;
  --pass:#1e9e5a; --fail:#d63b3b; --skip:#7d8fb0;
  --display:"Outfit",-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }
* { box-sizing: border-box; }
body { margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  color:var(--ink); background:var(--page); min-height:100vh; }
.wrap { max-width:1040px; margin:0 auto; padding:32px 20px 64px; }
.hero { display:flex; align-items:flex-start; justify-content:space-between;
  gap:20px 28px; flex-wrap:wrap; padding:28px 32px 96px; border-radius:22px;
  color:#fff; background:linear-gradient(160deg, var(--blue-light) 0%, var(--blue) 55%,
  var(--blue-deep) 100%); box-shadow:0 10px 30px rgba(30,76,197,.25); }
.hero-meta { text-align:right; font-size:13px; color:rgba(255,255,255,.88); line-height:1.6; }
.badge { display:inline-block; padding:3px 10px; border-radius:999px; font-size:11px;
  font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#fff;
  background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.45); margin-bottom:4px; }
.brand { display:flex; align-items:center; gap:16px; min-width:240px; }
.mark { width:68px; height:68px; border-radius:16px; object-fit:cover;
  border:2px solid rgba(255,255,255,.85); box-shadow:0 4px 14px rgba(9,36,110,.35); }
div.mark { display:grid; place-items:center; background:#fff; color:var(--blue);
  font-size:32px; font-weight:700; }
h1 { font-family:var(--display); font-size:28px; margin:0; font-weight:600;
  letter-spacing:0; color:#fff; }
.sub { color:rgba(255,255,255,.88); font-size:14px; margin-top:4px; }
.score { position:relative; margin:-72px 20px 24px; padding:30px 36px;
  background:#fff; border-radius:22px; display:grid; grid-template-columns:auto 1fr;
  gap:40px; align-items:center;
  box-shadow:0 18px 40px rgba(18,48,95,.12), 0 2px 6px rgba(18,48,95,.06); }
.ring { position:relative; width:240px; height:240px; }
.ring svg { display:block; width:100%; height:100%; }
.ring .track { fill:none; stroke:#e9effa; stroke-width:20; }
.ring .arc { fill:none; stroke-width:20; stroke-linecap:round;
  animation:draw 1.3s cubic-bezier(.2,.7,.2,1) both; }
@keyframes draw { from { stroke-dasharray:0 1000; } }
.ring-center { position:absolute; inset:0; display:flex; flex-direction:column;
  align-items:center; justify-content:center; }
.ring-pct { font-family:var(--display); font-size:80px; font-weight:300; line-height:1;
  letter-spacing:-1.5px; color:var(--blue-deep); }
.ring-pct small { font-size:34px; font-weight:400; margin-left:2px; letter-spacing:0; }
.ring-pct.wide { font-size:66px; }
.ring-pct.wide small { font-size:28px; }
.ring-lbl { font-size:11px; font-weight:700; letter-spacing:1.6px; text-transform:uppercase;
  color:var(--muted); margin-top:10px; }
.ring-sub { font-size:12px; color:var(--muted); margin-top:3px; }
.score-k { font-size:11px; font-weight:700; letter-spacing:1.6px; text-transform:uppercase;
  color:var(--blue); }
.verdict { font-family:var(--display); font-size:26px; font-weight:600; margin:6px 0 20px; display:flex; align-items:center;
  gap:12px; }
.verdict .dot { flex:0 0 12px; height:12px; border-radius:50%; background:var(--pass);
  box-shadow:0 0 0 5px rgba(30,158,90,.16); }
.verdict.bad .dot { background:var(--fail); box-shadow:0 0 0 5px rgba(214,59,59,.16); }
.tiles { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; }
.tile { background:var(--tint); border:1px solid var(--line); border-top:4px solid var(--pass);
  border-radius:14px; padding:14px 16px; }
.tile.fail { border-top-color:var(--fail); }
.tile.skip { border-top-color:var(--skip); }
.tile-n { font-family:var(--display); font-size:38px; font-weight:500; line-height:1; color:var(--pass); }
.tile.fail .tile-n { color:var(--fail); }
.tile.skip .tile-n, .tile.none .tile-n { color:var(--skip); }
.tile-k { font-size:13px; font-weight:700; margin-top:8px; }
.tile-s { font-size:12px; color:var(--muted); margin-top:2px; }
.chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }
.filters { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:28px; }
.filter { appearance:none; background:#fff; border:1px solid var(--line);
  color:var(--muted); border-radius:999px; padding:6px 12px; font:inherit;
  font-size:13px; cursor:pointer; }
.filter b { color:var(--ink); font-weight:600; }
.filter.is-on, .filter.is-on b { color:#fff; }
.filter.is-on { border-color:var(--blue); background:var(--blue); }
.filter[data-filter="passed"].is-on { border-color:var(--pass); background:var(--pass); }
.filter[data-filter="failed"].is-on { border-color:var(--fail); background:var(--fail); }
.filter[data-filter="skipped"].is-on { border-color:var(--skip); background:var(--skip); }
body[data-filter="passed"] .attention,
body[data-filter="failed"] .attention,
body[data-filter="skipped"] .attention { display:none; }
body[data-filter="passed"] .case:not(.passed),
body[data-filter="failed"] .case:not(.failed),
body[data-filter="skipped"] .case:not(.skipped) { display:none; }
body[data-filter="passed"] .group:not([data-has~="passed"]),
body[data-filter="failed"] .group:not([data-has~="failed"]),
body[data-filter="skipped"] .group:not([data-has~="skipped"]) { display:none; }
.chip { background:#fff; border:1px solid var(--line); border-radius:10px;
  padding:7px 11px; display:flex; flex-direction:column; min-width:88px;
  box-shadow:0 1px 2px rgba(18,48,95,.05); }
.chip .k { font-size:11px; letter-spacing:.2px; color:var(--muted); }
.chip .v { font-size:13px; font-weight:600; margin-top:2px; }
.attention { background:#fff; border:1px solid var(--line); border-left:4px solid var(--fail);
  border-radius:12px; padding:16px 16px 8px; margin-bottom:28px; }
.attention h2 { font-family:var(--display); font-size:18px; margin:0 0 4px; font-weight:600; }
.attention .lead { color:var(--muted); font-size:13px; margin:0 0 12px; }
.sec { font-family:var(--display); font-size:18px; font-weight:600; margin:28px 0 10px; padding-left:12px;
  border-left:3px solid var(--blue); display:flex; align-items:baseline; gap:10px; }
.secstat { font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  font-size:12px; font-weight:500; color:var(--muted); }
.case { background:#fff; border:1px solid var(--line); border-radius:10px;
  margin-bottom:8px; overflow:hidden; border-left:8px solid var(--pass);
  box-shadow:0 1px 2px rgba(18,48,95,.05); }
.case.failed { border-left-color:var(--fail); }
.case.skipped { border-left-color:var(--skip); }
summary { list-style:none; cursor:pointer; display:flex; align-items:center;
  gap:12px; padding:12px 14px; }
summary:hover { background:var(--tint); }
summary::-webkit-details-marker { display:none; }
.cid { color:var(--muted); font-size:12px; min-width:44px; }
.title { flex:1; font-weight:600; font-size:14px; }
.pill { color:#fff; font-weight:700; font-size:10px; padding:3px 8px;
  border-radius:999px; letter-spacing:.3px; }
.dur { color:var(--muted); font-size:12px; min-width:52px; text-align:right; }
.detail { padding:0 14px 14px; }
.shots { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
  gap:12px; margin-top:4px; }
.shot-card { margin:0; }
.shot { display:block; width:100%; max-height:420px; object-fit:contain;
  border-radius:8px; border:1px solid var(--line); background:var(--tint); }
.shot-caption { color:var(--muted); font-size:11px; margin:6px 0 0; }
.noshot { color:var(--muted); font-size:13px; margin:0 0 10px; }
.msg { background:#fff5f5; border:1px solid #f2c9c9; border-radius:8px;
  padding:10px; color:#8f1d1d; font-size:12px; white-space:pre-wrap;
  overflow-x:auto; margin:0 0 12px; }
.evidence { background:var(--tint); border:1px solid #d3e2fa; border-left:3px solid var(--blue);
  border-radius:8px; padding:10px; color:var(--ink); font-size:12px;
  white-space:pre-wrap; overflow-x:auto; margin:0 0 12px; }
footer { color:var(--muted); font-size:12px; text-align:center; margin-top:36px; }
.deck { position:fixed; inset:0; z-index:0; overflow:hidden; pointer-events:none;
  -webkit-mask-image:linear-gradient(90deg, #000 0, #000 12%, rgba(0,0,0,.3) 28%,
    rgba(0,0,0,.3) 72%, #000 88%, #000 100%);
  mask-image:linear-gradient(90deg, #000 0, #000 12%, rgba(0,0,0,.3) 28%,
    rgba(0,0,0,.3) 72%, #000 88%, #000 100%); }
.wrap { position:relative; z-index:1; }
.pc { position:absolute; left:0; top:0; will-change:transform; }
.pc > i { display:block; animation:deal 1.1s cubic-bezier(.2,.7,.2,1) both; }
.pc b { display:block; position:relative; width:46px; height:64px; border-radius:7px;
  animation:bob var(--dur, 9s) ease-in-out var(--delay, 0s) infinite alternate; }
.pc .face { background:#fff; border:1px solid #cddcf5; color:var(--blue-deep);
  box-shadow:0 8px 18px rgba(30,76,197,.12); font:600 11px/1.05 var(--display); }
.pc .face.red { color:#e05a5a; }
.pc .ix { position:absolute; left:6px; top:5px; text-align:center; }
.pc .pip { position:absolute; inset:0; display:grid; place-items:center; font-size:24px; }
.pc .back { border:3px solid #fff; box-shadow:0 0 0 1px #cddcf5, 0 8px 18px rgba(30,76,197,.18);
  background:repeating-linear-gradient(45deg, rgba(255,255,255,.16) 0 4px, transparent 4px 9px),
    linear-gradient(160deg, var(--blue-light), var(--blue-deep)); }
.pc .back::after { content:"\2660\FE0E"; position:absolute; inset:0; display:grid;
  place-items:center; color:rgba(255,255,255,.8); font-size:18px; }
@keyframes deal { from { opacity:0; transform:translateY(-60px) rotate(-25deg) scale(.7); } }
@keyframes bob { from { transform:translateY(-7px) rotate(-5deg); }
  to { transform:translateY(7px) rotate(5deg); } }
@media (prefers-reduced-motion: reduce) { .pc > i, .pc b { animation:none; } }
@media print { .deck { display:none; } }
@media (max-width:760px) {
  .hero-meta { text-align:left; }
  .score { grid-template-columns:1fr; justify-items:center; margin:-72px 0 24px; padding:24px; }
  .score-side { width:100%; }
}
@media (prefers-reduced-motion: reduce), print { .ring .arc { animation:none; } }
"""

STATUS = {"pass": "passed", "fail": "failed", "skip": "skipped", "block": "skipped",
          "dev": "skipped", "later": "skipped"}
STATUS_PILL = {"passed": "var(--pass)", "failed": "var(--fail)", "skipped": "var(--skip)"}
PILL_TEXT = {"pass": "passed", "fail": "failed", "skip": "skipped", "block": "blocked",
             "dev": "dev build", "later": "later"}

FILTER_JS = """
(function () {
  var buttons = document.querySelectorAll(".filter");
  function apply(mode) {
    document.body.setAttribute("data-filter", mode);
    buttons.forEach(function (button) {
      var on = button.getAttribute("data-filter") === mode;
      button.classList.toggle("is-on", on);
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      apply(button.getAttribute("data-filter"));
    });
  });
  apply("all");
})();
"""

# The background deck: cards on a jittered grid, each at its own depth.
# Nearer cards are larger, stronger and move further per pixel scrolled,
# turning a little; they wrap off-screen so the deck never runs out.
DECK_JS = """
(function () {
  var deck = document.querySelector(".deck");
  if (!deck) return;
  var still = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"];
  var SUITS = [["\\u2660", ""], ["\\u2665", " red"], ["\\u2666", " red"], ["\\u2663", ""]];
  var CELL = 180, SPARE = 240, cards = [], seed, width = 0;
  function rnd() { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }
  function build() {
    width = innerWidth;
    seed = 20261019;
    deck.textContent = "";
    cards = [];
    var span = innerHeight + SPARE;
    var cols = Math.max(4, Math.round(width / CELL)), rows = Math.max(4, Math.round(span / CELL));
    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        var depth = 0.15 + rnd() * 0.55;
        var card = {x: (c + 0.15 + rnd() * 0.7) / cols * width - 23,
                    y: (r + 0.15 + rnd() * 0.7) / rows * span,
                    depth: depth, rot: rnd() * 60 - 30, spin: (rnd() - 0.5) * 0.06,
                    scale: 0.65 + depth * 0.75};
        var outer = document.createElement("div"), deal = document.createElement("i"),
            face = document.createElement("b");
        outer.className = "pc";
        outer.style.opacity = (0.35 + depth * 0.85).toFixed(2);
        deal.style.animationDelay = (card.y / span * 0.9 + rnd() * 0.3).toFixed(2) + "s";
        if (rnd() < 0.3) {
          face.className = "back";
        } else {
          var suit = SUITS[Math.floor(rnd() * 4)], rank = RANKS[Math.floor(rnd() * 13)];
          var pip = suit[0] + "\\ufe0e";
          face.className = "face" + suit[1];
          face.innerHTML = '<span class="ix">' + rank + "<br>" + pip + '</span><span class="pip">'
                           + pip + "</span>";
        }
        face.style.setProperty("--dur", (7 + rnd() * 6).toFixed(1) + "s");
        face.style.setProperty("--delay", (-rnd() * 12).toFixed(1) + "s");
        deal.appendChild(face);
        outer.appendChild(deal);
        deck.appendChild(outer);
        card.el = outer;
        cards.push(card);
      }
    }
    place();
  }
  function place() {
    var scroll = still ? 0 : window.scrollY, span = innerHeight + SPARE;
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var y = ((card.y - scroll * card.depth) % span + span) % span - SPARE / 2;
      card.el.style.transform = "translate3d(" + card.x.toFixed(1) + "px," + y.toFixed(1) + "px,0)"
        + " rotate(" + (card.rot + scroll * card.spin).toFixed(2) + "deg) scale("
        + card.scale.toFixed(2) + ")";
    }
  }
  var queued = false, resizing;
  addEventListener("scroll", function () {
    if (queued || still) return;
    queued = true;
    requestAnimationFrame(function () { queued = false; place(); });
  }, {passive: true});
  addEventListener("resize", function () {
    clearTimeout(resizing);
    resizing = setTimeout(function () { innerWidth !== width ? build() : place(); }, 150);
  });
  build();
})();
"""


def _format_duration(seconds) -> str:
    if seconds in (None, "", 0, 0.0):
        return "—"
    seconds = float(seconds)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remainder = divmod(round(seconds), 60)
    return f"{minutes}m {remainder:02d}s"


def _format_run_time(value) -> str:
    if not value:
        return "No run recorded"
    try:
        moment = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return str(value)
    pretty = moment.strftime("%b %-d, %Y, %-I:%M %p")
    offset = moment.strftime("%z")
    if len(offset) == 5:
        offset = f"{offset[:3]}:{offset[3:]}"
    return f"{pretty} (UTC{offset or ' local'})"


def _image_uri(path: str, box=(900, 900)):
    if not path or not os.path.isfile(path):
        return None
    try:
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail(box)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=78, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    except (OSError, ValueError):
        return None


def _font_face() -> str:
    """Outfit embedded, so the report looks the same where it is not installed."""
    try:
        with open(DISPLAY_FONT, "rb") as fh:
            data = base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return ""
    return ('@font-face { font-family:"Outfit"; font-weight:200 700; font-display:swap; '
            f'src:url(data:font/woff2;base64,{data}) format("woff2"); }}\n')


def _chip(label: str, value) -> str:
    return (f'<div class="chip"><span class="k">{html.escape(label)}</span>'
            f'<span class="v">{html.escape(str(value or "—"))}</span></div>')


def _case_card(row: dict, uri_cache: dict, open_failed: bool = True) -> str:
    status = STATUS[row["status"]]
    color = STATUS_PILL[status]
    detail = [f'<div class="evidence">Automated parent: {html.escape(row["test"])}</div>']
    if row["status"] in ("dev", "later", "skip", "block"):
        detail.append(f'<p class="noshot">Not run on this build: '
                      f'{html.escape(row["detail"] or "")}</p>')
    elif row["status"] == "fail":
        detail.append(f'<pre class="msg">{html.escape(row["detail"] or "")}</pre>')
    elif row.get("detail"):
        detail.append(f'<p class="noshot">{html.escape(row["detail"])}</p>')
    note = catalog.ADAPTED.get(row["id"])
    if note:
        detail.append(f'<p class="noshot">FreeCell: {html.escape(note)}</p>')
    found = []
    for shot in dict.fromkeys(row.get("shots") or []):
        if shot not in uri_cache:
            uri_cache[shot] = _image_uri(shot)
        if uri_cache[shot]:
            name = os.path.basename(shot)
            found.append(f'<figure class="shot-card"><img class="shot" src="{uri_cache[shot]}" '
                         f'alt="{html.escape(name)}"><figcaption class="shot-caption">'
                         f'{html.escape(name)}</figcaption></figure>')
    if found:
        detail.append(f'<div class="shots">{"".join(found)}</div>')
    elif row["status"] in ("pass", "fail"):
        detail.append('<p class="noshot">No screenshot was captured for this case.</p>')
    opened = " open" if (open_failed and status == "failed") else ""
    return (f'<details class="case {status}"{opened}><summary>'
            f'<span class="cid">{html.escape(row["id"])}</span>'
            f'<span class="title">{html.escape(row["title"])}</span>'
            f'<span class="pill" style="background:{color}">'
            f'{html.escape(PILL_TEXT[row["status"]])}</span>'
            f'<span class="dur">{_format_duration(row.get("seconds"))}</span></summary>'
            f'<div class="detail">{"".join(detail)}</div></details>')


RING_SIZE, RING_RADIUS, RING_WIDTH, RING_GAP = 240, 100, 20, 8


def _ring(counts: dict, executed: int) -> str:
    """The executed cases as an SVG ring, passed then failed. Round caps
    reach past each arc's ends, hence the gap; a share too small to see is
    drawn as a dot, taken from the larger arc."""
    centre = RING_SIZE / 2
    circ = 2 * math.pi * RING_RADIUS
    circle = f'cx="{centre}" cy="{centre}" r="{RING_RADIUS}"'
    shapes = [f'<circle class="track" {circle}/>']
    parts = [(n, color) for n, color in ((counts["passed"], "var(--pass)"),
                                         (counts["failed"], "var(--fail)")) if n]
    if len(parts) == 1:
        shapes.append(f'<circle class="arc" {circle} stroke="{parts[0][1]}" '
                      f'stroke-dasharray="{circ:.2f} 0" '
                      f'transform="rotate(-90 {centre} {centre})"/>')
    elif parts:
        lengths = [max(circ * n / executed, RING_WIDTH + RING_GAP + 2) for n, _ in parts]
        lengths[lengths.index(max(lengths))] -= sum(lengths) - circ
        start = 0.0
        for length, (_n, color) in zip(lengths, parts):
            angle = -90 + 360 * (start + (RING_WIDTH + RING_GAP) / 2) / circ
            shapes.append(f'<circle class="arc" {circle} stroke="{color}" '
                          f'stroke-dasharray="{length - RING_WIDTH - RING_GAP:.2f} {circ:.2f}" '
                          f'transform="rotate({angle:.2f} {centre} {centre})"/>')
            start += length
    return (f'<svg viewBox="0 0 {RING_SIZE} {RING_SIZE}" role="img" aria-label="'
            f'{counts["passed"]} passed, {counts["failed"]} failed">{"".join(shapes)}</svg>')


def _score(counts: dict, executed: int) -> str:
    """The result card under the header: the pass-rate ring, a verdict and
    a tile per status. The rate is never rounded up to 100% past a failure."""
    passed, failed, skipped = counts["passed"], counts["failed"], counts["skipped"]

    def share(n: int) -> str:
        return f"{100 * n / executed:.0f}% of executed" if executed else "none executed"

    pct, wide = "—", ""
    if executed:
        rate = 100 * passed / executed
        shown = math.floor(rate) if failed else round(rate)
        pct, wide = f"{shown}<small>%</small>", " wide" if shown == 100 else ""
    if not executed:
        verdict, mood = "No cases were executed", "bad"
    elif failed:
        verdict = f"{failed} case{'s' if failed != 1 else ''} need{'s' if failed == 1 else ''} attention"
        mood = "bad"
    else:
        verdict, mood = f"All {executed} executed cases passed", "good"
    tiles = [("pass", passed, "Passed", share(passed)),
             ("fail" if failed else "fail none", failed, "Failed",
              share(failed) if failed else "nothing failed"),
             ("skip", skipped, "Skipped", "not run on this build")]
    tile_html = "".join(f'<div class="tile {cls}"><div class="tile-n">{n}</div>'
                        f'<div class="tile-k">{label}</div><div class="tile-s">{note}</div></div>'
                        for cls, n, label, note in tiles)
    return f"""<section class="score">
<div class="ring">{_ring(counts, executed)}
<div class="ring-center"><div class="ring-pct{wide}">{pct}</div><div class="ring-lbl">pass rate</div>
<div class="ring-sub">{passed} of {executed} executed</div></div></div>
<div class="score-side"><div class="score-k">Run result</div>
<div class="verdict {mood}"><span class="dot"></span>{html.escape(verdict)}</div>
<div class="tiles">{tile_html}</div></div>
</section>"""


def _filters(counts: dict) -> str:
    chips = [("all", "All", sum(counts.values())), ("passed", "Passed", counts["passed"]),
             ("failed", "Failed", counts["failed"]), ("skipped", "Skipped", counts["skipped"])]
    buttons = []
    for key, label, n in chips:
        on = " is-on" if key == "all" else ""
        pressed = "true" if key == "all" else "false"
        buttons.append(f'<button type="button" class="filter{on}" data-filter="{key}" '
                       f'aria-pressed="{pressed}">{html.escape(label)} <b>{n}</b></button>')
    return f'<div class="filters" role="group" aria-label="Filter cases">{"".join(buttons)}</div>'


def build(results_path: str = DEFAULT_RESULTS, out_path: str = DEFAULT_OUT) -> str:
    try:
        with open(results_path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        payload = {}
    recorded = {row["id"]: row for row in payload.get("cases", [])}

    rows = []
    for case in catalog.CASES:
        cid = case["id"]
        row = recorded.get(cid)
        if row is None:
            owner = catalog.owner(cid)
            reason = (catalog.LATER.get(cid) or catalog.DEV_CASES.get(cid)
                      or (catalog.entry(owner) or [None] * 5)[4] or "not run in this invocation")
            status = "later" if cid in catalog.LATER else "dev" if reason.startswith("needs") else "skip"
            row = {"id": cid, "title": catalog.TITLES[cid], "section": catalog.SECTIONS[cid],
                   "test": owner, "status": status, "detail": reason, "shots": [], "seconds": 0}
        rows.append(row)

    counts = {"passed": 0, "failed": 0, "skipped": 0}
    by_section = OrderedDict()
    failed = []
    for row in rows:
        status = STATUS[row["status"]]
        counts[status] += 1
        by_section.setdefault(row["section"], []).append(row)
        if status == "failed":
            failed.append(row)

    uri_cache: dict = {}
    body = []
    if failed:
        body.append('<section class="attention"><h2>Needs attention</h2>'
                    f'<p class="lead">{len(failed)} failed case{"s" if len(failed) != 1 else ""} '
                    'from this run</p>')
        body.extend(_case_card(row, uri_cache) for row in failed)
        body.append("</section>")
    for section, section_rows in by_section.items():
        passed = sum(STATUS[r["status"]] == "passed" for r in section_rows)
        present = " ".join(sorted({STATUS[r["status"]] for r in section_rows}))
        body.append(f'<section class="group" data-has="{present}">'
                    f'<h2 class="sec">{html.escape(section)}'
                    f'<span class="secstat">· {passed}/{len(section_rows)}</span></h2>')
        body.extend(_case_card(row, uri_cache) for row in section_rows)
        body.append("</section>")

    executed = counts["passed"] + counts["failed"]
    device, app = payload.get("device", {}), payload.get("app", {})
    app_value = " ".join(x for x in (app.get("name"), app.get("version"),
                                     f"(build {app['build']})" if app.get("build") else "")
                         if x).strip() or "—"
    kinds = {}
    for row in rows:
        kinds[row["status"]] = kinds.get(row["status"], 0) + 1
    scope = (f"{kinds.get('pass', 0) + kinds.get('fail', 0)} run · "
             f"{kinds.get('dev', 0)} dev build · "
             f"{kinds.get('skip', 0) + kinds.get('block', 0)} skipped · "
             f"{kinds.get('later', 0)} later")
    logo = _image_uri(HEADER_LOGO, box=(256, 256))
    mark = (f'<img class="mark" src="{logo}" alt="FreeCell Solitaire logo">'
            if logo else '<div class="mark">F</div>')
    build_kind = payload.get("build_kind", "prod")
    run_time = _format_run_time(payload.get("finished") or payload.get("started"))

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FreeCell Solitaire — Regression Report</title>
<style>{_font_face()}{CSS}</style></head><body><div class="deck" aria-hidden="true"></div>
<div class="wrap">
<div class="hero">
<div class="brand">{mark}<div><h1>FreeCell Solitaire</h1>
<div class="sub">Regression report · Spider suite and FreeCell's own cases on the {html.escape(build_kind)} build</div></div></div>
<div class="hero-meta"><span class="badge">{html.escape(build_kind)} build</span><br>
{html.escape(run_time)}<br>{html.escape(app_value)}</div>
</div>
{_score(counts, executed)}
<div class="chips">
{_chip("Device", device.get("model"))}
{_chip("Platform", "iOS " + device.get("ios", "") if device.get("ios") else "")}
{_chip("App", app_value)}
{_chip("Screen", device.get("screen"))}
{_chip("Duration", _format_duration(payload.get("duration_seconds")))}
{_chip("Run", run_time)}
{_chip("Scope", scope)}
</div>
{_filters(counts)}
{"".join(body)}
<footer>Generated by scripts/gen_spider_format_report.py · cases and titles from the
Spider TestRail suite, plus FreeCell's own cases (Daily, the gameplay timer and score) ·
screenshots are compressed JPEG evidence from log/</footer>
</div><script>{FILTER_JS}{DECK_JS}</script></body></html>
"""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(document)
    return out_path


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", default=DEFAULT_RESULTS)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    print(f"wrote {build(args.results, args.out)}")


if __name__ == "__main__":
    main()
