# Architecture Documentation

## 1. Architecture Overview

The Movie Venture BI platform follows a **Medallion Architecture** implemented entirely within **Microsoft Fabric**. Data flows through four distinct layers, each with clear responsibilities:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL DATA SOURCES                            │
│                                                                         │
│   Box Office Mojo ──> Python Notebooks ──> TMDb / OMDb / Wikidata APIs │
│   (manual collection)   (5 iterations)      (enrichment)                │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: SOURCE DATA                                                   │
│                                                                         │
│  Lakehouse: LH_SOURCES_MAD_MOVIES                                       │
│  8 source CSVs (Actor, Film, Director, Production Company,              │
│  Daily Box Office, Final Data Set, treat/treated datasets)              │
│                                                                         │
│  Dataflows Gen2: 6 entity-specific transforms + missing values/BK       │
│  Pipeline: PL_MAD_MOVIES_SPLIT_SOURCE_FILES                             │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: STAGING AREA                                                  │
│                                                                         │
│  Warehouse: STG_MAD_MOVIES                                              │
│  Tables: stg_dim_actor, stg_dim_date, stg_dim_director,                 │
│          stg_dim_film, stg_dim_production_company,                      │
│          stg_fact_daily_box_office, log_quality_checks                   │
│                                                                         │
│  Dataflows Gen2: 6 loads (Kimball methodology)                          │
│  Pipelines: PL_MAD_MOVIES_LOAD_STG, PL_MAD_MOVIES_VALIDATE_STG         │
│  Validation: 17 automated rules (15 OK, 2 FAIL — investigated)         │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: DATA WAREHOUSE                                                │
│                                                                         │
│  Warehouse: DW_MAD_MOVIES                                               │
│  Star Schema: 1 fact + 5 dimensions (surrogate keys)                    │
│  Pipeline: PL_MAD_MOVIES_LOAD_DW                                        │
└───────────────────────┬─────────────────────┬───────────────────────────┘
                        │                     │
                        ▼                     ▼
