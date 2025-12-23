from django.contrib import admin
from django.db import transaction
from django.contrib.auth.models import Group
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils.dateparse import parse_date
from django.contrib.admin import DateFieldListFilter

from rangefilter.filters import DateRangeFilter

from importer.models import (
    RawFile,
    ExtractedRecord,
    ExtractionLog,
    ZSODemand,
    ProcessProgress,
)

from importer.services.process_file import process_file

import json
import http.client
import csv
from datetime import datetime


# ─────────────────────────────────────────────
# Admin branding
# ─────────────────────────────────────────────
admin.site.site_header = "JKMGAL Demand Portal"
admin.site.site_title = "JKMGAL Demand Portal"
admin.site.index_title = "JKMGAL Demand Portal"


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
# Hide unwanted admin models
# ─────────────────────────────────────────────
try:
    from admin_interface.models import Theme
    admin.site.unregister(Theme)
except Exception:
    pass

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


# ─────────────────────────────────────────────
# RawFile Admin
# ─────────────────────────────────────────────
@admin.register(RawFile)
class RawFileAdmin(admin.ModelAdmin):
    fields = ("raw_file",)
    list_display = ("file_name", "file_type", "uploaded_at")
    change_form_template = "admin/importer/rawfile/change_form.html"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        transaction.on_commit(lambda: process_file(obj))


