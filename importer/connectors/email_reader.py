"""
Django-integrated IMAP email reader (PURE INGESTION).

Flow:
1. Fetch unread emails
2. Save each attachment to media/raw_files
3. Save email body to media/raw_files (as Excel)
4. Raw folder processor handles extraction → ZSO
"""

import os
import imaplib
import email
import datetime
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd

from django.conf import settings
from config.logger import logger


# ------------------------------------------------------------------
# IMAP CONFIG
# ------------------------------------------------------------------

IMAP_HOST = os.getenv("EMAIL_IMAP_HOST")
IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT", 993))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
MAILBOX = os.getenv("EMAIL_MAILBOX", "INBOX")
SEARCH_CRITERIA = os.getenv("EMAIL_SEARCH_CRITERIA", "(UNSEEN)")


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def _safe_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("_", "-", "."))[:80]


# --------------------------
# Save attachment to raw_files
# --------------------------
def save_attachment_to_media(part):
    filename = part.get_filename() or f"attachment_{datetime.datetime.now().timestamp()}.bin"
    filename = _safe_filename(filename)

    raw_dir = Path(settings.MEDIA_ROOT) / "raw_files"
    raw_dir.mkdir(parents=True, exist_ok=True)

    file_path = raw_dir / filename
    with open(file_path, "wb") as f:
        f.write(part.get_payload(decode=True))

    logger.info(f"Saved email attachment → {file_path}")
    return file_path


# --------------------------
# Extract email body text (plain + html)
# --------------------------
def extract_body_text(message) -> str:
    plain_text = None
    html_text = None

    for part in message.walk():
        ctype = part.get_content_type()
        disp = str(part.get("Content-Disposition") or "")

        if "attachment" in disp:
            continue

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        if ctype == "text/plain" and not plain_text:
            plain_text = payload.decode(
                part.get_content_charset() or "utf-8",
                errors="ignore",
            )

        elif ctype == "text/html" and not html_text:
            soup = BeautifulSoup(
                payload.decode("utf-8", errors="ignore"),
                "html.parser",
            )
            html_text = soup.get_text(" ")

    # ✅ Prefer plain text, fallback to HTML
    return (plain_text or html_text or "").strip()


# --------------------------
# Save email body to Excel file
# --------------------------
def save_email_body_to_excel(body_text: str, subject: str, uid):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_subject = _safe_filename(subject or "email")
    filename = f"email_body_{safe_subject}_{uid}_{ts}.xlsx"

    raw_dir = Path(settings.MEDIA_ROOT) / "raw_files"
    raw_dir.mkdir(parents=True, exist_ok=True)
    file_path = raw_dir / filename

    # Convert body text → rows
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    df = pd.DataFrame(lines, columns=["email_text"])

    df.to_excel(file_path, index=False)
    logger.info(f"Saved email body as Excel → {file_path}")

    return file_path


# ------------------------------------------------------------------
# MAIN EMAIL PROCESSOR
# ------------------------------------------------------------------

def process_email_message(msg_bytes, uid=None):
    msg = email.message_from_bytes(msg_bytes)
    subject = msg.get("Subject", "no_subject")

    logger.info(f"Processing Email: {subject}")

    # 1️⃣ Save attachments
    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            save_attachment_to_media(part)

    # 2️⃣ Save FULL email body as Excel (always)
    body_text = extract_body_text(msg)
    if body_text:
        save_email_body_to_excel(body_text, subject, uid)
    else:
        logger.info("Email has no body content")


# ------------------------------------------------------------------
# FETCH EMAILS FROM SERVER
# ------------------------------------------------------------------

def fetch_and_process_all():
    logger.info("Connecting to Email Server...")

    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(EMAIL_USER, EMAIL_PASSWORD)
    mail.select(MAILBOX)

    typ, data = mail.search(None, SEARCH_CRITERIA)
    if typ != "OK":
        logger.error("Email search failed")
        return

    uids = data[0].split()
    logger.info(f"Found {len(uids)} unread emails.")

    for uid in uids:
        typ, msg_data = mail.fetch(uid, "(RFC822)")
        if typ != "OK":
            logger.error(f"Failed to fetch email {uid}")
            continue

        msg_bytes = msg_data[0][1]
        process_email_message(msg_bytes, uid)

        # Mark email as seen
        mail.store(uid, "+FLAGS", "\\Seen")

    mail.logout()
    logger.info("Email fetch complete.")