┌───────────────────────────────┐ ┌───────────────────────────────────────┐
│  LAYER 4A: SEMANTIC MODEL     │ │  LAYER 4B: ML / PREDICTIVE            │
│                               │ │                                       │
│  SM MAD Movies                │ │  NB_Predictive_BQ (Fabric Spark)      │
│  DAX measures + hierarchies   │ │  Genre Trends + Film Tier Prediction  │
│  → Power BI Dashboard         │ │  → Delta tables in Lakehouse          │
└───────────────────────────────┘ └───────────────────────────────────────┘
```

---

## 2. Source Layer (1 SOURCE DATA)

### Data Collection

The primary data source is **Box Office Mojo**, with daily box-office performance tables manually collected into spreadsheets to ensure compliance with the platform's usage policies.

### API Enrichment Pipeline

Data enrichment was performed iteratively across 5 Python notebooks, each building on the previous version:

| Notebook | Phase | Enrichment |
|----------|-------|-----------|
| `01_initial_enrichment` | Film Identification | TMDb + OMDb: lead director, lead actor, IMDb/RT ratings, genre, country, language |
| `02_enrichment_runtime_franchise` | Contextual Expansion | Runtime, franchise/sequel detection, production company country, birth years, Wikidata |
| `03_enrichment_caching_matching` | Accuracy Refinement | Persistent caching, studio hint matching, composite scoring, fuzzy matching (Levenshtein) |
| `04_enrichment_budget_posters` | Financial Data | Budget USD, poster URLs, director/actor birthdates and nationalities |
| `05_enrichment_company_geo` | Geographic Context | Production company city and continent via TMDb + Wikidata SPARQL queries |

Key technical decisions:
- **Fuzzy title matching** with Levenshtein distance and +/-1 year release tolerance
- **Persistent caching layer** to prevent unnecessary API calls and ensure reproducibility
- **Multi-source fallback**: TMDb as primary, OMDb for ratings gaps, Wikidata for geographic metadata

### Fabric Components

| Component | Type | Owner | Purpose |
|-----------|------|-------|---------|
| LH_SOURCES_MAD_MOVIES | Lakehouse | Diogo Merca | Store raw and enriched source CSVs |
| DF create Actor source data | Dataflow Gen2 | Madalina Noje | Split and load actor data |
| DF create Daily Box Office source data | Dataflow Gen2 | Madalina Noje | Split and load daily box office data |
| DF create Director source data | Dataflow Gen2 | Madalina Noje | Split and load director data |
| DF create Film source data | Dataflow Gen2 | Madalina Noje | Split and load film data |
| DF create Production Company source data | Dataflow Gen2 | Madalina Noje | Split and load production company data |
| DF missing values and BK treatment | Dataflow Gen2 | Madalina Noje | Handle missing values and business key construction |
| PL_MAD_MOVIES_SPLIT_SOURCE_FILES | Pipeline | Madalina Noje | Orchestrate parallel dataflow execution |

### Source Files in Lakehouse

| File | Size | Description |
|------|------|------------|
| Actor source data.csv | 4 MB | Actor attributes |
| Daily box office source data.csv | 9 MB | Daily revenue records |
| Director source data.csv | 3 MB | Director attributes |
| Film source data.csv | 12 MB | Film metadata |
| Final Data Set.csv | 12 MB | Consolidated enriched dataset |
| Production Company source data.csv | 5 MB | Company attributes |
| treat_dataset.csv | 20 MB | Intermediate treated data |
| treated_dataset.csv | 20 MB | Final treated data |

---

## 3. Staging Layer (2 STAGING AREA)

### Purpose

The Staging Area is a governed intermediary between source data and the analytical Data Warehouse. It uses **business keys** (not surrogate keys), preserves source semantics, and enforces data quality rules before downstream loading.

### Staging Dataflows (Kimball Methodology)

Each Dataflow Gen2 applies Power Query transformations following Kimball dimensional modeling principles:

| Dataflow | Target Table | Key Transformations |
|----------|-------------|-------------------|
| DF STG DIM Actor | stg_dim_actor | Data type standardization, name splitting |
| DF STG Dim Date | stg_dim_date | Kimball date dimension construction: calendar_season, is_holiday, marketing_season, weekday_type, holiday classification |
| DF STG Dim Director | stg_dim_director | Data type standardization, name splitting |
| DF STG Dim Film | stg_dim_film | Award parsing, genre semantic resolution, non-numeric placeholder handling, deduplication |
| DF STG Dim Production Company | stg_dim_production_company | Geographic attribute standardization |
| DF STG Fact Daily Box Office | stg_fact_daily_box_office | Nullable measure handling, FK alignment |

### Staging Table Schemas

**stg_dim_date** (Kimball-compliant):

| Attribute | Type | Description |
|-----------|------|------------|
| sk_date | INT | Surrogate key (YYYYMMDD format) |
| proper_date | DATE | Calendar date |
| full_date | VARCHAR(50) | Full date string |
| monthday_number | INT | Day of month |
| weekday_number | INT | Day of week (1-7) |
| weekday_name | VARCHAR(50) | Monday, Tuesday, etc. |
| weekday_type | VARCHAR(10) | Weekday / Weekend |
| weekday_name_short | VARCHAR(10) | Mon, Tue, etc. |
| month_number | INT | Month (1-12) |
| month_name | VARCHAR(50) | January, February, etc. |
| month_name_short | VARCHAR(50) | Jan, Feb, etc. |
| calendar_season | VARCHAR(20) | Winter, Spring, Summer, Fall |
| is_holiday | BIT | Holiday flag |
| holiday_name | VARCHAR(50) | Holiday name (nullable) |
| marketing_season | VARCHAR(50) | Award season, Holiday season, etc. |
| calendar_year | INT | Year |

**stg_dim_film**:

| Attribute | Type | Description |
|-----------|------|------------|
| bk_film | VARCHAR(400) | Business key |
| film_title | VARCHAR(200) | Film title |
| film_release_year | INT | Year of release |
| film_genre | VARCHAR(100) | Genre classification |
| film_age_classification | VARCHAR(100) | Age rating (PG-13, R, etc.) |
| primary_language_film | VARCHAR(100) | Primary spoken language |
| secondary_language_film | VARCHAR(100) | Secondary language |
| film_runtime_min | INT | Runtime in minutes |
| imdb_rating | DECIMAL(3,1) | IMDb score |
| rt_rating | DECIMAL(4,1) | Rotten Tomatoes score |
| film_budget_usd | DECIMAL(18,2) | Production budget |
| main_filming_country | VARCHAR(100) | Primary filming location |
| secondary_filming_country | VARCHAR(100) | Secondary filming location |
| tertiary_filming_country | VARCHAR(100) | Tertiary filming location |
| film_awards_won | INT | Total award wins |
| film_awards_nominations | INT | Total nominations |
| film_oscars_won | INT | Oscar wins |
| film_oscar_nominations | INT | Oscar nominations |

### Pipelines

| Pipeline | Purpose |
|----------|---------|
| PL_MAD_MOVIES_LOAD_STG | Orchestrate all 6 staging dataflows |
| PL_MAD_MOVIES_VALIDATE_STG | Execute 17 validation rules and log results |

---

## 4. Data Quality Framework

### Overview

A custom data quality framework was built using a `log_quality_checks` table that stores the results of every automated validation rule. This approach provides full auditability and makes quality issues visible rather than silently correcting them.

### log_quality_checks Schema

| Attribute | Type | Description |
|-----------|------|------------|
| id_check | INT | Rule identifier |
| etl_phase | VARCHAR(20) | Phase (Staging Area) |
| etl_table | VARCHAR(100) | Target table |
| etl_checktype | VARCHAR(150) | Type of check |
| description_result | VARCHAR(150) | Detailed result description |
| etl_result | VARCHAR(10) | OK or FAIL |

### Validation Rules

| ID | Rule | Tables | Check Type |
|----|------|--------|-----------|
| 1 | BK integrity | All dims | No repeated business keys |
| 2 | Attribute uniqueness | All dims | No duplicate attribute combinations (NULL-safe) |
| 3 | Fact PK integrity | Fact table | No repeated composite keys |
| 4 | FK parent existence | Fact table | No orphan records (all FKs reference valid parents) |
| 5 | Revenue non-negative | Fact table | gross_revenue_per_day >= 0 |
| 6 | Days non-negative | Fact table | days_since_release >= 0 |
| 7 | Revenue completeness | Fact table | Revenue rows must have days_since_release |

### Results

**15 out of 17 rules passed.** Two failures were identified and investigated:

1. **Rule 2 on dim_film** (FAIL): 2 rows with non-unique attribute combinations but different business keys — films differentiated only by production company
2. **Rule 7 on fact** (FAIL): Revenue records with missing days_since_release — data limitation from source

Both failures were documented and accepted as known data limitations rather than silently corrected.

---

## 5. Data Warehouse Layer

### Star Schema Design

The Data Warehouse uses a **star schema** centered on `fact_daily_box_office`:

- **Grain**: One record per Film x Date
- **Fact table**: `fact_daily_box_office` (gross_revenue_per_day, days_since_release)
- **Dimensions**: dim_date, dim_film, dim_actor, dim_director, dim_production_company
- **Surrogate keys**: Generated via `ROW_NUMBER() OVER (ORDER BY bk_*)` during DW loading

### DW Loading Pipeline

```
PL_MAD_MOVIES_LOAD_DW
═════════════════════════════════════════════════════════════════

  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │ SQL clear    │    │ SQL clear    │    │    Wait      │
  │ fact Daily   │──>│ ALL          │──>│              │
  │ Box Office   │    │ dimensions   │    │              │
  └──────────────┘    └──────────────┘    └──────┬───────┘
                                                  │
                          ┌───────────────────────┼───────────────────┐
                          │                       │                   │
                          ▼                       ▼                   ▼
                   ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
                   │ CD load Dim │    │ CD load Dim  │    │ CD load Dim  │
                   │ Film to DW  │    │ Actor to DW  │    │ Director     │
                   └─────────────┘    └──────────────┘    │ to DW        │
                                                          └──────────────┘
                          │                       │                   │
                          └───────────────────────┼───────────────────┘
                                                  │
                                           ┌──────┴───────┐
                                           │    Wait      │
                                           └──────┬───────┘
                                                  │
                                                  ▼
                                      ┌──────────────────┐
                                      │ CD load Fact     │
                                      │ Daily Box Office │
                                      │ to DW            │
                                      └──────────────────┘
