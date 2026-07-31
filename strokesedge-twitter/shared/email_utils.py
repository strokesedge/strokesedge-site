"""
Thin Gmail SMTP wrapper. No stream-specific formatting here — each
stream's own emailer/alert code builds the subject/body it wants and
calls send_email().
"""

import os
import smtplib
from email.mime.text import MIMEText

GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
GMAIL_ADDRESS = "strokesedge@gmail.com"


def send_email(subject, body, to_address=GMAIL_ADDRESS):
    if not GMAIL_APP_PASSWORD:
        print(f"[email_utils] GMAIL_APP_PASSWORD not set — skipping email.\n"
              f"  Subject would have been: {subject}")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_address

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[email_utils] Failed to send email ({subject!r}): {e}")
        return False
