# Observed FreeCell build

Captured on the connected iPhone 15 Pro Max (`1290×2796`) through the
already-installed WDA runner on 2026-09-17.

## Navigation

- Main menu: Play, Daily, Stats, Options, Help, About, More Games, Choose Look.
- Play offers Easy, Medium, Hard, Expert, and Master.
- The Play picker also exposes Standard Rules, Last Score, and Resume when a
  game is paused.
- Options has Sounds, Cards, and Interface sections; it includes Applause
  Volume, Effects Volume, Auto Mute Sounds, Maintain Card Spacing, Card
  Bouncing, and Card Lowering.
- Help contains FreeCell-specific foundation/cell/tableau diagrams and rules.
- About identifies the build as `279 build 60706F` and the marketing version as
  `7.42.5`.

## Table

The Easy table visibly contains:

- four foundation slots at the top-left;
- four free-cell slots at the top-right;
- eight tableau columns;
- new, replay, back, and menu controls;
- tap-to-undo, tap-to-lower, and tap-for-hints controls;
- score, timer, and multiplier;
- the in-game drawer with replay, abandon, options, new, help, and FAQ.

The game can be paused. Starting another level then raises the native
confirmation: “Are you sure you want to abandon the currently paused game?”

## QA and victory

The confirmed QA path is:

1. About → tap the version line to reveal the build number.
2. Ten rapid taps on the FreeCell emblem.
3. Enter `943010`.
4. Return to the menu; the confidential QA watermark confirms QA is enabled.
5. Deal an active game.
6. Open the QA badge on the table.
7. Open Synthetic Win, select `90% - 99%`, then press `WIN`.

The victory screen observed after the synthetic win shows the current score,
time, rank, best, leaderboards, achievements, Help, New, Stats, and a footer
reporting `easy level • standard rules` plus scores/time/moves/run.

The victory screen's top-right `menu` can invoke an online cross-promo
interstitial, so the functional suite must run offline except for explicitly
online tests.

## Discovery walk — 2026-10-10

Walked offline (Airplane Mode, Wi-Fi off) on the iPhone 15 Pro Max, iOS
27.0.1, right after a fresh install. The build was the **App Store** release,
7.42.5 (280). That is a production build: **the QA code does nothing** (no
watermark, no QA entry in the drawer), so nothing below depends on QA. Every
regression run uses a **dev build** that the tester installs fresh before the
run. Re-confirm the items marked *(dev build)* on it.

### Menu and About

- The crown logo on the main menu opens About.
- About's "help" opens Help and "more games" opens the in-app More Games
  page. Back from either returns to About.
- Tapping About's version line cycles through more than two states: first
  `280 build 60706F`, then a diagnostic line (`us -29 =40 ~64 :03 H`).
- A **Welcome** alert ("most of the features of the game can be enabled and
  disabled at any time in the Options page") appears on the menu the first
  time a table is left. OK closes it, and Options opens Options. It is a
  native alert, so WDA reads its text.
- The **promo icon strip** ("more fun with us!", five icons) appeared on the
  menu after the first game was *played*. No game had been won. Spider shows
  it only after a win.

### Play picker

- "standard rules / tap to change" toggles to "relaxed rules", which adds
  "Relaxed rules make the game easier to win by allowing piles of any size to
  be moved... but you score less points :)". A second tap goes back to
  standard.
- The red ribbon under the levels is empty until a game is paused. Then it
  reads **Resume** and continues the paused game.

### Daily

- The first visit shows two tip cards over the calendar. Tip 1 says "Tap on
  the Level Button to select your favorite level" and outlines the level
  button. Tip 2 says "Tap on any available date to play a game", with replay
  and gold-star notes. Tapping the card advances, then shows the calendar.
- The calendar shows the current month. Today is orange, earlier days are
  white, and later days are dimmed. Tapping a future date does nothing.
- The level button opens a menu: **Standard** Easy–Master and **Relaxed**
  Easy–Master. Choosing Standard Hard makes the button read "Hard". Choosing
  Relaxed Easy makes it read "Easy" with an "R" badge.
