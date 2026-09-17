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
