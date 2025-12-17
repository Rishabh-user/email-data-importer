import pandas as pd
from importer.extraction.unified.normalize import normalize_table
from config.logger import logger


class ExcelImporter:

    def parse(self, path: str) -> dict:
        """
        Always returns:

        {
            "raw_text": "",
            "raw_json": {"tables": [...]},
            "rows": [ {...}, {...}, ... ]   # flat row dictionaries
        }
        """
        logger.info(f"Parsing Excel file: {path}")

        try:
            df = pd.read_excel(path)
        except Exception as e:
            logger.error(f"❌ Cannot read Excel: {e}")
            return {"raw_text": "", "raw_json": {}, "rows": []}

        df = self._clean_dataframe(df)

        if df.empty:
            return {
                "raw_text": "",
                "raw_json": {"tables": []},
                "rows": []
            }

        # Step 1 — extract tables using your existing logic
        tables = self._extract_tables(df)

        # Step 2 — flatten rows (they are already dicts!)
        flattened_rows = []

        for table in tables:
            rows = table.get("rows", [])

            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        flattened_rows.append(row)
                    else:
                        logger.warning(f"⚠️ Unexpected row format: {row}")
            else:
                logger.warning(f"⚠️ Table rows not list: {rows}")

        # FINAL UNIFIED OUTPUT
        return {
            "raw_text": "",
            "raw_json": {"tables": tables},
            "rows": flattened_rows
        }

    @staticmethod
    def _clean_dataframe(df):
        df = df.dropna(axis=1, how='all')
        df = df.dropna(axis=0, how='all')
        df = df.reset_index(drop=True)
        return df

    @staticmethod
    def _extract_tables(df):
        tables = []

        df_filled = df.fillna("")
        sections = []
        current_section = None
        section_rows = []

        for idx, row in df_filled.iterrows():
            row_values = row.tolist()
            row_str = " ".join(str(v).strip() for v in row_values if str(v).strip())
            is_header = any(keyword in row_str for keyword in 
                           ["SERVICES", "MATERIALS", "PURCHASE", "TOTAL", "ORDER"])
            is_empty = not any(str(v).strip() for v in row_values)

            if is_header and section_rows:
                sections.append((current_section, section_rows))
                current_section = row_str[:50]
                section_rows = []
            elif not is_empty:
                if not current_section:
                    current_section = "Data"
                section_rows.append(row)

        if section_rows:
            sections.append((current_section, section_rows))

        # Normalize tables
        for section_name, rows in sections:
            try:
                table = normalize_table(
                    list(df.columns),
                    [row.tolist() for row in rows]
                )
                table["section"] = section_name
                tables.append(table)
            except Exception as e:
                logger.error(f"❌ normalize_table failed: {e}")

        return tables
