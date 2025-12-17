from pathlib import Path
from config.logger import logger

from importer.extraction.unified.excel_importer import ExcelImporter
from importer.extraction.unified.csv_importer import CSVImporter
from importer.extraction.unified.text_importer import TextImporter
from importer.extraction.unified.word_importer import WordImporter
from importer.extraction.unified.pdf_importer import PDFImporter


class UnifiedImporter:
    def parse(self, file_path: str):
        ext = Path(file_path).suffix.lower()
        logger.info(f"Routing file {file_path} (ext={ext})")

        if ext in [".xlsx", ".xls"]:
            return ExcelImporter().parse(file_path)

        if ext == ".csv":
            return CSVImporter().parse(file_path)

        if ext == ".txt":
            return TextImporter().parse(file_path)

        if ext == ".docx":
            return WordImporter().parse(file_path)

        if ext == ".pdf":
            return PDFImporter().parse(file_path)

        raise ValueError(f"Unsupported extension: {ext}")
