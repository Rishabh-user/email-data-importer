"""
Django-integrated IMAP email reader.

Flow:
1. Fetch unread emails
2. Save each attachment to media/raw_files
3. Save email body to media/raw_files
4. Raw folder processor picks files → extraction → ZSO
"""

import os
import imaplib
import email
import datetime
from pathlib import Path
from bs4 import BeautifulSoup

from django.conf import settings

from importer.extraction.unified import pdf_importer as pdf_parser
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
# Extract email body text
# --------------------------
def extract_body_text(message) -> str:
    for part in message.walk():
        ctype = part.get_content_type()
        disp = str(part.get("Content-Disposition") or "")

        if ctype == "text/plain" and "attachment" not in disp:
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode(part.get_content_charset() or "utf-8", errors="ignore")

        if ctype == "text/html" and "attachment" not in disp:
            payload = part.get_payload(decode=True)
            if payload:
                soup = BeautifulSoup(payload.decode("utf-8", errors="ignore"), "html.parser")
                return soup.get_text(" ")

    return ""


# --------------------------
# Detect PO table in body
# --------------------------
def looks_like_po_table(text: str) -> bool:
    keywords = [
        "PO Number",
        "PO Line",
        "Qty Ordered",
        "Unit of Measure",
        "Vendor Due Date",
    ]
    return sum(1 for k in keywords if k.lower() in text.lower()) >= 3


# --------------------------
# Save email body to raw_files
# --------------------------
def save_email_body_to_media(body_text: str, subject: str, uid):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_subject = _safe_filename(subject or "email")

    filename = f"email_body_{safe_subject}_{uid}_{ts}.txt"

    raw_dir = Path(settings.MEDIA_ROOT) / "raw_files"
    raw_dir.mkdir(parents=True, exist_ok=True)

    path = raw_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        f.write(body_text)

    logger.info(f"Saved email body → {path}")
    return path


# ------------------------------------------------------------------
# MAIN EMAIL PROCESSOR
# ------------------------------------------------------------------

def process_email_message(msg_bytes, uid=None):
    msg = email.message_from_bytes(msg_bytes)

    subject = msg.get("Subject", "no_subject")
    logger.info(f"Processing Email: {subject}")

    body_text = extract_body_text(msg)

    # 1️⃣ Save attachments ONLY
    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            save_attachment_to_media(part)

    # 2️⃣ Save PO-table email body as raw file (same as attachment)
    if body_text.strip() and looks_like_po_table(body_text):
        save_email_body_to_media(body_text, subject, uid)

    # 3️⃣ Optional: invoice-like free text (LOG ONLY)
    elif body_text.strip():
        structured = {
            "invoice_number": pdf_parser.extract_invoice_no(body_text),
            "dates": pdf_parser.extract_dates(body_text),
            "gstin": pdf_parser.extract_gstin(body_text),
            "total_amount": pdf_parser.extract_total(body_text),
        }
        logger.info(f"Email body structured result: {structured}")


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
