#!/usr/bin/env python3
"""Build a self-contained HTML report for the FreeCell Obj-C regression run.

One expandable card per TestRail case (docs/testrail/cases.py), with the
case's OWN result as recorded by its test through caselog: pass, fail, not
reached (its test stopped before it), skip / blocked, needs dev build (a
--prod run left its test out), not run (its test was not in this
invocation) or online later. Screenshots are the ones the case
attached, embedded as compressed JPEG so the file stays portable.

Run:
  ./.venv/bin/python scripts/gen_regression_report.py
  ./.venv/bin/python scripts/gen_regression_report.py --out log/freecell_regression.html
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "docs" / "testrail"))

import catalog  # noqa: E402
import config  # noqa: E402
from cases import CASES  # noqa: E402

HEADER_LOGO = ROOT / "assets" / "about_emblem.png"
RESULTS = config.LOG / "run_results.json"
OUT = config.LOG / "freecell_regression.html"

# caselog / run_all status -> (filter bucket, pill label)
BUCKET = {
    "pass": ("passed", "passed"),
    "fail": ("failed", "failed"),
    "not reached": ("failed", "not reached"),
    "skip": ("skipped", "skipped"),
    "block": ("skipped", "blocked"),
    "dev build": ("skipped", "needs dev build"),
    "not run": ("skipped", "not run"),
    "online later": ("later", "online later"),
}
COLOR = {
    "passed": "#6f9e7a",
    "failed": "#b85a48",
    "skipped": "#d4b483",
    "later": "#7f97b5",
}

CSS = r"""
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  color:#eef2ec; background:#1d2a22; min-height:100vh; }
.wrap { max-width:1040px; margin:0 auto; padding:32px 20px 64px; }
.hero { display:flex; align-items:center; justify-content:space-between;
  gap:28px; flex-wrap:wrap; margin-bottom:22px; }
