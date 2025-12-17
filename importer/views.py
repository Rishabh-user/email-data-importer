from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from importer.models import RawFile
from importer.services.process_file import process_file

class UploadFileView(APIView):
    def post(self, request):
        file = request.FILES.get('file')

        if not file:
            return Response({"error": "No file uploaded"}, status=400)

        raw = RawFile.objects.create(
            file_name=file.name,
            file_type=file.content_type,
            raw_file=file
        )

        result = process_file(raw)

        return Response({
            "message": "File processed",
            "file_id": raw.id,
            "result": result,
            # expose zso_preview at top-level for convenience (if present)
            "zso_preview": result.get("zso_preview", []),
        })