# ─────────────────────────────────────────────
# ExtractedRecord Admin (WITH PROGRESS BAR)
# ─────────────────────────────────────────────
@admin.register(ExtractedRecord)
class ExtractedRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "po_number",
        "customer_part",
        "open_qty",
        "raw_file",
        "created_at",
        "is_processed",
    )

    list_filter = ("raw_file", "is_processed")
    search_fields = ("po_number", "customer_part")
    change_list_template = "admin/importer/extractedrecord/change_list.html"

    exclude = (
        "need_date",
        "promised_date",
        "ship_date",
        "quantity",
    )

    actions = ["mark_as_unprocessed"]

    # ─────────────────────────────
    # Actions
    # ─────────────────────────────
    def mark_as_unprocessed(self, request, queryset):
        count = queryset.update(is_processed=False)
        messages.success(request, f"{count} records marked as UNPROCESSED")

    mark_as_unprocessed.short_description = "🔁 Mark selected as UNPROCESSED"

    # ─────────────────────────────
    # URLs
    # ─────────────────────────────
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "process/",
                self.admin_site.admin_view(self.process_records),
                name="process_extracted_records",
            ),
            path(
                "process-status/",
                self.admin_site.admin_view(self.process_status),
                name="process_status",
            ),
        ]
        return custom + urls

    # ─────────────────────────────
    # Helpers
    # ─────────────────────────────
    def calculate_confidence_score(self, row: dict) -> float:
        filled = sum(
            1 for field in EXPECTED_FIELDS
            if row.get(field) not in (None, "", [], {})
        )
        return round((filled / len(EXPECTED_FIELDS)) * 100, 2)

    # ─────────────────────────────
    # PROCESS RECORDS (MAIN)
    # ─────────────────────────────
    def process_records(self, request):
        records = ExtractedRecord.objects.filter(is_processed=False)
        total = records.count()

        if total == 0:
            messages.warning(request, "No unprocessed records found.")
            return redirect("..")

        progress, _ = ProcessProgress.objects.update_or_create(
            key="extracted_records",
            defaults={
                "total": total,
                "processed": 0,
                "failed": 0,
                "is_running": True,
            },
        )

        conn = http.client.HTTPSConnection("zso-api-production.up.railway.app")
        headers = {"Content-Type": "application/json"}

        success = 0
        failed = 0

        for record in records:
            try:
                if not record.full_row_json:
                    raise ValueError("Empty row JSON")

                payload = json.dumps(record.full_row_json)

                conn.request("POST", "/zso/get_report", payload, headers)
                res = conn.getresponse()
                data = json.loads(res.read().decode())

                row = data.get("report")
                if not row:
                    raise ValueError("Empty report")

                with transaction.atomic():
                    confidence_score = self.calculate_confidence_score(row)

                    ZSODemand.objects.create(
                        raw_file=record.raw_file,
                        extracted_record=record,
                        kas_name='Praveen',
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
                progress.processed += 1

            except Exception:
                failed += 1
                progress.failed += 1

            progress.save(update_fields=["processed", "failed", "updated_at"])

        progress.is_running = False
        progress.save(update_fields=["is_running"])

        messages.success(
            request,
            f"Processing complete → Success: {success}, Failed: {failed}"
        )
        return redirect("..")

    # ─────────────────────────────
    # PROGRESS STATUS API
    # ─────────────────────────────
    def process_status(self, request):
        progress = ProcessProgress.objects.filter(
            key="extracted_records"
        ).first()

        if not progress:
            return JsonResponse({"running": False})

        percent = (
            int((progress.processed / progress.total) * 100)
            if progress.total else 0
        )

        return JsonResponse({
            "running": progress.is_running,
            "total": progress.total,
            "processed": progress.processed,
            "failed": progress.failed,
            "percent": percent,
        })


# ─────────────────────────────────────────────
# ExtractionLog Admin
# ─────────────────────────────────────────────
@admin.register(ExtractionLog)
class ExtractionLogAdmin(admin.ModelAdmin):
    list_display = ("raw_file", "level", "message", "created_at")
    list_filter = ("level",)
    search_fields = ("message",)


# ─────────────────────────────────────────────
# ZSO Demand Admin
# ─────────────────────────────────────────────
@admin.register(ZSODemand)
class ZSODemandAdmin(admin.ModelAdmin):
    list_display = (
        "po_or_forecast",
        "customer_part",
        "open_qty",
        "sales_month",
        "confidence_score",
    )

    list_filter = (
        ("ship_date", DateFieldListFilter),
        ("ship_date", DateRangeFilter),
        "sales_month",
        "raw_file",
    )

    search_fields = ("po_or_forecast", "customer_part")
    actions = ["download_csv"]

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                "export-csv/",
                self.admin_site.admin_view(self.export_csv),
                name="zsodemand_export_csv",
            )
        ] + urls

    def export_csv(self, request):
        changelist = self.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        return self._build_csv_response(queryset)

    def download_csv(self, request, queryset):
        return self._build_csv_response(queryset)

    download_csv.short_description = "⬇️ Download filtered records as CSV"

    def _build_csv_response(self, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="zso_demands.csv"'
        writer = csv.writer(response)

        writer.writerow([
            "S No", "KAS Name", "Customer Name", "Site Location", "Country",
            "Incoterms", "Sales Type", "PO / Forecast", "Category",
            "Sub Category", "Customer Part", "Maini Part", "Open Qty",
            "Unit Price", "Currency", "Unit Price INR", "Total INR",
            "Doc Date", "Ship Date", "Sales Month",
        ])

        for idx, obj in enumerate(queryset, start=1):
            writer.writerow([
                idx,
                obj.kas_name,
                obj.customer_name,
                obj.site_location,
                obj.country,
                obj.incoterms,
                obj.sales_type,
                obj.po_or_forecast,
                obj.category,
                obj.sub_category,
                obj.customer_part,
                obj.maini_part,
                obj.open_qty,
                obj.unit_price,
                obj.currency,
                obj.unit_price_inr,
                obj.total_inr,
                obj.doc_date.strftime("%d-%m-%Y") if obj.doc_date else "",
                obj.ship_date.strftime("%d-%m-%Y") if obj.ship_date else "",
                obj.sales_month,
            ])

        return response


# ─────────────────────────────────────────────
# Date parser
# ─────────────────────────────────────────────
def parse_any_date(value):
    if not value:
        return None

    date = parse_date(value)
    if date:
        return date

    try:
        return datetime.strptime(value, "%d-%m-%Y").date()
    except ValueError:
        return None
