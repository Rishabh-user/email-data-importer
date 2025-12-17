import json
import os
from pathlib import Path

from django.utils.dateparse import parse_date

from importer.models import (
    RawFile,
    ExtractedRecord,
    ExtractionLog,
)
from importer.extraction.router import UnifiedImporter


# -----------------------------------------------------------
# HELPER: Save extracted JSON to file
# -----------------------------------------------------------

def save_extracted_json_file(file_id, extracted_rows):
    """
    Saves extracted rows to media/extracted_json/<id>.json
    """
    output_dir = Path("media/extracted_json")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{file_id}.json"

    with open(output_path, "w") as f:
        json.dump(extracted_rows, f, indent=2)


# -----------------------------------------------------------
# HELPER: Auto-detect customer type from extracted JSON
# -----------------------------------------------------------

def detect_customer_type(data):
    """
    Simple heuristic to detect customer format.
    """
    if isinstance(data, dict):
        data = [data]

    if not data or not isinstance(data, list):
        return None

    first_row = data[0]

    if "Blanket Nbr" in first_row or "Sched Rel" in first_row:
        return "Customer P Series"

    if "ERP Code" in first_row:
        return "Customer S1"

    if "Customer Material Number" in first_row:
        return "Customer S2"

    if "Demand/Due Date" in first_row:
        return "Forecast W1"

    if "ECL" in first_row and "Item Number" in first_row:
        return "Customer W1"

    return "Unknown"


# -----------------------------------------------------------
# MAIN PROCESSOR
# -----------------------------------------------------------

def process_file(raw_file: RawFile):
    """
    Core extraction pipeline:
    - Runs UnifiedImporter
    - Saves raw text & JSON
    - Stores extracted rows
    - Writes extraction logs
    """

    print("\n-------------------------")
    print("PROCESS_FILE STARTED")
    print("RAW FILE PATH:", raw_file.raw_file.path)
    print("FILE EXISTS?:", os.path.exists(raw_file.raw_file.path))
    print("-------------------------\n")

    # ---- LOG: Start ----
    ExtractionLog.objects.create(
        raw_file=raw_file,
        level="INFO",
        message="Extraction started",
        context={"file_path": raw_file.raw_file.path},
    )

    try:
        importer = UnifiedImporter()

        # --------------------
        # RUN EXTRACTION ENGINE
        # --------------------
        extracted_output = importer.parse(raw_file.raw_file.path)

        if not extracted_output:
            ExtractionLog.objects.create(
                raw_file=raw_file,
                level="ERROR",
                message="Extractor returned empty output",
                context={"stage": "parse"},
            )
            return {"status": "error", "message": "Empty extraction output"}

        raw_text = extracted_output.get("raw_text")
        raw_json = extracted_output.get("raw_json")
        extracted_rows = extracted_output.get("rows", [])

        # --------------------
        # SAVE RAW DATA
        # --------------------
        raw_file.raw_text = raw_text
        raw_file.raw_json = raw_json
        raw_file.customer_detected = detect_customer_type(extracted_rows)
        raw_file.save()

        # --------------------
        # NO ROWS CASE
        # --------------------
        if not extracted_rows:
            ExtractionLog.objects.create(
                raw_file=raw_file,
                level="WARNING",
                message="No rows extracted",
                context={"stage": "row_extraction"},
            )

            save_extracted_json_file(raw_file.id, extracted_rows)

            return {
                "status": "warning",
                "message": "No rows extracted",
                "rows_saved": 0,
            }

        # --------------------
        # SAVE ROWS
        # --------------------
        rows_saved = 0

        def to_date(value):
            if not value:
                return None
            try:
                return parse_date(str(value))
            except Exception:
                return None

        for row in extracted_rows:
            ExtractedRecord.objects.create(
                raw_file=raw_file,
                po_number=row.get("po_number") or row.get("PO Number") or row.get("PO"),
                customer_part=row.get("customer_part")
                or row.get("Part Nbr")
                or row.get("Item Number"),
                description=row.get("description") or row.get("Description"),
                quantity=row.get("quantity")
                or row.get("Qty Ordered")
                or row.get("Firm Qty"),
                open_qty=row.get("open_qty")
                or row.get("Open Sched Qty")
                or row.get("Balance Due"),
                need_date=to_date(row.get("need_date")),
                promised_date=to_date(row.get("promised_date")),
                ship_date=to_date(row.get("ship_date")),
                full_row_json=row,
            )
            rows_saved += 1

        # --------------------
        # SAVE JSON BACKUP
        # --------------------
        save_extracted_json_file(raw_file.id, extracted_rows)

        # ---- LOG: Success ----
        ExtractionLog.objects.create(
            raw_file=raw_file,
            level="INFO",
            message="Extraction completed successfully",
            context={"rows_saved": rows_saved},
        )

        return {
            "status": "success",
            "rows_saved": rows_saved,
        }

    except Exception as e:
        # ---- LOG: Exception ----
        ExtractionLog.objects.create(
            raw_file=raw_file,
            level="ERROR",
            message=str(e),
            context={"stage": "exception"},
        )

        return {
            "status": "error",
            "message": str(e),
        }
