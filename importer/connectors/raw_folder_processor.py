"""
Scan media/raw_files for unprocessed files,
push them into Django extraction pipeline,
then move them to media/processed.
"""

import shutil
from pathlib import Path

from django.conf import settings
from importer.models import RawFile
from importer.services.process_file import process_file
from config.logger import logger


def process_raw_folder():
    raw_dir = Path(settings.MEDIA_ROOT) / "raw_files"
    processed_dir = Path(settings.MEDIA_ROOT) / "processed"

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Scanning raw folder: {raw_dir}")

    for file_path in raw_dir.iterdir():
        if not file_path.is_file():
            continue

        logger.info(f"Processing raw file: {file_path.name}")

        try:
            # 1️⃣ Create RawFile entry
            raw_obj = RawFile.objects.create(
                raw_file=f"raw_files/{file_path.name}"
            )

            # 2️⃣ Run extraction
            process_file(raw_obj)

            # 3️⃣ Move processed file
            dest_path = processed_dir / file_path.name
            shutil.move(str(file_path), dest_path)

            logger.info(f"Moved file to processed: {dest_path}")

        except Exception as e:
            logger.exception(f"Error processing file {file_path}: {e}")

    logger.info("Raw folder processing complete.")
