from django.db import models
import os


# -----------------------------
# RAW UPLOADED FILE
# -----------------------------
class RawFile(models.Model):
    raw_file = models.FileField(
        upload_to="raw_files/",
        verbose_name="Upload File",
    )

    class Meta:
        verbose_name = "Upload File"
        verbose_name_plural = "Upload Files"


    file_name = models.CharField(max_length=255, blank=True)
    file_type = models.CharField(max_length=50, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    raw_text = models.TextField(null=True, blank=True)
    raw_json = models.JSONField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.raw_file:
            self.file_name = os.path.basename(self.raw_file.name)
            self.file_type = os.path.splitext(self.raw_file.name)[1].lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.file_name


# -----------------------------
# EXTRACTED ROW (RAW STRUCTURE)
# -----------------------------
class ExtractedRecord(models.Model):
    raw_file = models.ForeignKey(
        RawFile,
        on_delete=models.CASCADE,
        related_name="extracted_records"
    )

    po_number = models.CharField(max_length=255, null=True, blank=True)
    customer_part = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    quantity = models.FloatField(null=True, blank=True)
    open_qty = models.FloatField(null=True, blank=True)

    need_date = models.DateField(null=True, blank=True)
    promised_date = models.DateField(null=True, blank=True)
    ship_date = models.DateField(null=True, blank=True)

    is_processed = models.BooleanField(default=False)
    full_row_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.po_number or 'NO-PO'} | {self.customer_part}  | {self.id}"


# -----------------------------
# FINAL ZSO DEMAND FORMAT (FIXED)
# -----------------------------
class ZSODemand(models.Model):
    """
    Final standardized ZSO demand row.
    Exactly ONE ZSO row per ExtractedRecord.
    """

    raw_file = models.ForeignKey(
        RawFile,
        on_delete=models.CASCADE,
        related_name="zso_demands"
    )

    extracted_record = models.OneToOneField(
        ExtractedRecord,
        on_delete=models.CASCADE,
        related_name="zso"
    )

    # -------- Customer / Sales --------
    kas_name = models.CharField(max_length=255, null=True, blank=True)
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    site_location = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)

    sales_type = models.CharField(max_length=100, null=True, blank=True)
    incoterms = models.CharField(max_length=50, null=True, blank=True)

    # -------- Demand Identifiers --------
    po_or_forecast = models.CharField(max_length=255, null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    sub_category = models.CharField(max_length=100, null=True, blank=True)

    # -------- Part Info --------
    customer_part = models.CharField(max_length=255, null=True, blank=True)
    maini_part = models.CharField(max_length=255, null=True, blank=True)

    # -------- Quantity / Price --------
    open_qty = models.FloatField(null=True, blank=True)
    unit_price = models.FloatField(null=True, blank=True)
    currency = models.CharField(max_length=20, null=True, blank=True)
    unit_price_inr = models.FloatField(null=True, blank=True)
    total_inr = models.FloatField(null=True, blank=True)

    # -------- Dates --------
    doc_date = models.DateField(null=True, blank=True)
    ship_date = models.DateField(null=True, blank=True)

    sales_month = models.CharField(
        max_length=7,
        null=True,
        blank=True,
        help_text="YYYY-MM derived from ship date"
    )

    # -------- Quality / Meta --------
    confidence_score = models.FloatField(default=0.0)
    mapping_notes = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ZSO | {self.po_or_forecast or 'N/A'} | {self.customer_part or 'UNKNOWN'}"


# -----------------------------
# EXTRACTION / ERROR LOGGING
# -----------------------------
class ExtractionLog(models.Model):
    LEVEL_CHOICES = (
        ("INFO", "Info"),
        ("SUCCESS", "Success"),
        ("ERROR", "Error"),
    )

    raw_file = models.ForeignKey(
        RawFile,
        on_delete=models.CASCADE,
        related_name="logs"
    )

    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    message = models.TextField()
    context = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.level} | {self.raw_file.file_name}"
    
class ProcessProgress(models.Model):
    key = models.CharField(max_length=100, unique=True)
    total = models.IntegerField(default=0)
    processed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    is_running = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key


