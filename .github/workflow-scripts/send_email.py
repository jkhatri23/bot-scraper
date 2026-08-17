#!/usr/bin/env python3
"""Send the alert email over SMTP using only the standard library.

This replaces dawidd6/action-send-mail. That action is fetched from codeload
on every single run, and at a two-minute poll cadence that is ~720 tarball
downloads a day, which starts returning 429. The failure lands in "Set up job",
before any step-level guard can contain it, so a rate-limited download takes
out the entire cycle — both board checks and the state commit.

stdlib smtplib has no such failure mode, and it keeps the Gmail app password
out of a third-party action.

Inputs arrive as environment variables so nothing is interpolated into a shell
command line: MAIL_SUBJECT, MAIL_HTML, MAIL_PLAIN, MAIL_USERNAME,
MAIL_PASSWORD, MAIL_TO, and optionally MAIL_FROM and MAIL_DRYRUN.
"""

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        sys.exit(f"send_email: {name} is empty; refusing to send")
    return value


def main() -> None:
    subject = require("MAIL_SUBJECT")
    plain = require("MAIL_PLAIN")
    html = os.environ.get("MAIL_HTML", "")
    to_addr = require("MAIL_TO")
    from_name = os.environ.get("MAIL_FROM", "Internship Watcher")
    dryrun = bool(os.environ.get("MAIL_DRYRUN"))

    username = os.environ.get("MAIL_USERNAME", "") if dryrun else require("MAIL_USERNAME")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = to_addr
    msg["From"] = f"{from_name} <{username}>" if username else from_name
    msg.set_content(plain)
    if html:
        msg.add_alternative(html, subtype="html")

    if dryrun:
        # Exercises construction and header encoding without touching SMTP.
        print(f"DRYRUN subject={subject!r} to={to_addr!r} "
              f"plain={len(plain)}B html={len(html)}B")
        print(msg.as_string()[:400])
        return

    password = require("MAIL_PASSWORD")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=30) as smtp:
        smtp.login(username, password)
        smtp.send_message(msg)
    print(f"sent: {subject!r} -> {to_addr}")


if __name__ == "__main__":
    main()
