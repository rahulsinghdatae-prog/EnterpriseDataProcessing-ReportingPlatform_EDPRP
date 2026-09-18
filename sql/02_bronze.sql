-- ============================================================
-- 02. Bronze Layer - ECOMMERCE_DB.BRONZE
-- ============================================================
-- Purpose:
--   The BRONZE layer stores the raw data exactly as it was
--   received from the source system (S3 CSV files). No
--   transformation or business logic is applied here.
--
-- Components created by this script:
--   1. CUSTOMERS table       -> raw landing table
--   2. CSV_FORMAT format     -> parser for the CSV files
--   3. S3 Storage Integration-> trust link role: Snowflake <-> AWS S3
--   4. S3_CUSTOMERS_STAGE    -> stage pointing to raw S3 folder
-- ============================================================


-- ============================================================
-- 1. Bronze Landing Table: CUSTOMERS
-- ============================================================
-- Stores each CSV row plus auditing columns so we know exactly
-- which source file and batch produced every record.
-- ============================================================

CREATE TABLE IF NOT EXISTS ECOMMERCE_DB.BRONZE.CUSTOMERS (
    CUSTOMER_ID NUMBER,          -- Customer business key from source
    FIRST_NAME VARCHAR(100),     -- Customer first name
    LAST_NAME VARCHAR(100),      -- Customer last name
    EMAIL VARCHAR(200),          -- Customer email address
    CITY VARCHAR(100),           -- City of residence
    STATE VARCHAR(100),          -- State / province
    COUNTRY VARCHAR(100),        -- Country
    SOURCE_FILE_NAME VARCHAR(500), -- Which S3 file this row came from
    LOAD_TIMESTAMP VARCHAR(100),  -- When the row was loaded
    BATCH_ID VARCHAR(100)          -- Batch / run identifier
);


-- ============================================================
-- 2. CSV File Format: BRONZE.CSV_FORMAT
-- ============================================================
-- Defines how the incoming CSV files are parsed.
-- ============================================================

CREATE OR REPLACE FILE FORMAT BRONZE.CSV_FORMAT
TYPE = CSV
FIELD_DELIMITER = ','
SKIP_HEADER = 1                     -- First line is a header, skip it
FIELD_OPTIONALLY_ENCLOSED_BY = '"'  -- Fields may be quoted
TRIM_SPACE = TRUE                   -- Trim leading/trailing spaces
EMPTY_FIELD_AS_NULL = TRUE ;         -- Empty fields become NULL


-- ============================================================
-- Work in the BRONZE schema for the statements below
-- ============================================================

USE DATABASE ECOMMERCE_DB;
USE SCHEMA BRONZE;


-- ============================================================
-- 3. Storage Integration: S3_ECOMMERCE_INTEGRATION
-- ============================================================
-- Links Snowflake to the AWS S3 bucket using the IAM role
-- below, so Snowflake can read the raw files directly.
-- ============================================================

DESC FILE FORMAT ECOMMERCE_DB.BRONZE.CSV_FORMAT;

CREATE OR REPLACE STORAGE INTEGRATION S3_ECOMMERCE_INTEGRATION
TYPE = EXTERNAL_STAGE
STORAGE_PROVIDER = 'S3'
ENABLED = TRUE
STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::470451076022:role/amz-EDPRP-Snowflake-S3-Role-Thailand'
STORAGE_ALLOWED_LOCATIONS = (
    's3://amz-s3-data-snow-ap-thailand/raw/customers/'
);

DESC STORAGE INTEGRATION S3_ECOMMERCE_INTEGRATION;
/*
Reference values (do not enable unless the role setup changes):
STORAGE_AWS_IAM_USER_ARN = 'arn:aws:iam::192929863221:user/ebt62000-s';
STORAGE_AWS_ROLE_ARN      = 'arn:aws:iam::470451076022:role/amz-EDPRP-Snowflake-S3-Role-Thailand';
STORAGE_AWS_EXTERNAL_ID   = 'AO72901_SFCRole=4_+cgqSEDoRvi1NH/yjK1Tmzc8nak=';
*/


-- ============================================================
-- 4. External Stage: S3_CUSTOMERS_STAGE
-- ============================================================
-- Points to the raw customers folder in S3 and uses the CSV
-- file format created above. COPY INTO reads from this stage.
-- ============================================================

CREATE OR REPLACE STAGE ECOMMERCE_DB.BRONZE.S3_CUSTOMERS_STAGE
URL = 's3://amz-s3-data-snow-ap-thailand/raw/customers/'
STORAGE_INTEGRATION = S3_ECOMMERCE_INTEGRATION
FILE_FORMAT = ECOMMERCE_DB.BRONZE.CSV_FORMAT;


-- ============================================================
-- Manual Checks (run these to inspect the stage)
-- ============================================================

-- List the files currently staged in S3
LIST @ECOMMERCE_DB.BRONZE.S3_CUSTOMERS_STAGE;

-- Preview the raw staged rows (untyped, as parsed)
select $1, $2, $3, $4, $5, $6, $7, $8, $9, $10 from @ECOMMERCE_DB.BRONZE.S3_CUSTOMERS_STAGE;

select * from ECOMMERCE_DB.BRONZE.CUSTOMERS;