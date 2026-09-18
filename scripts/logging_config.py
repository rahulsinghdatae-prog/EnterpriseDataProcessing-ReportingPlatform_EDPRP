# ============================================================
# EDPRP Logging Configuration
# ============================================================
# Every pipeline run writes a new timestamped log file into the
# project's "logs" folder. The log is also mirrored to the console.
#
# Usage from any script:
#   import logging
#   logger = logging.getLogger("EDPRP")
# ============================================================

import logging
import os
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOG_FOLDER = os.path.join(PROJECT_ROOT, "logs")

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(message)s"

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOGGER_NAME = "EDPRP"


def setup_logging():
    """Configure a logger that writes to a per-run log file and the console."""
    os.makedirs(LOG_FOLDER, exist_ok=True)

    log_file = os.path.join(
        LOG_FOLDER,
        f"EDPRP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)

    # Avoid registering duplicate handlers when setup_logging()
    # is called more than once in the same process.
    if logger.handlers:
        return logger, log_file

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger, log_file


def get_logger():
    """Return the shared EDPRP logger (module-level, no setup side effects)."""
    return logging.getLogger(LOGGER_NAME)