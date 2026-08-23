# Tests for send.py — SMTP wiring, with smtplib monkeypatched (no network).

import pytest

import send
from models import PlatformCredentials


class FakeSMTP:
    instances = []

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.calls = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        self.calls.append(("ehlo",))

    def starttls(self):
        self.calls.append(("starttls",))

    def login(self, username, password):
        self.calls.append(("login", username, password))

    def sendmail(self, from_addr, to_addrs, message):
        self.calls.append(("sendmail", from_addr, to_addrs, message))


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(send.smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


CREDS = PlatformCredentials(smtp_host="smtp.test.com", smtp_port=2525,
                            smtp_username="sender@test.com", smtp_password="pw")


def test_send_email_builds_and_sends_message(smtp):
    send.send_email("<p>digest</p>", subject="Your Lit-Search Digest",
                    to_addr="reader@uni.edu", credentials=CREDS,
                    attachment=("full-list.html", "<p>full</p>"))
    (conn,) = smtp.instances
    assert (conn.host, conn.port) == ("smtp.test.com", 2525)
    assert ("login", "sender@test.com", "pw") in conn.calls
    op, from_addr, to_addrs, message = conn.calls[-1]
    assert op == "sendmail"
    assert from_addr == "sender@test.com"   # email_from empty → smtp_username
    assert to_addrs == ["reader@uni.edu"]
    assert "Subject: Your Lit-Search Digest" in message
    assert 'filename="full-list.html"' in message


def test_send_email_email_from_overrides_username(smtp):
    creds = PlatformCredentials(smtp_username="sender@test.com",
                                smtp_password="pw", email_from="digest@lab.org")
    send.send_email("<p>x</p>", subject="s", to_addr="r@x.com", credentials=creds)
    op, from_addr, _, message = smtp.instances[0].calls[-1]
    assert from_addr == "digest@lab.org"
    assert "From: digest@lab.org" in message


def test_send_email_requires_recipient(smtp):
    with pytest.raises(ValueError, match="EMAIL_TO"):
        send.send_email("<p>x</p>", subject="s", to_addr="", credentials=CREDS)
    assert not smtp.instances


def test_send_email_requires_smtp_credentials(smtp):
    with pytest.raises(ValueError, match="SMTP_USERNAME"):
        send.send_email("<p>x</p>", subject="s", to_addr="r@x.com",
                        credentials=PlatformCredentials())
    assert not smtp.instances
