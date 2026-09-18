# ============================================================
# EDPRP Bronze → Silver Promotion
# ============================================================
# This module transforms data that was landed in the BRONZE layer
# and promotes it to the SILVER layer:
#   1. Creates the SILVER schema and table if they don't exist.
#   2. Reads the total record count from BRONZE.CUSTOMERS.
#   3. Cleanses / standardizes the data (trim whitespace, fix
#      case, validate email format, parse timestamps) and inserts
#      only the VALID records into SILVER.CUSTOMERS.
#   4. Every record that FAILS validation is NOT silently dropped:
#      it is written to the ERROR schema (CUSTOMER_ERROR_LOG table)
#      together with the validation rule(s) it violated, so the bad
#      rows can be reviewed and fixed later.
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
# Validation rules that move a Bronze row to the ERROR log
# ============================================================
# Each tuple is: (ERROR_TYPE, ERROR_MESSAGE, SQL condition that marks
# a row as INVALID for that rule).
#
# A single row can violate more than one rule; in that case it is
# written once per violated rule so every problem is captured.
#
# The conditions below are the NEGATION of the checks used in the
# Silver INSERT: whatever a row does NOT satisfy for Silver, it IS
# flagged for the ERROR log.
# ============================================================

ERROR_LOG_RULES = [
    (
        "NULL_CUSTOMER_ID",
        "CUSTOMER_ID is NULL (required field).",
        "CUSTOMER_ID IS NULL"
    ),
    (
        "INVALID_CUSTOMER_ID",
        "CUSTOMER_ID must be a positive number (> 0).",
        "CUSTOMER_ID IS NOT NULL AND CUSTOMER_ID <= 0"
    ),
    (
        "EMPTY_FIRST_NAME",
        "FIRST_NAME is NULL or made up of blank characters.",
        "FIRST_NAME IS NULL OR TRIM(FIRST_NAME) = ''"
    ),
    (
        "EMPTY_LAST_NAME",
        "LAST_NAME is NULL or made up of blank characters.",
        "LAST_NAME IS NULL OR TRIM(LAST_NAME) = ''"
    ),
    (
        "EMPTY_EMAIL",
        "EMAIL is NULL or made up of blank characters.",
        "EMAIL IS NULL OR TRIM(EMAIL) = ''"
    ),
    (
        "INVALID_EMAIL_FORMAT",
        "EMAIL does not match a valid email pattern "
        "(local part @ domain.tld).",
        "EMAIL IS NOT NULL AND TRIM(EMAIL) <> '' "
        "AND NOT REGEXP_LIKE("
        "TRIM(EMAIL), '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$')"
    ),
    (
        "EMPTY_SOURCE_FILE_NAME",
        "SOURCE_FILE_NAME is NULL or made up of blank characters.",
        "SOURCE_FILE_NAME IS NULL OR TRIM(SOURCE_FILE_NAME) = ''"
    ),
    (
        "EMPTY_BATCH_ID",
        "BATCH_ID is NULL or made up of blank characters.",
        "BATCH_ID IS NULL OR TRIM(BATCH_ID) = ''"
    ),
]


# ============================================================
# Bronze → Silver transformation
# ============================================================

