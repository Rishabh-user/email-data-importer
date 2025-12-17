"""
Django-integrated IMAP email reader.

Flow:
1. Fetch emails
2. Save each attachment as RawFile
3. Run process_file(rawfile)
4. (Optional) Extract invoice fields from body
"""

import os
import imaplib
import email
import datetime
from pathlib import Path
from bs4 import BeautifulSoup

from django.conf import settings
from importer.models import RawFile
from importer.services.process_file import process_file
from importer.extraction.unified import pdf_importer as pdf_parser
from config.logger import logger


IMAP_HOST = os.getenv("EMAIL_IMAP_HOST")
IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT", 993))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
MAILBOX = os.getenv("EMAIL_MAILBOX", "INBOX")
SEARCH_CRITERIA = os.getenv("EMAIL_SEARCH_CRITERIA", "(UNSEEN)")


# --------------------------
# Save attachment to media/
# --------------------------
def save_attachment_to_media(part):
    filename = part.get_filename()
    if not filename:
        filename = f"attachment_{datetime.datetime.now().timestamp()}.bin"

    filename = "".join(c for c in filename if c not in "/\\<>:|?*")

    raw_dir = Path(settings.MEDIA_ROOT) / "raw_files"
    raw_dir.mkdir(parents=True, exist_ok=True)

    file_path = raw_dir / filename

    with open(file_path, "wb") as f:
        f.write(part.get_payload(decode=True))

    logger.info(f"Saved email attachment → {file_path}")
    return file_path


# --------------------------
# Extract body text
# --------------------------
def extract_body_text(message):
    for part in message.walk():
        ctype = part.get_content_type()
        disp = str(part.get("Content-Disposition"))

        if ctype == "text/plain" and "attachment" not in disp:
            try:
                return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
            except:
                return part.get_payload(decode=True).decode("utf-8")

        if ctype == "text/html" and "attachment" not in disp:
            html = part.get_payload(decode=True).decode("utf-8")
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text("\n")

    return ""


# --------------------------
# MAIN EMAIL PROCESSOR
# --------------------------
def process_email_message(msg_bytes, uid=None):
    msg = email.message_from_bytes(msg_bytes)

    subject = msg.get("Subject")
    sender = msg.get("From")
    date = msg.get("Date")
    logger.info(f"Processing Email: {subject}")

    body_text = extract_body_text(msg)

    # 1️⃣ Process attachments
    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            file_path = save_attachment_to_media(part)

            # Create a RawFile entry in Django
            rf = RawFile.objects.create(raw_file=f"raw_files/{file_path.name}")

            # Run extraction
            process_file(rf)

    # 2️⃣ Optional: Extract invoice-like fields from body
    if body_text.strip():
        structured = {
            "invoice_number": pdf_parser.extract_invoice_no(body_text),
            "dates": pdf_parser.extract_dates(body_text),
            "gstin": pdf_parser.extract_gstin(body_text),
            "total_amount": pdf_parser.extract_total(body_text),
        }

        logger.info(f"Email body structured result: {structured}")


# --------------------------
# FETCH EMAILS FROM SERVER
# --------------------------
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
        msg_bytes = msg_data[0][1]

        process_email_message(msg_bytes, uid)

        # Mark seen + move to processed
        mail.store(uid, '+FLAGS', '\\Seen')

    mail.logout()
    logger.info("Email fetch complete.")
