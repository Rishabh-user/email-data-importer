from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect

from importer.services.process_extracted_records import process_extracted_records


@staff_member_required
def process_extracted_records_admin(request):
    result = process_extracted_records()

    if result["processed"] == 0:
        messages.warning(request, result["message"])
    else:
        messages.success(
            request,
            f"Successfully processed {result['processed']} records"
        )

    return redirect("/admin/importer/extractedrecord/")
