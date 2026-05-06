"""
Predictive Business Questions — Movie Venture BI Project
=========================================================
Group 81 — Nova IMS, MSc Information Management (BI), 2025/2026

This script runs on Microsoft Fabric Spark and connects to the
DW_MAD_MOVIES warehouse via JDBC to generate predictive insights:

  BQ P1 — Genre Revenue Trend Forecasting (Linear Regression)
  BQ P2 — Film Tier Classification (Random Forest vs Gradient Boosting)

Results are written back to the Lakehouse as Delta tables:
  - ml_genre_trends     (193 genres, trend + projected revenue)
  - ml_tier_predictions (782 films, predicted tier + confidence)

Note: This script requires a Fabric Spark environment with access
to the DW_MAD_MOVIES warehouse. The `notebookutils` and `spark`
objects are provided by the Fabric runtime.
"""

import warnings
warnings.filterwarnings("ignore")

import struct
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import StratifiedKFold, cross_validate

# =============================================================================
# Configuration
# =============================================================================

CONFIG = {
    "SERVER": "75u33zhx4yxezmshig2uxisjby-6cmxyam7nyzulj6g4chlffw2xe.datawarehouse.fabric.microsoft.com",
    "DATABASE": "DW_MAD_MOVIES",
    "JDBC_URL_TEMPLATE": "jdbc:sqlserver://{server};databaseName={database};encrypt=true;trustServerCertificate=false",
    "NUM_COLS": ['film_runtime_min', 'film_budget_usd', 'imdb_rating', 'rt_rating', 'film_awards_won', 'film_awards_nominations'],
    "CAT_COLS": ['film_genre', 'film_age_classification', 'release_season'],
    "GENRES_TO_PLOT": ['AnimationAdventureComedy', 'ActionAdventureComedy', 'ComedyDramaRomance', 'Comedy', 'Horror']
}

# Ensure global Spark and notebookutils are available in Fabric environment
# In local dev these would raise NameError, handled gracefully in main()
try:
    _spark = spark
    _notebookutils = notebookutils
except NameError:
    _spark = None
    _notebookutils = None

# =============================================================================
# Connection Helper
# =============================================================================

def read_sql(query: str) -> pd.DataFrame:
    """Read from DW_MAD_MOVIES via JDBC using Fabric token authentication."""
    if _spark is None or _notebookutils is None:
        raise EnvironmentError("Fabric 'spark' and 'notebookutils' objects not found in environment.")

    jdbc_url = CONFIG["JDBC_URL_TEMPLATE"].format(server=CONFIG["SERVER"], database=CONFIG["DATABASE"])
    token = _notebookutils.credentials.getToken("https://database.windows.net/")

    return (_spark.read
                 .format("jdbc")
                 .option("url", jdbc_url)
                 .option("query", query)
                 .option("accessToken", token)
                 .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver")
                 .load()
                 .toPandas())

# =============================================================================
# Utility Functions
# =============================================================================

def runtime_segment(mins: float) -> str:
    """Segment film runtime into Short, Standard, or Long."""
    if pd.isna(mins):
        return 'Unknown'
    elif mins < 90:
        return 'Short'
    elif mins <= 120:
        return 'Standard'
    else:
        return 'Long'

# =============================================================================
# BQ P1 — Genre Revenue Trend Forecasting
# =============================================================================

def forecast_genre_trends() -> pd.DataFrame:
    """Forecast genre revenue trends using Linear Regression."""
    print("\n--- BQ P1: Genre Revenue Trend Forecasting ---")

    query = """
        SELECT
            f.film_genre,
            d.calendar_year                  AS box_year,
            SUM(b.gross_revenue_per_day)     AS annual_revenue
        FROM dbo.fact_daily_box_office b
        JOIN dbo.dim_film f ON b.fk_film  = f.sk_film
        JOIN dbo.dim_date d ON b.fk_date  = d.sk_date
        WHERE f.film_genre IS NOT NULL
        GROUP BY f.film_genre, d.calendar_year
    """

    try:
        genre_rev_df = read_sql(query)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

    if genre_rev_df.empty:
        print("Warning: genre_rev_df is empty.")
        return pd.DataFrame()

    genre_rev_df['annual_revenue'] = pd.to_numeric(genre_rev_df['annual_revenue'], errors='coerce').astype(float)
    genre_rev_df['box_year'] = pd.to_numeric(genre_rev_df['box_year'], errors='coerce').astype(int)

    print(f"Genres: {genre_rev_df['film_genre'].nunique()}  |  "
          f"Years: {int(genre_rev_df['box_year'].min())}–{int(genre_rev_df['box_year'].max())}")

    next_year = int(genre_rev_df['box_year'].max()) + 1
    records = []

    for genre, grp in genre_rev_df.groupby('film_genre'):
        grp = grp.sort_values('box_year')
        if len(grp) < 2:
            records.append({
                'film_genre': genre,
                'genre_trend': 'Stable',
                'genre_projected_revenue': float(grp['annual_revenue'].mean())
            })
            continue

        X = grp[['box_year']].values.astype(float)
        y = grp['annual_revenue'].values.astype(float)

        lr = LinearRegression().fit(X, y)
        slope = float(lr.coef_[0])
        proj = max(float(lr.predict([[next_year]])[0]), 0)
        thresh = float(y.mean()) * 0.05

        if slope > thresh:
            trend = 'Growing'
        elif slope < -thresh:
            trend = 'Declining'
        else:
            trend = 'Stable'

        records.append({
            'film_genre': genre,
            'genre_trend': trend,
            'genre_projected_revenue': proj
        })

    trend_df = pd.DataFrame(records)
    print("\n-- BQ P1 Results --")
    print(trend_df.sort_values('genre_trend').head(10).to_string(index=False))

    visualize_genre_trends(genre_rev_df, next_year)

    return trend_df

