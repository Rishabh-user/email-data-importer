# parsers/unified/text_importer.py
import pandas as pd
from importer.extraction.unified.normalize import normalize_table
from config.logger import logger


class TextImporter:
    def parse(self, path: str) -> dict:
        """
        Parse a TXT file that contains a delimited table (CSV/TSV).
        Tries to auto-detect the delimiter.
        """
        logger.info(f"Parsing text file as table: {path}")

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            sample = f.read()

        # Simple delimiter detection
        if "," in sample:
            delimiter = ","
        elif "\t" in sample:
            delimiter = "\t"
        else:
            raise ValueError("Cannot detect delimiter in TXT file")

        df = pd.read_csv(path, delimiter=delimiter)

        columns = df.columns.tolist()
        rows = df.values.tolist()

        table = normalize_table(columns, rows)
        return {"tables": [table]}
