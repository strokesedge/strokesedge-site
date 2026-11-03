"""
Thin Gmail SMTP wrapper. No stream-specific formatting here — each
stream's own emailer/alert code builds the subject/body it wants and
calls send_email().
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
GMAIL_ADDRESS = "strokesedge@gmail.com"


def send_email(subject, body, to_address=GMAIL_ADDRESS, attachment_path=None):
    """attachment_path (optional): a local PNG to attach — used for chart
    images (stream2_manual's batch emails). A missing/unreadable
    attachment falls back to sending the email without it rather than
    losing the whole email over an image problem."""
    if not GMAIL_APP_PASSWORD:
        print(f"[email_utils] GMAIL_APP_PASSWORD not set — skipping email.\n"
              f"  Subject would have been: {subject}")
        return False

    if attachment_path:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body))
        try:
            with open(attachment_path, "rb") as f:
                # _subtype passed explicitly rather than left to MIMEImage's
                # default guess — that default relies on the stdlib imghdr
                # module, removed in Python 3.13+ (this runs on 3.14), which
                # would raise ModuleNotFoundError. We only ever attach the
                # PNGs chart_gen.py produces, so "png" is always correct.
                img = MIMEImage(f.read(), _subtype="png")
            img.add_header("Content-Disposition", "attachment",
                            filename=os.path.basename(attachment_path))
            msg.attach(img)
        except Exception as e:
            print(f"[email_utils] Could not attach {attachment_path!r}, sending without it: {e}")
    else:
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
