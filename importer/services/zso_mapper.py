from importer.models import ZSODemand

def map_extracted_to_zso(extracted):
    row = extracted.full_row_json or {}

    zso = ZSODemand.objects.create(
        extracted_record=extracted,

        po_or_forecast=(
            extracted.po_number
            or row.get("PO/POS number")
            or row.get("PO")
            or row.get("Forecast")
        ),

        customer_part=(
            extracted.customer_part
            or row.get("ERP Code")
            or row.get("Customer Material Number")
        ),

        open_qty=(
            extracted.open_qty
            or row.get("Open Sched Qty")
            or row.get("Remaining Quantity")
        ),

        doc_date=(
            extracted.need_date
            or extracted.promised_date
        ),

        ship_date=extracted.ship_date,

        sales_month=(
            extracted.ship_date.strftime("%Y-%m")
            if extracted.ship_date else None
        ),

        confidence_score=calculate_confidence(row)
    )

    return zso


def calculate_confidence(row):
    filled = sum(1 for v in row.values() if v)
    total = len(row)
    return round(filled / total, 2) if total else 0.0
