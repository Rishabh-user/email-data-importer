from pathlib import Path
import os
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env
load_dotenv(os.path.join(BASE_DIR, ".env"))

OUTPUT_DIR = BASE_DIR / "output"
ATTACHMENTS_DIR = BASE_DIR / "attachments" / "raw"

OUTPUT_DIR.mkdir(exist_ok=True)
(OUTPUT_DIR / "json").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "csv").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "html").mkdir(parents=True, exist_ok=True)

ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
