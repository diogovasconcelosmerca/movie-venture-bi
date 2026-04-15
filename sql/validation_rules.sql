-- ============================================================
-- DATA QUALITY VALIDATION RULES
-- STG_MAD_MOVIES Warehouse
-- Movie Venture BI Project — Group 81, Nova IMS (2025/2026)
--
-- These rules are executed by PL_MAD_MOVIES_VALIDATE_STG
-- Results are logged to log_quality_checks
-- ============================================================


-- ============================================================
-- RULE 1: Check Integrity of Business Key (no repeated BKs)
-- Applied to: All dimension tables
-- ============================================================

-- Example: stg_dim_film
INSERT INTO STG_MAD_MOVIES.dbo.log_quality_checks
SELECT 1 AS ID_CHECK,
    'Staging Area' AS ETL_PHASE,
    'stg_dim_film' AS ETL_TABLE,
    'check integrity of BK' AS ETL_CHECKTYPE,
    'number of rows with repeated BK: ' +
        str(count(row_count)) AS DESCRIPTION_RESULT,
    CASE
        WHEN count(row_count) > 0 THEN 'FAIL'
        ELSE 'OK'
    END AS ETL_RESULT
FROM (
    SELECT bk_film, COUNT(*) AS row_count
    FROM STG_MAD_MOVIES.dbo.stg_dim_film
    GROUP BY bk_film
    HAVING COUNT(*) > 1
) duplicates;


-- ============================================================
-- RULE 2: Check Uniqueness of All Dimension Attributes
-- Uses NULL-safe comparison to handle nullable columns
-- Applied to: All dimension tables
-- ============================================================

-- Investigation query: Find attribute-level duplicates in dim_film
SELECT f.*
FROM STG_MAD_MOVIES.dbo.stg_dim_film f
JOIN (
    SELECT
        film_title,
        film_release_year,
        film_runtime_min,
        primary_language_film,
        main_filming_country
    FROM STG_MAD_MOVIES.dbo.stg_dim_film
    GROUP BY
        film_title,
        film_release_year,
        film_runtime_min,
        primary_language_film,
        main_filming_country
    HAVING COUNT(*) > 1
) d
ON f.film_title = d.film_title
AND ( (f.film_release_year = d.film_release_year)
      OR (f.film_release_year IS NULL AND d.film_release_year IS NULL) )
AND ( (f.film_runtime_min = d.film_runtime_min)
      OR (f.film_runtime_min IS NULL AND d.film_runtime_min IS NULL) )
AND ( (f.primary_language_film = d.primary_language_film)
      OR (f.primary_language_film IS NULL AND d.primary_language_film IS NULL) )
AND ( (f.main_filming_country = d.main_filming_country)
      OR (f.main_filming_country IS NULL AND d.main_filming_country IS NULL) )
ORDER BY f.film_title, f.film_release_year, f.bk_film;


-- ============================================================
-- RULE 3: Check Integrity of Fact PK (Composite Key)
-- ============================================================

INSERT INTO STG_MAD_MOVIES.dbo.log_quality_checks
SELECT 3 AS ID_CHECK,
    'Staging Area' AS ETL_PHASE,
    'stg_fact_daily_box_office' AS ETL_TABLE,
    'check integrity of fact PK (combo all FKs)' AS ETL_CHECKTYPE,
    'number of rows with repeated PK: ' +
        str(count(row_count)) AS DESCRIPTION_RESULT,
    CASE
        WHEN count(row_count) > 0 THEN 'FAIL'
        ELSE 'OK'
    END AS ETL_RESULT
FROM (
    SELECT fk_date, fk_film, fk_production_company, fk_director, fk_actor,
           COUNT(*) AS row_count
    FROM STG_MAD_MOVIES.dbo.stg_fact_daily_box_office
    GROUP BY fk_date, fk_film, fk_production_company, fk_director, fk_actor
    HAVING COUNT(*) > 1
) duplicates;


-- ============================================================
-- RULE 4: Check Parent of FK (no orphan records)
-- Applied to: All FK relationships in fact table
-- ============================================================

