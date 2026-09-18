# ============================================================
# EDPRP Silver → Gold Promotion
# ============================================================
# This module transforms data from the SILVER layer and promotes
# it to the GOLD layer:
#   1. Creates the GOLD schema and table if they don't exist.
#   2. Reads the total record count from SILVER.CUSTOMERS.
#   3. Re-validates the business-required columns as a final
#      quality gate and inserts the valid records into
#      GOLD.DIM_CUSTOMER (a cleaned, business-ready dimension).
#
# Rows that fail the Gold-level validation are NOT promoted: they
# are counted and reported in the log so they can be reviewed.
#
# Returns True on success and False on any error, so the pipeline
# orchestrator (main.py) can decide whether to continue.
# ============================================================

import snowflake.connector

try:
    from scripts.logging_config import get_logger, setup_logging
except ImportError:
    from logging_config import get_logger, setup_logging

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
# Connect to Snowflake
# ============================================================

def get_snowflake_connection():
    """Open and return a new Snowflake connection using the config above."""

    conn = snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA
    )

    return conn


# ============================================================
# Silver → Gold transformation
# ============================================================

def silver_to_gold():
    """Promote validated customer records from SILVER to GOLD.

    The Gold-level validation below acts as a second quality gate on
    top of the Bronze → Silver cleanse. Only records that still pass
    the required-column checks are inserted into GOLD.DIM_CUSTOMER.

    Returns True if the promotion succeeded, False otherwise.
    """

    conn = None
    cursor = None

    try:

        logger.info("==============================================")
        logger.info("SILVER → GOLD PROCESS STARTED")
        logger.info("==============================================")

        conn = get_snowflake_connection()
        cursor = conn.cursor()

        logger.info("Connected to Snowflake successfully.")

        # ----------------------------------------------------
        # Step 1: Create Gold Schema
        # ----------------------------------------------------

        cursor.execute("""
            CREATE SCHEMA IF NOT EXISTS ECOMMERCE_DB.GOLD
        """)

        logger.info("Gold schema verified.")

        # ----------------------------------------------------
        # Step 2: Create Gold Customer Dimension Table
        # ----------------------------------------------------
        # GOLD tables are business-ready. DIM_CUSTOMER extends the
        # Silver data with derived fields:
        #   - FULL_NAME           -> concatenated first + last name
        #   - GOLD_LOAD_TIMESTAMP -> when the row entered GOLD
        # SILVER_LOAD_TIMESTAMP is carried over to keep lineage.

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ECOMMERCE_DB.GOLD.DIM_CUSTOMER (

                CUSTOMER_ID NUMBER,

                FULL_NAME VARCHAR(201),

                FIRST_NAME VARCHAR(100),

                LAST_NAME VARCHAR(100),

                EMAIL VARCHAR(200),

                CITY VARCHAR(100),

                STATE VARCHAR(100),

                COUNTRY VARCHAR(100),

                SOURCE_FILE_NAME VARCHAR(500),

                LOAD_TIMESTAMP TIMESTAMP_NTZ,

                BATCH_ID VARCHAR(100),

                SILVER_LOAD_TIMESTAMP TIMESTAMP_NTZ,

                GOLD_LOAD_TIMESTAMP TIMESTAMP_NTZ
                    DEFAULT CURRENT_TIMESTAMP()

            )
        """)

        logger.info("Gold customer table verified.")

        # ----------------------------------------------------
        # Step 3: Read Silver Count
        # ----------------------------------------------------
        # Baseline count of the source data so the log shows how many
        # rows existed in Silver before the promotion.

        cursor.execute("""
            SELECT COUNT(*)
            FROM ECOMMERCE_DB.SILVER.CUSTOMERS
        """)

        silver_count = cursor.fetchone()[0]

        logger.info("Silver record count: %s", silver_count)

        # ----------------------------------------------------
        # Step 4: Insert Valid Records into Gold
        # ----------------------------------------------------
        # The WHERE clause re-checks the business-required columns as a
        # final validation gate before a row reaches the GOLD layer:
        #
        #   1) NOT-NULL / NON-EMPTY CHECK
        #      CUSTOMER_ID, FIRST_NAME, LAST_NAME and EMAIL must not be
        #      NULL and must contain at least one non-space character.
        #
        #   2) RANGE / BUSINESS CHECK
        #      CUSTOMER_ID must be a positive number (> 0).
        #
        #   3) FORMAT / PATTERN CHECK (REGEX)
        #      EMAIL must still match the valid email pattern.
        #
        #   4) LINEAGE CHECK
        #      SILVER_LOAD_TIMESTAMP must be present so every Gold row
        #      keeps an auditable trail back to when it was promoted.
        #
        # Rows failing any check stay in Silver and are counted so the
        # log can report how many were skipped.

        gold_insert_sql = """

        INSERT INTO ECOMMERCE_DB.GOLD.DIM_CUSTOMER
        (
            CUSTOMER_ID,
            FULL_NAME,
            FIRST_NAME,
            LAST_NAME,
            EMAIL,
            CITY,
            STATE,
            COUNTRY,
            SOURCE_FILE_NAME,
            LOAD_TIMESTAMP,
            BATCH_ID,
            SILVER_LOAD_TIMESTAMP
        )

        SELECT
            CUSTOMER_ID,

            TRIM(FIRST_NAME) || ' ' || TRIM(LAST_NAME) AS FULL_NAME,

            FIRST_NAME,

            LAST_NAME,

            EMAIL,

            CITY,

            STATE,

            COUNTRY,

            SOURCE_FILE_NAME,

            LOAD_TIMESTAMP,

            BATCH_ID,

            SILVER_LOAD_TIMESTAMP

        FROM ECOMMERCE_DB.SILVER.CUSTOMERS

        WHERE CUSTOMER_ID IS NOT NULL
          AND CUSTOMER_ID > 0

          AND FIRST_NAME IS NOT NULL
          AND TRIM(FIRST_NAME) <> ''

          AND LAST_NAME IS NOT NULL
          AND TRIM(LAST_NAME) <> ''

          AND EMAIL IS NOT NULL
          AND TRIM(EMAIL) <> ''

          AND REGEXP_LIKE(
              TRIM(EMAIL),
              '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'
          )

          AND SILVER_LOAD_TIMESTAMP IS NOT NULL

        """

        cursor.execute(gold_insert_sql)

        inserted_rows = cursor.rowcount

        logger.info("Rows inserted into Gold: %s", inserted_rows)

        # ----------------------------------------------------
        # Step 5: Report Skipped (Rejected) Rows
        # ----------------------------------------------------
        # Any Silver row that failed the Gold validation above stays in
        # the Silver table. The difference between the source count and
        # the inserted count is reported here for visibility.

        rejected_rows = silver_count - inserted_rows

        if rejected_rows > 0:
            logger.warning(
                "Records skipped (failed Gold validation): %s",
                rejected_rows
            )
        else:
            logger.info("No records were skipped: all rows passed validation.")

        # ----------------------------------------------------
        # Step 6: Commit
        # ----------------------------------------------------
        # Commit the transaction so the promoted rows are persisted.

        conn.commit()

        # ----------------------------------------------------
        # Step 7: Gold Count
        # ----------------------------------------------------
        # Confirm the promotion by reading the total number of rows now
        # in the Gold dimension table.

        cursor.execute("""
            SELECT COUNT(*)
            FROM ECOMMERCE_DB.GOLD.DIM_CUSTOMER
        """)

        gold_count = cursor.fetchone()[0]

        logger.info("Gold record count: %s", gold_count)

        logger.info("==============================================")
        logger.info("SILVER → GOLD COMPLETED SUCCESSFULLY")
        logger.info("==============================================")

        return True

    except Exception as e:

        # Roll back any uncommitted work so Silver/Gold stays intact.
        if conn:
            conn.rollback()

        logger.error("==============================================")
        logger.error("SILVER → GOLD FAILED")
        logger.error("==============================================")

        logger.error("Error: %s", e)

        return False

    finally:

        # Always release the cursor and connection, even on failure.
        if cursor:
            cursor.close()

        if conn:
            conn.close()

        logger.info("Snowflake connection closed.")


# ============================================================
# Main
# ============================================================
# When run directly, configure logging first so the console/file
# handlers exist, then execute the Silver → Gold promotion.
# ============================================================

if __name__ == "__main__":

    setup_logging()

    success = silver_to_gold()

    if success:
        logger.info("SILVER → GOLD STATUS: SUCCESS")
    else:
        logger.error("SILVER → GOLD STATUS: FAILED")