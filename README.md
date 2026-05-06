# Movie Venture — BI-Powered Cinematic Intelligence

![Microsoft Fabric](https://img.shields.io/badge/Microsoft%20Fabric-Data%20Platform-0078D4?logo=microsoftazure&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-Data%20Warehouse-CC2927?logo=microsoftsqlserver&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-ML-orange?logo=scikit-learn&logoColor=white)
![Power BI](https://img.shields.io/badge/Power%20BI-Dashboard-F2C811?logo=powerbi&logoColor=black)

## Project Overview

End-to-end Business Intelligence solution for **film investment decision-making**, built on **Microsoft Fabric**. The project ingests daily box-office data from Box Office Mojo, enriches it through multi-API pipelines (TMDb, OMDb, Wikidata), models it into a Kimball-compliant star schema, and delivers predictive analytics — all within a single cloud-native platform.

**782 films | 34,568 daily records | 5 dimensions | 13 business questions | 2 predictive models**

> **Academic Context:** Business Intelligence I & II, MSc Information Management (Business Intelligence) — Nova IMS, Universidade Nova de Lisboa (2025/2026)

---

## Architecture

```text
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
                                    │ Semantic │ │ ML Script    │
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

The Data Warehouse implements a Kimball-compliant Star Schema, designed for intuitive analytical queries on the daily box-office facts.

```text
    ┌──────────────┐     ┌───────────────────┐     ┌──────────────┐
    │  dim_actor   │     │  dim_prod_company │     │ dim_director │
    │──────────────│     │───────────────────│     │──────────────│
    │ sk_actor (PK)│     │ sk_prod_co (PK)   │     │ sk_dir (PK)  │
    │ name, nation-│     │ company, country, │     │ name, nation-│
    │ ality, age   │     │ continent, city   │     │ ality, age   │
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
               ┌──────┴───────┐         │ season       │
               │  dim_film    │         └──────────────┘
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

## Machine Learning & Predictive Analytics

The project answers specific Business Questions (BQ) via machine learning models developed directly against the Data Warehouse.

| # | Business Question | Methodology | Insights / Results |
|---|------------------|--------|--------|
| BQ P1 | Genre Revenue Trend Forecasting | **Linear Regression** (per genre) | Forecasted trends over 193 genres. Classified each as Growing, Declining, or Stable with precise revenue projections for 2025. |
| BQ P2 | Film Tier Classification | **Random Forest** vs **Gradient Boosting Machine (GBM)** | Evaluated two models for tier prediction (High/Mid/Low revenue). **Random Forest** provided the highest accuracy (F1=0.719). 782 films successfully classified based on features. |

**Top Predictive Features identified by the models:**
Budget USD (0.326), Age Classification (0.113), Runtime (0.071), Award Nominations (0.070), IMDb Rating (0.049)

*(Note: Initial problem scope considered SARIMAX, however, after empirical data analysis, Linear Regression provided robust outputs for annual trend lines given the granularity and volume of temporal data available across genres).*

---

## Data Quality Framework

17 automated validation rules were built natively using SQL assertions. Results are securely logged to a dedicated audit table `log_quality_checks`:

| Rule Scope | Checks Include | Applied To |
|------|-------|-----------|
| **Primary/Foreign Keys** | Business Key integrity (no duplicates), Fact composite PK integrity, FK parent existence (no orphans). | All dimensions, Fact table |
| **Attributes** | Attribute-level uniqueness testing. | All dimensions |
| **Business Logic** | Gross revenue non-negative, Days since release non-negative, Revenue rows must include valid days_since_release metrics. | Fact table |

**Result: 15/17 rules passed. 2 distinct failures flagged automatically, investigated, and fully documented.**

---

## Skills & Technologies Demonstrated

- **Cloud Platform:** Microsoft Fabric (Lakehouse, Warehouse, Pipelines, Dataflows Gen2)
- **Data Engineering:** Kimball Star Schema, ETL/ELT pipelines, parallel execution, incremental loading, Power Query
- **Data Quality:** Automated SQ validation rules, failure investigation logs
- **Software Engineering:** Python (API integration via TMDb, OMDb, Wikidata SPARQL, multi-phase enrichment, Levenshtein distance matching)
- **Machine Learning:** Scikit-Learn (Linear Regression, Random Forest, Gradient Boosting), Feature Engineering, Cross-Validation
- **Analytics:** Power BI Semantic Models (DAX, custom hierarchies)

---

## Repository Structure

```
movie-venture-bi/
├── README.md                                      # Project overview
├── requirements.txt                               # Python dependencies
├── notebooks/
│   └── enrichment/
│       ├── 01_initial_enrichment.ipynb            # TMDb + OMDb: directors, actors, ratings
│       ├── 02_enrichment_runtime_franchise.ipynb  # Runtime, franchise detection, Wikidata
│       ├── 03_enrichment_caching_matching.ipynb   # Persistent caching, studio matching
│       ├── 04_enrichment_budget_posters.ipynb     # Budget, posters, birthdates
│       └── 05_enrichment_company_geo.ipynb        # Company city/continent (SPARQL)
├── src/
│   └── ml/
│       └── predictive_business_questions.py       # ML Pipeline for Trends & Tiers (Linear Regression, Random Forest)
├── sql/
│   ├── stg_table_creation.sql                     # Staging area DDL
│   ├── dw_table_creation.sql                      # Data Warehouse DDL (Star Schema)
│   └── validation_rules.sql                       # 17 DQ validation rules
├── docs/
│   └── ARCHITECTURE.md                            # Detailed architecture documentation
├── report/
│   └── BI1_Group81_Report.pdf                     # Full academic report
└── assets/                                        # Architecture screenshots
```

---

## Authors

**Group 81** — Business Intelligence I & II, MSc Information Management (BI)
Nova IMS — Universidade Nova de Lisboa (2025/2026)

- [Diogo Merca](https://github.com/diogovasconcelosmerca)
- [Madalina Noje](https://github.com/madalinanoje)
- Alexandre Duarte
- Matilde Cordeiro
