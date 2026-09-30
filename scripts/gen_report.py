#!/usr/bin/env python3
"""Build the FreeCell Unity fidelity report: one page, a build switcher.

The Obj-C baseline is embedded once per screen; every build folder adds its
capture, its diff image and its diff% per screen. Switching build swaps all
of that and re-ranks the screen cards worst first. Each card has a wipe
(drag between Obj-C and the build), a Diff view and an Enlarge lightbox.

Builds are the sub-folders of ``log/unity/`` (newest first), or the folders
passed with ``--dir``. A folder's ``capture.json`` names it ("FreeCell 8.0.0
(353)"); otherwise the folder name is used.

Curated triage is optional: ``reports/notes.json`` maps a build label to
``{"verdict": html, "findings": [[kind, title, detail, scope], ...],
"notes": {screen: text}, "bugs": [screen, ...]}`` with kind one of bug /
drop / layout / minor / ok. Without it the verdict is the numbers.

Run:
  ./.venv/bin/python scripts/gen_report.py
  ./.venv/bin/python scripts/gen_report.py --dir log/objc_pass2 --out log/objc_selfcheck.html
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

import config  # noqa: E402
import visual  # noqa: E402

OUT = ROOT / "reports" / "FreeCell_Unity_Report.html"
NOTES = ROOT / "reports" / "notes.json"
CARD_W, CARD_Q = 480, 80      # baseline + build images (cards show ~360 px)
DIFF_W, DIFF_Q = 720, 74      # side-by-side diff image

SEV = {
    "bug": ("Content bug", "var(--bad)"),
    "drop": ("Dropped element", "var(--warn)"),
    "layout": ("Layout drift", "var(--info)"),
    "minor": ("Minor delta", "var(--muted)"),
    "ok": ("Fixed / correct", "var(--ok)"),
}


def label_of(name: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name)


def uri(path, width, q) -> str:
    img = cv2.imread(str(path))
    if img is None:
        return ""
    h, w = img.shape[:2]
    width = min(width, w)
    small = cv2.resize(img, (width, max(1, int(h * width / w))),
                       interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, q])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode() if ok else ""


def build_folders(dirs) -> list:
    if dirs:
        return [Path(d) for d in dirs]
    root = config.LOG / "unity"
    found = [d for d in root.glob("*") if d.is_dir() and any(d.glob("*.png"))] \
        if root.exists() else []
    return sorted(found, key=lambda d: d.stat().st_mtime, reverse=True)


def folder_identity(folder: Path) -> tuple:
    info = folder / "capture.json"
    data = json.loads(info.read_text()) if info.exists() else {}
    if data.get("version"):
        label = f"{data['version']} ({data.get('build', '?')})"
    else:
        label = folder.name
    started = data.get("started") or dt.datetime.fromtimestamp(
        folder.stat().st_mtime).isoformat(timespec="seconds")
    return label, started[:10]


def sev_of(pct: float, passed: bool) -> str:
    if passed:
        return "lo"
    return "hi" if pct >= 10 else "md"


def findings_html(findings) -> str:
    items = ""
    for kind, title, detail, scope in findings:
        name, colour = SEV[kind]
        items += (f"<li class='fi' style='--c:{colour}'><span class='chip'>{name}"
                  f"</span><div class='ft'><b>{title}</b><span class='fs'>{scope}"
                  f"</span><p>{detail}</p></div></li>")
    return f"<ul class='finds'>{items}</ul>" if items else \
        "<p class='hint'>No curated findings for this build yet (reports/notes.json).</p>"


def tiles_html(compared, total, bugs) -> str:
    pcts = [r["diff_pct"] for r in compared]
    worst = max(compared, key=lambda r: r["diff_pct"])
    over = sum(1 for r in compared if not r["passed"])
    tiles = [
        ("Screens compared", f"{len(compared)}<span class='u'>/{total}</span>",
         "same name, same device"),
        ("Median difference", f"{statistics.median(pcts):.1f}<span class='u'>%</span>",
         "of compared pixels"),
        ("Peak difference", f"{worst['diff_pct']:.0f}<span class='u'>%</span>",
         label_of(worst["name"])),
        ("Over threshold", f"{over}", f"content bugs flagged: {bugs}"),
    ]
    return "".join(f"<div class='tile'><div class='tv'>{v}</div><div class='tk'>{k}"
                   f"</div><div class='td'>{d}</div></div>" for k, v, d in tiles)


def auto_verdict(label, compared, total) -> str:
    over = [r for r in compared if not r["passed"]]
    worst = max(compared, key=lambda r: r["diff_pct"])
    return (f"Build <b>{label}</b>: {len(compared)} of {total} screens compared, "
            f"<b>{len(over)}</b> over their threshold. Peak difference "
            f"<b>{worst['diff_pct']:.1f}%</b> on {label_of(worst['name'])}.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", action="append", default=[],
                        help="build capture folder (repeatable; default log/unity/*)")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    folders = build_folders(args.dir)
    if not folders:
        print("no build captures — put each Unity build's screens in "
              "log/unity/<build>/ (one <Name>.png per screen in visual.SCREENS)")
        return 2
    names = [n for n in visual.SCREENS if (visual.BASELINES / f"{n}.png").exists()]
    if not names:
        print(f"no baselines in {visual.BASELINES} — promote an Obj-C pass first")
        return 2
    curated = json.loads(NOTES.read_text()) if NOTES.exists() else {}

    versions = []
    for folder in folders:
        label, date = folder_identity(folder)
        diff_dir = config.LOG / "diff" / folder.name
        results = [visual.compare(n, visual.capture_shots(folder, n),
                                  diff_dir=diff_dir, label=label) for n in names]
        compared = [r for r in results if r["status"] == "ok"]
        if not compared:
            print(f"  skipped {folder}: nothing comparable")
            continue
        notes = curated.get(label, {})
        screens = {}
        for r in compared:
            name = r["name"]
            screens[name] = {
                "pct": round(r["diff_pct"], 2),
                "max": round(r["max_diff_pct"], 2),
                "sev": sev_of(r["diff_pct"], r["passed"]),
                "img": uri(r["capture"], CARD_W, CARD_Q),
                "diff": uri(r["diff"], DIFF_W, DIFF_Q),
                "note": notes.get("notes", {}).get(name)
                or visual.SCREENS[name].note or visual.SCREENS[name].state,
                "bug": name in notes.get("bugs", []),
            }
        versions.append({
            "id": folder.name, "label": label, "date": date,
            "verdict": notes.get("verdict") or auto_verdict(label, compared, len(names)),
            "tiles": tiles_html(compared, len(names), len(notes.get("bugs", []))),
            "findings": findings_html(notes.get("findings", [])),
            "screens": screens,
            "missing": [r["name"] for r in results if r["status"] != "ok"],
        })
        print(f"  {label}: {len(compared)}/{len(names)} screens")
    if not versions:
        print("nothing comparable in any folder")
        return 2

    data = {
        "order": names,
        "labels": {n: label_of(n) for n in names},
        "baseline": {n: uri(visual.BASELINES / f"{n}.png", CARD_W, CARD_Q)
                     for n in names},
        "versions": versions,
    }
    html = (PAGE.replace("__OBJC__", f"{config.OBJC_VERSION} ({config.OBJC_BUILD})")
            .replace("__RES__", f"{visual.W}×{visual.H}")
            .replace("__ASPECT__", f"{visual.W}/{visual.H}")
            .replace("__DATA__", json.dumps(data)))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html)
    print(f"wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB, "
          f"{len(versions)} build(s))")
    return 0


PAGE = """<!doctype html><meta charset="utf-8"><title>FreeCell — Unity Port Fidelity</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{ --felt:#0d1512; --panel:#151f1a; --panel2:#1b2721; --line:#27342d; --ink:#e9f0ea;
  --muted:#8fa89a; --gold:#e3b64a; --bad:#f0616a; --warn:#e6a13c; --info:#5bb6c9; --ok:#4cba86;
  --disp:"Rockwell","Roboto Slab",Georgia,serif; --body:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace; }
