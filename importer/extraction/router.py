from pathlib import Path
from config.logger import logger

from importer.extraction.unified.excel_importer import ExcelImporter
from importer.extraction.unified.csv_importer import CSVImporter
from importer.extraction.unified.text_importer import TextImporter
from importer.extraction.unified.word_importer import WordImporter
from importer.extraction.unified.pdf_importer import PDFImporter


class UnifiedImporter:
    """
    Ensures ALL importers return the SAME structure:

    {
        "raw_text": "",
        "raw_json": {},
        "rows": [ {...}, {...} ]
    }
    """

    def parse(self, file_path: str) -> dict:
        ext = Path(file_path).suffix.lower()
        logger.info(f"Routing file: {file_path} (ext={ext})")

        try:
            if ext in (".xls", ".xlsx"):
                return ExcelImporter().parse(file_path)

            if ext == ".csv":
                return CSVImporter().parse(file_path)

            if ext == ".txt":
                return TextImporter().parse(file_path)

            if ext == ".docx":
                return WordImporter().parse(file_path)

            if ext == ".pdf":
                pdf_result = PDFImporter().parse(file_path)

                # 🔥 NORMALIZE PDF OUTPUT HERE
                if isinstance(pdf_result, dict):
                    return pdf_result

                if isinstance(pdf_result, list):
                    return {
                        "raw_text": "",
                        "raw_json": {"pdf_rows": pdf_result},
                        "rows": pdf_result,
                    }

                if isinstance(pdf_result, str):
                    return {
                        "raw_text": pdf_result,
                        "raw_json": {"text": pdf_result},
                        "rows": [],
                    }

                # Fallback
                return {
                    "raw_text": "",
                    "raw_json": {},
                    "rows": [],
                }

            raise ValueError(f"Unsupported extension: {ext}")

        except Exception as e:
            logger.exception(f"❌ UnifiedImporter failed for {file_path}")
            return {
                "raw_text": "",
                "raw_json": {},
                "rows": [],
            }
