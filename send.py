# send.py — email delivery via SMTP

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

import config

load_dotenv(os.path.expanduser("~/.env"))


def send_email(html_body: str, attachment: tuple[str, str] | None = None):
    """Send the HTML digest via SMTP.

    attachment: optional (filename, html_content) attached to the message as a
    downloadable HTML file — used for the full scored-paper list.
    """
    host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port     = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]
    from_addr = os.environ.get("EMAIL_FROM", username)  # default: same as SMTP_USERNAME
    to_addr   = os.environ["EMAIL_TO"]

    # multipart/mixed so the message can carry both the body and an attachment.
    msg = MIMEMultipart("mixed")
    msg["Subject"] = config.EMAIL_SUBJECT
    msg["From"]    = from_addr
    msg["To"]      = to_addr

    # The visible message body (HTML).
    body = MIMEMultipart("alternative")
    body.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(body)

    # Optional HTML attachment (the full scored list).
    if attachment is not None:
        filename, content = attachment
        part = MIMEText(content, "html", "utf-8")
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(username, password)
        smtp.sendmail(from_addr, [to_addr], msg.as_string())
