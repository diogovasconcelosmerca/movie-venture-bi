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

import struct, pandas as pd, numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import StratifiedKFold, cross_validate

# =============================================================================
# Connection helper
# =============================================================================

SERVER   = "75u33zhx4yxezmshig2uxisjby-6cmxyam7nyzulj6g4chlffw2xe.datawarehouse.fabric.microsoft.com"
DATABASE = "DW_MAD_MOVIES"
JDBC_URL = f"jdbc:sqlserver://{SERVER};databaseName={DATABASE};encrypt=true;trustServerCertificate=false"

def read_sql(query):
    """Read from DW_MAD_MOVIES via JDBC using Fabric token authentication."""
    token = notebookutils.credentials.getToken("https://database.windows.net/")
    return (spark.read
                 .format("jdbc")
                 .option("url", JDBC_URL)
                 .option("query", query)
                 .option("accessToken", token)
                 .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver")
                 .load()
                 .toPandas())

# =============================================================================
# BQ P1 — Genre Revenue Trend Forecasting
# =============================================================================

genre_rev_df = read_sql("""
    SELECT
        f.film_genre,
        d.calendar_year                  AS box_year,
        SUM(b.gross_revenue_per_day)     AS annual_revenue
    FROM dbo.fact_daily_box_office b
    JOIN dbo.dim_film f ON b.fk_film  = f.sk_film
    JOIN dbo.dim_date d ON b.fk_date  = d.sk_date
    WHERE f.film_genre IS NOT NULL
    GROUP BY f.film_genre, d.calendar_year
""")

genre_rev_df['annual_revenue'] = pd.to_numeric(genre_rev_df['annual_revenue'], errors='coerce').astype(float)
genre_rev_df['box_year']       = pd.to_numeric(genre_rev_df['box_year'], errors='coerce').astype(int)

print(f"Genres: {genre_rev_df['film_genre'].nunique()}  |  "
      f"Years: {int(genre_rev_df['box_year'].min())}\u2013{int(genre_rev_df['box_year'].max())}")

next_year = int(genre_rev_df['box_year'].max()) + 1
records   = []

for genre, grp in genre_rev_df.groupby('film_genre'):
    grp = grp.sort_values('box_year')
    if len(grp) < 2:
        records.append({'film_genre': genre, 'genre_trend': 'Stable',
                        'genre_projected_revenue': float(grp['annual_revenue'].mean())})
        continue
    X      = grp[['box_year']].values.astype(float)
    y      = grp['annual_revenue'].values.astype(float)
    lr     = LinearRegression().fit(X, y)
    slope  = float(lr.coef_[0])
    proj   = max(float(lr.predict([[next_year]])[0]), 0)
    thresh = float(y.mean()) * 0.05
    trend  = 'Growing' if slope > thresh else ('Declining' if slope < -thresh else 'Stable')
    records.append({'film_genre': genre, 'genre_trend': trend,
                    'genre_projected_revenue': proj})

trend_df = pd.DataFrame(records)

print("\n-- BQ P1 Results --")
print(trend_df.sort_values('genre_trend').to_string(index=False))

# =============================================================================
# BQ P2 — Film Tier Prediction
# =============================================================================

film_df = read_sql("""
    SELECT
        f.sk_film,
        f.bk_film,
        f.film_title,
        f.film_genre,
        f.film_runtime_min,
        f.film_age_classification,
        f.film_release_year,
        f.film_budget_usd,
        f.imdb_rating,
        f.rt_rating,
        f.film_awards_won,
        f.film_awards_nominations,
        d.calendar_season  AS release_season
    FROM dbo.dim_film f
    LEFT JOIN (
        SELECT fk_film, MIN(fk_date) AS first_date_key
        FROM dbo.fact_daily_box_office
        GROUP BY fk_film
    ) first_day ON f.sk_film = first_day.fk_film
    LEFT JOIN dbo.dim_date d ON first_day.first_date_key = d.sk_date
""")

revenue_df = read_sql("""
    SELECT fk_film, SUM(gross_revenue_per_day) AS total_revenue
    FROM dbo.fact_daily_box_office
    GROUP BY fk_film
""")

print(f"\nFilms loaded:       {len(film_df)}")
print(f"Films with revenue: {len(revenue_df)}")
print(f"Seasons found:      {sorted(film_df['release_season'].dropna().unique())}")

# -- Merge & tier labels --
df = film_df.merge(revenue_df, left_on='sk_film', right_on='fk_film', how='left')
df['total_revenue'] = pd.to_numeric(df['total_revenue'], errors='coerce').fillna(0).astype(float)

NUM_COLS = ['film_runtime_min', 'film_budget_usd', 'imdb_rating',
            'rt_rating', 'film_awards_won', 'film_awards_nominations']
for col in NUM_COLS:
    df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)

df = df.drop_duplicates(subset='bk_film').reset_index(drop=True)

