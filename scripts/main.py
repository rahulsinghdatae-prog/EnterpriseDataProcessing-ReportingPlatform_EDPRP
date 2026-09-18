# ============================================================
# EDPRP Pipeline Entry Point
# ============================================================
# Run with: python ./scripts/main.py
#
# This script orchestrates the full EDPRP pipeline:
#   1. Upload the raw customers file from local disk to S3.
#   2. Copy the file from the S3 stage into the Snowflake
#      BRONZE.CUSTOMERS table.
# It exits with a non-zero code if any step fails, so the
# pipeline can be wired into a scheduler (cron, Airflow, etc.).
# ============================================================

import os
import sys

# Prepend the project root to sys.path so that package imports
# (e.g. "scripts.upload_to_s3") work no matter where main.py is run from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.upload_to_s3 import upload_file_to_s3
from scripts.load_customers_from_s3_to_snowflake import load_customers


def main():
    print("Starting EDPRP pipeline...")

    # Step 1: Upload the local customers file to S3.
    upload_file_to_s3()

    # Step 2: Load the staged file from S3 into Snowflake (BRONZE.CUSTOMERS).
    success = load_customers()
    if not success:
        # load_customers() returns False on error, so abort the pipeline here.
        print("Customer load failed. Pipeline aborted.")
        sys.exit(1)

    print("Pipeline completed successfully.")


if __name__ == "__main__":
    main()

