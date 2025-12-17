# parsers/unified/csv_importer.py
import pandas as pd
from importer.extraction.unified.normalize import normalize_table
from config.logger import logger


class CSVImporter:
    def parse(self, path: str) -> dict:
        """
        Parse a CSV file into unified format.
        """
        logger.info(f"Parsing CSV file: {path}")
        df = pd.read_csv(path)

        columns = df.columns.tolist()
        rows = df.values.tolist()

        table = normalize_table(columns, rows)
        return {"tables": [table]}
