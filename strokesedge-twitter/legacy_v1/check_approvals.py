"""
StrokesEdge Twitter Auto-Poster — Reply-based approval via Gmail IMAP

Checks strokesedge@gmail.com over IMAP for new replies to the "N tweet(s)
need approval" alert emails queue_manager.py sends, parses loose approve/
reject commands out of the reply body, and applies them using the exact
same approve()/reject() functions approve.py's CLI uses — so there is only
ever one place that defines what "approve" and "reject" actually do to the
queue files.

Meant to run unattended on a schedule (Task Scheduler, every 5 minutes) so
Brian never has to open a terminal or run approve.py by hand.

Safety model:
- Only acts on messages whose subject looks like a reply ("Re: ...") to a
  subject containing "need approval" — never on some unrelated new email
  that happens to contain the word "approve".
- Only ever processes each message once: the highest UID seen is persisted
  in check_approvals_state.json, and every future run only looks at UIDs
  above that mark. The processed message is also marked \\Seen via IMAP as
  a second, belt-and-suspenders signal, but the UID watermark is the real
  dedup mechanism (a \\Seen flag can flip back in ways a stored UID can't).
- If a reply doesn't parse into at least one recognizable (approve/reject,
  index) command, this never guesses — it sends back a short "didn't
  understand" reply naming the current pending count, and does nothing to
  the queue files.
"""

import email
import imaplib
import json
import os
import re
import smtplib
import sys
from email.header import decode_header
from email.mime.text import MIMEText
from email.utils import parseaddr

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config import QUEUE_DIR, PENDING_REVIEW, MANUAL_POST_QUEUE
from approve import load_jsonl, approve, reject, mark_posted

GMAIL_ADDRESS = "strokesedge@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

STATE_FILE = os.path.join(QUEUE_DIR, "check_approvals_state.json")

# Must match the subject queue_manager.py's send_review_email() sends:
#   f"StrokesEdge: {len(pending_items)} tweet(s) need approval"
# A genuine reply's subject is "Re: <that>" (possibly "Re: Re: ..." from
# some clients) — IMAP SUBJECT search matches substrings, so searching for
# this phrase alone catches both the original alert and every reply to it;
# the reply-vs-original distinction is enforced separately below.
SUBJECT_MARKER = "need approval"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_uid": 0}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def decode_subject(raw_subject):
    if not raw_subject:
        return ""
    parts = decode_header(raw_subject)
    out = ""
    for text, enc in parts:
        out += text.decode(enc or "utf-8", errors="replace") if isinstance(text, bytes) else text
    return out


def get_body_text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                return payload.decode(charset, errors="replace") if payload else ""
        return ""
    charset = msg.get_content_charset() or "utf-8"
    payload = msg.get_payload(decode=True)
    return payload.decode(charset, errors="replace") if payload else ""


# Matches a verb (approve/yes/reject/no/posted/done/etc.) followed, within
# a short span, by one or more numbers separated by commas/"and"/"&"/
# whitespace. Deliberately loose: "approve 1", "Approve 1, 2",
# "APPROVE 1 and 2", "yes 1", "reject 2", "posted 3", "done 3" all match.
# Does NOT try to handle every conceivable phrasing — anything it doesn't
# match falls through to the "not understood" reply rather than being
# guessed at.
# NOTE: "posted"/"done" target a DIFFERENT list (manual_post_queue.jsonl)
# than "approve"/"reject" (pending_review.jsonl) — see process_message(),
# which splits commands by target list before executing either group.
ACTION_PATTERN = re.compile(
    r"\b(approve|approved|yes|reject|rejected|no|deny|discard|posted|done)\b"
    r"[^\d\n]{0,20}((?:\d+[\s,&]*(?:and)?[\s,&]*)+)",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"\d+")

ACTION_VERB_MAP = {
    "approve": "approve", "approved": "approve", "yes": "approve",
    "reject": "reject", "rejected": "reject", "no": "reject", "deny": "reject", "discard": "reject",
    "posted": "posted", "done": "posted",
}

# Email clients quote the entire original message below a reply (Gmail:
# "On <date>, <name> wrote:" then '>'-prefixed lines, or a line of dashes
# for some clients). Cut the body there before parsing, so stray digits
# in the quoted alert (tweet char counts, etc.) can never be mistaken for
# part of Brian's actual command.
QUOTE_CUT_RE = re.compile(r"\n\s*On .{0,120} wrote:|\n\s*>|\n_{5,}|\n-{5,} ?Original Message ?-{5,}", re.S)


def parse_command(body):
    body_top = QUOTE_CUT_RE.split(body, maxsplit=1)[0]
    commands = []
    for m in ACTION_PATTERN.finditer(body_top):
        action = ACTION_VERB_MAP[m.group(1).lower()]
        for n in NUMBER_PATTERN.findall(m.group(2)):
            commands.append((action, int(n)))
    return commands



# Every reply THIS script sends carries this header. Without it, our own
# confirmation reply ("Re: StrokesEdge: N tweet(s) need approval", sent
# from/to strokesedge@gmail.com just like a real reply from Brian) would
# look exactly like a genuine incoming reply on the next run — and since
# its body ("#1: Approved...") won't match ACTION_PATTERN, it would
# trigger a "didn't understand" auto-reply, which would ALSO match on the
# run after that, forever. This header is the only thing that tells our
# own sent mail apart from Brian's.
BOT_HEADER = "X-StrokesEdge-Autoreply"