```

Surrogate keys are generated at load time using SQL queries:
```sql
SELECT
    row_number() OVER (ORDER BY bk_actor ASC) AS sk_actor,
    *
FROM STG_MAD_MOVIES.dbo.stg_dim_actor;
```

---

## 6. Master ETL Pipeline

`PL_MAD_MOVIES_MASTER_ETL` orchestrates the entire ETL process as a sequential chain of sub-pipelines:

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ PL split      │     │ PL run STG    │     │ PL validate   │     │ PL run DW     │
│ source file   │────>│ initial       │────>│ Data          │────>│ load          │
│               │     │               │     │               │     │               │
│ Split CSVs    │     │ Load staging  │     │ Run 17 DQ     │     │ Clear + load  │
│ into entities │     │ tables        │     │ rules         │     │ star schema   │
└───────────────┘     └───────────────┘     └───────────────┘     └───────────────┘
```

This design ensures:
- **Separation of concerns**: Each pipeline has a single responsibility
- **Fail-fast behavior**: Validation runs before DW loading
- **Rerunability**: Individual pipelines can be re-executed independently

---

## 7. Semantic Model

**SM MAD Movies** connects to DW_MAD_MOVIES and provides the analytical layer for Power BI.

### DAX Measures

| Measure | Description |
|---------|------------|
| Average Daily Revenue | Mean revenue per day across all records |
| Average Days Since Release | Mean days since release |
| Average IMDb Rating | Mean IMDb score |
| Average RT Rating | Mean Rotten Tomatoes score |
| Avg Actor Revenue | Average total revenue per actor |
| Avg Genre Revenue | Average revenue per genre |
| Avg Genre Days Since Release | Average theatrical run per genre |
| Avg Revenue per Film | Average lifetime revenue per film |
| Avg Weekly Revenue Change | Average week-over-week revenue change |
| KPI Days vs Genre Avg | Film theatrical run vs genre average |
| KPI Revenue vs Actor Avg | Film revenue vs actor average |
| KPI Revenue vs Genre Average | Film revenue vs genre average |
| KPI ROI | Return on investment (revenue / budget) |
| Revenue Last Week | Revenue in the most recent 7 days |
| Revenue per Budget Dollar | Revenue generated per dollar of budget |
| Total Films | Count of distinct films |
| Total Revenue | Sum of all gross revenue |
| Weekly Revenue Change | Week-over-week revenue delta |

