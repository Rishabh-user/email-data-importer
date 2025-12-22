import json
import http.client
from importer.models import ExtractedRecord, ZSODemand


API_HOST = "zso-api-production.up.railway.app"
API_ENDPOINT = "/api/zso/get_report"



def process_extracted_records():
    """
    Process all unprocessed ExtractedRecord rows
    """
    records = ExtractedRecord.objects.filter(is_processed=False)

    if not records.exists():
        return {
            "processed": 0,
            "message": "No unprocessed records found"
        }

    conn = http.client.HTTPSConnection(API_HOST)
    headers = {
        "Content-Type": "application/json"
    }

    processed = 0
    errors = []

    for record in records:
        if not record.full_row_json:
            continue

        payload = json.dumps([record.full_row_json])
        print(payload)

        try:
            conn.request("POST", API_ENDPOINT, payload, headers)
            res = conn.getresponse()
            data = res.read().decode("utf-8")

            if res.status != 200:
                errors.append({"id": record.id, "error": data})
                continue

            api_response = json.loads(data)

            # 🔹 Save API output
            ZSODemand.objects.create(
                kas_name="Admin",
                customer_name=api_response.get("customer_name"),
                site_location=api_response.get("site_location"),
                country=api_response.get("country"),
                sales_type=api_response.get("sales_type"),
                po_or_forecast=api_response.get("po_or_forecast"),
                category=api_response.get("category"),
                sub_category=api_response.get("sub_category"),
                customer_part=api_response.get("customer_part_number"),
                maini_part=api_response.get("maini_part_number"),
                open_qty=api_response.get("open_quantity"),
                unit_price=api_response.get("unit_price"),
                currency=api_response.get("currency"),
                unit_price_inr=api_response.get("unit_price_in_inr"),
                doc_date=api_response.get("document_date"),
                ship_date=api_response.get("ship_date"),
                sales_month=api_response.get("sales_month"),
                raw_payload=api_response,
            )

            # 🔹 Mark processed
            record.is_processed = True
            record.save(update_fields=["is_processed"])

            processed += 1

        except Exception as exc:
            errors.append({"id": record.id, "error": str(exc)})

    return {
        "processed": processed,
        "errors": errors,
    }
