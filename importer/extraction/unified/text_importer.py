# parsers/unified/text_importer.py
from pathlib import Path
import pandas as pd
from importer.extraction.unified.normalize import normalize_table
from config.logger import logger


class TextImporter:
    def parse(self, path: str) -> dict:
        """
        Parse a TXT file.

        - If delimited table exists → extract rows
        - Else → treat as free text (email body, notes, etc.)
        """
        logger.info(f"Parsing TXT file: {path}")

        text = Path(path).read_text(encoding="utf-8", errors="ignore")

        # ---------- Try table detection ----------
        delimiter = None
        if "," in text:
            delimiter = ","
        elif "\t" in text:
            delimiter = "\t"

        # ---------- TABLE MODE ----------
        if delimiter:
            try:
                df = pd.read_csv(path, delimiter=delimiter)

                columns = df.columns.tolist()
                rows = df.values.tolist()
                table = normalize_table(columns, rows)

                return {
                    "raw_text": text,
                    "raw_json": None,
                    "rows": table.get("rows", []),
                }

            except Exception as e:
                logger.warning(
                    "TXT table parse failed, falling back to raw text",
                    extra={"error": str(e)},
                )

        # ---------- FREE-TEXT MODE (SAFE DEFAULT) ----------
        logger.info("TXT file has no detectable table; stored as raw text")

        return {
            "raw_text": text,
            "raw_json": None,
            "rows": [],  # IMPORTANT: no rows, but NOT an error
        }
