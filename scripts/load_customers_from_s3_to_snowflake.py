# Firstly install connector using pip install snowflake-connector-python

import snowflake.connector

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
# S3 / Snowflake Stage
# ============================================================

STAGE_NAME = "S3_CUSTOMERS_STAGE"

TABLE_NAME = "CUSTOMERS"


# ============================================================
# Load Customer Data
# ============================================================

def load_customers():

    conn = None
    cursor = None

    try:

        print("Connecting to Snowflake...")

        conn = snowflake.connector.connect(
            account=SNOWFLAKE_ACCOUNT,
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE,
            schema=SNOWFLAKE_SCHEMA
        )

        cursor = conn.cursor()

        print("Connected successfully.")

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
     
#| Option            | Meaning                                                     |
#| ----------------- | ----------------------------------------------------------- |
#| `ABORT_STATEMENT` | Stop the current `COPY INTO` statement when an error occurs |
#| `CONTINUE`        | Continue loading valid records and skip erroneous records   |
#| `SKIP_FILE`       | Skip the entire file if an error occurs                     |
#| `SKIP_FILE_num`   | Skip the file after a specified number of errors            |
#| `SKIP_FILE_num%`  | Skip the file after errors exceed a percentage              |


        print("Loading customer data from S3...")

        cursor.execute(copy_sql)

        results = cursor.fetchall()

        print("\nLoad Result:")

        all_loaded = True

        for row in results:
            print(row)
            if row[1] != "LOADED":
                all_loaded = False

        conn.commit()

        if all_loaded:
            print("\nCustomer data loaded successfully.")
            return True

        print("\nCustomer data load FAILED. Review the rejected rows above.")
        return False

    except Exception as e:

        print("\nERROR while loading customer data:")
        print(e)

        return False

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

        print("Snowflake connection closed.")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    success = load_customers()

    if success:
        print("CUSTOMER LOAD STATUS: SUCCESS")
    else:
        print("CUSTOMER LOAD STATUS: FAILED")