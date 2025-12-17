# parsers/unified/word_importer.py
from docx import Document
from importer.extraction.unified.normalize import normalize_table
from config.logger import logger


class WordImporter:
    def parse(self, path: str) -> dict:
        """
        Parse the first table in a .docx file into unified format.
        """
        logger.info(f"Parsing Word file: {path}")
        doc = Document(path)

        tables = doc.tables
        if not tables:
            raise ValueError("No tables found in Word document")

        normalized_tables = []

        for table in tables:
            rows = []
            # Assume first row is header
            header_cells = table.rows[0].cells
            columns = [cell.text.strip() for cell in header_cells]

            for row in table.rows[1:]:
                rows.append([cell.text.strip() for cell in row.cells])

            normalized_tables.append(normalize_table(columns, rows))

        return {"tables": normalized_tables}
