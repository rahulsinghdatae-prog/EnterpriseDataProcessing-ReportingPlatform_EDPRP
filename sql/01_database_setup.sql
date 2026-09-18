-- ============================================================
-- 01. EDPRP Database Setup
-- ============================================================
-- Purpose:
--   One-time bootstrap script that creates the database,
--   schemas and adapters used by the EDPRP pipeline.
--
-- Layer definitions (medallion architecture):
--   BRONZE  -> raw data as it arrived (no transformation)
--   SILVER  -> cleaned / standardized / deduplicated data
--   GOLD    -> business-ready aggregates and wide tables
--   CONTROL -> metadata / audit tables (load runs, batches)
--
-- Run order: 01 -> 02 (bronze) -> 03 (silver) -> 04 (gold)
-- ============================================================


-- ============================================================
-- Create Database (if it does not exist yet)
-- ============================================================

CREATE DATABASE IF NOT EXISTS ECOMMERCE_DB;


-- ============================================================
-- Create Schemas (one per data layer)
-- ============================================================

-- Raw / ingestion layer: holds COPY target tables
CREATE SCHEMA IF NOT EXISTS ECOMMERCE_DB.BRONZE;

-- Cleansed layer: standardized, validated, deduplicated data
CREATE SCHEMA IF NOT EXISTS ECOMMERCE_DB.SILVER;

-- Business-ready layer: aggregates / facts used for reporting
CREATE SCHEMA IF NOT EXISTS ECOMMERCE_DB.GOLD;

-- Control / audit layer: load metadata and run tracking
CREATE SCHEMA IF NOT EXISTS ECOMMERCE_DB.CONTROL;


-- ============================================================
-- Diagnostic Queries (manual sanity checks)
-- ============================================================

-- Which warehouse is currently active for the session?
SELECT CURRENT_WAREHOUSE();

-- List all warehouses available in the account
SHOW WAREHOUSES;

-- Which user is executing this session?
SELECT CURRENT_USER();

-- Show stages that already exist in the BRONZE schema
SHOW STAGES IN SCHEMA ECOMMERCE_DB.BRONZE;

-- Account and region of the current Snowflake account
SELECT CURRENT_ACCOUNT(), CURRENT_REGION();


-- ============================================================
-- Query History (audit / troubleshooting)
-- ============================================================
-- Show the last 100 executed queries with their status and
-- execution time. Useful to track what the pipeline ran.
-- ============================================================

SELECT
    query_id,
    query_text,
    execution_status,
    start_time
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    RESULT_LIMIT => 100
))
ORDER BY start_time DESC;