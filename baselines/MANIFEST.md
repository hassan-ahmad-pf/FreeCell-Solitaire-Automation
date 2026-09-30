# FreeCell Obj-C baselines

The reference the Unity port is compared against. **Never re-baseline these to a Unity build** — a large diff is the finding.

- App: FreeCell 7.42.5 (build 279, About shows "279 build 60706F"), `com.fingerarts.FreeCell`
- Device: iPhone16,2 (iPhone 15 Pro Max), iOS 27.0, portrait 1290x2796
- Captured by `tests/capture_baselines.py` on fresh installs; last promoted 2026-10-01T03:09:40. Each screen's pass and kept shot (of 3, the one closest to their per-pixel median) are in `baselines.json`
- Daily table: 2026-10-01, Medium — a Unity capture must deal the same date for `DailyTable` to be comparable
- Network: offline except the Terms / Privacy pages; QA locked except phase B

Every screen masks the status bar; screens above the wood tray also mask `BANNER` (house cross-promo banner and the wood below it). `volatile` is the share of the screen masked by `<Name>.volatile.png`: motion seen in at least two of the three shots, plus any glint in the shot that was kept (More Games: anything that moved in any shot of either pass). A comparison takes the per-pixel median of its own shots, so a one-off glint needs no mask.

About is not listed as a bottom page: it fits on one screen.

