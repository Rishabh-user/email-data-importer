from django.db import models
import os

class RawFile(models.Model):
    # Only upload field is visible to user
    raw_file = models.FileField(upload_to='raw_files/',
                                verbose_name="Upload File")

    # Auto-filled fields
    file_name = models.CharField(max_length=255, blank=True)
    file_type = models.CharField(max_length=50, blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    raw_text = models.TextField(null=True, blank=True)
    raw_json = models.JSONField(null=True, blank=True)
    customer_detected = models.CharField(max_length=255, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.raw_file:
            self.file_name = os.path.basename(self.raw_file.name)
            self.file_type = os.path.splitext(self.raw_file.name)[1].lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.file_name or "Uploaded File"
    
    class Meta:
        verbose_name = "Upload File"
        verbose_name_plural = "Upload File"

class ExtractedRecord(models.Model):
    raw_file = models.ForeignKey(RawFile, on_delete=models.CASCADE, related_name="records")

    # common extracted fields (optional, dynamic)
    po_number = models.CharField(max_length=255, null=True, blank=True)
    customer_part = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    quantity = models.FloatField(null=True, blank=True)
    open_qty = models.FloatField(null=True, blank=True)
    need_date = models.DateField(null=True, blank=True)
    promised_date = models.DateField(null=True, blank=True)
    ship_date = models.DateField(null=True, blank=True)

    # full extracted row as JSON (always stored)
    full_row_json = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.raw_file.file_name} — {self.po_number or 'No PO'}"


# importer/models.py

class ZSODemand(models.Model):
    extracted_record = models.ForeignKey(
        ExtractedRecord,
        on_delete=models.CASCADE,
        related_name="zso_records"
    )

    # -------- ZSO Fields --------
    kas_name = models.CharField(max_length=255, null=True, blank=True)
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    site_location = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    incoterms = models.CharField(max_length=50, null=True, blank=True)
    sales_type = models.CharField(
        max_length=50,
        help_text="Direct Sales / WH Movement",
        null=True, blank=True
    )

    po_or_forecast = models.CharField(max_length=255, null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True)
    sub_category = models.CharField(max_length=255, null=True, blank=True)

    customer_part = models.CharField(max_length=255, null=True, blank=True)
    maini_part = models.CharField(max_length=255, null=True, blank=True)

    open_qty = models.FloatField(null=True, blank=True)
    unit_price = models.FloatField(null=True, blank=True)
    currency = models.CharField(max_length=10, null=True, blank=True)
    unit_price_inr = models.FloatField(null=True, blank=True)
    total_inr = models.FloatField(null=True, blank=True)

    doc_date = models.DateField(null=True, blank=True)
    ship_date = models.DateField(null=True, blank=True)
    sales_month = models.CharField(max_length=20, null=True, blank=True)

    # -------- Metadata --------
    confidence_score = models.FloatField(
        null=True, blank=True,
        help_text="Accuracy score of mapping"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ZSO | {self.po_or_forecast} | {self.customer_part}"

class ExtractionLog(models.Model):
    raw_file = models.ForeignKey(
        RawFile, on_delete=models.CASCADE, related_name="logs"
    )

    level = models.CharField(
        max_length=20,
        choices=[
            ("INFO", "INFO"),
            ("WARNING", "WARNING"),
            ("ERROR", "ERROR")
        ]
    )

    message = models.TextField()
    context = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.level} | {self.raw_file.file_name}"
