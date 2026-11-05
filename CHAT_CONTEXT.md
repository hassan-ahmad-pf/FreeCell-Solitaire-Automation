# FreeCell regression — chat handoff (5 Nov 2026)

Upload this file into a new Claude chat so it has the same project context as the Cursor session that ended today. This is a working handoff, not a product spec. The live source of case IDs and run order is `tests/freecell_suite/catalog.py`.

Repo: `/Users/hassan/Automation-FA/FreeCell-Solitaire-Automation`  
Remote: `https://github.com/hassan-ahmad-pf/FreeCell-Solitaire-Automation.git`  
**Current branch: `main` at `3b16ea4`.** Work was briefly on `fix/phone-auto-lock` (wrong name) then fast-forwarded onto `main` and that branch was deleted.

---

## 1. What this project is

Functional regression for FingerArts **FreeCell Solitaire** on a real iPhone. Not Spider. Not Unity-port comparison unless asked.

| | |
|---|---|
| Bundle | `com.fingerarts.FreeCell` |
| Phone | iPhone 15 Pro Max, UDID `00008130-00010D283A31001C`, iOS 27.2 |
| Last build under test | dev **7.42.1 (266)** |
| QA code | `943010` — About → version line → 10 emblem taps → code |
| Driver | WebDriverAgent over USB, `scripts/wda.sh`, HTTP `:8100` |
| Live suite | `tests/freecell_suite/` via `scripts/regression.sh` → `present_regression.py` → `run_all.py` |

The user’s role is Software engineer. They run the suite themselves in a real terminal a lot. Give a command when they want to start a run. Do not start WDA or a phone test unless they asked.

---

## 2. Hard rules from this work (keep these)

- **Do not edit** plan files, Spider (`reference/spider` unless they ask), `docs/testrail/cases.py`, or TestRail CSVs.
- **Allowed:** `docs/testrail/suite_cases.py`, `tests/freecell_suite/catalog.py` EXTRA cases.
- **Clone is read-only:** `/Users/hassan/Automation-FA/cardgames`. Never write to the clone or its origin. Ads facts came from `origin/develop` (not `master`).
- **Commits only when asked.** Today they asked: all work is on `main`.
- **`--no-open` / never personal apps.** Never turn **Wi-Fi on with FreeCell on screen** (an ad loads and fires later offline).
- **Do not run `./scripts/wda.sh stop` unless asked.** Agent sandbox often cannot see USB; the user starts/stops WDA locally.
- **Parked (out of `--all` / `--main`, run only when named):** `verifyDeviceSetup`, `openDebugTools`, `verifyAds`, `triggerAdPoints`.
- Phone tests only when the request covers them.
- Browser verification does not apply here (native iPhone app).

---

## 3. How to run

Picker (what they use for demos):

```bash
cd /Users/hassan/Automation-FA/FreeCell-Solitaire-Automation && ./scripts/regression.sh --pick
```

WDA already up, one module, no WDA restart:

```bash
caffeinate -i ./.venv/bin/python -u scripts/present_regression.py --dev verifyDaily
```

Start WDA (user’s machine, phone unlocked):

```bash
./scripts/wda.sh "$DEVICE_UDID"
```

Stop WDA only if asked:

```bash
./scripts/wda.sh stop
```

`--main` is the presentation run (no parked ads). `--all` still leaves parked modules out. Failed cases rerun once before the HTML report. First-run pass is kept (`[KEEP]`).

Logs: `log/regression_<time>.log`, `log/freecell_suite_results.json`, HTML under `log/reports/<version>_<build>/`.

---

## 4. Suite size and order (today)

**169 cases:** 82 any build, 86 need the dev build, 1 skip (`FL-06` TestFlight).

`verifyDaily` RUN_ORDER (49 cases on the live list):

```
DY-01, 02, 03, 05, 07, 11,
DY-22, 12, 24, 26, 65, 13,          # Medium 15–30 today
DY-15, 28, 29, 66, 43, 16,          # Medium 15–30 past
DY-44, 45, 46, 47, 67, 48, 49,      # Medium today 90–99 +N
DY-50, 51, 52, 68, 53, 54, 55,      # Medium past 00–15 No improvement
DY-56, 57, 71,                      # table Replay / No score recorded + table
DY-17, 23, 18, 19, 69, 25,          # Easy today 90–99
DY-27, 20, 21, 70, 40, 41,          # Easy past 90–99
DY-10, 14
```