| Screen | Phase | Reached by | State | Masks | Volatile | Notes |
|---|---|---|---|---|---|---|
| `FirstLaunchTerms` | A | cold launch of a fresh install, offline | Terms & Conditions card over the first menu (no banner yet) | STATUS_BAR | 0.06% | Menu sparkles behind the card are volatile. |
| `TermsPage` | A | Terms card → "Terms & Conditions" link (online, pages only) | in-app web view of the Terms page, top | — | 0.00% | Live web content: a changed policy page is not a port bug. |
| `PrivacyPage` | A | Terms card → "Privacy Policy" link (online, pages only) | in-app web view of the Privacy page, top | — | 0.00% | Live web content: a changed policy page is not a port bug. |
| `StatsSoloEmpty` | A | menu → Stats | Solo tab, top, every value none/0 (fresh install, offline, QA locked) | — | 0.00% |  |
| `StatsSoloBottom` | A | Stats Solo → scrolled to the end | Solo tab, bottom (Reset link) | — | 0.00% |  |
| `ResetSoloDialog` | A | Stats Solo bottom → Reset Solo Statistics | first reset confirmation (answered No) | — | 0.00% |  |
| `StatsDailyEmpty` | A | Stats → Daily tab | Daily tab, top, every value none/0 | — | 0.00% |  |
| `StatsDailyBottom` | A | Stats Daily → scrolled to the end | Daily tab, bottom (Reset link) | — | 0.00% |  |
| `MainMenu` | A | back to the menu, banner drawn | menu before More Games is visited (badge "1") and before any win | — | 0.43% | Sparkle glints are volatile. |
| `AboutTop` | A | menu → ABOUT | About, version 7.42.5 (the page does not scroll) | — | 0.00% |  |
| `AdFreePrompt` | A | About → ad free version | iOS alert No / Yes (answered No) | — | 0.00% |  |
| `FeedbackAlert` | A | About → submit feedback | iOS alert Cancel / Write Email (answered Cancel) | — | 0.00% |  |
| `AboutVersion` | A | About → tap the version line | About with "279 build 60706F" in place of the version | — | 0.00% |  |
| `FAQTop` | A | About → frequently asked questions | FAQ, General tab, top | — | 0.00% |  |
| `FAQBottom` | A | FAQ → scrolled to the end | FAQ, General tab, bottom | — | 0.00% |  |
| `FAQSolo` | A | FAQ → Solo tab | FAQ, Solo tab, top | — | 0.00% |  |
| `FAQDaily` | A | FAQ → Daily tab | FAQ, Daily tab, top | — | 0.00% |  |
| `HelpTop` | A | menu → Help | Help, top | — | 0.00% |  |
| `HelpMid` | A | Help → one slow 900 px drag | Help, part way down | — | 0.00% | Offset set by a slow drag without a fling. |
| `HelpBottom` | A | Help → scrolled to the end | Help, bottom | — | 0.00% |  |
| `OptionsTop` | A | menu → Options | Options, top, defaults | — | 0.00% |  |
| `OptionsMid` | A | Options → one slow 900 px drag | Options, part way down | — | 0.00% | Offset set by a slow drag without a fling. |
| `OptionsBottom` | A | Options → scrolled to the end | Options, bottom | — | 0.00% |  |
| `ChooseLookSurface` | A | menu → Choose Look | Surface tab, default look (1 / 1) | — | 0.00% |  |
| `ChooseLookCards` | A | Choose Look → Cards tab | Cards tab, default look (1 / 1) | — | 0.00% |  |
| `PlayPicker` | A | menu → Play | difficulty picker, no paused game (no Resume) | PICKER_FAN | 0.89% | The card fan hops with the rules block; it is masked. The difficulty spades hop with their labels (a small box there is Obj-C motion). |
| `LastScoreNotice` | A | Play → LAST SCORE | "No game has been completed yet" card | — | 0.07% |  |
| `LastScore` | A | Last Score → dismiss the card | Last Won Game Score, empty (Week of Jan 1, 1970) | — | 0.05% | Thumbs-up sparkle is volatile. The two period arrows slide (a small box on either is Obj-C motion). |
| `TableDeal` | A | Play → Easy | fresh Easy table, untouched (tap a card to start, 0:00, X98), Rich Features + Rank Strip on | TABLEAU | 0.00% | Dealt cards masked; foundations (3s) and HUD are deterministic. |
| `TableDrawer` | A | table → menu | table drawer open | TABLEAU, DRAWER_BANNER | 0.00% | Dealt cards and the drawer banner masked. |
| `PlayPickerResume` | A | table → back → Play | picker with the Resume ribbon (paused game) | PICKER_FAN | 2.97% | The card fan hops with the rules block; it is masked. |
| `AbandonPrompt` | A | picker with a paused game → Easy | iOS alert: abandon the paused game? (answered Yes) | PICKER_FAN | 0.11% | The card fan hops with the rules block; it is masked. |
| `TableRichOff` | A | table → menu → options → Rich Features OFF → back | Easy table without timer / score / multiplier / moves | TABLEAU | 0.00% |  |
| `TableRankStripOff` | A | table → menu → options → Rank Strip OFF → back | Easy table without the rank strip (Rich Features back on) | TABLEAU | 0.00% |  |
| `DailyTutorial1` | A | menu → Daily (first visit) | first Daily tip over the calendar | DAILY_MONTH, DAILY_DAYS | 0.24% | Calendar dates masked. |
| `DailyTutorial2` | A | Daily tip 1 → tap | second Daily tip over the calendar | DAILY_MONTH, DAILY_DAYS | 0.02% | Calendar dates masked. |
| `DailyCalendar` | A | Daily tip 2 → tap | Daily calendar, Medium | DAILY_MONTH, DAILY_DAYS | 0.00% | Month and dates masked. |
| `DailyTable` | A | Daily calendar → day 1 of the month (date in capture.json) | untouched Daily table for that date, Medium | DAILY_TABLEAU, DAILY_STAR | 0.00% | Cards masked: the same date and level dealt different cards on two installs. The star is masked: it is gold only when that date is today. |
| `MoreGamesTop` | A | menu → More Games | More Games stage, top | — | 13.34% | Game items animate on long, separate loops; their mask is learned from every shot of both Obj-C passes. |
| `MoreGamesScrolled` | A | More Games → scrolled to the end | More Games stage, bottom | — | 17.23% | Game items animate on long, separate loops; their mask is learned from every shot of both Obj-C passes. |
| `Victory` | B | QA unlock → Play → Easy → Complete Game (90-99) | victory / ranking for This Week | VICTORY_WON, VICTORY_NUMBERS, QA_BRACKETS, QA_RECYCLE, QA_BADGE, TEST_BANNER | 1.83% | Score, time, moves, rank and QA marks masked. back / menu were dim on 3 of 4 Obj-C runs and white on one (cause unknown), so a brightness-only change to those two is not by itself a port bug. The thumbs-up bounces (a small box on it is Obj-C motion). |
| `MainMenuAfterWin` | B | victory → back, QA turned off again | menu after a completed game (promo icons, no badge) | — | 2.24% | Sparkle glints are volatile. |
| `StatsSoloAfterWin` | B | menu → Stats | Solo tab, top, one Easy win | STATS_TOTALS, STATS_EASY, (30, 475, 125, 550), (1175, 530, 1270, 630), TEST_BANNER | 0.00% | Values masked (they follow the synthetic win). |
