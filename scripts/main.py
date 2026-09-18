# ============================================================
# EDPRP Pipeline Entry Point
# ============================================================
# Run with: python ./scripts/main.py
#
# This script orchestrates the full EDPRP pipeline:
#   1. Upload the raw customers file from local disk to S3.
#   2. Copy the file from the S3 stage into the Snowflake
#      BRONZE.CUSTOMERS table.
#   3. Promote the validated/cleansed records from the BRONZE
#      schema into the SILVER schema (bronze_to_silver).
#   4. Promote the validated records from the SILVER schema
#      into the GOLD schema (silver_to_gold).
# It exits with a non-zero code if any step fails, so the
# pipeline can be wired into a scheduler (cron, Airflow, etc.).
# ============================================================

import os
import sys

# Prepend the project root to sys.path so that package imports
# (e.g. "scripts.upload_to_s3") work no matter where main.py is run from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.logging_config import setup_logging
from scripts.upload_to_s3 import upload_file_to_s3
from scripts.load_customers_from_s3_to_snowflake import load_customers
from scripts.bronze_to_silver import bronze_to_silver
from scripts.silver_to_gold import silver_to_gold

logger, run_log_file = setup_logging()


def main():
    logger.info("Starting EDPRP pipeline...")
    logger.info("Log file for this run: %s", run_log_file)

    # Step 1: Upload the local customers file to S3.
    upload_file_to_s3()

    # Step 2: Load the staged file from S3 into Snowflake (BRONZE.CUSTOMERS).
    success = load_customers()
    if not success:
        # load_customers() returns False on error, so abort the pipeline here.
        logger.error("Customer load failed. Pipeline aborted.")
        sys.exit(1)

    # Step 3: Promote BRONZE.CUSTOMERS to SILVER.CUSTOMERS.
    # bronze_to_silver() cleanses & validates the Bronze data and loads the
    # valid records into Silver. It returns False on error, so we abort too.
    success = bronze_to_silver()
    if not success:
        logger.error("Bronze → Silver promotion failed. Pipeline aborted.")
        sys.exit(1)

    # Step 4: Promote SILVER.CUSTOMERS to GOLD.DIM_CUSTOMER.
    # silver_to_gold() re-validates the business-required columns and builds
    # the business-ready customer dimension in Gold. It returns False on
    # error, so we abort the pipeline here as well.
    success = silver_to_gold()
    if not success:
        logger.error("Silver → Gold promotion failed. Pipeline aborted.")
        sys.exit(1)

    logger.info("Pipeline completed successfully.")


if __name__ == "__main__":
    main()

