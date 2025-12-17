from pathlib import Path
import datetime

from importer.extraction.router import UnifiedImporter
from storage.file_saver import FileSaver
from config.logger import logger


def test_importer():
    """
    Manual local testing utility.
    NOT used in Django / cron / production.
    """

    importer = UnifiedImporter()

    file_path = input("Enter path of file to parse: ").strip()
    logger.info(f"Parsing: {file_path}")

    result = importer.parse(file_path)

    filename = Path(file_path).stem
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    json_filename = f"{filename}_{timestamp}.json"
    html_filename = f"{filename}_{timestamp}.html"
    csv_base_filename = f"{filename}_{timestamp}"

    # Save JSON
    json_path = FileSaver.save_json(result, json_filename)
    logger.info(f"Saved JSON output to: {json_path}")

    # Save HTML
    html_path = FileSaver.save_html(result, html_filename)
    logger.info(f"Saved HTML output to: {html_path}")

    # Save CSV tables if present
    if "tables" in result:
        for idx, table in enumerate(result["tables"]):
            rows = table.get("rows", [])
            if rows:
                csv_filename = f"{csv_base_filename}_table_{idx}.csv"
                csv_path = FileSaver.save_csv(
                    rows,
                    csv_filename,
                    headers=table.get("columns")
                )
                logger.info(f"Saved CSV output to: {csv_path}")

    print("\n" + "=" * 60)
    print("PARSING COMPLETE")
    print("=" * 60)
    print(f"📄 JSON:  output/json/{json_filename}")
    print(f"📊 HTML:  output/html/{html_filename}")
    print(f"📋 CSV:   output/csv/{csv_base_filename}_table_*.csv")
    print(f"📈 Total tables extracted: {len(result.get('tables', []))}")
    print("=" * 60 + "\n")

    logger.info("Manual parsing complete.")


if __name__ == "__main__":
    # 🔴 IMPORTANT:
    # main.py is ONLY for local/manual testing.
    # Email fetching, admin uploads, and cron jobs
    # are handled via Django (manage.py commands).

    test_importer()