@media (prefers-color-scheme: light){ :root{ --felt:#f4f1e9; --panel:#fffefb; --panel2:#efece2; --line:#e2ddce;
  --ink:#1b2620; --muted:#5d6f66; --gold:#9c6f13; --bad:#c1373f; --warn:#a86c15; --info:#2c7889; --ok:#2c855a; } }
*{box-sizing:border-box}
body{margin:0;background:var(--felt);color:var(--ink);font-family:var(--body);line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto;padding:34px 22px 80px}
.eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);margin:0 0 10px}
h1{font-family:var(--disp);font-weight:700;font-size:clamp(26px,4.4vw,42px);line-height:1.05;margin:0}
.sub{color:var(--muted);margin:10px 0 0;font-size:15px;font-family:var(--mono)}
.vswitch{display:inline-flex;flex-wrap:wrap;gap:2px;margin:20px 0 4px;border:1px solid var(--line);border-radius:11px;padding:3px;background:var(--panel)}
.vswitch button{font-family:var(--mono);font-size:13px;color:var(--muted);background:transparent;border:0;padding:8px 16px;border-radius:8px;cursor:pointer}
.vswitch button.on{background:var(--gold);color:#1a130a;font-weight:700}
.vswitch button .d{font-size:11px;opacity:.7;margin-left:6px}
.verdict{margin:16px 0 0;font-size:clamp(16px,2.2vw,19px);max-width:64ch}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:22px 0 6px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 16px 14px}
.tv{font-family:var(--disp);font-weight:700;font-size:30px;font-variant-numeric:tabular-nums}
.tv .u{font-size:15px;color:var(--muted);font-weight:400;margin-left:1px}
.tk{margin-top:2px;font-size:13px;font-weight:600}.td{color:var(--muted);font-size:12px;margin-top:2px}
.sect{font-family:var(--disp);font-size:20px;font-weight:700;margin:40px 0 4px;display:flex;align-items:center;gap:10px}
.sect::after{content:"";flex:1;height:1px;background:var(--line)}
.hint{color:var(--muted);font-size:13px;margin:6px 0 16px}
.finds{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.fi{display:flex;gap:14px;background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--c);border-radius:12px;padding:13px 15px}
.chip{color:var(--c);border:1px solid color-mix(in srgb,var(--c) 45%,transparent);background:color-mix(in srgb,var(--c) 12%,transparent);
  font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;padding:4px 8px;border-radius:20px;white-space:nowrap;height:max-content;margin-top:2px}
