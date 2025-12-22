from django.utils.dateparse import parse_date
from importer.models import ZSODemand

def _to_date(value):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        # already a date/datetime
        return value
    try:
        return parse_date(str(value))
    except Exception:
        return None


def calculate_confidence(row):
    """
    Basic heuristic: give higher score when key fields are present.
    You can replace this with a more advanced model later.
    """
    keys = [
        "PO", "PO/POS number", "Forecast", "ERP Code", "Customer Material Number",
        "Open Sched Qty", "Remaining Quantity", "Customer Name", "KAS Name"
    ]
    present = 0
    for k in keys:
        if row.get(k) not in (None, "", []):
            present += 1
    return round(present / len(keys), 2) if keys else 0.0


def map_extracted_to_zso(extracted):
    """
    Map an ExtractedRecord instance to a ZSODemand DB row.
    Accepts either values already in ExtractedRecord or the raw full_row_json.
    """
    row = extracted.full_row_json or {}

    # helpers to read with multiple possible key forms
    def g(*names):
        for n in names:
            if row.get(n) not in (None, ""):
                return row.get(n)
        return None

    po_or_forecast = (
        extracted.po_number
        or g("PO/POS number", "PO", "po_number", "Forecast", "Forecast#")
    )

    customer_part = (
        extracted.customer_part
        or g("ERP Code", "Customer Material Number", "customer_part")
    )

    open_qty = (
        extracted.open_qty
        or g("Open Sched Qty", "Remaining Quantity", "open_qty", "Balance Due")
    )

    doc_date = _to_date(g("Doc date", "doc_date", "need_date", "promised_date"))
    ship_date = _to_date(g("Ship date", "ship_date"))

    sales_month = None
    if ship_date:
        try:
            sales_month = ship_date.strftime("%Y-%m")
        except Exception:
            sales_month = None

    # zso = ZSODemand.objects.create(
    #     raw_file=extracted.raw_file,
    #     extracted_record=extracted,

    #     # requested columns
    #     kas_name=g("KAS Name", "kas_name"),
    #     customer_name=g("Customer Name", "customer_name"),
    #     site_location=g("Site location", "Site Location", "site_location"),
    #     country=g("Country", "country"),
    #     incoterms=g("Incoterms", "Incoterm", "Line Incoterm"),
    #     sales_type=g("Direct Sales / WH Movement", "sales_type", "Direct Sales"),
    #     po_or_forecast=po_or_forecast,
    #     category=g("Category", "category"),
    #     sub_category=g("Sub Category", "Sub Category", "sub_category"),

    #     customer_part=customer_part,
    #     maini_part=g("Maini part #", "Maini part", "maini_part"),

    #     open_qty=_safe_float(open_qty),
    #     unit_price=_safe_float(g("Unit Price", "unit_price")),
    #     currency=g("Currency", "currency"),
    #     unit_price_inr=_safe_float(g("Unit Price in INR", "unit_price_inr")),
    #     total_inr=_safe_float(g("Total in INR", "total_inr")),

    #     doc_date=doc_date,
    #     ship_date=ship_date,
    #     sales_month=sales_month,

    #     confidence_score=calculate_confidence(row)
    # )

    # return zso


def _safe_float(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except Exception:
        return None