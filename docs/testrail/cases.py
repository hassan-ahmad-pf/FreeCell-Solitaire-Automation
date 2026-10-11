"""TestRail cases for the Objective-C build of FreeCell.

Written for a person on the phone, not for Airtest. One case per behaviour
a tester can fail independently. Adapted from Spider's list and extended with
what only FreeCell has (Daily, the Solo / Daily statistics, the FAQ tabs, the
rules toggle, the in-game drawer's extras). Behaviour is as observed on the
device — see docs/OBSERVED_FREECELL.md.

The run assumes a DEV build, installed fresh before the run: the QA code
(About) only exists there, and every win below comes from its Synthetic Win.

    ./.venv/bin/python scripts/export_testrail_csv.py
"""


def C(cid, title, section, steps, *, type="Functional", priority="Medium"):
    if not steps:
        raise ValueError(f"{cid}: steps must not be empty")
    return {
        "id": cid,
        "title": title,
        "section": section,
        "type": type,
        "priority": priority,
        "steps": list(steps),
    }


S = "FreeCell Solitaire Obj-C"

CASES = [
    # ── Launch ────────────────────────────────────────────────────────
    C("FL-01", "Launch - Force-quit and reopen reaches the main menu",
      f"{S} > Launch",
      [
          ("If FreeCell is open, swipe it away from the app switcher, then "
           "tap the FreeCell icon.",
           "The app opens."),
          ("If Terms & Conditions or the tracking prompt appear, dismiss "
           "them (Continue, then Allow).",
           "No pop-up is left on screen."),
          ("Wait until the menu finishes appearing.",
           "Play and the rest of the main menu are showing."),
      ],
      priority="High"),
    C("FL-02", "Launch - Fresh install shows Terms & Conditions",
      f"{S} > Launch",
      [
          ("Delete FreeCell, install the dev build, and open it.",
           "A card reads \"To use FreeCell you must agree to our Terms & "
           "Conditions and affirm you have reviewed our Privacy Policy\" "
           "with a Continue button."),
          ("Tap Continue.",
           "The card goes away. The iOS tracking prompt may appear next."),
      ],
      priority="High"),
    C("FL-03", "Launch - Fresh install shows the tracking prompt",
      f"{S} > Launch",
      [
          ("After Terms & Conditions, wait for the iOS tracking prompt "
           "(Allow / Ask App Not to Track).",
           "The system tracking alert is on screen."),
          ("Tap Allow. Do not tap Ask App Not to Track — that does not "
           "clear the gate.",
           "The prompt goes away and the main menu is reachable."),
      ],
      priority="High"),
    C("FL-04", "Launch - Terms & Conditions link opens the terms page",
      f"{S} > Launch",
      [
          ("On a fresh install, with the Terms & Conditions card on screen "
           "and Wi-Fi on, tap the Terms & Conditions link. Do not tap "
           "Continue yet.",
           "A PeopleFun Terms of Service page opens, not the Privacy "
           "Notice."),
          ("If Accept All Cookies appears, tap it and wait for the banner "
           "to go.",
           "The Terms of Service heading is fully visible."),
          ("Close the page.",
           "The Terms & Conditions card is still there."),
      ],
      priority="High"),
    C("FL-05", "Launch - Privacy Policy link opens the privacy page",
      f"{S} > Launch",
      [
          ("On the same card, tap Privacy Policy.",
           "A PeopleFun Privacy Notice page opens, not the Terms of "
           "Service."),
          ("Accept cookies if asked, then close the page.",
           "The Terms & Conditions card is still there. Continue is "
           "checked in FL-02."),
      ],
      priority="High"),

    # ── Main Menu ─────────────────────────────────────────────────────
    C("MM-01", "Main Menu - All eight controls are visible",
      f"{S} > Main Menu",
      [
          ("Open the app and wait until the menu finishes animating.",
           "Play, Daily, Stats, Options, Help, About, More Games, Choose "
           "Look, and the FreeCell crown are all on screen."),
      ],
      priority="High"),
    C("MM-02", "Main Menu - Welcome tip after the first game opens Options",
      f"{S} > Main Menu",
      [
          ("On a fresh install, deal a game, then tap the table's Back.",
           "A Welcome alert says most features can be enabled and disabled "
           "in the Options page, with OK and Options."),
          ("Tap Options.",
           "Options opens."),
          ("Tap Back.",
           "The main menu is showing and the Welcome alert does not come "
           "back."),
      ]),

    # ── Statistics ────────────────────────────────────────────────────
    C("ST-01", "Statistics - Opens on the Solo tab",
      f"{S} > Statistics",
      [
          ("From the main menu, tap Stats.",
           "Statistics opens with the Solo tab selected and Game Center in "
           "the header."),
      ]),
    C("ST-02", "Statistics - Fresh install reads 0 and none",
      f"{S} > Statistics",
      [
          ("On a fresh install, before any game, open Stats.",
           "Solo reads best score 0, games played 0, games won 0, playtime "
           "0:00, and Standard • Easy reads best score none."),
      ],
      priority="High"),
    C("ST-03", "Statistics - Solo scrolls down to Reset Solo Statistics",
      f"{S} > Statistics",
      [
          ("On the Solo tab, scroll all the way down. Do not tap Reset.",
           "Standard and Relaxed blocks for every level pass by, and Reset "
           "Solo Statistics is at the bottom."),
      ]),
    C("ST-04", "Statistics - Back returns to the main menu",
      f"{S} > Statistics",
      [
          ("From Statistics, tap Back.",
           "The main menu is showing."),
      ]),
    C("ST-05", "Statistics - Daily tab shows the Daily totals",
      f"{S} > Statistics",
      [
          ("On Statistics, tap Daily.",
           "The Daily tab is selected. It shows best score, games played, "
           "games won, and playtime (0 / 0:00 on a fresh install)."),
      ]),
    C("ST-06", "Statistics - Daily scrolls down to Reset Daily Statistics",
      f"{S} > Statistics",
      [
          ("On the Daily tab, scroll all the way down. Do not tap Reset.",
           "Reset Daily Statistics is at the bottom."),
      ]),
    C("ST-07", "Statistics - Solo shows the score of a won game",
      f"{S} > Statistics",
      [
          ("Win an Easy game (dev build: QA code, then Synthetic Win) and "
           "note the Victory score.",
           "Victory shows a current score."),
          ("Go to the menu and open Stats on the Solo tab.",
           "Best score and Standard • Easy show that same score, and games "
           "won is 1 or more."),
      ],
      priority="High"),

    # ── Options ───────────────────────────────────────────────────────
    C("OP-01", "Options - Opens from the main menu",
      f"{S} > Options",
      [
          ("From the main menu, tap Options.",
           "Options opens on the Sounds section. The main menu is gone."),
      ]),
    C("OP-02", "Options - Back returns to the main menu",
      f"{S} > Options",
      [
          ("From Options, tap Back.",
           "The main menu is showing."),
      ]),
    C("OP-03", "Options - Applause Volume moves to min, max, and middle",
      f"{S} > Options",
      [
          ("On Options, drag the Applause Volume knob all the way left, all "
           "the way right, then to the middle.",
           "The knob sits at the left end, the right end, then in the "
           "middle — not only at the two ends."),
      ],
      priority="High"),
    C("OP-04", "Options - Applause Volume stays after you leave the screen",
      f"{S} > Options",
      [
          ("Drag Applause Volume to a new position and remember it.",
           "The knob moves."),
          ("Go back to the main menu, then open Options again.",
           "The knob is still where you left it."),
      ],
      priority="High"),
    C("OP-05", "Options - Effects Volume moves to min, max, and middle",
      f"{S} > Options",
      [
          ("Drag the Effects Volume knob all the way left, all the way "
           "right, then to the middle.",
           "The knob reaches both ends and can sit in the middle."),
      ]),
    C("OP-06", "Options - Auto Mute Sounds turns off and on",
      f"{S} > Options",
      [
          ("Look at Auto Mute Sounds (it ships ON), tap it, then tap it "
           "again.",
           "It turns off the first time and back on the second. A tap that "
           "does nothing fails."),
      ]),
    C("OP-07", "Options - Maintain Card Spacing turns off and on",
      f"{S} > Options",
      [
          ("In the Cards section, tap Maintain Card Spacing (ships ON) "
           "twice.",
           "It turns off, then back on."),
      ]),
    C("OP-08", "Options - Card Bouncing turns off and on",
      f"{S} > Options",
      [
          ("Tap Card Bouncing (ships ON) twice.",
           "It turns off, then back on."),
      ]),
    C("OP-09", "Options - Card Lowering moves to min, max, and middle",
      f"{S} > Options",
      [
          ("In Interface, drag the Card Lowering knob all the way left, "
           "all the way right, then to the middle.",
           "The knob reaches both ends and can sit in the middle."),
      ]),
    C("OP-10", "Options - Show Status Bar OFF hides the status bar in a game",
      f"{S} > Options",
      [
          ("On a game table, note the iOS status bar (time, battery). Open "
           "the in-game menu → options and turn Show Status Bar off. Go "
           "back to the table.",
           "The status bar is gone and the table moves up."),
          ("Turn Show Status Bar back on and return to the table.",
           "The status bar is back and the table is where it started."),
      ],
      priority="High"),
    C("OP-11", "Options - Show Card Messages ON explains a stuck card",
      f"{S} > Options",
      [
          ("On a table, fill all four free cells, then tap a bottom card "
           "that has nowhere to go.",
           "\"this card cannot attach anywhere\" flashes on the felt for "
           "under a second."),
      ]),
    C("OP-12", "Options - Show Card Messages OFF hides the stuck-card note",
      f"{S} > Options",
      [
          ("Turn Show Card Messages off, go back to the same table, and "
           "tap the same stuck card.",
           "No \"cannot attach\" note appears. Turn the switch back on "
           "afterwards."),
      ]),
    C("OP-13", "Options - UI Brightness moves to min, max, and middle",
      f"{S} > Options",
      [
          ("Drag the UI Brightness knob all the way left, all the way "
           "right, then to the middle.",
           "The knob reaches both ends and can sit in the middle."),
      ]),
    C("OP-14", "Options - Auto Hint turns on and off",
      f"{S} > Options",
      [
          ("Tap Auto Hint (ships OFF), then tap it again.",
           "It turns on, then back off."),
      ]),
    C("HS-01", "Options - Contact Us opens support",
      f"{S} > Options",
      [
          ("With Wi-Fi on, open Options and tap Contact Us.",
           "You leave Options and the PeopleFun Support page opens."),
      ]),
    C("HS-02", "Options - Contact Us still leaves Options without internet",
      f"{S} > Options",
      [
          ("With Airplane Mode on and Wi-Fi off, open Options and tap "
           "Contact Us.",
           "You leave Options. A no-connection page instead of PeopleFun "
           "Support is expected — the redirect still happened."),
          ("Close the support page.",
           "Options is showing again."),
      ]),

    # ── Help ──────────────────────────────────────────────────────────
    C("HP-01", "Help - Opens on Introduction",
      f"{S} > Help",
      [
          ("From the main menu, tap Help.",
           "Help opens with the foundations / cells / tableaux diagram "
           "and the Introduction heading."),
      ]),
    C("HP-02", "Help - Rules scroll down to the FAQ link",
      f"{S} > Help",
      [
          ("Scroll Help all the way down.",
           "Rules, Undo button and Menu button pass by, and a frequently "
           "asked questions link is at the bottom."),
      ]),
    C("HP-03", "Help - Back returns to the main menu",
      f"{S} > Help",
      [
          ("From Help, tap Back.",
           "The main menu is showing."),
      ]),
    C("HP-04", "Help - FAQ link opens the FAQ",
      f"{S} > Help",
      [
          ("At the bottom of Help, tap frequently asked questions.",
           "The FAQ opens inside FreeCell."),
          ("Tap Back.",
           "Help is showing again."),
      ]),

    # ── About ─────────────────────────────────────────────────────────
    C("AB-01", "About - Opens from the About menu item",
      f"{S} > About",
      [
          ("From the main menu, tap ABOUT.",
           "About opens with \"FreeCell ▻ Solitaire\" and the copyright "
           "line."),
      ]),
    C("AB-02", "About - Version and links are on the page",
      f"{S} > About",
      [
          ("Look over About. Do not tap ad free version or submit feedback "
           "here.",
           "A Version line, © PeopleFun, Inc., and the links help, ad free "
           "version, frequently asked questions, more games, and submit "
           "feedback."),
      ]),
    C("AB-03", "About - Tapping the version line shows the build",
      f"{S} > About",
      [
          ("Tap the Version line.",
           "It changes to the build number and hash, e.g. \"279 build "
           "60706F\"."),
      ]),
    C("AB-04", "About - Frequently asked questions stays in the app",
      f"{S} > About",
      [
          ("Tap frequently asked questions.",
           "The FAQ opens inside FreeCell with General, Solo, and Daily "
           "tabs. You do not leave for a browser."),
      ]),
    C("AB-05", "About - FAQ scrolls down to submit feedback",
      f"{S} > About",
      [
          ("On the FAQ's General tab, scroll all the way down.",
           "submit feedback is at the bottom. The FAQ header stays put."),
      ]),
    C("AB-06", "About - Crown logo also opens About",
      f"{S} > About",
      [
          ("From the main menu, tap the FreeCell crown.",
           "About opens, the same screen as the ABOUT item."),
      ],
      priority="High"),
    C("AB-07", "About - Help link opens Help and comes back",
      f"{S} > About",
      [
          ("On About, tap help.",
           "Help opens on Introduction."),
          ("Tap Back.",
           "About is showing again, not the main menu."),
      ]),
    C("AB-08", "About - More games link opens More Games and comes back",
      f"{S} > About",
      [
          ("On About, tap more games.",
           "The in-app More Games stage opens. The App Store does not."),
          ("Tap Back.",
           "About is showing again."),
      ]),
    C("AB-09", "About - Back returns to the main menu",
      f"{S} > About",
      [
          ("From About, tap Back.",
           "The main menu is showing."),
      ]),

    # ── FAQ ───────────────────────────────────────────────────────────
    C("FQ-01", "FAQ - Opens on the General tab",
      f"{S} > FAQ",
      [
          ("Open the FAQ from About.",
           "General is selected and the first question is \"How do I play "
           "a Solo or Daily game?\"."),
      ]),
    C("FQ-02", "FAQ - Solo tab answers What are Solo games",
      f"{S} > FAQ",
      [
          ("Tap Solo.",
           "Solo is selected and the first question is \"What are Solo "
           "games?\"."),
      ]),
    C("FQ-03", "FAQ - Daily tab answers What are Daily games",
      f"{S} > FAQ",
      [
          ("Tap Daily.",
           "Daily is selected and the first question is \"What are Daily "
           "games?\"."),
      ]),
    C("FQ-04", "FAQ - Back returns to About",
      f"{S} > FAQ",
      [
          ("From the FAQ opened on About, tap Back.",
           "About is showing."),
      ]),

    # ── Ad-free / Feedback ────────────────────────────────────────────
    C("AF-01", "Ad-free - Link asks No or Yes before the store",
      f"{S} > App Store / Mail",
      [
          ("On About, tap ad free version.",
           "A card asks \"Would you like to take a look at the Ad free "
           "version?\" with No and Yes. You are still in FreeCell."),
      ]),
    C("AF-02", "Ad-free - No leaves you on About",
      f"{S} > App Store / Mail",
      [
          ("On that card, tap No.",
           "The card closes. About is showing and the App Store did not "
           "open."),
      ]),
    C("AF-03", "Ad-free - Yes opens the ad-free FreeCell in the App Store",
      f"{S} > App Store / Mail",
      [
          ("With Wi-Fi on, tap ad free version, then Yes.",
           "The App Store opens on the paid, ad-free FreeCell."),
      ],
      priority="High"),
    C("AF-04", "Ad-free - Status-bar back lands on About",
      f"{S} > App Store / Mail",
      [
          ("From the App Store, tap ◀ FreeCell in the status bar.",
           "About is showing. Landing on the main menu means the app "
           "restarted instead of resuming."),
      ]),
    C("FB-01", "Feedback - Submit feedback asks Cancel or Write Email",
      f"{S} > App Store / Mail",
      [
          ("On About, tap submit feedback.",
           "\"We appreciate your feedback\" offers Cancel and Write Email."),
      ]),
    C("FB-02", "Feedback - Cancel leaves you on About",
      f"{S} > App Store / Mail",
      [
          ("On that alert, tap Cancel.",
           "The alert closes and About is showing."),
      ]),
    C("FB-03", "Feedback - Write Email opens a Mail draft",
      f"{S} > App Store / Mail",
      [
          ("Tap submit feedback, then Write Email. A Mail account must be "
           "set up on the phone.",
           "Mail opens with a draft. No Mail Accounts is the phone setup, "
           "not the game."),
      ],
      priority="High"),
    C("FB-04", "Feedback - Subject names the game, version, phone, and iOS",
      f"{S} > App Store / Mail",
      [
          ("Read the draft subject. Compare it with Settings → General → "
           "About and the game's About.",
           "The subject names FreeCell, the app version, this phone's "
           "model, and this iOS version."),
      ],
      priority="High"),
    C("FB-05", "Feedback - Delete the draft — do not send",
      f"{S} > App Store / Mail",
      [
          ("Delete the draft. Never tap send.",
           "The draft is gone. Nothing was sent."),
      ],
      priority="High"),
    C("FB-06", "Feedback - Status-bar back returns to FreeCell",
      f"{S} > App Store / Mail",
      [
          ("From Mail, tap ◀ FreeCell in the status bar.",
           "FreeCell is in front. Mail is a separate app, so the main menu "
           "is acceptable."),
      ]),

    # ── More Games / promo icons ──────────────────────────────────────
    C("MG-01", "More Games - Gift icon opens the in-app promo page",
      f"{S} > More Games",
      [
          ("From the main menu, tap More Games (the gift icon).",
           "A curtained stage opens with \"Tap any game to download it!\". "
           "The App Store does not open."),
      ]),
    C("MG-02", "More Games - Swipe reveals Card Games and Spiderette",
      f"{S} > More Games",
      [
          ("Swipe the stage up until it stops.",
           "Card Games and Spiderette come into view. Back and the "
           "instruction line stay put."),
      ]),
    C("MG-03", "More Games - Back returns to the main menu",
      f"{S} > More Games",
      [
          ("From More Games, tap Back.",
           "The main menu is showing."),
      ]),
    C("PI-01", "Promo icons - Five game icons on the menu after a game",
      f"{S} > More Games",
      [
          ("After at least one game, go to the main menu and wait a few "
           "seconds.",
           "Five icons sit on the left beside \"more fun with us!\": "
           "Spider, Solitaire, Sudoku 2, Card Games, and Spiderette."),
      ]),
    C("PI-02", "Promo icons - Spider opens Spider Solitaire",
      f"{S} > More Games",
      [
          ("With Wi-Fi on, tap the Spider icon.",
           "The App Store opens on Spider Solitaire."),
          ("Tap ◀ FreeCell in the status bar.",
           "The main menu is showing. FreeCell did not restart."),
      ]),
    C("PI-03", "Promo icons - Solitaire opens Solitaire",
      f"{S} > More Games",
      [
          ("Tap the Solitaire icon.",
           "The App Store opens on Solitaire."),
          ("Switch back to FreeCell.",
           "The main menu is showing."),
      ]),
    C("PI-04", "Promo icons - Sudoku 2 opens Sudoku",
      f"{S} > More Games",
      [
          ("Tap the Sudoku 2 icon.",
           "The App Store opens on Sudoku."),
          ("Switch back to FreeCell.",
           "The main menu is showing."),
      ]),
    C("PI-05", "Promo icons - Card Games opens Card Games",
      f"{S} > More Games",
      [
          ("Tap the Card Games icon.",
           "The App Store opens on Card Games."),
          ("Switch back to FreeCell.",
           "The main menu is showing."),
      ]),
    C("PI-06", "Promo icons - Spiderette opens Spiderette",
      f"{S} > More Games",
      [
          ("Tap the Spiderette icon.",
           "The App Store opens on Spiderette."),
          ("Switch back to FreeCell.",
           "The main menu is showing."),
      ]),

    # ── Play ──────────────────────────────────────────────────────────
    C("PL-01", "Play - Opens the difficulty picker",
      f"{S} > Play",
      [
          ("From the main menu, tap Play.",
           "The difficulty picker opens. No game starts yet."),
      ],
      priority="High"),
    C("PL-02", "Play - Picker shows all five levels",
      f"{S} > Play",
      [
          ("Open Play.",
           "Easy, Medium, Hard, Expert, and Master are listed, with LAST "
           "SCORE at the bottom."),
      ],
      priority="High"),
    C("PL-03", "Play - Easy starts a game",
      f"{S} > Play",
      [
          ("On the picker, tap Easy. If asked to abandon a paused game, "
           "tap Yes.",
           "The game table is showing: foundations, free cells, and eight "
           "columns."),
      ],
      priority="High"),
    C("PL-04", "Play - Declining abandon stays on the picker",
      f"{S} > Play",
      [
          ("With a paused game, open Play and tap a level.",
           "\"Are you sure you want to abandon the currently paused "
           "game?\" appears."),
          ("Tap No.",
           "The picker stays open and the Resume ribbon is still there."),
      ]),
    C("PL-05", "Play - Rules toggle switches standard and relaxed",
      f"{S} > Play",
      [
          ("On the picker, tap \"standard rules / tap to change\".",
           "It reads relaxed rules and explains that relaxed rules let "
           "piles of any size move but score less."),
          ("Tap it again.",
           "It reads standard rules again."),
      ]),
    C("PL-06", "Play - Resume continues the paused game",
      f"{S} > Play",
      [
          ("Make a move on a table, tap Back, then tap Play.",
           "The red ribbon under the levels reads Resume."),
          ("Tap Resume.",
           "The same board comes back, with your move still made."),
      ],
      priority="High"),
    C("PL-07", "Play - Relaxed rules deal a relaxed game",
      f"{S} > Play",
      [
          ("Switch the picker to relaxed rules and tap Easy.",
           "The table footer reads \"easy level relaxed rules\"."),
          ("Go back and switch the picker to standard rules.",
           "The picker reads standard rules again."),
      ]),

    # ── Gameplay ──────────────────────────────────────────────────────
    C("GP-01", "Gameplay - Table controls are on screen",
      f"{S} > Gameplay",
      [
          ("Start an Easy game.",
           "Back, new, the move counter, and menu at the top; four "
           "foundations, four free cells, and eight columns; tap to undo, "
           "tap to lower, and tap for hints at the bottom."),
      ],
      priority="High"),
    C("GP-02", "Gameplay - Tapping a card moves it",
      f"{S} > Gameplay",
      [
          ("Tap the bottom card of a column that has a legal move.",
           "The card moves to a column, a free cell, or a foundation, and "
           "the move counter goes up by one."),
      ],
      priority="High"),
    C("GP-03", "Gameplay - Undo puts the board back",
      f"{S} > Gameplay",
      [
          ("After a move, tap tap to undo.",
           "The card is back where it was and the move counter goes back "
           "down."),
      ],
      priority="High"),
    C("GP-04", "Gameplay - Tap to lower drops the playfield",
      f"{S} > Gameplay",
      [
          ("Tap tap to lower once.",
           "The whole playfield slides down."),
      ]),
    C("GP-05", "Gameplay - Tap to raise brings the playfield back",
      f"{S} > Gameplay",
      [
          ("With the playfield lowered, tap the same control again.",
           "The playfield slides back up to where it started."),
      ]),
    C("GP-06", "Gameplay - Tap for hints steps through moves",
      f"{S} > Gameplay",
      [
          ("Tap tap for hints.",
           "The label changes to \"tap for more / move 1 of N\"."),
          ("Tap it again.",
           "It reads move 2 of N."),
      ],
      priority="High"),
    C("GP-07", "Gameplay - In-game menu shows all its actions",
      f"{S} > Gameplay",
      [
          ("On the table, tap menu.",
           "A drawer shows replay, abandon, options, new, help, FAQ, and "
           "the rotation lock."),
      ]),
    C("GP-08", "Gameplay - Rank Strip OFF hides the A-K strip",
      f"{S} > Gameplay",
      [
          ("On a table, note the A 2 3 … K strip above the bottom labels. "
           "Turn Rank Strip off in Options and go back.",
           "The strip is gone."),
      ],
      priority="High"),
    C("GP-09", "Gameplay - Rank Strip ON brings the strip back",
      f"{S} > Gameplay",
      [
          ("Turn Rank Strip back on and go back to the table.",
           "The A-K strip is back."),
      ],
      priority="High"),
    C("GP-10", "Gameplay - Rich Features OFF hides timer, score, multiplier",
      f"{S} > Gameplay",
      [
          ("Turn Rich Features off in Options and go back to the table.",
           "Timer, score, multiplier, and the move counter are gone."),
      ],
      priority="High"),
    C("GP-11", "Gameplay - Rich Features ON brings timer, score, multiplier back",
      f"{S} > Gameplay",
      [
          ("Turn Rich Features back on and go back to the table.",
           "Timer, score, multiplier, and moves are visible again."),
      ],
      priority="High"),
    C("GP-12", "Gameplay - Timer waits for the first move",
      f"{S} > Gameplay",
      [
          ("Deal a new game and wait about ten seconds without touching "
           "a card.",
           "The timer still reads 0:00 and the footer says tap a card to "
           "start."),
          ("Move a card.",
           "The timer starts counting."),
      ]),
    C("GP-13", "Gameplay - Rules prompt after the first deal opens Help",
      f"{S} > Gameplay",
      [
          ("On a fresh install, deal the first game and wait a few seconds.",
           "\"Would you like to review the game rules before to play?\" "
           "appears with No and Yes."),
          ("Tap Yes, then Back on Help.",
           "Help opened, and Back returns to the same table."),
      ]),
    C("GP-14", "Gameplay - New deals a different board",
      f"{S} > Gameplay",
      [
          ("Look at the board, tap new, and confirm if asked.",
           "A different deal is on the table."),
      ],
      priority="High"),
    C("GP-15", "Gameplay - Replay asks first, and No keeps the board",
      f"{S} > Gameplay",
      [
          ("Make a move, open the menu, and tap replay.",
           "\"Are you sure you want to play this game again?\" warns that "
           "the replay breaks the current run and is not recorded."),
          ("Tap No.",
           "The board still has your move."),
      ]),
    C("GP-16", "Gameplay - Replay Yes restores the original deal",
      f"{S} > Gameplay",
      [
          ("Tap replay again and answer Yes.",
           "The page turns and the original deal is back: the move is "
           "undone, the counter is 0, and the timer reads 0:00."),
      ],
      priority="High"),
    C("GP-17", "Gameplay - Menu help opens Help and returns to the table",
      f"{S} > Gameplay",
      [
          ("Open the menu and tap help.",
           "Help opens on Introduction."),
          ("Tap Back.",
           "The same table is showing."),
      ]),
    C("GP-18", "Gameplay - Menu FAQ opens on Solo and returns to the table",
      f"{S} > Gameplay",
      [
          ("Open the menu and tap FAQ.",
           "The FAQ opens with the Solo tab selected."),
          ("Tap Back.",
           "The same table is showing."),
      ]),
    C("GP-19", "Gameplay - Menu options opens Options and returns to the table",
      f"{S} > Gameplay",
      [
          ("Open the menu and tap options.",
           "Options opens."),
          ("Tap Back.",
           "The same table is showing."),
      ]),
    C("GP-20", "Gameplay - A stuck card offers help",
      f"{S} > Gameplay",
      [
          ("With all free cells full, tap a card that has nowhere to go.",
           "A help button replaces the score and timer under the board."),
          ("Tap help.",
           "Help opens. Back returns to the table."),
      ]),
    C("GP-21", "Gameplay - Rotation lock keeps the table in portrait",
      f"{S} > Gameplay",
      [
          ("Open the menu and tap the round arrow (rotation lock).",
           "The first time, an alert says the interface orientation is "
           "locked. Tap OK."),
          ("Turn the phone to landscape.",
           "The table stays in portrait."),
      ]),
    C("GP-22", "Gameplay - Unlocked table turns to landscape",
      f"{S} > Gameplay",
      [
          ("Tap the rotation lock again, then turn the phone to landscape.",
           "The table turns: foundations in a left column, free cells in "
           "a right column."),
          ("Turn the phone back to portrait.",
           "The portrait table is back."),
      ]),
    C("GP-23", "Gameplay - Abandon ends the game",
      f"{S} > Gameplay",
      [
          ("Open the menu and tap abandon. Confirm if asked.",
           "The game ends and you leave the table. Play shows no Resume "
           "ribbon for it."),
      ]),
    C("GP-24", "Gameplay - Tapping a buried card highlights its rank",
      f"{S} > Gameplay",
      [
          ("Tap a card that is buried under others.",
           "Every card of that rank is outlined. Nothing moves."),
      ]),

    # ── Relaunch ──────────────────────────────────────────────────────
    C("RL-01", "Relaunch - Same board after closing the app for a few seconds",
      f"{S} > Relaunch",
      [
          ("On a table, make one move and remember the board.",
           "The board has changed from the deal."),
          ("Press Home first (the app saves when it goes to the "
           "background), swipe FreeCell away, wait about 3 seconds, and "
           "open it again.",
           "The same table comes back. A tap a card to start overlay is "
           "fine."),
      ],
      priority="High"),
    C("RL-02", "Relaunch - Same board after closing the app for 35 seconds",
      f"{S} > Relaunch",
      [
          ("Do the same, but wait about 35 seconds before opening it.",
           "The same table comes back."),
      ],
      priority="High"),

    # ── QA ────────────────────────────────────────────────────────────
    C("QA-01", "QA - Code entry opens from About",
      f"{S} > QA",
      [
          ("On About, tap the Version line, then tap the FreeCell emblem "
           "ten times quickly.",
           "A code entry appears. A build without QA (the App Store "
           "release) shows nothing — that build cannot run this list."),
      ],
      priority="High"),
    C("QA-02", "QA - The code turns QA on",
      f"{S} > QA",
      [
          ("Enter 943010 and go back to the main menu.",
           "A CONFIDENTIAL watermark covers the menu."),
      ],
      priority="High"),
    C("QA-03", "QA - The table badge opens Synthetic Win",
      f"{S} > QA",
      [
          ("Deal Easy, tap a card to start, and tap the QA badge.",
           "The Synthetic Win card opens with score bands and WIN."),
      ],
      priority="High"),
    C("QA-04", "QA - Entering the code again turns QA off",
      f"{S} > QA",
      [
          ("Repeat the code entry on About with 943010.",
           "The CONFIDENTIAL watermark is gone from the menu."),
      ]),

    # ── Victory ───────────────────────────────────────────────────────
    C("VI-01", "Victory - Synthetic Win shows the win screen",
      f"{S} > Victory",
      [
          ("On the Synthetic Win card, pick 90% - 99% and tap WIN.",
           "The Victory screen appears."),
      ],
      priority="High"),
    C("VI-02", "Victory - Win screen shows all of its parts",
      f"{S} > Victory",
      [
          ("Look over the Victory screen.",
           "ranking for This Week, current / rank / best columns, "
           "leaderboards, achievements, and the help, new, and stats "
           "buttons."),
      ]),
    C("VI-03", "Victory - Footer names the level and rules you played",
      f"{S} > Victory",
      [
          ("Win an Easy standard game and read the footer.",
           "It reads easy level • standard rules."),
      ],
      priority="High"),
    C("VI-04", "Victory - Back returns to the main menu",
      f"{S} > Victory",
      [
          ("Tap the Victory screen's Back — not new.",
           "The main menu is showing."),
      ]),
    C("VI-05", "Victory - Stats opens Statistics",
      f"{S} > Victory",
      [
          ("Win a game and tap stats.",
           "Statistics opens."),
      ]),
    C("VI-06", "Victory - New deals the next game",
      f"{S} > Victory",
      [
          ("Win a game and tap new.",
           "A new table is dealt."),
      ]),
    C("VI-07", "Victory - Help opens Help",
      f"{S} > Victory",
      [
          ("Win a game and tap help.",
           "Help opens."),
      ]),

    # ── Difficulty ────────────────────────────────────────────────────
    C("DL-01", "Difficulty - Medium starts and can be completed",
      f"{S} > Difficulty",
      [
          ("Tap Play, then Medium. Win it with Synthetic Win.",
           "A Medium table dealt, Victory appeared with a medium level "
           "footer, and Back reaches the menu."),
      ],
      priority="High"),
    C("DL-02", "Difficulty - Hard starts and can be completed",
      f"{S} > Difficulty",
      [
          ("Tap Play, then Hard. Win it with Synthetic Win.",
           "A Hard table dealt, Victory appeared, and Back reaches the "
           "menu."),
      ],
      priority="High"),
    C("DL-03", "Difficulty - Expert starts and can be completed",
      f"{S} > Difficulty",
      [
          ("Tap Play, then Expert. Win it with Synthetic Win.",
           "An Expert table dealt, Victory appeared, and Back reaches the "
           "menu."),
      ],
      priority="High"),
    C("DL-04", "Difficulty - Master starts and can be completed",
      f"{S} > Difficulty",
      [
          ("Tap Play, then Master. Win it with Synthetic Win.",
           "A Master table dealt, Victory appeared, and Back reaches the "
           "menu."),
      ],
      priority="High"),

    # ── Last Score ────────────────────────────────────────────────────
    C("LS-01", "Last Score - Before any win it says no game is completed",
      f"{S} > Last Score",
      [
          ("On a fresh install, tap Play, then LAST SCORE.",
           "\"No game has been completed yet — At least one Solo game has "
           "to be completed before any data can be shown\"."),
      ]),
    C("LS-02", "Last Score - After a win it opens Last Won Game Score",
      f"{S} > Last Score",
      [
          ("After a win, tap Play, then LAST SCORE.",
           "Last Won Game Score opens with current / rank / best for the "
           "won game."),
      ]),
    C("LS-03", "Last Score - Arrows change the ranking period",
      f"{S} > Last Score",
      [
          ("Tap the arrow beside the ranking period.",
           "The period changes and you stay on Last Won Game Score."),
      ]),
    C("LS-04", "Last Score - Leaderboards opens Game Center",
      f"{S} > Last Score",
      [
          ("With Wi-Fi on and an Apple ID signed in, tap leaderboards.",
           "Game Center opens on Leaderboards. Close it to return."),
      ]),
    C("LS-05", "Last Score - Achievements opens Game Center",
      f"{S} > Last Score",
      [
          ("Tap achievements.",
           "Game Center opens on Achievements. Close it to return."),
      ]),
    C("LS-06", "Last Score - Back returns to the main menu",
      f"{S} > Last Score",
      [
          ("From Last Score, tap Back.",
           "The main menu is showing (not the difficulty picker)."),
      ]),

    # ── Daily ─────────────────────────────────────────────────────────
    C("DY-01", "Daily - Opens the calendar from the main menu",
      f"{S} > Daily",
      [
          ("From the main menu, tap Daily.",
           "The Daily screen opens with a level button at the top right."),
      ],
      priority="High"),
    C("DY-02", "Daily - First visit points at the level button",
      f"{S} > Daily",
      [
          ("On a fresh install, open Daily.",
           "A tip says \"Tap on the Level Button to select your favorite "
           "level\" and the level button is outlined."),
      ]),
    C("DY-03", "Daily - Second tip explains dates and replays",
      f"{S} > Daily",
      [
          ("Tap the first tip.",
           "A second tip says \"Tap on any available date to play a "
           "game\", with notes on replays and gold stars."),
          ("Tap it.",
           "The calendar is showing with no tip."),
      ]),
    C("DY-04", "Daily - Calendar shows this month with today marked",
      f"{S} > Daily",
      [
          ("Look at the calendar.",
           "It shows the current month. Today is orange, past days are "
           "white, and future days are dimmed."),
      ]),
    C("DY-05", "Daily - Level button lists Standard and Relaxed levels",
      f"{S} > Daily",
      [
          ("Tap the level button.",
           "A list shows Standard Easy, Medium, Hard, Expert, Master and "
           "Relaxed Easy, Medium, Hard, Expert, Master, with a note on "
           "relaxed rules."),
      ]),
    C("DY-06", "Daily - Choosing a level updates the button",
      f"{S} > Daily",
      [
          ("Choose Standard Hard.",
           "The button reads Hard."),
          ("Open the list again and choose Relaxed Easy.",
           "The button reads Easy with an R badge."),
          ("Choose Standard Medium.",
           "The button reads Medium again."),
      ]),
    C("DY-07", "Daily - A future date cannot be played",
      f"{S} > Daily",
      [
          ("Tap a dimmed future date.",
           "Nothing happens. The calendar stays."),
      ]),
    C("DY-08", "Daily - Offline, a date asks for internet",
      f"{S} > Daily",
      [
          ("With Airplane Mode on, tap today.",
           "\"Sorry, Daily Games can be initiated only when Internet is "
           "available\" offers a Solo game instead, with No and Yes."),
          ("Tap No.",
           "The calendar is still showing."),
      ],
      priority="High"),
    C("DY-09", "Daily - Offline, Yes goes to the main menu",
      f"{S} > Daily",
      [
          ("Tap a past date, then Yes on the same alert.",
           "Daily closes onto the main menu. No game is dealt."),
      ]),
    C("DY-10", "Daily - Back returns to the main menu",
      f"{S} > Daily",
      [
          ("From the calendar, tap back.",
           "The main menu is showing."),
      ]),
    C("DY-11", "Daily - FAQ link opens the FAQ",
      f"{S} > Daily",
      [
          ("Under the calendar, tap FAQ.",
           "The FAQ opens inside FreeCell. Back returns to the calendar."),
      ]),
    C("DY-12", "Daily - Today deals a Daily game",
      f"{S} > Daily",
      [
          ("With Wi-Fi on, tap today.",
           "A Daily table is dealt, with a star in its header and the "
           "chosen level in its footer."),
      ],
      priority="High"),
    C("DY-13", "Daily - Winning today puts a gold star on the calendar",
      f"{S} > Daily",
      [
          ("Win today's Daily game (Synthetic Win) and go back to Daily.",
           "Today carries a gold star."),
      ],
      priority="High"),
    C("DY-14", "Daily - A Daily win counts on the Daily statistics",
      f"{S} > Daily",
      [
          ("Open Stats → Daily after that win.",
           "Games won is 1 and best score shows the win."),
      ]),

    # ── Choose Look ───────────────────────────────────────────────────
    C("CL-01", "Choose Look - Opens on the Surface tab",
      f"{S} > Choose Look",
      [
          ("From the main menu, tap Choose Look.",
           "The look picker opens on Surface, with six felts and Simulate "
           "Depth."),
      ]),
    C("CL-02", "Choose Look - Close returns to the main menu",
      f"{S} > Choose Look",
      [
          ("Tap the X.",
           "The picker closes and the main menu is usable."),
      ]),
    C("CL-03", "Choose Look - Surface and Cards tabs switch",
      f"{S} > Choose Look",
      [
          ("Tap Cards, then Surface.",
           "Cards shows six card backs and Extra Large Card-Symbols. "
           "Surface shows the felts again."),
      ]),
    C("CL-04", "Choose Look - Another surface shows on the game table",
      f"{S} > Choose Look",
      [
          ("Pick a different felt, close the picker, and start or resume "
           "Easy.",
           "The table felt matches the felt you picked."),
      ],
      priority="High"),
    C("CL-05", "Choose Look - Another card back shows on the table",
      f"{S} > Choose Look",
      [
          ("Pick a different card back and look at the table's undo and "
           "hint piles.",
           "The backs match the deck you picked."),
      ],
      priority="High"),
    C("CL-06", "Choose Look - Extra Large Card-Symbols turns on and off",
      f"{S} > Choose Look",
      [
          ("On Cards, tap Extra Large Card-Symbols (ships OFF) twice.",
           "It turns on, then back off."),
      ]),
    C("CL-07", "Choose Look - Simulate Depth turns off and on",
      f"{S} > Choose Look",
      [
          ("On Surface, tap Simulate Depth twice.",
           "It changes state, then returns to where it was."),
      ]),

    # ── Reset (destructive) ───────────────────────────────────────────
    C("RS-01", "Reset Statistics - Solo reset asks twice",
      f"{S} > Statistics",
      [
          ("On Solo, scroll to Reset Solo Statistics and tap it.",
           "\"Would you like to reset local scores?\" notes that Game "
           "Center scores are not reset (No / Yes)."),
          ("Tap Yes.",
           "\"Just to be on the safe side…\" asks once more (No / Yes)."),
      ],
      type="Destructive",
      priority="High"),
    C("RS-02", "Reset Statistics - Confirming wipes the Solo scores",
      f"{S} > Statistics",
      [
          ("Tap Yes on the second alert, then open Stats.",
           "You land on the main menu. Solo reads best score 0 and every "
           "level none."),
      ],
      type="Destructive",
      priority="High"),
    C("RS-03", "Reset Statistics - Declining leaves the Solo scores alone",
      f"{S} > Statistics",
      [
          ("Tap Reset Solo Statistics, then No.",
           "Statistics stays open and the scores are unchanged."),
      ],
      type="Destructive"),
    C("RS-04", "Reset Statistics - Daily reset asks twice",
      f"{S} > Statistics",
      [
          ("On Daily, scroll to Reset Daily Statistics and tap it, then "
           "Yes.",
           "The same two alerts as the Solo reset appear."),
      ],
      type="Destructive"),
    C("RS-05", "Reset Statistics - Confirming wipes the Daily scores",
      f"{S} > Statistics",
      [
          ("Tap Yes on the second alert, then open Stats → Daily.",
           "You land on the main menu. Daily reads 0 everywhere."),
      ],
      type="Destructive"),
    C("RS-06", "Reset Statistics - Declining leaves the Daily scores alone",
      f"{S} > Statistics",
      [
          ("Tap Reset Daily Statistics, then No.",
           "Statistics stays open on Daily and nothing changed."),
      ],
      type="Destructive"),
]


def validate(cases=CASES):
    """Raise if titles or ids collide, or a case has no steps."""
    ids, titles = [], []
    for case in cases:
        if not case["steps"]:
            raise ValueError(f"{case['id']}: empty steps")
        ids.append(case["id"])
        titles.append(case["title"])
    dups = {i for i in ids if ids.count(i) > 1}
    if dups:
        raise ValueError(f"duplicate case ids: {sorted(dups)}")
    dups = {t for t in titles if titles.count(t) > 1}
    if dups:
        raise ValueError(f"duplicate titles: {sorted(dups)}")
    return len(cases)


if __name__ == "__main__":
    n = validate()
    print(f"{n} TestRail cases, titles unique")
