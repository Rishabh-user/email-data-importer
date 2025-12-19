from django.contrib import admin
from django.db import transaction
from importer.models import RawFile, ExtractedRecord, ExtractionLog, ZSODemand
from importer.services.process_file import process_file
from django.contrib.auth.models import Group
from django.contrib.admin import AdminSite
import json
import http.client
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
import os
from datetime import datetime
from django.utils.dateparse import parse_date
import csv
from django.http import HttpResponse
from django.contrib.admin import DateFieldListFilter
from django.contrib import admin
from django.db.models import Exists, OuterRef



ZSO_API_TOKEN = os.getenv("ZSO_API_TOKEN")
admin.site.site_header = "JKMGAL Demand Portal"
admin.site.site_title = "JKMGAL Demand Portal"
admin.site.index_title = "JKMGAL Demand Portal"

EXPECTED_FIELDS = [
    "customer_name",
    "site_location",
    "country",
    "sales_type",
    "incoterms",
    "po_or_forecast",
    "category",
    "sub_category",
    "customer_part_number",
    "maini_part_number",
    "open_quantity",
    "unit_price",
    "currency",
    "unit_price_in_inr",
    "total_in_inr",
    "document_date",
    "ship_date",
    "sales_month",
]


# 🔒 Hide Admin Interface menu (keep theme active)
try:
    from admin_interface.models import Theme
    admin.site.unregister(Theme)
except Exception:
    pass

# Remove Groups from admin menu
try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


class NoAddAdminMixin:
    def has_add_permission(self, request):
        return False
        

@admin.register(RawFile)
class RawFileAdmin(admin.ModelAdmin):
    fields = ("raw_file",)
    list_display = ("file_name", "file_type", "uploaded_at")
    change_form_template = "admin/importer/rawfile/change_form.html"

    def save_model(self, request, obj, form, change):
        """
        IMPORTANT:
        - Admin runs inside atomic()
        - We MUST defer extraction until commit
        """
        super().save_model(request, obj, form, change)

        # 🔐 SAFELY run extraction AFTER commit
        transaction.on_commit(lambda: process_file(obj))


@admin.register(ExtractedRecord)
class ExtractedRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "po_number",
        "customer_part",
        "quantity",
        "open_qty",
        "raw_file",
        "created_at",
        "is_processed",
    )
    list_filter = ("raw_file", "is_processed")
    search_fields = ("po_number", "customer_part")
    change_list_template = "admin/importer/extractedrecord/change_list.html"
    actions = ["mark_as_unprocessed"]

    def mark_as_unprocessed(self, request, queryset):
        updated = queryset.update(is_processed=False)
        messages.success(
            request,
            f"{updated} records marked as unprocessed."
        )

    mark_as_unprocessed.short_description = "🔁 Mark selected records as UNPROCESSED"

    # 🔗 Register admin URL
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "process/",
                self.admin_site.admin_view(self.process_records),
                name="process_extracted_records",
            )
        ]
        return custom_urls + urls
    
    def calculate_confidence_score(self, row: dict) -> float:
        filled = sum(
            1 for field in EXPECTED_FIELDS
            if row.get(field) not in (None, "", [], {})
        )
        return round((filled / len(EXPECTED_FIELDS)) * 100, 2)

   
    def process_records(self, request):
        
        records = ExtractedRecord.objects.filter(
            is_processed=False
        ).annotate(
            has_zso=Exists(
                ZSODemand.objects.filter(extracted_record=OuterRef("pk"))
            )
        ).filter(has_zso=False)

        if not records.exists():
            messages.warning(request, "No unprocessed records found.")
            return redirect("..")

        conn = http.client.HTTPSConnection("stageanalyse.skillmotion.ai")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ZSO_API_TOKEN}",
        }

        print(ZSO_API_TOKEN)

        success = 0
        failed = 0

        for record in records:
            if not record.full_row_json:
                failed += 1
                continue

            payload = json.dumps([record.full_row_json])

            try:
                conn.request(
                    "POST",
                    "/api/zso/get_report",
                    payload,
                    headers,
                )

                res = conn.getresponse()
                
                data = json.loads(res.read().decode())
                print(data)

                report = data.get("report", [])
                if not report:
                    raise ValueError("Empty report")

                row = report[0]

            except Exception as e:
                failed += 1
                continue

            # ✅ SAVE ATOMIC PER RECORD
            with transaction.atomic():
                confidence_score = self.calculate_confidence_score(row)
                ZSODemand.objects.create(
                    raw_file=record.raw_file,
                    extracted_record=record,

                    kas_name=request.user.username,
                    customer_name=row.get("customer_name", ""),
                    site_location=row.get("site_location", ""),
                    country=row.get("country", ""),

                    sales_type=row.get("sales_type", ""),
                    incoterms=row.get("incoterms", ""),

                    po_or_forecast=row.get("po_or_forecast", ""),
                    category=row.get("category", ""),
                    sub_category=row.get("sub_category", ""),

                    customer_part=row.get("customer_part_number", ""),
                    maini_part=row.get("maini_part_number", ""),

                    open_qty=row.get("open_quantity"),
                    unit_price=row.get("unit_price"),
                    currency=row.get("currency", "USD"),
                    unit_price_inr=row.get("unit_price_in_inr"),
                    total_inr=row.get("total_in_inr"),

                    doc_date=parse_any_date(row.get("document_date")),
                    ship_date=parse_any_date(row.get("ship_date")),

                    sales_month=row.get("sales_month", ""),
                    confidence_score=confidence_score,
                )

                record.is_processed = True
                record.save(update_fields=["is_processed"])

                success += 1

        messages.success(
            request,
            f"Processed: {success} | Failed: {failed}"
        )

        return redirect("..")