def send_reply(original_msg, body_text):
    subject = decode_subject(original_msg["Subject"]) or ""
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    reply = MIMEText(body_text)
    reply["Subject"] = subject
    reply["From"] = GMAIL_ADDRESS
    reply["To"] = GMAIL_ADDRESS
    reply[BOT_HEADER] = "1"
    if original_msg["Message-ID"]:
        reply["In-Reply-To"] = original_msg["Message-ID"]
        refs = original_msg.get("References", "")
        reply["References"] = f"{refs} {original_msg['Message-ID']}".strip()

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(reply)


def is_genuine_reply(msg):
    """Subject must actually start with 'Re:' (case-insensitive) — this is
    what distinguishes Brian's real reply from the original outbound alert
    itself, which also matches the SUBJECT_MARKER search but is never a
    reply. Threading headers are a bonus signal, not required, since some
    mobile mail clients drop In-Reply-To on reply. Explicitly excludes our
    own auto-replies (see BOT_HEADER above) — otherwise every confirmation
    or "didn't understand" reply this script sends would be picked back up
    as a new incoming reply on the next run."""
    if msg.get(BOT_HEADER):
        return False
    subject = decode_subject(msg["Subject"]) or ""
    return subject.strip().lower().startswith("re:") and SUBJECT_MARKER in subject.lower()


def process_message(imap, uid, msg):
    from_addr = parseaddr(msg.get("From", ""))[1]
    body = get_body_text(msg)
    commands = parse_command(body)
    pending_count = len(load_jsonl(PENDING_REVIEW))
    manual_count = len(load_jsonl(MANUAL_POST_QUEUE))

    if not commands:
        print(f"[uid {uid}] from {from_addr}: no recognizable command — replying for clarification.")
        send_reply(
            msg,
            f"Couldn't understand that as an approve/reject/posted command.\n\n"
            f"There are currently {pending_count} tweet(s) pending review and "
            f"{manual_count} in the manual post queue. "
            f"Reply with something like \"approve 1\", \"reject 2\", or \"posted 3\" "
            f"(or \"approve 1, 2\").",
        )
        imap.uid("STORE", str(uid), "+FLAGS", r"(\Seen)")
        return

    # "posted" targets manual_post_queue.jsonl; approve/reject target
    # pending_review.jsonl — two entirely different lists, so each group
    # is sorted and executed independently. Within each group, descending
    # index order so removing a higher-numbered item never shifts the
    # position of a lower-numbered one still queued up to be processed in
    # the same reply (both files are plain lists — indices are positional,
    # not stable IDs).
    approve_reject_cmds = sorted((c for c in commands if c[0] in ("approve", "reject")),
                                  key=lambda c: c[1], reverse=True)
    posted_cmds = sorted((c for c in commands if c[0] == "posted"), key=lambda c: c[1], reverse=True)

    results = []
    for action, idx in approve_reject_cmds:
        item = approve(idx) if action == "approve" else reject(idx)
        if item is None:
            results.append(f"#{idx}: could not find a pending-review item at that position (ignored).")
        else:
            verb = "Approved" if action == "approve" else "Rejected"
            preview = item["text"][:80] + ("..." if len(item["text"]) > 80 else "")
            results.append(f"#{idx}: {verb} — \"{preview}\"")

    for _, idx in posted_cmds:
        item = mark_posted(idx)
        if item is None:
            results.append(f"posted {idx}: could not find a manual-post-queue item at that position (ignored).")
        else:
            preview = item["text"][:80] + ("..." if len(item["text"]) > 80 else "")
            results.append(f"posted {idx}: Marked posted — \"{preview}\"")

    reply_body = "\n".join(results)
    print(f"[uid {uid}] from {from_addr}: {reply_body}")
    send_reply(msg, reply_body)
    imap.uid("STORE", str(uid), "+FLAGS", r"(\Seen)")


def run():
    if not GMAIL_APP_PASSWORD:
        print("[check_approvals] GMAIL_APP_PASSWORD not set — cannot check IMAP. Aborting.")
        return

    state = load_state()
    last_uid = state.get("last_uid", 0)

    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        imap.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    except imaplib.IMAP4.error as e:
        print(f"[check_approvals] IMAP login failed: {e}\n"
              f"If this is an AUTHENTICATIONFAILED error, IMAP access may not be enabled on this "
              f"Gmail account yet — check Gmail Settings > Forwarding and POP/IMAP > Enable IMAP.")
        return

    try:
        imap.select("INBOX")
        typ, data = imap.uid("SEARCH", None, "SUBJECT", f'"{SUBJECT_MARKER}"')
        if typ != "OK":
            print(f"[check_approvals] IMAP SEARCH failed: {typ} {data}")
            return

        all_uids = [int(u) for u in data[0].split()]
        new_uids = sorted(u for u in all_uids if u > last_uid)

        if not new_uids:
            print("[check_approvals] No new replies since last check.")
            return

        max_uid_seen = last_uid
        for uid in new_uids:
            max_uid_seen = max(max_uid_seen, uid)
            typ, msgdata = imap.uid("FETCH", str(uid), "(RFC822)")
            if typ != "OK" or not msgdata or msgdata[0] is None:
                continue
            msg = email.message_from_bytes(msgdata[0][1])

            if not is_genuine_reply(msg):
                # This is the original outbound alert itself (or an
                # unrelated match) — never a command to act on, but its
                # UID still counts toward the watermark so it's never
                # re-inspected.
                continue

            process_message(imap, uid, msg)

        state["last_uid"] = max_uid_seen
        save_state(state)
    finally:
        try:
            imap.logout()
        except Exception:
            pass


if __name__ == "__main__":
    run()
