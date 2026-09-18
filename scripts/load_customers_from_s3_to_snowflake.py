# Firstly install connector using pip install snowflake-connector-python

import os
import boto3
import snowflake.connector

try:
    from scripts.logging_config import setup_logging, get_logger
except ImportError:
    from logging_config import setup_logging, get_logger

logger = get_logger()


# ============================================================
# Snowflake Configuration
# ============================================================

SNOWFLAKE_ACCOUNT = "AO72901.ap-southeast-7.aws"
SNOWFLAKE_USER = "RAHULSINGH"
SNOWFLAKE_PASSWORD = "Rahul@12345678"
SNOWFLAKE_WAREHOUSE = "COMPUTE_WH"
SNOWFLAKE_DATABASE = "ECOMMERCE_DB"
SNOWFLAKE_SCHEMA = "BRONZE"


# ============================================================
# S3 Bucket / Folder Configuration
# ============================================================
# The customers file is first uploaded to the "raw" S3 folder.
# After the Snowflake COPY is attempted, the file is moved:
#   - raw      -> archive   when the file is loaded successfully
#   - raw      -> rejected  when the file fails to load
# ============================================================

S3_BUCKET = "amz-s3-data-snow-ap-thailand"

RAW_S3_FOLDER = "raw/customers/"
ARCHIVE_S3_FOLDER = "archive/customers/"
REJECTED_S3_FOLDER = "rejected/customers/"


# ============================================================
# S3 / Snowflake Stage
# ============================================================

STAGE_NAME = "S3_CUSTOMERS_STAGE"

TABLE_NAME = "CUSTOMERS"


# ============================================================
# Move File Within S3
# ============================================================
# S3 has no native "move", so we copy the object to the target
# folder and then delete the original object afterwards.
# If any step fails an error is raised and the file is NOT moved.
# ============================================================

def move_s3_file(s3_client, bucket, source_folder, target_folder, file_name):

    # Build the full S3 keys (folder + file name)
    source_key = source_folder + file_name
    target_key = target_folder + file_name

    # Copy the object from the source to the target location
    s3_client.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": source_key},
        Key=target_key
    )

    # Delete the original object now that the copy exists
    s3_client.delete_object(
        Bucket=bucket,
        Key=source_key
    )

    logger.info("  File moved: %s -> %s", source_key, target_key)


# ============================================================
# Load Customer Data
# ============================================================

def load_customers():

    conn = None
    cursor = None

    try:

        logger.info("Connecting to Snowflake...")

        conn = snowflake.connector.connect(
            account=SNOWFLAKE_ACCOUNT,
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE,
            schema=SNOWFLAKE_SCHEMA
        )

        cursor = conn.cursor()

        logger.info("Connected successfully.")

        # ----------------------------------------------------
        # COPY data from S3 stage into Snowflake table
        # ----------------------------------------------------

        copy_sql = f"""
        COPY INTO {SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.{TABLE_NAME}
        FROM @{SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.{STAGE_NAME}
        FILE_FORMAT = (
            FORMAT_NAME = '{SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.CSV_FORMAT'
        )
        --ON_ERROR = 'ABORT_STATEMENT';
        ON_ERROR = 'CONTINUE';
        """

        # --------------------------------------------------------
        # ON_ERROR options
        #   ABORT_STATEMENT : stop the COPY WHEN an error occurs
        #   CONTINUE        : load valid rows, skip erroneous rows
        #   SKIP_FILE       : skip the whole file if an error occurs
        #   SKIP_FILE_num   : skip the file after given # of errors
        #   SKIP_FILE_num%  : skip file when error % is exceeded
        # --------------------------------------------------------

        logger.info("Loading customer data from S3...")

        cursor.execute(copy_sql)

        # One result row is returned per file in the stage.
        # row info: [source_file, status, rows_parsed, rows_loaded, ...]
        # status can be 'LOADED', 'PARTIALLY_LOADED' or 'LOAD_FAILED'.
        results = cursor.fetchall()

        print("\nLoad Result:")

        s3 = boto3.client("s3")

        # If COPY processed no files (e.g. every file in the stage was
        # already loaded in a previous run), Snowflake returns a single
        # summary row with one column instead of per-file result rows.
        if len(results) == 1 and len(results[0]) == 1:
            logger.info(results[0][0])
            logger.info("No new files to load (already loaded in a previous run).")
            return True

        all_loaded = True

        for row in results:

            logger.info(row)

            # row[0] is the full S3 path (e.g. s3://bucket/raw/customers/xxx.csv).
            # Extract just the file name for the S3 copy/delete below.
            file_name = os.path.basename(row[0])
            status = row[1]

            # --------------------------------------------------
            # Success: move the file to the archive folder
            # --------------------------------------------------

            if status == "LOADED":

                logger.info("  File loaded successfully: %s", file_name)

                move_s3_file(
                    s3,
                    S3_BUCKET,
                    RAW_S3_FOLDER,
                    ARCHIVE_S3_FOLDER,
                    file_name
                )

            # --------------------------------------------------
            # Failure: move the file to the rejected folder
            # --------------------------------------------------

            else:

                logger.warning("  File FAILED to load: %s (status = %s)", file_name, status)

                all_loaded = False

                move_s3_file(
                    s3,
                    S3_BUCKET,
                    RAW_S3_FOLDER,
                    REJECTED_S3_FOLDER,
                    file_name
                )

        conn.commit()

        # ------------------------------------------------------
        # Final status of the whole customer load
        # ------------------------------------------------------

        if all_loaded:
            logger.info("Customer data loaded successfully.")
            return True

        logger.error("Customer data load FAILED. Review the rejected rows above.")
        return False

    except Exception as e:

        logger.error("ERROR while loading customer data:")
        logger.exception(e)

        return False

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

        logger.info("Snowflake connection closed.")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    setup_logging()

    success = load_customers()

    if success:
        logger.info("CUSTOMER LOAD STATUS: SUCCESS")
    else:
        logger.error("CUSTOMER LOAD STATUS: FAILED")