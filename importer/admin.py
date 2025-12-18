from django.contrib import admin
from django.db import transaction
from importer.models import RawFile, ExtractedRecord, ExtractionLog, ZSODemand
from importer.services.process_file import process_file
from django.contrib.auth.models import Group
from django.contrib.admin import AdminSite


admin.site.site_header = "JKMGAL Demand Portal"
admin.site.site_title = "JKMGAL Demand Portal"
admin.site.index_title = "JKMGAL Demand Portal"


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
    )
    list_filter = ("raw_file",)
    search_fields = ("po_number", "customer_part")


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

    list_filter = ("sales_month",)
    search_fields = ("po_or_forecast", "customer_part")