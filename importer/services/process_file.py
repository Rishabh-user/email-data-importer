import json
from pathlib import Path
from django.utils.dateparse import parse_date
from django.db import transaction

from importer.models import (
    RawFile,
    ExtractedRecord,
    ExtractionLog,
)
from importer.extraction.router import UnifiedImporter
from importer.services.zso_mapper import map_extracted_to_zso


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _json_safe(value):
    try:
        json.dumps(value)
        return value
    except Exception:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)


def make_json_safe(obj):
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    return _json_safe(obj)


def save_extracted_json_file(file_id, extracted_payload):
    """
    Save full extracted payload (dict) for audit/debug.
    """
    output_dir = Path("media/extracted_json")
    output_dir.mkdir(parents=True, exist_ok=True)

    path = output_dir / f"{file_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(make_json_safe(extracted_payload), f, indent=2)


# ---------------------------------------------------------
# MAIN PROCESSOR
# ---------------------------------------------------------

def process_file(raw_file: RawFile):
    """
    Main orchestration:
    RawFile → ExtractedRecord → ZSODemand
    """

    ExtractionLog.objects.create(
        raw_file=raw_file,
        level="INFO",
        message="Extraction started",
    )

    try:
        importer = UnifiedImporter()

        # ✅ UnifiedImporter returns a DICT
        extracted_payload = importer.parse(raw_file.raw_file.path) or {}

        # ---- Validate payload structure ----
        if not isinstance(extracted_payload, dict):
            raise ValueError("Extractor did not return a dict")

        extracted_rows = extracted_payload.get("rows", [])

        if not isinstance(extracted_rows, list):
            raise ValueError("Extracted rows is not a list")

        # ---- Save RAW JSON ALWAYS ----
        raw_file.raw_json = make_json_safe(extracted_payload)
        raw_file.save(update_fields=["raw_json"])

        save_extracted_json_file(raw_file.id, extracted_payload)

        if not extracted_rows:
            ExtractionLog.objects.create(
                raw_file=raw_file,
                level="WARNING",
                message="No structured rows found, raw JSON saved",
            )
            return

        # ---- CLEAN OLD DATA (re-upload safe) ----
        ExtractedRecord.objects.filter(raw_file=raw_file).delete()

        rows_saved = 0
        zso_created = 0

        # ---- PROCESS ROWS ----
        for idx, row in enumerate(extracted_rows, start=1):
            if not isinstance(row, dict):
                ExtractionLog.objects.create(
                    raw_file=raw_file,
                    level="ERROR",
                    message="Invalid row format (not a dict)",
                    context={
                        "row": idx,
                        "row_data": row,
                    },
                )
                continue

            try:
                row = make_json_safe(row)

                with transaction.atomic():
                    extracted = ExtractedRecord.objects.create(
                        raw_file=raw_file,

                        po_number=(
                            row.get("PO")
                            or row.get("PO Number")
                            or row.get("PURCHASE_ORDER")
                        ),

                        customer_part=(
                            row.get("ERP Code")
                            or row.get("Customer Material Number")
                            or row.get("ITEM_NO")
                        ),

                        description=(
                            row.get("Description")
                            or row.get("DESCRIPTION")
                        ),

                        quantity=(
                            row.get("Qty Ordered")
                            or row.get("QUANTITY")
                        ),

                        open_qty=(
                            row.get("Open Sched Qty")
                            or row.get("Balance Due")
                            or row.get("QUANTITY")
                        ),

                        need_date=(
                            parse_date(str(row.get("Need Date")))
                            if row.get("Need Date") else None
                        ),

                        promised_date=(
                            parse_date(str(row.get("Promised Date")))
                            if row.get("Promised Date") else None
                        ),

                        ship_date=(
                            parse_date(str(row.get("Ship Date")))
                            if row.get("Ship Date") else None
                        ),

                        full_row_json=row,
                    )

                    rows_saved += 1

                    # ---- ZSO MAPPING ----
                    try:
                        created = map_extracted_to_zso(extracted)
                        if created:
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
                        "row_data": row,
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