Victory / difficulty table cases:

- `VI-01, VI-02, VI-08, VI-03, VI-04` — Easy win, parts, **current/rank/best**, footer, back
- `DL-01`+`DL-05` Medium, `DL-02`+`DL-06` Hard, `DL-03`+`DL-07` Expert, `DL-04`+`DL-08` Master
- Last Score `LS-01, LS-02, LS-05` after promo icons, same online session

---

## 5. Daily flow (intended, current code)

Finish **all Standard Medium first**, then Easy.

1. **Medium today + past** at Synthetic Win **15–30**.
2. **Medium today again** at **90–99** → Victory **+N** (90–99 minus the earlier 15–30). Case `DY-48`.
3. **Same Medium past date** at **00–15** → Victory **No improvement**. Case `DY-53`.
4. **Today table-menu Replay** (not a calendar-date replay) → alert “play this game again / will not be recorded”, then Victory **Replay / No score recorded**. `DY-56`, `DY-57`. Table still checked: `DY-71`.
5. **Easy today + past only at 90–99.** No Easy 00–15. Easy today is **not** played twice.
6. Stats: **6 wins** (Medium 4, Easy 2). Table Replay is **not** counted (`DoNotRecord` / `Replayed`).

Clone Daily Victory extra band:

- first win → ✥ (not a run)
- better replay → `+N` (`DailyImprovement` = latest − previous best, > 0)
- not better → `{noImprovement}` “no improvement”
- table Replay (`Comp.Info.Replayed`) → `Replay` / `No score recorded`, no +N

Synthetic Win bands (clone `qaSlrImports.uxf`, Step 25pt): win1 = 00–15, win2 = 15–30, win7 = 90–99.

Daily popups besides the two first-visit tips: monthly-score tip after ≥3 dates (“Tap on the monthly score…”).

---

## 6. Victory current / rank / best (clone + suite)

Clone: `uiEndFrame.mm` `updateValues` / `updateRankLabel` + CLASSIC `gameImports.uxf`.

| Column | Rows |
|---|---|
| **current** | score, time, total moves, Solo run |
| **rank** | yellow rank for score / time / moves (runRank is not drawn on FreeCell) |
| **best** | previous best, or `-` if none. When rank==1 && isSaved, best is the *previous* / second-best, not the current |

Daily has **no run** (`REF_20161210a`). First Daily win shows ✥ in that slot.

Reader: `daily.victory_table` / `daily.check_victory_table`.

- Headers hunted if Last Score sits ~80px lower than Solo Victory (`Last Won Game Score` bar + “Week of …”).
- Rank: yellow glyphs.
- Best `-` must not be read as `5` or `0:05`.
- Replay paints the **current score gold**; Vision then split `77,902` into `77` and `90` (`2` as `₴`). Digit shapes keep the whole number.
- `daily_farm=True` skips the run row. Last Score auto-skips run when it is blank.

Wired on every Victory in the suite except parked ads.

---

## 7. OCR — do not regress this

All score compares go through `ocr.py`:

- `ocr.clean` / lookalikes: `З`→3, `₴`→2, `ř`→7, Cyrillic `х`→x, …
- `ocr.numbers`, `ocr.glue` (77+902 → 77902; do not glue two already-full scores)
- `ocr.score` — best reconstructed score
- `ocr.same` — exact, or prefix cut of a 5+ digit score (`7790` ≈ `77902`), or one-digit Hamming on 5+ digits. **Prefix only** (suffix would treat `69` as `34,369`). Short counts 2/4/6 stay exact (those are games won).
- `ocr.pick(nums, want)` — the number that matches `want`, else the longest ≥ 1000

Used by Victory cells, `victory_score` Vision fallback, Daily popup, monthly box, HUD, Statistics.

**Presentation-day fails this chat fixed (reader, not the app):**

| Case | Symptom | Cause |
|---|---|---|
| **LS-01** | `Victory is missing the current header` | Last Score table ~80px lower than Victory crop |
| **DY-71** | current score `90` ≠ win `77,902` | gold Replay score, Vision `77,90₴`, `max(77,90)=90` |
| **DY-41** | popup lists `4` for the 5th, Victory `34,369` | gold `34,369 x2` read as `З4‚З69х2` |