-- Example: FK for Actor dimension
INSERT INTO STG_MAD_MOVIES.dbo.log_quality_checks
SELECT 4 AS ID_CHECK,
    'Staging Area' AS ETL_PHASE,
    'stg_fact_daily_box_office' AS ETL_TABLE,
    'check parent of FK for Actor dimension' AS ETL_CHECKTYPE,
    'number of rows without parent key: ' +
        str(count(*)) AS DESCRIPTION_RESULT,
    CASE
        WHEN count(*) > 0 THEN 'FAIL'
        ELSE 'OK'
    END AS ETL_RESULT
FROM STG_MAD_MOVIES.dbo.stg_fact_daily_box_office fact
LEFT JOIN STG_MAD_MOVIES.dbo.stg_dim_actor dim
    ON fact.fk_actor = dim.bk_actor
WHERE dim.bk_actor IS NULL;


-- ============================================================
-- RULE 5: Business Rule — Gross Revenue Non-Negative
-- ============================================================

INSERT INTO STG_MAD_MOVIES.dbo.log_quality_checks
SELECT 5 AS ID_CHECK,
    'Staging Area' AS ETL_PHASE,
    'stg_fact_daily_box_office' AS ETL_TABLE,
    'business rule: gross revenue per day must be non-negative' AS ETL_CHECKTYPE,
    'number of rows with negative gross revenue: ' +
        str(count(*)) AS DESCRIPTION_RESULT,
    CASE
        WHEN count(*) > 0 THEN 'FAIL'
        ELSE 'OK'
    END AS ETL_RESULT
FROM STG_MAD_MOVIES.dbo.stg_fact_daily_box_office
WHERE gross_revenue_per_day < 0;


-- ============================================================
-- RULE 6: Business Rule — Days Since Release Non-Negative
-- ============================================================

INSERT INTO STG_MAD_MOVIES.dbo.log_quality_checks
SELECT 6 AS ID_CHECK,
    'Staging Area' AS ETL_PHASE,
    'stg_fact_daily_box_office' AS ETL_TABLE,
    'business rule: days since release must be non-negative' AS ETL_CHECKTYPE,
    'number of rows with negative days since release: ' +
        str(count(*)) AS DESCRIPTION_RESULT,
    CASE
        WHEN count(*) > 0 THEN 'FAIL'
        ELSE 'OK'
    END AS ETL_RESULT
FROM STG_MAD_MOVIES.dbo.stg_fact_daily_box_office
WHERE days_since_release < 0;


-- ============================================================
-- RULE 7: Business Rule — Revenue Rows Must Have Days Since Release
-- ============================================================

INSERT INTO STG_MAD_MOVIES.dbo.log_quality_checks
SELECT 7 AS ID_CHECK,
    'Staging Area' AS ETL_PHASE,
    'stg_fact_daily_box_office' AS ETL_TABLE,
    'business rule: revenue rows must have days_since_release' AS ETL_CHECKTYPE,
    'number of rows with revenue but missing days_since_release: ' +
        str(count(*)) AS DESCRIPTION_RESULT,
    CASE
        WHEN count(*) > 0 THEN 'FAIL'
        ELSE 'OK'
    END AS ETL_RESULT
FROM STG_MAD_MOVIES.dbo.stg_fact_daily_box_office
WHERE gross_revenue_per_day IS NOT NULL
  AND days_since_release IS NULL;


-- ============================================================
-- INVESTIGATION: Records failing Rule 7
-- ============================================================

SELECT
    f.film_title,
    fact.fk_date,
    fact.gross_revenue_per_day,
    fact.days_since_release
FROM STG_MAD_MOVIES.dbo.stg_fact_daily_box_office fact
JOIN STG_MAD_MOVIES.dbo.stg_dim_film f
    ON fact.fk_film = f.bk_film
WHERE fact.gross_revenue_per_day IS NOT NULL
    AND fact.days_since_release IS NULL
ORDER BY f.film_title, fact.fk_date;


-- ============================================================
-- DW VALIDATION: Verify FK integrity after loading
-- ============================================================

SELECT TOP 10
    f.fk_date,
    d.proper_date,
    f.gross_revenue_per_day,
    f.days_since_release,
    film.film_title
FROM DW_MAD_MOVIES.dbo.fact_daily_box_office f
JOIN DW_MAD_MOVIES.dbo.dim_date d ON f.fk_date = d.sk_date
JOIN DW_MAD_MOVIES.dbo.dim_film film ON f.fk_film = film.sk_film;