.ft b{font-size:15px}.ft .fs{color:var(--muted);font-family:var(--mono);font-size:11px;margin-left:8px}
.ft p{margin:4px 0 0;color:var(--muted);font-size:13.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px;margin-top:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;overflow:hidden;display:flex;flex-direction:column}
.card.s-hi{border-color:color-mix(in srgb,var(--bad) 42%,var(--line))}
.card.gone{opacity:.45}
.ch{display:flex;align-items:center;justify-content:space-between;padding:13px 15px;background:var(--panel2);border-bottom:1px solid var(--line)}
.ch h3{margin:0;font-family:var(--disp);font-size:16px;font-weight:700}
.pill{font-family:var(--mono);font-weight:700;font-size:13px;font-variant-numeric:tabular-nums;padding:3px 9px;border-radius:20px;color:var(--ok);background:color-mix(in srgb,var(--ok) 14%,transparent)}
.pill.s-md{color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent)}
.pill.s-hi{color:var(--bad);background:color-mix(in srgb,var(--bad) 16%,transparent)}
.cmp{position:relative;background:#000}
.wipe{position:relative;width:100%;aspect-ratio:__ASPECT__;overflow:hidden;touch-action:none}
.wipe img{position:absolute;inset:0;width:100%;height:100%;display:block;object-fit:cover}
.hdl{position:absolute;top:0;bottom:0;left:50%;width:2px;background:var(--gold);transform:translateX(-1px);pointer-events:none}
.hdl::after{content:"";position:absolute;top:50%;left:50%;width:26px;height:26px;transform:translate(-50%,-50%);border-radius:50%;background:var(--gold);box-shadow:0 1px 6px rgba(0,0,0,.5)}
.wipe input{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:ew-resize}
.lab{position:absolute;top:9px;font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:#fff;background:rgba(0,0,0,.55);padding:3px 8px;border-radius:20px;pointer-events:none}
.lab.l{left:9px}.lab.r{right:9px}
.diffimg{display:none;width:100%;height:auto}
.cmp[data-mode="diff"] .wipe{display:none}.cmp[data-mode="diff"] .diffimg{display:block}
.foot{padding:12px 15px 14px;display:flex;flex-direction:column;gap:9px;flex:1}
.segrow{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden}
.seg button,.zoombtn{font-family:var(--mono);font-size:11.5px;color:var(--muted);background:transparent;border:0;padding:5px 12px;cursor:pointer}
.seg button.on{background:var(--gold);color:#1a130a;font-weight:700}
.zoombtn{border:1px solid var(--line);border-radius:9px}
.note{margin:0;color:var(--muted);font-size:13px}
.lb{position:fixed;inset:0;z-index:100;background:rgba(3,7,5,.95);display:flex;align-items:center;justify-content:center;padding:26px}
.lb[hidden]{display:none}
.lbwrap{display:flex;gap:18px;max-width:100%;max-height:100%;overflow:auto;align-items:flex-start}
.lbwrap figure{margin:0;display:flex;flex-direction:column;align-items:center;gap:9px}
.lbwrap img{max-height:85vh;width:auto;border-radius:10px;background:#000}
.lbwrap figcaption{font-family:var(--mono);font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--gold)}
.lbx{position:fixed;top:14px;right:18px;width:42px;height:42px;border-radius:50%;border:0;background:rgba(255,255,255,.15);color:#fff;font-size:20px;cursor:pointer}
footer{color:var(--muted);font-size:12px;font-family:var(--mono);margin-top:40px;text-align:center}
</style>
<div class="wrap">
  <p class="eyebrow">FreeCell · Objective-C → Unity port</p>
  <h1>iPhone 15 Pro Max — Unity Port Fidelity</h1>
  <p class="sub">Obj-C __OBJC__ baseline · __RES__ portrait · switch builds below</p>
  <div class="vswitch" id="vswitch"></div>
  <p class="verdict" id="verdict"></p>
  <div class="tiles" id="tiles"></div>
  <h2 class="sect">Findings · triage</h2>
  <div id="findings"></div>
  <h2 class="sect">Screen by screen</h2>
  <p class="hint">Worst first for the selected build. Drag to wipe between Obj-C and the build, or switch to Diff (changed pixels red, masked areas dimmed). The status bar, cross-promo banner, dealt cards (except the Daily table), dates, scores and QA marks are masked.</p>
  <div class="grid" id="grid"></div>
  <footer>Regenerate with scripts/gen_report.py · masks and thresholds in visual.py</footer>
</div>
<div class="lb" id="lb" hidden>
  <button class="lbx" id="lbx" type="button" aria-label="Close">✕</button>
  <div class="lbwrap">
    <figure><img id="lbb" alt="Obj-C"><figcaption>Obj-C __OBJC__</figcaption></figure>
    <figure><img id="lbt" alt="build"><figcaption id="lbcap"></figcaption></figure>
  </div>
</div>
<script>
const DATA = __DATA__;
const grid = document.getElementById('grid'), cards = {};
let current = null;
DATA.order.forEach(name => {
  const c = document.createElement('article');
  c.className = 'card';
  c.innerHTML = `
    <div class="ch"><h3></h3><span class="pill"></span></div>
    <div class="cmp" data-mode="wipe">
      <div class="wipe">
        <img class="b" src="${DATA.baseline[name]}" alt="Obj-C">
        <img class="t" src="" alt="build">
        <span class="hdl"></span>
        <input type="range" min="0" max="100" value="50" aria-label="wipe">
        <span class="lab l">Obj-C</span><span class="lab r">build</span>
      </div>
      <img class="diffimg" src="" alt="diff">
    </div>
    <div class="foot">
      <div class="segrow">
        <div class="seg"><button class="on" data-m="wipe">Wipe</button><button data-m="diff">Diff</button></div>
        <button class="zoombtn" type="button">⤢ Enlarge</button>
      </div>
      <p class="note"></p>
    </div>`;
  grid.appendChild(c);
  cards[name] = c;
  const t = c.querySelector('.t'), h = c.querySelector('.hdl');
  const set = v => { t.style.clipPath = 'inset(0 0 0 ' + v + '%)'; h.style.left = v + '%'; };
  c.querySelector('input').addEventListener('input', e => set(e.target.value)); set(50);
  const cmp = c.querySelector('.cmp');
  c.querySelectorAll('.seg button').forEach(b => b.addEventListener('click', () => {
    cmp.dataset.mode = b.dataset.m;
    c.querySelectorAll('.seg button').forEach(x => x.classList.toggle('on', x === b));
  }));
  c.querySelector('.zoombtn').addEventListener('click', () => {
    document.getElementById('lbb').src = c.querySelector('.b').src;
    document.getElementById('lbt').src = t.src;
    document.getElementById('lbcap').textContent = current ? current.label : '';
    document.getElementById('lb').hidden = false;
  });
});
const lb = document.getElementById('lb');
lb.addEventListener('click', e => { if (!e.target.closest('figure')) lb.hidden = true; });
document.addEventListener('keydown', e => { if (e.key === 'Escape') lb.hidden = true; });
function render(id){
  const v = DATA.versions.find(x => x.id === id);
  current = v;
  document.getElementById('verdict').innerHTML = v.verdict;
  document.getElementById('tiles').innerHTML = v.tiles;
  document.getElementById('findings').innerHTML = v.findings;
  document.querySelectorAll('#vswitch button').forEach(b => b.classList.toggle('on', b.dataset.v === id));
  const pct = n => v.screens[n] ? v.screens[n].pct : -1;
  [...DATA.order].sort((a, b) => pct(b) - pct(a)).forEach(name => {
    const s = v.screens[name], c = cards[name];
    c.querySelector('h3').textContent = DATA.labels[name] + (s && s.bug ? ' 🐛' : '');
    const pill = c.querySelector('.pill');
    if (!s) {
      c.className = 'card gone';
      pill.textContent = 'not captured'; pill.className = 'pill';
      c.querySelector('.t').src = ''; c.querySelector('.diffimg').src = '';
      c.querySelector('.note').textContent = 'This build has no capture of this screen.';
    } else {
      c.className = 'card s-' + s.sev;
      pill.textContent = s.pct.toFixed(2) + '%'; pill.className = 'pill s-' + s.sev;
      pill.title = 'threshold ' + s.max.toFixed(2) + '%';
      c.querySelector('.t').src = s.img;
      c.querySelector('.diffimg').src = s.diff;
      c.querySelector('.note').textContent = s.note;
    }
    grid.appendChild(c);
  });
}
const vs = document.getElementById('vswitch');
DATA.versions.forEach(v => {
  const b = document.createElement('button');
  b.dataset.v = v.id;
  b.innerHTML = v.label + `<span class="d">${v.date}</span>`;
  b.addEventListener('click', () => render(v.id));
  vs.appendChild(b);
});
render(DATA.versions[0].id);
</script>
"""


if __name__ == "__main__":
    sys.exit(main())