Saved shots that must still parse: `log/DailyTableReplayVictory.png` (77,902 / rank 2 / best 78,730), `log/DailyREScorePopup.png` (4th 33,316; 5th 34,369 ×2), `log/last_score.png` (46,670).

---

## 8. Offline “waiting for an interstitial”

Daily wins were calling `fc.clear_ad(..., wait=3)` even offline. `clear_ad` always labeled that timer `waiting for an interstitial after …`.

**Now:** offline Daily win / Victory back use `wait=0`. `clear_ad(wait<=0)` only closes an ad already up; no countdown. Online still uses `LATE_AD` (12s). Ads modules stay parked.

---

## 9. Ads (parked — do not revive unless asked)

Facts from clone **`origin/develop`** (checkout `master` is a different ads story):

- Boot: no interstitial
- Pre-game: on leave / Play→Easy
- Post-game win ~5s
- 30s play-seconds grace from **showAd appear** (not close)
- Resume: never
- Abandon No: never
- One-shot `interstitialish` flag until New/Replay
- Cannot flush MAX cache; “waste” = play the cached ad
- New-to-clear is itself a pre-game ask

`triggerAdPoints` was rewritten to those facts then parked because it was still flaky / playables have no close.

---

## 10. WDA / agent limits

- Agent shell often **cannot see USB** and cannot start WDA. User runs `wda.sh` locally.
- `wda.sh stop` needs `all` perms and only when asked.
- After a FreeCell session, WDA does **not** wait for app idle (FreeCell sometimes never reports idle). Pause 1s tap / 2s swipe instead.
- Never restart WDA just to run a module if it is already up.
- Never turn Wi-Fi on with FreeCell on screen.

---

## 11. Clone

Path: `/Users/hassan/Automation-FA/cardgames` — **read-only**.  
FreeCell lives inside that peoplefun/cardgames tree. Ads: read `origin/develop`. Daily / Victory: `uiEndFrame.mm`, `gameImports.uxf`, `qaSlrImports.uxf`, Daily miscellanea `REF_20161210a`.

---

## 12. Files this chat actually changed (now on `main`)

Core: `ocr.py`, `tests/freecell_suite/daily.py`, `verifyDaily.py`, `verifyVictory.py`, `verifyDifficultyLevels.py`, `visitLastScore.py`, `fc.py`, `catalog.py`, `docs/testrail/suite_cases.py`, `README.md`, `caselog.py`, `present_regression.py`, `regression.sh`.

Also on the same `main` tip (from earlier on that branch): DS-01/DS-02 device setup, live console restyle, Last Score merged into the promo-icons online session, parked ads/debug tools, Daily +N / No improvement / Replay cases.

**Do not “fix” by editing the clone.**

---

## 13. What a new chat should do by default

1. Read `catalog.py` + the module the user named before changing cases.
2. If a case failed: read `log/freecell_suite_results.json` and the newest `log/regression_*.log`, then the FAIL shot. Prefer “reader missed a visible number” over “app is wrong”.
3. Do not start WDA, do not stop WDA, do not run the phone suite unless asked. Give the command.
4. Do not un-park ads.
5. Do not play Easy today twice. Do not add Easy 00–15. Medium first, then Easy 90–99 only.
6. Every new Victory surface must call `daily.check_victory_table`.

---

## 14. Useful commands the user already has

```bash
# picker / full
./scripts/regression.sh --pick

# Daily only, WDA already up
caffeinate -i ./.venv/bin/python -u scripts/present_regression.py --dev verifyDaily

# catalog count
./.venv/bin/python -m tests.freecell_suite.catalog
```

Phone: unlocked. For a first launch of WDA, online long enough to trust the runner if iOS asks.

---

## 15. Conversation arc (so Claude is not starting from zero)

This Cursor session (continued across a compaction) covered: diagnose `--pick` / ads; whole regression without ads; park ads + debug tools; merge Last Score into the promo-icons online session; Daily settings / stars / +N / No improvement / Replay; stats flake (read Daily stats in one downward pass); DY-17 Easy OCR; Victory current/rank/best on every win; LS-01 / DY-71 / DY-41 OCR fails on presentation day; glue lookalikes in `ocr.py`; drop offline interstitial countdown; update README; push (wrongly) to `fix/phone-auto-lock`; then move that tip onto `main` and delete the auto-lock branch.

If the user says “one case failed, check why”, look at the latest regression log first. Today’s pattern was OCR/crop, not a bad Daily flow.
