import pandas as pd
from pathlib import Path
import tempfile
from openpyxl import Workbook
import xlrd

from importer.extraction.unified.normalize import normalize_table
from config.logger import logger


def convert_xls_to_xlsx(xls_path: str) -> str:
    book = xlrd.open_workbook(xls_path)
    sheet = book.sheet_by_index(0)

    wb = Workbook()
    ws = wb.active

    for r in range(sheet.nrows):
        ws.append(sheet.row_values(r))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    wb.save(tmp.name)

    logger.info(f"Converted .xls to .xlsx: {tmp.name}")
    return tmp.name


class ExcelImporter:

    def parse(self, path: str) -> dict:
        logger.info(f"Parsing Excel file: {path}")
        file_path = Path(path)

        try:
            if file_path.suffix.lower() == ".xls":
                xlsx_path = convert_xls_to_xlsx(path)
                df = pd.read_excel(xlsx_path, engine="openpyxl")
            else:
                df = pd.read_excel(path, engine="openpyxl")
        except Exception as e:
            logger.error(f"❌ Cannot read Excel: {e}")
            return {"raw_text": "", "raw_json": {}, "rows": []}

        df = self._clean_dataframe(df)

        if df.empty:
            return {"raw_text": "", "raw_json": {"tables": []}, "rows": []}

        tables = self._extract_tables(df)

        flattened_rows = []
        for table in tables:
            for row in table.get("rows", []):
                if isinstance(row, dict):
                    flattened_rows.append(row)

        return {
            "raw_text": "",
            "raw_json": {"tables": tables},
            "rows": flattened_rows
        }

    @staticmethod
    def _clean_dataframe(df):
        df = df.dropna(axis=1, how="all")
        df = df.dropna(axis=0, how="all")
        df = df.reset_index(drop=True)
        df = df.where(pd.notnull(df), "")
        return df

    @staticmethod
    def _extract_tables(df):
        tables = []
        sections = []
        current_section = None
        section_rows = []

        for _, row in df.iterrows():
            row_values = row.tolist()
            row_str = " ".join(str(v).strip() for v in row_values if str(v).strip())

            is_header = any(
                k in row_str.upper()
                for k in ["SERVICES", "MATERIALS", "PURCHASE", "TOTAL", "ORDER"]
            )
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

        for section_name, rows in sections:
            try:
                table = normalize_table(
                    list(df.columns),
                    [row.tolist() for row in rows]
                )
                table["section"] = section_name
                tables.append(table)
            except Exception as e:
                logger.error(f"normalize_table failed: {e}")

        return tables
