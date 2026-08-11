# send.py — email delivery via SMTP

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

import config

load_dotenv(os.path.expanduser("~/.env"))


def send_email(html_body: str):
    """Send the HTML digest via SMTP."""
    host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port     = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]
    from_addr = os.environ.get("EMAIL_FROM", username)  # default: same as SMTP_USERNAME
    to_addr   = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = config.EMAIL_SUBJECT
    msg["From"]    = from_addr
    msg["To"]      = to_addr

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(username, password)
        smtp.sendmail(from_addr, [to_addr], msg.as_string())
