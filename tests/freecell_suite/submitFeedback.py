#!/usr/bin/env python3
"""submitFeedback: About's "submit feedback" mail draft. [ONLINE]

FB-02  the link asks Cancel / Write Email
FB-03  Write Email opens a Mail draft
FB-04  the subject names FreeCell, the app version, this phone's model and iOS
FB-05  the draft is deleted — never sent
FB-06  the status-bar crumb returns to FreeCell

Every expected subject field is read off this device in the same run. The
draft is deleted even when the subject is wrong. Needs a Mail account.

Run:  ./.venv/bin/python -u tests/freecell_suite/submitFeedback.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402

LINK = "about_feedback"
APP_NAME = "FreeCell"


def expected_fields() -> list[tuple[str, str]]:
    # The subject carries major.minor ("7.42") while About shows the full 7.42.5.
    version = ".".join((helpers.installed_build() or ("", ""))[0].split(".")[:2])
    return [("game name", APP_NAME), ("app version", version),
            ("device model", helpers.device_model()), ("iOS version", helpers.os_version())]


def run() -> None:
    fc.go_online()
    fields = expected_fields()
    fc.menu()
    ui.expect(ui.tap("menu_about", settle=2.5), "About control not found on the menu")
    ui.expect(ui.expect_screen("about"), "tapping About did not open About")
    ui.expect(ui.is_on(LINK), "the 'submit feedback' link is not on About")

    with caselog.case("FB-02") as c:
        ui.expect(ui.tap(LINK, settle=3.0), "the 'submit feedback' link could not be tapped")
        caselog.step("Check FreeCell asks about feedback, offering Cancel and Write Email")
        text = fc.wait_alert("feedback", timeout=6.0)
        ui.expect(text, "tapping 'submit feedback' did not raise the feedback prompt "
                        f"(alert on screen: {helpers.alert_text()!r})")
        buttons = helpers.alert_buttons()
        c.shot(ui.shoot("SubmitFeedbackAsk"))
        ui.expect(buttons == ["Cancel", "Write Email"],
                  f"the feedback prompt should offer Cancel then Write Email, got {buttons}")
        c.note("asks Cancel / Write Email")

    with caselog.case("FB-03") as c:
        ui.expect(helpers.answer_alert("Write Email", settle=4.0),
                  "could not press Write Email")
        caselog.step("Check Mail opens with a new draft")
        went = fc.left_app(timeout=12.0)
        ui.expect(went == fc.MAIL,
                  f"Write Email did not open Mail — in {went} (is a Mail account set up?)")
        draft = fc.mail_draft()
        c.shot(ui.shoot("SubmitFeedback"))
        ui.expect(draft["subject"], "Mail opened but the draft has no readable subject")
        print(f"  subject: {draft['subject']!r}")
        print(f"  to     : {draft['to']!r}")
        c.note(f"Mail draft to {draft['to'] or '?'}")

    discarded = False
    try:
        with caselog.case("FB-04", soft=True) as c:
            caselog.step("Check the subject names the game, app version, device model and "
                         "iOS version")
            unread = [label for label, value in fields if not value]
            ui.expect(not unread, f"could not read {unread} off the device")
            subject = draft["subject"].lower()
            missing = [f"{label} ({value!r})" for label, value in fields
                       if value.lower() not in subject]
            ui.expect(not missing, f"the subject {draft['subject']!r} does not name "
                                   f"{', '.join(missing)}")
            c.note(draft["subject"])
    finally:
        with caselog.case("FB-05") as c:
            discarded = fc.mail_discard()
            ui.expect(discarded, "the draft could not be deleted — check Mail; nothing was sent")
            c.note("draft deleted, nothing sent")

    with caselog.case("FB-06") as c:
        ui.expect(fc.tap_back_to_app(), "the status-bar crumb did not bring FreeCell back")
        caselog.step("Check FreeCell is back on About or the main menu")
        landed = ("About" if ui.expect_screen("about", timeout=6.0)
                  else "the main menu" if ui.on_menu(6.0) else "")
        c.shot(ui.shoot("SubmitFeedbackBack"))
        ui.expect(landed, "came back to FreeCell but not to About or the main menu")
        c.note(f"back in FreeCell on {landed}")

    ui.expect(ui.to_menu(), "could not reach the main menu after coming back")
    caselog.raise_if_failed()
    print("PASS: 'submit feedback' opens a Mail draft naming the game, version, "
          "model and iOS; the draft was deleted and FreeCell came back")


if __name__ == "__main__":
    fc.main(run)
