import logging
from config.settings import OUTPUT_DIR

LOG_FILE = OUTPUT_DIR / "logs" / "app.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("email_importer")
logger.setLevel(logging.INFO)

fh = logging.FileHandler(LOG_FILE)
ch = logging.StreamHandler()

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

fh.setFormatter(formatter)
ch.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(fh)
    logger.addHandler(ch)