### Hierarchies

| Hierarchy | Levels |
|-----------|--------|
| Calendar | Year > Calendar Season > Month |
| Marketing Season | Year > Marketing Season > Is Holiday > Holiday Name |
| Weekday | Type of Weekday > Weekday |
| Actor | Nationality > Surname > First Name |
| Director | Nationality > Surname > First Name |
| Production Company | Continent > Country > City > Production Company |

---

## 8. ML Layer (Predictive Analytics)

### Infrastructure

The predictive notebook (`NB_Predictive_BQ`) runs on **Fabric Spark** and reads from DW_MAD_MOVIES via JDBC with token-based authentication.

### BQ P1: Genre Revenue Trend Forecasting

- **Method**: Linear Regression fitted per genre on annual revenue (2022-2024)
- **Output**: Trend classification (Growing/Declining/Stable) + 2025 revenue projection
- **Threshold**: 5% of mean revenue to classify slope direction
- **Coverage**: 193 distinct genres analyzed
- **Storage**: Delta table `ml_genre_trends`

### BQ P2: Film Tier Classification

- **Objective**: Classify films into High/Mid/Low revenue tiers based on historical performance terciles
- **Candidates**: Random Forest (300 trees, depth 8) vs Gradient Boosting (300 estimators, LR 0.05)
- **Validation**: 5-fold Stratified Cross-Validation
- **Winner**: Random Forest (F1=0.719 vs GBM F1=0.713)
- **Features**: 216 columns after One-Hot Encoding (genre, age classification, season + 6 numeric)
- **Coverage**: 782 films predicted
- **Storage**: Delta table `ml_tier_predictions`

### Feature Importance (Top 5)

| Feature | Importance |
|---------|-----------|
| film_budget_usd | 0.326 |
| film_age_classification_Unknown | 0.113 |
| film_runtime_min | 0.071 |
| film_awards_nominations | 0.070 |
| imdb_rating | 0.049 |