def visualize_genre_trends(genre_rev_df: pd.DataFrame, next_year: int):
    """Generate plots for revenue trends of specific genres."""
    genres_to_plot = [g for g in CONFIG["GENRES_TO_PLOT"] if g in genre_rev_df['film_genre'].unique()]

    if not genres_to_plot:
        print("Warning: None of the target genres found for visualization.")
        return

    fig, axes = plt.subplots(len(genres_to_plot), 1, figsize=(10, 4 * len(genres_to_plot)))
    if len(genres_to_plot) == 1:
        axes = [axes] # Ensure iterable

    for ax, genre in zip(axes, genres_to_plot):
        grp = genre_rev_df[genre_rev_df['film_genre'] == genre].sort_values('box_year')
        X = grp[['box_year']].values.astype(float)
        y = grp['annual_revenue'].values.astype(float)

        if len(X) < 2:
             continue

        lr = LinearRegression().fit(X, y)

        ax.scatter(grp['box_year'], y, color='steelblue', label='Actual Revenue', zorder=5)

        x_line = np.linspace(X.min(), next_year, 100)
        y_line = lr.predict(x_line.reshape(-1, 1))
        ax.plot(x_line, y_line, color='tomato', label='Trend Line')

        proj = max(float(lr.predict([[next_year]])[0]), 0)
        ax.scatter(next_year, proj, color='green', marker='*', s=200,
                   label=f'Projection {next_year}: ${proj:,.0f}', zorder=5)

        slope = lr.coef_[0]
        intercept = lr.intercept_
        ax.set_title(f'{genre}   |   y = {slope:,.0f}x + {intercept:,.0f}', fontsize=11)
        ax.set_xlabel('Year')
        ax.set_ylabel('Annual Revenue ($)')
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('genre_trends.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("\nSaved visualization as genre_trends.png")


# =============================================================================
# BQ P2 — Film Tier Prediction
# =============================================================================

def classify_film_tiers() -> pd.DataFrame:
    """Classify films into revenue tiers using Random Forest/GBM."""
    print("\n--- BQ P2: Film Tier Classification ---")

    film_query = """
        SELECT
            f.sk_film, f.bk_film, f.film_title, f.film_genre,
            f.film_runtime_min, f.film_age_classification, f.film_release_year,
            f.film_budget_usd, f.imdb_rating, f.rt_rating,
            f.film_awards_won, f.film_awards_nominations,
            d.calendar_season  AS release_season
        FROM dbo.dim_film f
        LEFT JOIN (
            SELECT fk_film, MIN(fk_date) AS first_date_key
            FROM dbo.fact_daily_box_office
            GROUP BY fk_film
        ) first_day ON f.sk_film = first_day.fk_film
        LEFT JOIN dbo.dim_date d ON first_day.first_date_key = d.sk_date
    """

    revenue_query = """
        SELECT fk_film, SUM(gross_revenue_per_day) AS total_revenue
        FROM dbo.fact_daily_box_office
        GROUP BY fk_film
    """

    try:
        film_df = read_sql(film_query)
        revenue_df = read_sql(revenue_query)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

    if film_df.empty or revenue_df.empty:
        print("Warning: Could not load film or revenue data.")
        return pd.DataFrame()

    print(f"Films loaded:       {len(film_df)}")
    print(f"Films with revenue: {len(revenue_df)}")

    # Merge and format
    df = film_df.merge(revenue_df, left_on='sk_film', right_on='fk_film', how='left')
    df['total_revenue'] = pd.to_numeric(df['total_revenue'], errors='coerce').fillna(0).astype(float)

    for col in CONFIG["NUM_COLS"]:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)

    df = df.drop_duplicates(subset='bk_film').reset_index(drop=True)

    # Establish Tiers based on historical revenue > 0
    historical_mask = df['total_revenue'] > 0
    hist = df[historical_mask]

    if hist.empty:
        print("Warning: No historical data > 0 found for training.")
        return pd.DataFrame()

    q33 = hist['total_revenue'].quantile(0.33)
    q66 = hist['total_revenue'].quantile(0.66)

    df['tier'] = df['total_revenue'].apply(
        lambda r: 'High' if r >= q66 else ('Mid' if r >= q33 else 'Low')
    )
    df.loc[~historical_mask, 'tier'] = np.nan

    print(f"Q33: {q33:,.0f}  |  Q66: {q66:,.0f}")

    # Feature Engineering
    df['runtime_segment'] = df['film_runtime_min'].apply(runtime_segment)

    # Preprocessing
    for col in CONFIG["CAT_COLS"]:
        df[col] = df[col].fillna('Unknown')
    for col in CONFIG["NUM_COLS"]:
        df[col] = df[col].fillna(df[col].median())

    historical_df = df[historical_mask].copy()

    X_train = pd.get_dummies(historical_df[CONFIG["CAT_COLS"]], drop_first=False)
    for col in CONFIG["NUM_COLS"]:
        X_train[col] = historical_df[col].values
    X_train = X_train.fillna(0)

    y_train = historical_df['tier']

    X_all = pd.get_dummies(df[CONFIG["CAT_COLS"]], drop_first=False)
    X_all = X_all.reindex(columns=X_train.columns, fill_value=0)
    for col in CONFIG["NUM_COLS"]:
        X_all[col] = df[col].values
    X_all = X_all.fillna(0)

    print(f"Train: {len(X_train)} films  |  Total: {len(df)} films")

    # Model Selection (RF vs GBM)
    candidates = {
        'RF':  RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=3,
                                       class_weight='balanced', random_state=42),
        'GBM': GradientBoostingClassifier(n_estimators=300, max_depth=4,
                                           learning_rate=0.05, subsample=0.8, random_state=42)
    }

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    best_model, best_f1, best_name = None, 0.0, ''

    print("\n-- Cross-Validation (5 folds) --")
    for name, model in candidates.items():
        res = cross_validate(model, X_train, y_train, cv=cv,
                             scoring=['accuracy', 'f1_weighted'],
                             return_train_score=True)
        test_f1 = res['test_f1_weighted'].mean()
        print(f"  {name}: Test F1 = {test_f1:.3f}")
        if test_f1 > best_f1:
            best_f1, best_model, best_name = test_f1, model, name

    print(f"\nWinner: {best_name} (F1={best_f1:.3f})")

    if best_model is None:
        print("Warning: Failed to train a model.")
        return pd.DataFrame()

    best_model.fit(X_train, y_train)

    # Feature importance
    feat_imp = (pd.Series(best_model.feature_importances_, index=X_train.columns)
                  .sort_values(ascending=False))
    print("\n-- Feature Importance (top 5) --")
    print(feat_imp.head(5).to_string())

    # Predict
    probs = best_model.predict_proba(X_all)
    df['predicted_tier']  = best_model.predict(X_all)
    df['tier_confidence'] = probs.max(axis=1).round(4)

    print(f"\n-- Predictions Sample --")
    print(df[['film_title', 'predicted_tier', 'tier_confidence']].head(5).to_string(index=False))

    output_cols = ['bk_film', 'film_title', 'film_genre', 'runtime_segment',
                   'release_season', 'film_age_classification', 'predicted_tier',
                   'tier_confidence']
    return df[output_cols].copy()

# =============================================================================
# Main Execution
# =============================================================================

def main():
    if _spark is None:
        print("Not running in a Fabric environment. Dry-run mode / Schema validation only.")
        return

    # Run BQ P1
    trend_df = forecast_genre_trends()
    if not trend_df.empty:
        spark_bq1 = _spark.createDataFrame(trend_df)
        spark_bq1.write.mode("overwrite").format("delta").saveAsTable("ml_genre_trends")
        print(f"Saved ml_genre_trends: {len(trend_df)} records.")

    # Run BQ P2
    output_df = classify_film_tiers()
    if not output_df.empty:
        spark_bq2 = _spark.createDataFrame(output_df)
        spark_bq2.write.mode("overwrite").format("delta").saveAsTable("ml_tier_predictions")
        print(f"Saved ml_tier_predictions: {len(output_df)} records.")

if __name__ == "__main__":
    main()
