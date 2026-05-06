-- ============================================================
-- DATA WAREHOUSE TABLE CREATION
-- DW_MAD_MOVIES Warehouse
-- Movie Venture BI Project — Group 81, Nova IMS (2025/2026)
-- ============================================================

/*==========================================================
    DIM_DATE
==========================================================*/

CREATE TABLE dim_date (
    sk_date             INT             NOT NULL PRIMARY KEY,
    proper_date         DATE            NOT NULL,

    full_date           VARCHAR(50)     NOT NULL,
    monthday_number     INT             NOT NULL,

    weekday_number      INT             NOT NULL,
    weekday_name        VARCHAR(50)     NOT NULL,
    weekday_type        VARCHAR(10)     NOT NULL,
    weekday_name_short  VARCHAR(10)     NOT NULL,

    month_number        INT             NOT NULL,
    month_name          VARCHAR(50)     NOT NULL,
    month_name_short    VARCHAR(50)     NOT NULL,

    calendar_season     VARCHAR(20)     NOT NULL,

    is_holiday          BIT             NOT NULL,
    holiday_name        VARCHAR(50)     NULL,

    marketing_season    VARCHAR(50)     NOT NULL,
    calendar_year       INT             NOT NULL
);

/*==========================================================
    DIM_FILM (with surrogate key)
==========================================================*/

CREATE TABLE dim_film (
    sk_film                     INT             NOT NULL PRIMARY KEY,
    bk_film                     VARCHAR(400)    NOT NULL,
    film_title                  VARCHAR(200)    NOT NULL,
    film_release_year           INT             NULL,
    film_genre                  VARCHAR(100)    NULL,
    film_age_classification     VARCHAR(100)    NULL,
    primary_language_film       VARCHAR(100)    NULL,
    secondary_language_film     VARCHAR(100)    NULL,
    film_runtime_min            INT             NULL,
    imdb_rating                 DECIMAL(3,1)    NULL,
    rt_rating                   DECIMAL(4,1)    NULL,
    film_budget_usd             DECIMAL(18,2)   NULL,
    main_filming_country        VARCHAR(100)    NULL,
    secondary_filming_country   VARCHAR(100)    NULL,
    tertiary_filming_country    VARCHAR(100)    NULL,
    film_awards_won             INT             NULL,
    film_awards_nominations     INT             NULL,
    film_oscars_won             INT             NULL,
    film_oscar_nominations      INT             NULL
);

/*==========================================================
    DIM_ACTOR (with surrogate key)
==========================================================*/

CREATE TABLE dim_actor (
    sk_actor            INT             NOT NULL PRIMARY KEY,
    bk_actor            VARCHAR(150)    NOT NULL,
    first_name_actor    VARCHAR(100)    NULL,
    surname_actor       VARCHAR(100)    NULL,
    nationality_actor   VARCHAR(100)    NULL,
    age_actor           INT             NULL
);

/*==========================================================
    DIM_DIRECTOR (with surrogate key)
==========================================================*/

CREATE TABLE dim_director (
    sk_director             INT             NOT NULL PRIMARY KEY,
    bk_director             VARCHAR(150)    NOT NULL,
    first_name_director     VARCHAR(100)    NULL,
    surname_director        VARCHAR(100)    NULL,
    nationality_director    VARCHAR(100)    NULL,
    age_director            INT             NULL
);

/*==========================================================
    DIM_PRODUCTION_COMPANY (with surrogate key)
==========================================================*/

CREATE TABLE dim_production_company (
    sk_production_company           INT             NOT NULL PRIMARY KEY,
    bk_production_company           VARCHAR(150)    NOT NULL,
    production_company              VARCHAR(200)    NULL,
    country_production_company      VARCHAR(100)    NULL,
    continent_production_company    VARCHAR(50)     NULL,
    city_production_company         VARCHAR(100)    NULL
);

/*==========================================================
    FACT_DAILY_BOX_OFFICE (with surrogate FKs)
    Grain: One record per Film x Date
    PK: Composite of all foreign keys
==========================================================*/

CREATE TABLE fact_daily_box_office (
    fk_date                 INT             NOT NULL,
    fk_film                 INT             NOT NULL,
    fk_production_company   INT             NOT NULL,
    fk_director             INT             NOT NULL,
    fk_actor                INT             NOT NULL,
    gross_revenue_per_day   DECIMAL(18,2)   NULL,
    days_since_release      INT             NULL,
    PRIMARY KEY (fk_date, fk_film, fk_production_company, fk_director, fk_actor)
);
