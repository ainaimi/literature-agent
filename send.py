# send.py — email delivery via SMTP

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(html_body: str, *, subject: str, to_addr: str,
               credentials, attachment: tuple[str, str] | None = None):
    """Send the HTML digest via SMTP.

    credentials: a models.PlatformCredentials holding the SMTP account.
    attachment: optional (filename, html_content) attached to the message as a
    downloadable HTML file — used for the full scored-paper list.
    """
    if not to_addr:
        raise ValueError("No recipient: set EMAIL_TO in the environment "
                         "(or email_to in the tenant settings).")
    if not credentials.smtp_username or not credentials.smtp_password:
        raise ValueError("SMTP_USERNAME / SMTP_PASSWORD not set in the "
                         "environment — cannot send email.")

    from_addr = credentials.email_from or credentials.smtp_username

    # multipart/mixed so the message can carry both the body and an attachment.
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
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

    with smtplib.SMTP(credentials.smtp_host, credentials.smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(credentials.smtp_username, credentials.smtp_password)
        smtp.sendmail(from_addr, [to_addr], msg.as_string())