.brand { display:flex; align-items:center; gap:16px; min-width:240px; }
.mark { width:64px; height:64px; border-radius:16px; object-fit:contain;
  background:#2c3f33; padding:6px; box-shadow:0 4px 16px rgba(0,0,0,.25); }
h1 { font-family:"Iowan Old Style","Palatino Linotype",Palatino,serif;
  font-size:26px; margin:0; font-weight:700; color:#eef2ec; }
.sub { color:#b5c4b9; font-size:14px; margin-top:4px; }
.hero-stat { display:flex; align-items:center; gap:20px; }
.donut { width:132px; height:132px; border-radius:50%;
  display:grid; place-items:center; flex:0 0 132px;
  box-shadow:inset 0 0 0 1px #3c5245; }
.donut-hole { width:86px; height:86px; border-radius:50%; background:#1d2a22;
  display:flex; flex-direction:column; align-items:center; justify-content:center; }
.donut-pct { font-family:"Iowan Old Style","Palatino Linotype",Palatino,serif;
  font-size:26px; font-weight:700; line-height:1; }
.donut-lbl { color:#b5c4b9; font-size:10px; letter-spacing:.3px; margin-top:3px; }
.legend { display:flex; flex-direction:column; gap:7px; font-size:13px; color:#b5c4b9; }
.legend b { color:#eef2ec; font-weight:600; }
.swatch { display:inline-block; width:9px; height:9px; border-radius:50%;
  margin-right:7px; vertical-align:middle; }
.chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }
.chip { background:#2c3f33; border:1px solid #3c5245; border-radius:10px;
  padding:7px 11px; display:flex; flex-direction:column; min-width:88px; }
.chip .k { font-size:11px; letter-spacing:.2px; color:#b5c4b9; }
.chip .v { font-size:13px; font-weight:600; margin-top:2px; }
.filters { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:28px; }
.filter { appearance:none; background:#2c3f33; border:1px solid #3c5245;
  color:#b5c4b9; border-radius:999px; padding:6px 12px; font:inherit;
  font-size:13px; cursor:pointer; }
.filter b { color:#eef2ec; font-weight:600; }
.filter.is-on { color:#eef2ec; border-color:#c9a64a; background:#344a3c; }
body:not([data-filter="all"]) .attention { display:none; }
body[data-filter="passed"] .case:not(.passed),
body[data-filter="failed"] .case:not(.failed),
body[data-filter="skipped"] .case:not(.skipped),
body[data-filter="later"] .case:not(.later) { display:none; }
body[data-filter="passed"] .group:not([data-has~="passed"]),
body[data-filter="failed"] .group:not([data-has~="failed"]),
body[data-filter="skipped"] .group:not([data-has~="skipped"]),
body[data-filter="later"] .group:not([data-has~="later"]) { display:none; }
.attention { background:#2c3f33; border:1px solid #3c5245; border-left:4px solid #b85a48;
  border-radius:12px; padding:16px 16px 8px; margin-bottom:28px; }
.attention h2 { font-family:"Iowan Old Style","Palatino Linotype",Palatino,serif;
  font-size:17px; margin:0 0 4px; font-weight:700; }
.attention .lead { color:#b5c4b9; font-size:13px; margin:0 0 12px; }
.sec { font-family:"Iowan Old Style","Palatino Linotype",Palatino,serif;
  font-size:17px; font-weight:700; margin:28px 0 10px; padding-left:12px;
  border-left:3px solid #c9a64a; display:flex; align-items:baseline; gap:10px; }
.secstat { font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  font-size:12px; font-weight:500; color:#b5c4b9; }
.case { background:#2c3f33; border:1px solid #3c5245; border-radius:10px;
  margin-bottom:8px; overflow:hidden; border-left:8px solid #6f9e7a; }
.case.failed { border-left-color:#b85a48; }
.case.skipped { border-left-color:#d4b483; }
.case.later { border-left-color:#7f97b5; }
summary { list-style:none; cursor:pointer; display:flex; align-items:center;
  gap:12px; padding:12px 14px; }
summary::-webkit-details-marker { display:none; }
.cid { color:#b5c4b9; font-size:12px; font-variant-numeric:tabular-nums; min-width:44px; }
.title { flex:1; font-weight:600; font-size:14px; }
.pill { color:#1d2a22; font-weight:700; font-size:10px; padding:3px 8px;
  border-radius:999px; letter-spacing:.3px; white-space:nowrap; }
.dur { color:#b5c4b9; font-size:12px; min-width:52px; text-align:right; }
.detail { padding:0 14px 14px; }
.meta { color:#b5c4b9; font-size:12px; margin:0 0 10px; }
.steps { margin:0 0 12px; padding-left:20px; font-size:13px; color:#dfe7e1; }
.steps li { margin-bottom:4px; }
.steps .exp { color:#b5c4b9; }
.shots { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
  gap:12px; margin-top:4px; }
.shot-card { margin:0; }
.shot { display:block; width:100%; max-height:420px; object-fit:contain;
  border-radius:8px; border:1px solid #3c5245; background:#1d2a22; }
.shot-caption { color:#b5c4b9; font-size:11px; margin:6px 0 0; }
.noshot { color:#b5c4b9; font-size:13px; margin:0 0 10px; }
.msg { background:#1d2a22; border:1px solid #3c5245; border-radius:8px;
  padding:10px; color:#ecd2c8; font-size:12px; white-space:pre-wrap;
  overflow-x:auto; margin:0 0 12px; }
footer { color:#b5c4b9; font-size:12px; text-align:center; margin-top:36px; }
@media (max-width:720px) { .hero-stat { width:100%; } }
"""

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


def _duration(seconds) -> str:
    if not seconds:
        return "—"
    seconds = float(seconds)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes}m {rest:02d}s"


def _run_time(value) -> str:
    if not value:
        return "No run recorded"
    try:
        moment = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return str(value)
    offset = moment.strftime("%z")
    if len(offset) == 5:
        offset = f"{offset[:3]}:{offset[3:]}"
    return f"{moment.strftime('%b %-d, %Y, %-I:%M %p')} (UTC{offset or ' local'})"


def _image_uri(path: Path) -> str | None:
    """A resized JPEG data URI, or None when the file is missing or unreadable."""
    if not path.is_file():
        return None
    try:
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((900, 900))
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=78, optimize=True)
    except (OSError, ValueError):
        return None
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def _load(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rows(payload: dict) -> list[dict]:
    """One row per case: run_results' own table, else every case "not run"."""
    by_id = {row["id"]: row for row in payload.get("cases", [])
             if isinstance(row, dict) and row.get("id")}
    rows = []
    for spec in CASES:
        cid = spec["id"]
        row = dict(by_id.get(cid) or {})
        if not row:
            later = cid in catalog.ONLINE_LATER
            row = {"status": "online later" if later else "not run",
                   "detail": catalog.ONLINE_LATER.get(cid, ""),
                   "test": catalog.owner(cid) or "", "shots": [], "seconds": 0}
        row["spec"] = spec
        row["bucket"], row["label"] = BUCKET.get(row["status"], ("skipped", row["status"]))
        rows.append(row)
    return rows


def _chip(label: str, value) -> str:
    return (f'<div class="chip"><span class="k">{html.escape(label)}</span>'
            f'<span class="v">{html.escape(str(value or "—"))}</span></div>')


def _card(row: dict, uri_cache: dict) -> str:
    spec = row["spec"]
    bucket = row["bucket"]
    parts = []
    test = row.get("test") or ""
    if bucket == "later":
        parts.append(f'<p class="meta">Online - later: {html.escape(row.get("detail", ""))}</p>')
    elif test:
        parts.append(f'<p class="meta">Automated by <code>{html.escape(test)}</code></p>')
    if row["status"] == "not run":
        parts.append(f'<p class="noshot">Not in this invocation — run '
                     f'<code>run_all.py {html.escape(test)}</code>.</p>')
    elif row.get("detail") and bucket != "later":
        parts.append(f'<pre class="msg">{html.escape(row["detail"])}</pre>')
    steps = "".join(
        f'<li>{html.escape(action)}<br><span class="exp">→ {html.escape(expected)}</span></li>'
        for action, expected in spec["steps"])
    parts.append(f'<ol class="steps">{steps}</ol>')

    found = []
    for shot in dict.fromkeys(row.get("shots", [])):
        path = Path(shot)
        if not path.is_absolute():
            path = config.LOG / path
        key = str(path)
        if key not in uri_cache:
            uri_cache[key] = _image_uri(path)
        if uri_cache[key]:
            found.append(
                f'<figure class="shot-card"><img class="shot" src="{uri_cache[key]}" '
                f'alt="{html.escape(path.name)}"><figcaption class="shot-caption">'
                f'{html.escape(path.name)}</figcaption></figure>')
    if found:
        parts.append(f'<div class="shots">{"".join(found)}</div>')
    elif bucket in ("passed", "failed"):
        parts.append('<p class="noshot">No screenshot attached to this case.</p>')

    opened = " open" if bucket == "failed" else ""
    return (
        f'<details class="case {bucket}"{opened}><summary>'
        f'<span class="cid">{html.escape(spec["id"])}</span>'
        f'<span class="title">{html.escape(spec["title"])}</span>'
        f'<span class="pill" style="background:{COLOR[bucket]}">'
        f'{html.escape(row["label"])}</span>'
        f'<span class="dur">{_duration(row.get("seconds"))}</span></summary>'
        f'<div class="detail">{"".join(parts)}</div></details>'
    )


def _donut(counts: dict) -> str:
    total = max(sum(counts.values()), 1)
    executed = counts["passed"] + counts["failed"]
    stops, start = [], 0.0
    for bucket in ("passed", "failed", "skipped", "later"):
        end = start + 100.0 * counts[bucket] / total
        stops.append(f"{COLOR[bucket]} {start:.2f}% {end:.2f}%")
        start = end
    gradient = "conic-gradient(" + ", ".join(stops) + ")"
    center = f"{100 * counts['passed'] / executed:.0f}%" if executed else "—"
    legend = "".join(
        f'<div><span class="swatch" style="background:{COLOR[b]}"></span>'
        f'<b>{counts[b]}</b> {label}</div>'
        for b, label in (("passed", "passed"), ("failed", "failed"),
                         ("skipped", "skipped / not run"), ("later", "online - later")))
    return (f'<div class="hero-stat"><div class="donut" style="background:{gradient}">'
            f'<div class="donut-hole"><div class="donut-pct">{center}</div>'
            f'<div class="donut-lbl">pass rate</div></div></div>'
            f'<div class="legend">{legend}<div style="margin-top:4px">'
            f'{counts["passed"]}/{executed} executed</div></div></div>')


def _filters(counts: dict) -> str:
    chips = [("all", "All", sum(counts.values())), ("passed", "Passed", counts["passed"]),
             ("failed", "Failed", counts["failed"]), ("skipped", "Skipped", counts["skipped"]),
             ("later", "Online - later", counts["later"])]
    buttons = "".join(
        f'<button type="button" class="filter{" is-on" if key == "all" else ""}" '
        f'data-filter="{key}" aria-pressed="{"true" if key == "all" else "false"}">'
        f'{html.escape(label)} <b>{n}</b></button>'
        for key, label, n in chips)
    return f'<div class="filters" role="group" aria-label="Filter cases">{buttons}</div>'


def build(results: Path = RESULTS, out: Path = OUT) -> Path:
    catalog.validate(CASES)
    payload = _load(results)
    rows = _rows(payload)
    counts = {"passed": 0, "failed": 0, "skipped": 0, "later": 0}
    sections: OrderedDict[str, list] = OrderedDict()
    for row in rows:
        counts[row["bucket"]] += 1
        sections.setdefault(row["spec"]["section"].split(" > ")[-1], []).append(row)

    uri_cache: dict = {}
    body = []
    failed = [row for row in rows if row["bucket"] == "failed"]
    if failed:
        body.append('<section class="attention"><h2>Needs attention</h2>'
                    f'<p class="lead">{len(failed)} case{"s" if len(failed) != 1 else ""} '
                    'failed or not reached in this run</p>')
        body.extend(_card(row, uri_cache) for row in failed)
        body.append("</section>")
    for section, items in sections.items():
        passed = sum(row["bucket"] == "passed" for row in items)
        present = " ".join(sorted({row["bucket"] for row in items}))
        body.append(f'<section class="group" data-has="{present}">'
                    f'<h2 class="sec">{html.escape(section)}'
                    f'<span class="secstat">· {passed}/{len(items)}</span></h2>')
        body.extend(_card(row, uri_cache) for row in items)
        body.append("</section>")

    device = payload.get("device", {})
    app = payload.get("app", {})
    app_value = " ".join(x for x in (
        app.get("name"), app.get("version"),
        f"(build {app['build']})" if app.get("build") else "") if x) or "—"
    logo = _image_uri(HEADER_LOGO)
    mark = (f'<img class="mark" src="{logo}" alt="FreeCell emblem">' if logo
            else '<div class="mark"></div>')
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FreeCell Solitaire — Regression Report</title>
<style>{CSS}</style></head><body><div class="wrap">
<div class="hero">
<div class="brand">{mark}<div><h1>FreeCell Solitaire</h1>
<div class="sub">Regression report · Obj-C build · {len(rows)} TestRail cases</div></div></div>
{_donut(counts)}
</div>
<div class="chips">
{_chip("Device", device.get("model"))}
{_chip("Platform", "iOS " + device["ios"] if device.get("ios") else "")}
{_chip("App", app_value)}
{_chip("Build", payload.get("build_kind"))}
{_chip("Screen", device.get("screen"))}
{_chip("Duration", _duration(payload.get("duration_seconds")))}
{_chip("Run", _run_time(payload.get("finished") or payload.get("started")))}
</div>
{_filters(counts)}
{"".join(body)}
<footer>Generated by scripts/gen_regression_report.py from log/run_results.json ·
screenshots are compressed JPEG evidence from log/</footer>
</div><script>{FILTER_JS}</script></body></html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(document, encoding="utf-8")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    print(f"wrote {build(args.results, args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
