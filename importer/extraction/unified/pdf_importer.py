import re
import json
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from pytesseract import Output
from typing import List, Dict, Any

# Camelot is optional — handle gracefully
try:
    import camelot
    _HAS_CAMELOT = True
except:
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
# Step 1: Detect if PDF has real text
# ----------------------------------------------------
def has_text_layer(path: str, min_words=30) -> bool:
    try:
        with pdfplumber.open(path) as pdf:
            text = ""
            for p in pdf.pages[:2]:
                t = p.extract_text() or ""
                text += " " + t
            return len(text.strip().split()) >= min_words
    except:
        return False


# ----------------------------------------------------
# Step 2: OCR PDF
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
# Step 3: Extract tables (Camelot → pdfplumber → OCR fallback)
# ----------------------------------------------------
def extract_tables(path: str):
    tables = []

    # Try Camelot lattice
    if _HAS_CAMELOT:
        try:
            tb = camelot.read_pdf(path, flavor="lattice", pages="all")
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
        except:
            pass

    # Try Camelot stream
    if _HAS_CAMELOT:
        try:
            tb = camelot.read_pdf(path, flavor="stream", pages="all")
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
        except:
            pass

    # Try pdfplumber
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
    except:
        pass

    return tables


# ----------------------------------------------------
# OCR Table Fallback: simple y-clustering
# ----------------------------------------------------
def ocr_table_from_bboxes(ocr_data):
    rows = {}
    n = len(ocr_data["text"])

    for i in range(n):
        word = ocr_data["text"][i]
        if not word.strip():
            continue
        y = ocr_data["top"][i]
        key = round(y / 12) * 12  # group by y
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

AMOUNT_REGEX = r"\b([0-9]{1,3}(?:[, ]\d{3})*(?:\.\d{1,2})?)\b"


def extract_invoice_no(text): 
    for rg in INVOICE_REGEX:
        m = re.search(rg, text, re.I)
        if m:
            return m.group(1)
    return None


def extract_dates(text):
    out = []
    for rg in DATE_REGEX:
        out.extend(re.findall(rg, text))
    return list(dict.fromkeys(out))


def extract_gstin(text):
    m = re.search(GSTIN_REGEX, text)
    return m.group(1) if m else None


def extract_total(text):
    nums = re.findall(AMOUNT_REGEX, text)
    cleaned = []
    for n in nums:
        try:
            cleaned.append(float(n.replace(",", "").replace(" ", "")))
        except:
            pass
    return max(cleaned) if cleaned else None


# ----------------------------------------------------
# MAIN IMPORTER CLASS (Drop-In Replacement)
# ----------------------------------------------------
class PDFImporter:

    def parse(self, path: str) -> Dict[str, Any]:

        result = {
            "file": path,
            "scanned": False,
            "raw_text": [],
            "tables": [],
            "structured": {
                "invoice_number": None,
                "dates": [],
                "gstin": None,
                "total_amount": None
            }
        }

        # A) Determine extraction method
        text_ok = has_text_layer(path)
        result["scanned"] = not text_ok

        # B) Extract text
        if text_ok:
            with pdfplumber.open(path) as pdf:
                for p in pdf.pages:
                    t = p.extract_text() or ""
                    result["raw_text"].append({
                        "page": p.page_number,
                        "text": clean_text(t)
                    })
        else:
            ocr_pages = ocr_pdf(path)
            for p in ocr_pages:
                result["raw_text"].append({"page": p["page"], "text": p["text"]})

        # Combined text
        combined = "\n".join(p["text"] for p in result["raw_text"])

        # C) Field extraction
        result["structured"]["invoice_number"] = extract_invoice_no(combined)
        result["structured"]["dates"] = extract_dates(combined)
        result["structured"]["gstin"] = extract_gstin(combined)
        result["structured"]["total_amount"] = extract_total(combined)

        # D) Table extraction
        tables = extract_tables(path)
        if tables:
            result["tables"] = tables
        else:
            # OCR fallback only if scanned
            if result["scanned"]:
                first_page = ocr_pdf(path)[0]
                grid = ocr_table_from_bboxes(first_page["ocr_data"])
                if grid and len(grid) > 1:
                    header = grid[0]
                    rows = grid[1:]
                    row_dicts = []
                    for row in rows:
                        row_dict = {}
                        for i, h in enumerate(header):
                            row_dict[h] = row[i] if i < len(row) else ""
                        row_dicts.append(row_dict)
                    result["tables"].append({
                        "columns": header,
                        "rows": row_dicts
                    })

        return result
