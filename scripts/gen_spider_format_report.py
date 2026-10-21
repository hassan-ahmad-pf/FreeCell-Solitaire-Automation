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
DEFAULT_RESULTS = os.path.join(config.LOG, "spider_suite_results.json")
DEFAULT_OUT = os.path.join(config.LOG, "freecell_spider_regression.html")

CSS = r"""
:root { color-scheme: light;
  --blue-light:#54a4f6; --blue:#316edc; --blue-deep:#1e4cc5;
  --ink:#12305f; --muted:#5a6f95; --line:#d9e4f6; --page:#f3f7fe; --tint:#eef5ff;
  --pass:#1e9e5a; --fail:#d63b3b; --skip:#7d8fb0; }
* { box-sizing: border-box; }
body { margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  color:var(--ink); background:var(--page); min-height:100vh; }
.wrap { max-width:1040px; margin:0 auto; padding:32px 20px 64px; }
.hero { display:flex; align-items:center; justify-content:space-between;
  gap:28px; flex-wrap:wrap; margin-bottom:22px; padding:24px 28px; border-radius:20px;
  color:#fff; background:linear-gradient(160deg, var(--blue-light) 0%, var(--blue) 55%,
  var(--blue-deep) 100%); box-shadow:0 10px 30px rgba(30,76,197,.25); }
.brand { display:flex; align-items:center; gap:16px; min-width:240px; }
.mark { width:68px; height:68px; border-radius:16px; object-fit:cover;
  border:2px solid rgba(255,255,255,.85); box-shadow:0 4px 14px rgba(9,36,110,.35); }
div.mark { display:grid; place-items:center; background:#fff; color:var(--blue);
  font-size:32px; font-weight:700; }
h1 { font-family:"Iowan Old Style","Palatino Linotype",Palatino,serif;
  font-size:26px; margin:0; font-weight:700; letter-spacing:0; color:#fff; }
.sub { color:rgba(255,255,255,.88); font-size:14px; margin-top:4px; }
.hero-stat { display:flex; align-items:center; gap:20px; }
.donut { width:132px; height:132px; border-radius:50%;
  display:grid; place-items:center; flex:0 0 132px;
  box-shadow:0 0 0 3px rgba(255,255,255,.9); }
.donut-hole { width:86px; height:86px; border-radius:50%; background:#fff;
  display:flex; flex-direction:column; align-items:center; justify-content:center; }
.donut-pct { font-family:"Iowan Old Style","Palatino Linotype",Palatino,serif;
  font-size:26px; font-weight:700; line-height:1; color:var(--blue-deep); }
.donut-lbl { color:var(--muted); font-size:10px; letter-spacing:.3px; margin-top:3px; }
.legend { display:flex; flex-direction:column; gap:7px; font-size:13px;
  color:rgba(255,255,255,.88); }
.legend b { color:#fff; font-weight:600; }
.swatch { display:inline-block; width:10px; height:10px; border-radius:50%;
  margin-right:7px; vertical-align:middle; box-shadow:0 0 0 2px #fff; }
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
.attention h2 { font-family:"Iowan Old Style","Palatino Linotype",Palatino,serif;
  font-size:17px; margin:0 0 4px; font-weight:700; }
.attention .lead { color:var(--muted); font-size:13px; margin:0 0 12px; }
.sec { font-family:"Iowan Old Style","Palatino Linotype",Palatino,serif;
  font-size:17px; font-weight:700; margin:28px 0 10px; padding-left:12px;
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
@media (max-width:720px) {
  .hero-stat { width:100%; }
}
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


def _donut(counts: dict, executed: int, rate: float) -> str:
    total = max(sum(counts.values()), 1)
    pass_pct = 100.0 * counts["passed"] / total
    fail_end = pass_pct + 100.0 * counts["failed"] / total
    gradient = (f"conic-gradient(var(--pass) 0 {pass_pct:.2f}%, "
                f"var(--fail) {pass_pct:.2f}% {fail_end:.2f}%, var(--skip) {fail_end:.2f}% 100%)")
    if executed == 0:
        gradient = "conic-gradient(rgba(255,255,255,.35) 0 100%)"
    center = f"{rate:.0f}%" if executed else "—"
    return f"""<div class="hero-stat">
<div class="donut" style="background:{gradient}">
<div class="donut-hole"><div class="donut-pct">{center}</div>
<div class="donut-lbl">pass rate</div></div></div>
<div class="legend">
<div><span class="swatch" style="background:var(--pass)"></span><b>{counts["passed"]}</b> passed</div>
<div><span class="swatch" style="background:var(--fail)"></span><b>{counts["failed"]}</b> failed</div>
<div><span class="swatch" style="background:var(--skip)"></span><b>{counts["skipped"]}</b> skipped</div>
<div style="margin-top:4px">{counts["passed"]}/{executed or 0} executed</div>
</div></div>"""


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
    rate = (100 * counts["passed"] / executed) if executed else 0
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

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FreeCell Solitaire — Regression Report</title>
<style>{CSS}</style></head><body><div class="wrap">
<div class="hero">
<div class="brand">{mark}<div><h1>FreeCell Solitaire</h1>
<div class="sub">Regression report · Spider suite and FreeCell's own cases on the {html.escape(build_kind)} build</div></div></div>
{_donut(counts, executed, rate)}
</div>
<div class="chips">
{_chip("Device", device.get("model"))}
{_chip("Platform", "iOS " + device.get("ios", "") if device.get("ios") else "")}
{_chip("App", app_value)}
{_chip("Screen", device.get("screen"))}
{_chip("Duration", _format_duration(payload.get("duration_seconds")))}
{_chip("Run", _format_run_time(payload.get("finished") or payload.get("started")))}
{_chip("Scope", scope)}
</div>
{_filters(counts)}
{"".join(body)}
<footer>Generated by scripts/gen_spider_format_report.py · cases and titles from the
Spider TestRail suite, plus FreeCell's own cases (Daily, the gameplay timer and score) ·
screenshots are compressed JPEG evidence from log/</footer>
</div><script>{FILTER_JS}</script></body></html>
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
