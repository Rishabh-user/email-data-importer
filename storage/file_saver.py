import json
import csv
from pathlib import Path
from config.settings import OUTPUT_DIR, ATTACHMENTS_DIR
import datetime


class FileSaver:

    @staticmethod
    def _json_serializer(obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, float):
            if obj != obj:
                return None
            return obj
        raise TypeError(f"Type {type(obj)} not serializable")

    @staticmethod
    def save_json(data, filename):
        path = OUTPUT_DIR / "json" / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=4, default=FileSaver._json_serializer)
        return path

    @staticmethod
    def save_csv(data, filename, headers=None):
        path = OUTPUT_DIR / "csv" / filename
        fieldnames = headers or (data[0].keys() if data else [])
        
        cleaned_data = []
        for row in data:
            cleaned_row = {}
            for key in fieldnames:
                val = row.get(key)
                if isinstance(val, datetime.datetime):
                    val = val.isoformat()
                elif isinstance(val, datetime.date):
                    val = val.isoformat()
                elif isinstance(val, float) and val != val:
                    val = ""
                cleaned_row[key] = val
            cleaned_data.append(cleaned_row)
        
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(cleaned_data)
        return path

    @staticmethod
    def save_html(data, filename):
        """Save parsed data as a formatted HTML file"""
        path = OUTPUT_DIR / "html" / filename.replace('.json', '.html')
        
        html_content = FileSaver._generate_html(data)
        
        with open(path, "w") as f:
            f.write(html_content)
        
        return path

    @staticmethod
    def _generate_html(data):
        """Generate HTML representation of parsed tables"""
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "  <meta charset='UTF-8'>",
            "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            "  <title>Parsed Data</title>",
            "  <style>",
            "    body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }",
            "    .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            "    h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }",
            "    h2 { color: #555; margin-top: 30px; margin-bottom: 15px; border-left: 4px solid #007bff; padding-left: 10px; }",
            "    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }",
            "    th { background: #007bff; color: white; padding: 12px; text-align: left; font-weight: bold; }",
            "    td { padding: 10px; border-bottom: 1px solid #ddd; }",
            "    tr:hover { background: #f9f9f9; }",
            "    .empty { color: #999; font-style: italic; }",
            "    .metadata { background: #f0f0f0; padding: 10px; border-radius: 4px; margin-bottom: 20px; font-size: 12px; color: #666; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <div class='container'>",
            "    <h1>Parsed Data</h1>",
            "    <div class='metadata'>Generated on: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "</div>",
        ]
        
        if "tables" in data:
            for idx, table in enumerate(data["tables"]):
                section = table.get("section", f"Table {idx + 1}")
                html_parts.append(f"    <h2>{section}</h2>")
                
                if "rows" in table and table["rows"]:
                    columns = table.get("columns", [])
                    html_parts.append("    <table>")
                    html_parts.append("      <thead>")
                    html_parts.append("        <tr>")
                    for col in columns:
                        html_parts.append(f"          <th>{col}</th>")
                    html_parts.append("        </tr>")
                    html_parts.append("      </thead>")
                    html_parts.append("      <tbody>")
                    
                    for row in table["rows"]:
                        html_parts.append("        <tr>")
                        for col in columns:
                            val = row.get(col, "")
                            if val is None or val == "":
                                html_parts.append(f"          <td class='empty'>&mdash;</td>")
                            else:
                                val_str = str(val).replace("<", "&lt;").replace(">", "&gt;")
                                html_parts.append(f"          <td>{val_str}</td>")
                        html_parts.append("        </tr>")
                    
                    html_parts.append("      </tbody>")
                    html_parts.append("    </table>")
        
        html_parts.extend([
            "  </div>",
            "</body>",
            "</html>"
        ])
        
        return "\n".join(html_parts)

    @staticmethod
    def save_attachment(bytes_data, filename):
        path = ATTACHMENTS_DIR / filename
        with open(path, "wb") as f:
            f.write(bytes_data)
        return path