- **No Daily game can be dealt offline**, whether today or a past date. Each
  tap raises a native alert: "Sorry, Daily Games can be initiated only when
  Internet is available — Please connect to Internet and try again. Or, in
  alternative, would you like to play a Solo game instead?" **No** stays on
  the calendar. **Yes** closes Daily onto the main menu. It does not deal a
  Solo game; the picker shows no Resume afterwards.
  *(dev build: does the QA panel's Daily date override change this?)*
- The Daily table, a Daily win, the gold star and the Daily stats count
  therefore need the network.

### Table

- Easy deals with A–3 of every suit already on the foundations.
- The footer reads "easy level standard rules · tap a card to start". The
  timer stays at 0:00 until the first move, and the multiplier starts at X98.
- About 6 s after the first deal of a session a native alert asks "Would you
  like to review the game rules before to play?" **Yes** opens Help, and Back
  returns to the table. No closes it.
- Tapping a card moves it to a legal place, preferring the tableau, then a
  free cell. The move counter goes up, the timer starts, and the multiplier
  starts dropping.
- Undo (the pile at bottom-left) puts the card back and lowers the counter;
  the timer keeps running.
- Tapping a buried card highlights every card of that rank.
- "tap for hints" turns its label into "tap for more / move 1 of N". Each
  further tap advances to "move 2 of N".
- "tap to lower" drops the playfield about 100 px, and a second tap raises it
  back.
- Leaving the table for Help, FAQ or Options and coming back shows "tap a card
  to start" again, and the timer pauses until the next move.
- When the free cells are full, tapping a card with no legal move flashes
  "this card cannot attach anywhere" for under a second, controlled by Show
  Card Messages. The bottom bar also swaps the score and timer for a "help"
  button, which opens Help. The help button appears whether or not card
  messages are on.

### In-game drawer (menu)

- replay, abandon, options, new, help, FAQ, and a round **Rotation Lock**
  icon.
- **Help** opens Help, and **FAQ** opens the FAQ on its **Solo** tab (General
  / Solo / Daily). Back from either returns to the table.
- **Replay** after a move asks "Are you sure you want to play this game again?
  The game is not completed yet, and if you replay it now you will break your
  current Run. Also, any score achieved on the replay will not be recorded"
  (No / Yes). **No** keeps the board. **Yes** plays a page curl and restores
  the original deal, with the counter at 0, the timer at 0:00 and X98.
- After that replay a native "Did you know?" tip appeared: "If you have
  troubles reading the cards, in the Option page you can select cards with
  extra-large symbols" (OK / Show Me). **Show Me** goes to the menu and opens
  **Choose Look on the Cards tab**. That tab has an **Extra Large
  Card-Symbols** switch, off by default.
- **Rotation Lock** toggles on every press. The first lock raises an alert
  ("You selected the Rotation Lock :) ... To unlock it, simply press the Lock
  button again", OK). Later presses are silent, and the icon looks the same
  either way. While it is locked, WDA's `POST /orientation LANDSCAPE` fails
  with "Unable To Rotate Device". Unlocked, the app rotates and reflows:
  foundations go to a left column and free cells to a right column.
- Not probed yet: abandon, new.

### Options

Rows, top to bottom: Applause Volume (slider), Effects Volume (slider), Auto
Mute Sounds; Maintain Card Spacing, Card Bouncing; Card Lowering (slider),
Show Status Bar, Show Card Messages, UI Brightness (slider), Rich Features,
Auto Hint (**off** by default), Rank Strip; Game Center. "Contact Us" sits at
the top right.

- **Show Status Bar** off hides the iOS status bar on the table and moves the
  whole layout up about 100 px.
- **Show Card Messages** off stops "this card cannot attach anywhere" from
  appearing.
- **Auto Hint** on showed no visible change over three idle stretches of
  14–25 s, both straight from Options and after a move. Its case covers the
  switch alone.
- Row labels are matched on their white lettering (`find_ink`). In colour,
  "Card Bouncing" and "Card Lowering" score 0.75 against each other over the
  shared felt. On white text alone the worst cross-match between any two rows
  is 0.68, against a bar of 0.85.

### Statistics

- The Daily tab shows totals (best score, games played, games won, playtime),
  then Standard Easy–Master and Relaxed Easy–Master, each with best score,
  best time, fewest moves, games played and games won. The page ends in
  **Reset Daily Statistics**.
- The Daily reset asks twice, both native No/Yes alerts: "Would you like to
  reset local scores? Notice that Game Center online achievements and online
  score will not be reset", then "Just to be on the safe side… Please confirm
  once more...". After the second Yes the app lands on the main menu. That
  matches the Solo reset.

### Not reached on the App Store build

These need a win, which needs QA:

- Victory's stats / new / help buttons. *(dev build)*
- Last Score after a win, the Solo stats after a win, and the levels'
  "can be completed". *(dev build)*
