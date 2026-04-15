# Movie Venture — BI-Powered Cinematic Intelligence

![Microsoft Fabric](https://img.shields.io/badge/Microsoft%20Fabric-Data%20Platform-0078D4?logo=microsoftazure&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-Data%20Warehouse-CC2927?logo=microsoftsqlserver&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-ML-orange?logo=scikit-learn&logoColor=white)
![Power BI](https://img.shields.io/badge/Power%20BI-Dashboard-F2C811?logo=powerbi&logoColor=black)
![Status](https://img.shields.io/badge/Status-In%20Progress-yellow)

## Project Overview

End-to-end Business Intelligence solution for **film investment decision-making**, built on **Microsoft Fabric**. The project ingests daily box-office data from Box Office Mojo, enriches it through multi-API pipelines (TMDb, OMDb, Wikidata), models it into a Kimball-compliant star schema, and delivers predictive analytics — all within a single cloud-native platform.

**782 films | 34,568 daily records | 5 dimensions | 13 business questions | 2 predictive models**

> **Academic Context:** Business Intelligence I & II, MSc Information Management (Business Intelligence) — Nova IMS, Universidade Nova de Lisboa (2025/2026)

---

## Architecture

```
                         TMDb API ─┐
                         OMDb API ──┤── Python Enrichment (5 notebooks)
                      Wikidata API ─┘           │
                                                ▼
                                    ┌───────────────────────┐
                                    │  Fabric Lakehouse     │
                                    │  LH_SOURCES_MAD_MOVIES│
                                    │  (8 source CSVs)      │
                                    └───────────┬───────────┘
                                                │
                              Dataflows Gen2 (6 transforms)
                                                │
                                                ▼
                                    ┌───────────────────────┐
                                    │  Staging Warehouse    │
                                    │  STG_MAD_MOVIES       │
                                    │  (6 tables + DQ log)  │
                                    └───────────┬───────────┘
                                                │
                              17 Validation Rules (automated)
                                                │
                                                ▼
                                    ┌───────────────────────┐
                                    │  Data Warehouse       │
                                    │  DW_MAD_MOVIES        │
                                    │  (Star Schema)        │
                                    └──────┬────────┬───────┘
                                           │        │
                                           ▼        ▼
                                    ┌──────────┐ ┌──────────────┐
                                    │ Semantic │ │ ML Notebook  │
                                    │ Model    │ │ (PySpark)    │
                                    │ SM MAD   │ │ Genre Trends │
                                    │ Movies   │ │ Film Tiers   │
                                    └────┬─────┘ └──────────────┘
                                         │
                                         ▼
                                    ┌──────────┐
                                    │ Power BI │
                                    │ Dashboard│
                                    │ (soon)   │
                                    └──────────┘
```

For detailed architecture documentation, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Star Schema

```
    ┌──────────────┐     ┌───────────────────┐     ┌──────────────┐
    │  dim_actor   │     │  dim_prod_company  │     │ dim_director │
    │──────────────│     │───────────────────│     │──────────────│
    │ sk_actor (PK)│     │ sk_prod_co (PK)   │     │ sk_dir (PK)  │
    │ name, nation-│     │ company, country,  │     │ name, nation-│
    │ ality, age   │     │ continent, city    │     │ ality, age   │
    └──────┬───────┘     └────────┬──────────┘     └──────┬───────┘
           │                      │                        │
           └──────────┬───────────┴────────────┬───────────┘
                      │                        │
                      ▼                        │
              ┌───────────────────┐            │
              │ fact_daily_box    │            │
              │ _office           │            │
              │───────────────────│            │
              │ fk_date           │◄───────────┤
              │ fk_film           │            │
              │ fk_actor          │     ┌──────┴───────┐
              │ fk_director       │     │  dim_date    │
              │ fk_prod_company   │     │──────────────│
              │ gross_revenue/day │     │ sk_date (PK) │
              │ days_since_release│     │ weekday, type│
              └───────┬───────────┘     │ season, month│
                      │                 │ holiday, mkt │
               ┌──────┴───────┐        │ season       │
               │  dim_film    │        └──────────────┘
               │──────────────│
               │ sk_film (PK) │
               │ title, genre │
               │ budget, IMDb │
               │ RT, awards   │
               │ runtime, lang│
               │ country      │
               └──────────────┘

    Grain: One record per Film x Date
```

---

## Business Questions

### Analytical (BI 1 & 2)

| # | Business Question |
|---|------------------|
| BQ1 | Which actors appear in the highest-grossing films? |
| BQ2 | How do award-winning films differ from non-awarded in revenue, ratings, and genre? |
| BQ3 | How does performance differ across runtime segments (<90, 90-120, >120 min)? |
| BQ4 | Which genres experience the largest average weekly revenue change? |
| BQ5 | How do films perform across filming countries and production company countries? |
| BQ6 | What is the average revenue, runtime, and ratings per director? |
| BQ7 | Which genres generate highest revenue, and how do they differ in ratings/runtime/seasons? |
| BQ8 | How does revenue differ across IMDb and Rotten Tomatoes rating brackets? |
| BQ9 | How do revenues vary across age classifications, seasons, and genres? |
| BQ10 | Which weekdays generate the highest average daily revenue? |
| BQ11 | Which spoken languages appear most among the top 50 highest-grossing films? |
| BQ12 | Which films rank top 5 highest-rated in high-budget vs low-budget categories? |
| BQ13 | What is the most profitable day, season, and marketing season per year? |

### Predictive (ML)

| # | Business Question | Method | Result |
|---|------------------|--------|--------|
| BQ P1 | Genre Revenue Trend Forecasting | Linear Regression (per genre) | 193 genres classified as Growing/Declining/Stable with 2025 projections |
| BQ P2 | Film Tier Classification | Random Forest vs GBM | RF wins (F1=0.719), 782 films classified into High/Mid/Low revenue tiers |

**Top predictive features:** Budget USD (0.326), Age Classification (0.113), Runtime (0.071), Award Nominations (0.070), IMDb Rating (0.049)

---

## Data Pipeline

### Master ETL Pipeline

```
PL_MAD_MOVIES_MASTER_ETL
═══════════════════════════════════════════════════════════════════

  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │ PL split    │     │ PL run STG  │     │ PL validate │     │ PL run DW   │
  │ source file │────>│ initial     │────>│ Data        │────>│ load        │
  │             │     │ (load STG)  │     │ (17 rules)  │     │ (load DW)   │
  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
        │                    │                   │                    │
   Split CSVs into      6 Dataflows Gen2    Automated DQ       Clear + Copy
   entity-specific      load staging        validation with    dims parallel,
   source tables        tables (Kimball)    logging to         then load fact
                                            log_quality_checks
```

### Data Quality Framework

17 automated validation rules with results logged to `log_quality_checks`:

| Rule | Check | Applied To |
|------|-------|-----------|
| 1 | Business Key integrity (no duplicates) | All dimensions |
| 2 | Attribute-level uniqueness | All dimensions |
| 3 | Fact composite PK integrity | Fact table |
| 4 | FK parent existence (no orphans) | All FK relationships |
| 5 | Gross revenue non-negative | Fact table |
| 6 | Days since release non-negative | Fact table |
| 7 | Revenue rows must have days_since_release | Fact table |

**Result: 15/17 rules passed. 2 failures investigated and documented.**

---

## Data Sources

| Source | Type | Purpose |
|--------|------|---------|
| **Box Office Mojo** | Manual collection | Daily box-office performance (revenue, rankings) |
| **TMDb API** | REST API | Film metadata, cast, crew, ratings, posters |
| **OMDb API** | REST API | IMDb/RT ratings, awards, runtime |
| **Wikidata** | SPARQL | Production company geography (city, country, continent) |

Data enrichment was performed iteratively across **5 Python notebooks**, progressively adding attributes through a multi-phase pipeline with persistent caching and fuzzy title matching (Levenshtein distance).

---

## Skills Demonstrated

- **Microsoft Fabric** — Lakehouse, Warehouse, Dataflows Gen2, Pipelines, Semantic Model
- **Data Warehouse Design** — Kimball methodology, star schema, conformed dimensions
- **ETL/ELT Pipeline Design** — Master orchestration, parallel execution, incremental loading
- **SQL** — DDL, DQL, validation queries, surrogate key generation
- **Data Quality Framework** — Automated validation rules with logging and failure investigation
- **Python** — API integration (TMDb, OMDb, Wikidata SPARQL), data enrichment, fuzzy matching
- **Machine Learning** — Classification (RF, GBM), regression, cross-validation, feature importance
- **Semantic Modeling** — DAX measures, KPIs, hierarchies (Calendar, Marketing Season, Weekday)
- **Power Query** — Dataflows Gen2 transformations, Kimball-compliant dimension modeling

---

## Tech Stack

| Category | Tools |
|----------|-------|
| **Platform** | Microsoft Fabric (Lakehouse, Warehouse, Pipelines, Dataflows Gen2) |
| **Languages** | Python 3, SQL, DAX, PySpark |
| **ML** | scikit-learn (RandomForest, GradientBoosting, LinearRegression) |
| **Data** | pandas, NumPy, requests, fuzzywuzzy |
| **APIs** | TMDb, OMDb, Wikidata SPARQL |
| **Visualization** | Power BI (coming), Matplotlib, Seaborn |
| **Semantic Layer** | Power BI Semantic Model (DAX measures, hierarchies) |

---

## Project Structure

```
movie-venture-bi/
├── README.md
├── requirements.txt
├── .gitignore
├── notebooks/
│   ├── enrichment/
│   │   ├── 01_initial_enrichment.ipynb         # TMDb + OMDb: directors, actors, ratings
│   │   ├── 02_enrichment_runtime_franchise.ipynb  # Runtime, franchise detection, Wikidata
│   │   ├── 03_enrichment_caching_matching.ipynb   # Persistent caching, studio matching
│   │   ├── 04_enrichment_budget_posters.ipynb     # Budget, posters, birthdates
│   │   └── 05_enrichment_company_geo.ipynb        # Company city/continent (SPARQL)
│   └── ml/
│       └── predictive_business_questions.py       # Genre trends + Film tier prediction
├── sql/
│   ├── stg_table_creation.sql                     # Staging area DDL
│   ├── dw_table_creation.sql                      # Data Warehouse DDL
│   └── validation_rules.sql                       # 17 DQ validation rules
├── docs/
│   └── ARCHITECTURE.md                            # Detailed architecture documentation
├── report/
│   └── BI1_Group81_Report.pdf                     # Full academic report (20 pages)
└── assets/                                        # Architecture screenshots
```

---

## How to Run

The data enrichment notebooks can be run locally:

```bash
git clone https://github.com/diogovasconcelosmerca/movie-venture-bi.git
cd movie-venture-bi
pip install -r requirements.txt
jupyter notebook notebooks/enrichment/01_initial_enrichment.ipynb
```

The ETL pipelines, Data Warehouse, Semantic Model, and ML notebook run on **Microsoft Fabric** and require access to the workspace.

---

## Report

The full academic report with detailed methodology, architecture decisions, and data quality analysis is available at [`report/BI1_Group81_Report.pdf`](report/BI1_Group81_Report.pdf).

---

## Coming Soon

- **Power BI Dashboard** — Interactive dashboard answering all 13 business questions
- **BI 2 Report** — Semantic model documentation, predictive analytics, and dashboard design

---

## Authors

**Group 81** — Business Intelligence I & II, MSc Information Management (BI)
Nova IMS — Universidade Nova de Lisboa (2025/2026)

- [Diogo Merca](https://github.com/diogovasconcelosmerca)
- [Madalina Noje](https://github.com/madalinanoje)
- Alexandre Duarte
- Matilde Cordeiro
