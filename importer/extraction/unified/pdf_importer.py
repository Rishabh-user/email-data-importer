import re
import json
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from pytesseract import Output
from typing import List, Dict, Any

# Camelot is optional
try:
    import camelot
    _HAS_CAMELOT = True
except Exception:
    _HAS_CAMELOT = False


# ----------------------------------------------------
# Utility: Clean text block
# ----------------------------------------------------
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r", "\n")
    text = re.sub(r'\n\s*\n+', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


# ----------------------------------------------------
# Detect if PDF has real text
# ----------------------------------------------------
def has_text_layer(path: str, min_words=30) -> bool:
    try:
        with pdfplumber.open(path) as pdf:
            text = ""
            for p in pdf.pages[:2]:
                t = p.extract_text() or ""
                text += " " + t
            return len(text.strip().split()) >= min_words
    except Exception:
        return False


# ----------------------------------------------------
# OCR PDF
# ----------------------------------------------------
def ocr_pdf(path: str) -> List[Dict[str, Any]]:
    images = convert_from_path(path, dpi=300)
    pages = []

    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img)
        data = pytesseract.image_to_data(img, output_type=Output.DICT)

        pages.append({
            "page": i + 1,
            "text": clean_text(text),
            "ocr_data": data
        })

    return pages


# ----------------------------------------------------
# Extract tables (Camelot → pdfplumber → none)
# ----------------------------------------------------
def extract_tables(path: str):
    tables = []

    if _HAS_CAMELOT:
        for flavor in ("lattice", "stream"):
            try:
                tb = camelot.read_pdf(path, flavor=flavor, pages="all")
                for t in tb:
                    df = t.df
                    header = list(df.iloc[0])
                    rows = df.iloc[1:].values.tolist()
                    tables.append({
                        "columns": header,
                        "rows": [{header[i]: str(r[i]) for i in range(len(r))} for r in rows]
                    })
                if tables:
                    return tables
            except Exception:
                pass

    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                tb = page.extract_table()
                if tb:
                    header = tb[0]
                    rows = tb[1:]
                    tables.append({
                        "columns": header,
                        "rows": [{header[i]: r[i] for i in range(len(r))} for r in rows]
                    })
    except Exception:
        pass

    return tables


# ----------------------------------------------------
# OCR table fallback (not used for PO line items)
# ----------------------------------------------------
def ocr_table_from_bboxes(ocr_data):
    rows = {}
    n = len(ocr_data["text"])

    for i in range(n):
        word = ocr_data["text"][i]
        if not word.strip():
            continue
        y = ocr_data["top"][i]
        key = round(y / 12) * 12
        rows.setdefault(key, []).append((ocr_data["left"][i], word))

    table = []
    for key in sorted(rows.keys()):
        sorted_row = sorted(rows[key], key=lambda x: x[0])
        table.append([w for (_, w) in sorted_row])

    return table


# ----------------------------------------------------
# Field Extraction Rules
# ----------------------------------------------------
INVOICE_REGEX = [
    r"Invoice\s*No[:\s]*([A-Za-z0-9\-\/]+)",
    r"PO\s*#[:\s]*([A-Za-z0-9\-\/]+)",
    r"Order\s*No[:\s]*([A-Za-z0-9\-\/]+)",
]

DATE_REGEX = [
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
    r"\b([A-Za-z]{3,}\s+\d{1,2},\s*\d{4})\b",
]

GSTIN_REGEX = r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9])\b"
AMOUNT_REGEX = r"\$\s*([0-9,]+\.\d{2})"


# ----------------------------------------------------
# LINE ITEM REGEX (CRITICAL FIX)
# ----------------------------------------------------
LINE_ITEM_REGEX = re.compile(
    r'(?P<item>\d{3})\s+'
    r'(?P<qty>\d+)\s+'
    r'(?P<uom>[A-Z]{2})\s+'
    r'(?P<desc>.+?)\s+\$\s*(?P<price>\d+\.\d+)',
    re.MULTILINE
)


def extract_line_items(text: str):
    rows = []
    for m in LINE_ITEM_REGEX.finditer(text):
        rows.append({
            "ITEM_NO": m.group("item"),
            "QUANTITY": int(m.group("qty")),
            "UOM": m.group("uom"),
            "DESCRIPTION": m.group("desc").strip(),
            "UNIT_PRICE": float(m.group("price")),
        })
    return rows


# ----------------------------------------------------
# MAIN IMPORTER
# ----------------------------------------------------
class PDFImporter:

    def parse(self, path: str) -> List[Dict[str, Any]]:
        """
        IMPORTANT:
        Returns LIST OF ROWS (what process_file.py expects)
        """

        raw_text_blocks = []

        # Detect text layer
        text_ok = has_text_layer(path)

        # Extract text
        if text_ok:
            with pdfplumber.open(path) as pdf:
                for p in pdf.pages:
                    t = p.extract_text() or ""
                    raw_text_blocks.append(clean_text(t))
        else:
            ocr_pages = ocr_pdf(path)
            for p in ocr_pages:
                raw_text_blocks.append(p["text"])

        # Combine all text
        combined_text = "\n".join(raw_text_blocks)

        # 🔥 KEY FIX: extract line items
        line_items = extract_line_items(combined_text)

        # NEVER return empty None
        return line_items
