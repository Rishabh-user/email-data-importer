from django.contrib import admin
from importer.models import RawFile, ExtractedRecord, ZSODemand
from importer.services.process_file import process_file
from django.utils.html import format_html

admin.site.site_header = "JKMGAL Demand Portal"
admin.site.site_title = "JKMGAL Demand Portal"
admin.site.index_title = "JKMGAL Demand Portal"

@admin.register(RawFile)
class RawFileAdmin(admin.ModelAdmin):
    verbose_name_plural = "Upload File"

    # Only show upload field
    fields = ("raw_file",)

    # How the list page looks
    list_display = ("file_name", "file_type", "uploaded_at")
    change_form_template = "admin/importer/rawfile/change_form.html"

    # Make file_name read-only if visible anywhere
    readonly_fields = ()

    class Media:
        # Add custom CSS to make the upload widget modern
        css = {
            'all': ('admin/custom_upload.css',)
        }

    def save_model(self, request, obj, form, change):
        print("DEBUG: RawFile save_model triggered")

        # filename and type auto-fill in model.save()

        super().save_model(request, obj, form, change)

        print("DEBUG: Running extraction…")
        process_file(obj)


@admin.register(ExtractedRecord)
class ExtractedRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "po_number", "customer_part", "quantity", "raw_file", "created_at")
    list_filter = ("raw_file",)
    search_fields = ("po_number", "customer_part")


@admin.register(ZSODemand)
class ZSODemandAdmin(admin.ModelAdmin):
    list_display = (
        "po_or_forecast",
        "customer_part",
        "open_qty",
        "sales_month",
        "confidence_score"
    )

    list_filter = ("sales_month", "customer_name")
    search_fields = ("po_or_forecast", "customer_part")