historical_mask = df['total_revenue'] > 0
hist            = df[historical_mask]
q33 = hist['total_revenue'].quantile(0.33)
q66 = hist['total_revenue'].quantile(0.66)

df['tier'] = df['total_revenue'].apply(
    lambda r: 'High' if r >= q66 else ('Mid' if r >= q33 else 'Low')
)
df.loc[~historical_mask, 'tier'] = np.nan

print(f"\nQ33: {q33:,.0f}  |  Q66: {q66:,.0f}")
print("\nTier distribution (historical):")
print(df[historical_mask]['tier'].value_counts())

# -- Runtime segment --
def runtime_segment(mins):
    if pd.isna(mins):  return 'Unknown'
    elif mins < 90:    return 'Short'
    elif mins <= 120:  return 'Standard'
    else:              return 'Long'

df['runtime_segment'] = df['film_runtime_min'].apply(runtime_segment)

# -- Feature prep (OHE + numerics) --
CAT_COLS = ['film_genre', 'film_age_classification', 'release_season']
for col in CAT_COLS:
    df[col] = df[col].fillna('Unknown')
for col in NUM_COLS:
    df[col] = df[col].fillna(df[col].median())

historical_df = df[historical_mask].copy()

X_train = pd.get_dummies(historical_df[CAT_COLS], drop_first=False)
for col in NUM_COLS:
    X_train[col] = historical_df[col].values
X_train = X_train.fillna(0)

y_train = historical_df['tier']

X_all = pd.get_dummies(df[CAT_COLS], drop_first=False)
X_all = X_all.reindex(columns=X_train.columns, fill_value=0)
for col in NUM_COLS:
    X_all[col] = df[col].values
X_all = X_all.fillna(0)

print(f"\nTrain: {len(X_train)} films  |  Total: {len(df)} films")
print(f"Features after OHE: {X_train.shape[1]} columns")

# -- Model selection: RF vs GBM --
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
    print(f"\n  {name}:")
    print(f"    Train Acc : {res['train_accuracy'].mean():.3f} +/- {res['train_accuracy'].std():.3f}")
    print(f"    Test  Acc : {res['test_accuracy'].mean():.3f} +/- {res['test_accuracy'].std():.3f}")
    print(f"    Test  F1  : {test_f1:.3f} +/- {res['test_f1_weighted'].std():.3f}")
    if test_f1 > best_f1:
        best_f1, best_model, best_name = test_f1, model, name

print(f"\n  Winner: {best_name}  (F1={best_f1:.3f})")
best_model.fit(X_train, y_train)

# -- Feature importance --
feat_imp = (pd.Series(best_model.feature_importances_, index=X_train.columns)
              .sort_values(ascending=False))
print("\n-- Feature Importance (top 12) --")
print(feat_imp.head(12).to_string())

# -- Predict ALL films --
probs = best_model.predict_proba(X_all)
df['predicted_tier']  = best_model.predict(X_all)
df['tier_confidence'] = probs.max(axis=1).round(4)

print(f"\n-- Predictions (all {len(df)} films) --")
print(f"  Avg confidence: {df['tier_confidence'].mean():.3f}")
print(df[['film_title', 'film_genre', 'runtime_segment', 'release_season',
          'predicted_tier', 'tier_confidence']].head(10).to_string(index=False))

# =============================================================================
# Write to Lakehouse (Delta tables)
# =============================================================================

spark_bq1 = spark.createDataFrame(trend_df)
spark_bq1.write.mode("overwrite").format("delta").saveAsTable("ml_genre_trends")
print(f"\nml_genre_trends: {len(trend_df)} genres written")

output_cols = ['bk_film', 'film_title', 'film_genre', 'runtime_segment',
               'release_season', 'film_age_classification', 'predicted_tier',
               'tier_confidence']
output_df = df[output_cols].copy()

spark_bq2 = spark.createDataFrame(output_df)
spark_bq2.write.mode("overwrite").format("delta").saveAsTable("ml_tier_predictions")
print(f"ml_tier_predictions: {len(output_df)} films written")
print(f"Tier distribution: {output_df['predicted_tier'].value_counts().to_dict()}")


# =============================================================================
# Visualization — Genre Revenue Trends
# =============================================================================

import matplotlib.pyplot as plt

genres_to_plot = [
    'AnimationAdventureComedy',
    'ActionAdventureComedy',
    'ComedyDramaRomance',
    'Comedy',
    'Horror'
]

fig, axes = plt.subplots(len(genres_to_plot), 1, figsize=(10, 4 * len(genres_to_plot)))

for ax, genre in zip(axes, genres_to_plot):
    grp = genre_rev_df[genre_rev_df['film_genre'] == genre].sort_values('box_year')
    X = grp[['box_year']].values.astype(float)
    y = grp['annual_revenue'].values.astype(float)
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
plt.show()
print("Saved as genre_trends.png")
