import json
from pathlib import Path
from django.utils.dateparse import parse_date

from importer.models import (
    RawFile,
    ExtractedRecord,
    ExtractionLog,
)
from importer.extraction.router import UnifiedImporter
from importer.services.zso_mapper import map_extracted_to_zso


# ---------------------------------------------------------
# JSON SAFETY HELPERS
# ---------------------------------------------------------

def _json_safe(value):
    """
    Convert non-JSON-serializable values (Timestamp, date, etc.)
    """
    try:
        json.dumps(value)
        return value
    except Exception:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)


def make_json_safe(obj):
    """
    Recursively make dict/list JSON serializable
    """
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    return _json_safe(obj)


# ---------------------------------------------------------
# ZSO ENRICHMENT
# ---------------------------------------------------------

def enrich_row_for_zso(row: dict) -> dict:
    """
    Add normalized ZSO-friendly keys into the row.
    Does NOT remove existing keys.
    """
    enriched = dict(row)

    for target_key, possible_keys in ZSO_FIELD_RULES.items():
        for k in possible_keys:
            if row.get(k) not in (None, "", []):
                enriched[target_key] = row[k]
                break

    return enriched


# ---------------------------------------------------------
# SAVE EXTRACTED JSON FILE
# ---------------------------------------------------------

def save_extracted_json_file(file_id, extracted_rows):
    """
    Save extracted rows to media/extracted_json/<raw_file_id>.json
    """
    output_dir = Path("media/extracted_json")
    output_dir.mkdir(parents=True, exist_ok=True)

    path = output_dir / f"{file_id}.json"
    with open(path, "w") as f:
        json.dump(make_json_safe(extracted_rows), f, indent=2)


# ---------------------------------------------------------
# MAIN PROCESSOR
# ---------------------------------------------------------

def process_file(raw_file: RawFile):
    """
    Pipeline:
    RawFile → ExtractedRecord → ZSODemand
    """

    # ---- LOG START ----
    ExtractionLog.objects.create(
        raw_file=raw_file,
        level="INFO",
        message="Extraction started",
    )

    try:
        importer = UnifiedImporter()
        extracted_output = importer.parse(raw_file.raw_file.path)

        if not extracted_output:
            raise ValueError("Extractor returned empty output")

        # -------------------------------------------------
        # RAW DATA STORAGE
        # -------------------------------------------------
        raw_text = extracted_output.get("raw_text")
        raw_json = make_json_safe(extracted_output)

        # -------------------------------------------------
        # TABLE → ROW NORMALIZATION (CRITICAL FIX)
        # -------------------------------------------------
        tables = extracted_output.get("tables", [])
        extracted_rows = []

        for table in tables:
            extracted_rows.extend(table.get("rows", []))

        # ---- SAVE RAW EXTRACTION ----
        raw_file.raw_text = raw_text
        raw_file.raw_json = raw_json
        raw_file.save(update_fields=["raw_text", "raw_json"])

        # ---- SAFETY CHECK ----
        if not extracted_rows:
            ExtractionLog.objects.create(
                raw_file=raw_file,
                level="ERROR",
                message="No rows extracted",
            )
            return

        save_extracted_json_file(raw_file.id, extracted_rows)

        # ---- CLEAN OLD DATA (re-upload safe) ----
        ExtractedRecord.objects.filter(raw_file=raw_file).delete()

        rows_saved = 0
        zso_created = 0

        # -------------------------------------------------
        # ROW PROCESSING
        # -------------------------------------------------
        for idx, row in enumerate(extracted_rows, start=1):
            try:
                row = enrich_row_for_zso(make_json_safe(row))

                extracted = ExtractedRecord.objects.create(
                    raw_file=raw_file,

                    po_number=row.get("po_or_forecast") or row.get("PO"),
                    customer_part=row.get("customer_part"),
                    description=row.get("description") or row.get("Description"),

                    quantity=row.get("quantity") or row.get("Qty Ordered"),
                    open_qty=row.get("open_qty"),

                    need_date=parse_date(str(row.get("need_date"))) if row.get("need_date") else None,
                    promised_date=parse_date(str(row.get("promised_date"))) if row.get("promised_date") else None,
                    ship_date=parse_date(str(row.get("ship_date"))) if row.get("ship_date") else None,

                    full_row_json=row,
                )

                rows_saved += 1

                # ---- ZSO MAPPING ----
                try:
                    map_extracted_to_zso(extracted)
                    zso_created += 1
                except Exception as zso_err:
                    ExtractionLog.objects.create(
                        raw_file=raw_file,
                        level="ERROR",
                        message="ZSO mapping failed",
                        context={
                            "row": idx,
                            "error": str(zso_err),
                        },
                    )

            except Exception as row_err:
                ExtractionLog.objects.create(
                    raw_file=raw_file,
                    level="ERROR",
                    message="Row processing failed",
                    context={
                        "row": idx,
                        "error": str(row_err),
                    },
                )

        # ---- FINAL SUCCESS LOG ----
        ExtractionLog.objects.create(
            raw_file=raw_file,
            level="SUCCESS",
            message="Extraction completed",
            context={
                "rows_saved": rows_saved,
                "zso_created": zso_created,
            },
        )

    except Exception as e:
        ExtractionLog.objects.create(
            raw_file=raw_file,
            level="ERROR",
            message="Extraction failed",
            context={"error": str(e)},
        )