@admin.register(ExtractionLog)
class ExtractionLogAdmin(admin.ModelAdmin):
    list_display = ("raw_file", "level", "message", "created_at")
    list_filter = ("level",)
    search_fields = ("message",)


@admin.register(ZSODemand)
class ZSODemandAdmin(admin.ModelAdmin):
    list_display = (
        "po_or_forecast",
        "customer_part",
        "open_qty",
        "sales_month",
        "confidence_score",
    )

    # ✅ BUILT-IN DATE RANGE FILTER
    list_filter = (
        ("ship_date", DateFieldListFilter),
        "sales_month",
    )

    search_fields = ("po_or_forecast", "customer_part")

    actions = ["download_csv"]

    # 🔗 URL FOR TOP DOWNLOAD BUTTON
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "export-csv/",
                self.admin_site.admin_view(self.export_csv),
                name="zsodemand_export_csv",
            )
        ]
        return custom_urls + urls

    # 🔘 BUTTON CSV (uses filters)
    def export_csv(self, request):
        changelist = self.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        return self._build_csv_response(queryset)

    # 🔘 ACTION CSV (uses selected rows)
    def download_csv(self, request, queryset):
        return self._build_csv_response(queryset)

    download_csv.short_description = "⬇️ Download filtered records as CSV"

    # 🔧 SHARED CSV BUILDER
    def _build_csv_response(self, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="zso_demands.csv"'

        writer = csv.writer(response)

        # ✅ EXACT HEADERS
        writer.writerow([
            "S No",
            "KAS Name",
            "Customer Name",
            "Site location",
            "Country",
            "Incoterms",
            "Direct Sales /  WH Movement",
            "PO # / Forecast",
            "Category",
            "Sub Category",
            "Cust part #",
            "Maini part #",
            "Open qty",
            "Unit Price",
            "Currency",
            "Unit Price in INR",
            "Total in INR",
            "Doc date",
            "Ship date",
            "Sales Month",
        ])

        for idx, obj in enumerate(queryset, start=1):
            writer.writerow([
                idx,
                obj.kas_name or "",
                obj.customer_name or "",
                obj.site_location or "",
                obj.country or "",
                obj.incoterms or "",
                obj.sales_type or "",
                obj.po_or_forecast or "",
                obj.category or "",
                obj.sub_category or "",
                obj.customer_part or "",
                obj.maini_part or "",
                obj.open_qty or "",
                obj.unit_price or "",
                obj.currency or "",
                obj.unit_price_inr or "",
                obj.total_inr or "",
                obj.doc_date.strftime("%d-%m-%Y") if obj.doc_date else "",
                obj.ship_date.strftime("%d-%m-%Y") if obj.ship_date else "",
                obj.sales_month or "",
            ])

        return response

def parse_any_date(value):
    if not value:
        return None

    # Try ISO format first (YYYY-MM-DD)
    date = parse_date(value)
    if date:
        return date

    # Try DD-MM-YYYY
    try:
        return datetime.strptime(value, "%d-%m-%Y").date()
    except ValueError:
        return None