def bronze_to_silver():
    """Promote valid, cleansed customer records from BRONZE to SILVER.

    Valid rows are inserted into SILVER.CUSTOMERS. Rows that fail any
    validation rule are written to ERROR.CUSTOMER_ERROR_LOG (one entry
    per violated rule) instead of being dropped, so every rejected
    record stays visible for review.

    Returns True if the promotion succeeded, False otherwise.
    """

    conn = None
    cursor = None

    try:

        logger.info("==============================================")
        logger.info("BRONZE → SILVER PROCESS STARTED")
        logger.info("==============================================")

        conn = get_snowflake_connection()
        cursor = conn.cursor()

        logger.info("Connected to Snowflake successfully.")

        # ----------------------------------------------------
        # Step 1: Create Silver Schema
        # ----------------------------------------------------

        cursor.execute("""
            CREATE SCHEMA IF NOT EXISTS ECOMMERCE_DB.SILVER
        """)

        logger.info("Silver schema verified.")

        # ----------------------------------------------------
        # Step 2: Create Silver Customers Table
        # ----------------------------------------------------
        # The table is created idempotently (IF NOT EXISTS) so a repeat
        # run of the pipeline will reuse the existing table.
        # SILVER_LOAD_TIMESTAMP defaults to insert time so every row
        # records when it first reached the Silver layer.

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ECOMMERCE_DB.SILVER.CUSTOMERS (

                CUSTOMER_ID NUMBER,

                FIRST_NAME VARCHAR(100),

                LAST_NAME VARCHAR(100),

                EMAIL VARCHAR(200),

                CITY VARCHAR(100),

                STATE VARCHAR(100),

                COUNTRY VARCHAR(100),

                SOURCE_FILE_NAME VARCHAR(500),

                LOAD_TIMESTAMP TIMESTAMP_NTZ,

                BATCH_ID VARCHAR(100),

                SILVER_LOAD_TIMESTAMP TIMESTAMP_NTZ
                    DEFAULT CURRENT_TIMESTAMP()

            )
        """)

        logger.info("Silver table verified.")

        # ----------------------------------------------------
        # Step 3: Read Bronze Count
        # ----------------------------------------------------
        # Take a baseline count of the source data so the pipeline log
        # shows how many rows existed in Bronze before the promotion.

        cursor.execute("""
            SELECT COUNT(*)
            FROM ECOMMERCE_DB.BRONZE.CUSTOMERS
        """)

        bronze_count = cursor.fetchone()[0]

        logger.info("Bronze record count: %s", bronze_count)

        # ----------------------------------------------------
        # Step 4: Create Error Schema
        # ----------------------------------------------------
        # The ERROR layer is where rejected rows are kept. Creating the
        # schema this way keeps the promotion script self-contained even
        # if the schema was never created by the SQL setup scripts.

        cursor.execute("""
            CREATE SCHEMA IF NOT EXISTS ECOMMERCE_DB.ERROR
        """)

        logger.info("Error schema verified.")

        # ----------------------------------------------------
        # Step 5: Create Customer Error Log Table
        # ----------------------------------------------------
        # Mirrors the raw Bronze columns (LOAD_TIMESTAMP stays VARCHAR so
        # the ORIGINAL unparsed value is preserved) plus auditing fields:
        #   ERROR_ID            - auto-increment surrogate key
        #   ERROR_TYPE          - which validation rule failed
        #   ERROR_MESSAGE       - human readable description of the rule
        #   ERROR_TIMESTAMP     - when the error was logged

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ECOMMERCE_DB.ERROR.CUSTOMER_ERROR_LOG (

                ERROR_ID NUMBER AUTOINCREMENT,

                CUSTOMER_ID NUMBER,

                FIRST_NAME VARCHAR(100),

                LAST_NAME VARCHAR(100),

                EMAIL VARCHAR(200),

                CITY VARCHAR(100),

                STATE VARCHAR(100),

                COUNTRY VARCHAR(100),

                SOURCE_FILE_NAME VARCHAR(500),

                LOAD_TIMESTAMP VARCHAR(100),

                BATCH_ID VARCHAR(100),

                ERROR_TYPE VARCHAR(100),

                ERROR_MESSAGE VARCHAR(1000),

                ERROR_TIMESTAMP TIMESTAMP_NTZ
                    DEFAULT CURRENT_TIMESTAMP()

            )
        """)

        logger.info("Customer_error_log table verified.")

        # ----------------------------------------------------
        # Step 6: Insert Valid Records into Silver
        # ----------------------------------------------------
        # SELECT ... INSERT only keeps rows that pass validation and
        # standardizes every kept value:
        #   - INITCAP / TRIM fix casing and remove surrounding spaces.
        #   - LOWER normalizes the email address.
        #   - TRY_TO_TIMESTAMP parses the date or converts it to NULL.
        #   - REGEXP_LIKE checks the email has a valid domain format.
        # Rows failing any rule are left in Bronze and then reported to
        # the ERROR log in Step 7 below.

        silver_insert_sql = """

        INSERT INTO ECOMMERCE_DB.SILVER.CUSTOMERS
        (
            CUSTOMER_ID,
            FIRST_NAME,
            LAST_NAME,
            EMAIL,
            CITY,
            STATE,
            COUNTRY,
            SOURCE_FILE_NAME,
            LOAD_TIMESTAMP,
            BATCH_ID
        )

        SELECT
            CUSTOMER_ID,

            INITCAP(TRIM(FIRST_NAME)),

            INITCAP(TRIM(LAST_NAME)),

            LOWER(TRIM(EMAIL)),

            INITCAP(TRIM(CITY)),

            INITCAP(TRIM(STATE)),

            INITCAP(TRIM(COUNTRY)),

            TRIM(SOURCE_FILE_NAME),

            TRY_TO_TIMESTAMP(
                LOAD_TIMESTAMP,
                'DD-MM-YYYY HH24:MI:SS'
            ),

            TRIM(BATCH_ID)

        FROM ECOMMERCE_DB.BRONZE.CUSTOMERS

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

          AND SOURCE_FILE_NAME IS NOT NULL
          AND TRIM(SOURCE_FILE_NAME) <> ''

          AND BATCH_ID IS NOT NULL
          AND TRIM(BATCH_ID) <> ''

        """

        cursor.execute(silver_insert_sql)

        inserted_rows = cursor.rowcount

        logger.info("Rows inserted into Silver: %s", inserted_rows)

        # ----------------------------------------------------
        # Step 7: Insert Rejected Records into the Error Log
        # ----------------------------------------------------
        # Every rule in ERROR_LOG_RULES is checked one by one. A row
        # satisfying a rule's "invalid" condition is copied from Bronze
        # (raw values, unmodified) into ERROR.CUSTOMER_ERROR_LOG along
        # with the rule name and its description.
        # A row may be caught by several rules and therefore appear
        # more than once in the log - one entry per violated rule.

        total_error_rows = 0

        for error_type, error_message, invalid_condition in ERROR_LOG_RULES:

            # Escape any single quotes so the labels are SQL-safe.
            safe_message = error_message.replace("'", "''")

            cursor.execute(f"""
                INSERT INTO ECOMMERCE_DB.ERROR.CUSTOMER_ERROR_LOG
                (
                    CUSTOMER_ID,
                    FIRST_NAME,
                    LAST_NAME,
                    EMAIL,
                    CITY,
                    STATE,
                    COUNTRY,
                    SOURCE_FILE_NAME,
                    LOAD_TIMESTAMP,
                    BATCH_ID,
                    ERROR_TYPE,
                    ERROR_MESSAGE
                )

                SELECT
                    CUSTOMER_ID,
                    FIRST_NAME,
                    LAST_NAME,
                    EMAIL,
                    CITY,
                    STATE,
                    COUNTRY,
                    SOURCE_FILE_NAME,
                    LOAD_TIMESTAMP,
                    BATCH_ID,
                    '{error_type}',
                    '{safe_message}'

                FROM ECOMMERCE_DB.BRONZE.CUSTOMERS

                WHERE {invalid_condition}
            """)

            rule_error_rows = cursor.rowcount

            total_error_rows += rule_error_rows

            if rule_error_rows > 0:
                logger.info(
                    "  %s -> %s rejected row(s) logged",
                    error_type,
                    rule_error_rows
                )

        logger.info("Total rows logged to Customer_error_log: %s", total_error_rows)

        # ----------------------------------------------------
        # Step 8: Commit
        # ----------------------------------------------------
        # Commit the transaction so a later failure cannot roll back the
        # rows that were already promoted / logged.

        conn.commit()

        # ----------------------------------------------------
        # Step 9: Silver + Error Counts
        # ----------------------------------------------------
        # Confirm the promotion and the error capture by reading the
        # total number of rows now in both tables.

        cursor.execute("""
            SELECT COUNT(*)
            FROM ECOMMERCE_DB.SILVER.CUSTOMERS
        """)

        silver_count = cursor.fetchone()[0]

        logger.info("Silver record count: %s", silver_count)

        cursor.execute("""
            SELECT COUNT(*)
            FROM ECOMMERCE_DB.ERROR.CUSTOMER_ERROR_LOG
        """)

        error_log_count = cursor.fetchone()[0]

        logger.info("Customer_error_log record count: %s", error_log_count)

        logger.info("==============================================")
        logger.info("BRONZE → SILVER COMPLETED SUCCESSFULLY")
        logger.info("==============================================")

        return True

    except Exception as e:

        # Roll back any uncommitted work so Bronze/Silver/Error stays intact.
        if conn:
            conn.rollback()

        logger.error("==============================================")
        logger.error("BRONZE → SILVER FAILED")
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
# handlers exist, then execute the Bronze → Silver promotion.
# ============================================================

if __name__ == "__main__":

    setup_logging()

    success = bronze_to_silver()

    if success:
        logger.info("BRONZE → SILVER STATUS: SUCCESS")
    else:
        logger.error("BRONZE → SILVER STATUS: FAILED")