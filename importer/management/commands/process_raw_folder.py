from django.core.management.base import BaseCommand
from importer.connectors.raw_folder_processor import process_raw_folder


class Command(BaseCommand):
    help = "Process raw files from media folder"

    def handle(self, *args, **kwargs):
        process_raw_folder()
