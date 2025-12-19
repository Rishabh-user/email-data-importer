from django.core.management.base import BaseCommand
from importer.connectors.email_reader import fetch_and_process_all
from importer.connectors.raw_folder_processor import process_raw_folder



class Command(BaseCommand):
    help = "Fetch emails, save attachments, and run extraction pipeline"

    def handle(self, *args, **options):
        self.stdout.write("📧 Starting email fetch...")
        fetch_and_process_all()

        self.stdout.write("📦 Processing raw files...")
        process_raw_folder()

        self.stdout.write("✅ Email fetch & extraction completed")