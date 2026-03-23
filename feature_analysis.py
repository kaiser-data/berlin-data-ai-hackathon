"""
Feature importance & class imbalance analysis using Snowflake SQL.
Uses CV, between-group variance ratio (eta²), and correlation to rank features.
"""
import snowflake.connector
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap

conn = snowflake.connector.connect(
    account='OHHGHHL-ZM06890',
    user='martinkaiser.bln@gmail.com',
    password='DM#31BvDJOZxR7',
    warehouse='WH_TEAM_2_XS',
    login_timeout=15
)
cur = conn.cursor()
cur.execute("USE WAREHOUSE WH_TEAM_2_XS")

# ─────────────────────────────────────────────────
# 1. CV per feature — raw discriminating power
# ─────────────────────────────────────────────────
print("1. Computing CV per feature ...")

FEATURES = [
    'seenlist_adds','watchlist_adds','unique_titles','trailer_plays',
    'events_per_session','active_days','avg_session_mins','completion_ratio',
    'has_clickout','clickout_ratio','buyer_ratio','free_ratio','monetization_diversity',
    'show_ratio','movie_ratio','page_view_ratio','login_rate',
    'weekend_ratio','evening_ratio','holiday_ratio',
]

cv_sql = "SELECT " + ",\n".join(
    [f"ROUND(STDDEV(CAST(COALESCE({f},0) AS FLOAT)) / NULLIF(AVG(ABS(CAST(COALESCE({f},0) AS FLOAT))),0), 4) AS cv_{f}"
     for f in FEATURES]
) + " FROM DB_TEAM_2.BASE_BASE.user_features_v2"

cur.execute(cv_sql)
cv_row = cur.fetchone()
cv_dict = {FEATURES[i]: float(cv_row[i] or 0) for i in range(len(FEATURES))}
print("  CV per feature:")
for feat, cv in sorted(cv_dict.items(), key=lambda x: -x[1]):
    bar = "█" * int(cv * 5)
    print(f"    {feat:28s} CV={cv:.3f}  {bar}")

# ─────────────────────────────────────────────────
# 2. Eta² (η²) — between-group variance / total variance
# Uses existing v2 segments as reference labels
# ─────────────────────────────────────────────────
print("\n2. Computing eta² (segment discrimination power) ...")

eta_sql = """
WITH base AS (
    SELECT
        f.*,
        s.segment
    FROM DB_TEAM_2.BASE_BASE.user_features_v2 f
    JOIN DB_TEAM_2.BASE_MARTS.user_segments_v2 s USING (user_id)
),
grand AS (
    SELECT """ + ",\n        ".join(
        [f"AVG(CAST(COALESCE({feat},0) AS FLOAT)) AS grand_{feat}" for feat in FEATURES]
    ) + """
    FROM base
),
group_means AS (
    SELECT
        segment,
        COUNT(*) AS n_seg,
        """ + ",\n        ".join(
            [f"AVG(CAST(COALESCE({feat},0) AS FLOAT)) AS mean_{feat}" for feat in FEATURES]
        ) + """
    FROM base
    GROUP BY segment
),
ss_between AS (
    SELECT """ + ",\n        ".join(
        [f"SUM(n_seg * POWER(mean_{feat} - (SELECT grand_{feat} FROM grand),2)) AS ssb_{feat}"
         for feat in FEATURES]
    ) + """
    FROM group_means
),
ss_total AS (
    SELECT """ + ",\n        ".join(
        [f"SUM(POWER(CAST(COALESCE({feat},0) AS FLOAT) - (SELECT grand_{feat} FROM grand),2)) AS sst_{feat}"
         for feat in FEATURES]
    ) + """
    FROM base
)
SELECT """ + ",\n".join(
    [f"ROUND(ssb.ssb_{feat} / NULLIF(sst.sst_{feat},0), 4) AS eta2_{feat}"
     for feat in FEATURES]
) + """
FROM ss_between ssb, ss_total sst
"""

cur.execute(eta_sql)
eta_row = cur.fetchone()
eta_dict = {FEATURES[i]: float(eta_row[i] or 0) for i in range(len(FEATURES))}
print("  Eta² per feature (higher = better segment separation):")
for feat, eta in sorted(eta_dict.items(), key=lambda x: -x[1]):
    bar = "█" * int(eta * 100)
    print(f"    {feat:28s} η²={eta:.4f}  {bar}")

# ─────────────────────────────────────────────────
# 3. Class imbalance — current v2 segment distribution
# ─────────────────────────────────────────────────
print("\n3. Class imbalance (current v2 segments) ...")
cur.execute("""
SELECT segment, COUNT(*) AS n,
       ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER (),1) AS pct
FROM DB_TEAM_2.BASE_MARTS.user_segments_v2
GROUP BY segment
ORDER BY n DESC
""")
imbalance_rows = cur.fetchall()
print("  Segment distribution:")
for row in imbalance_rows:
    bar = "█" * int(row[2] / 2)
    print(f"    {row[0]:22s} {row[1]:>7,}  {row[2]:5.1f}%  {bar}")

# ─────────────────────────────────────────────────
# 4. Feature means per segment — see what drives each
# ─────────────────────────────────────────────────
print("\n4. Feature means by segment ...")
top_features = [f for f, _ in sorted(eta_dict.items(), key=lambda x: -x[1])[:10]]

seg_sql = """
SELECT
    s.segment,
    COUNT(*) AS n,
    """ + ",\n    ".join(
        [f"ROUND(AVG(CAST(COALESCE(f.{feat},0) AS FLOAT)), 4) AS {feat}"
         for feat in top_features]
    ) + """
FROM DB_TEAM_2.BASE_BASE.user_features_v2 f
JOIN DB_TEAM_2.BASE_MARTS.user_segments_v2 s USING (user_id)
GROUP BY s.segment
ORDER BY n DESC
"""
cur.execute(seg_sql)
seg_rows = cur.fetchall()
seg_names = [r[0] for r in seg_rows]
seg_ns    = [r[1] for r in seg_rows]

print(f"\n  {'Segment':22s} {'N':>7}  " + "  ".join(f"{f[:12]:>12}" for f in top_features))
for row in seg_rows:
    vals = "  ".join(f"{float(row[i+2]):>12.4f}" for i in range(len(top_features)))
    print(f"  {row[0]:22s} {row[1]:>7,}  {vals}")

cur.close()
conn.close()

# ─────────────────────────────────────────────────
# 5. Visualise: CV ranking + Eta² + Imbalance
# ─────────────────────────────────────────────────
print("\n5. Generating plots ...")
plt.style.use('dark_background')
fig = plt.figure(figsize=(18, 14))
fig.patch.set_facecolor('#0d1117')
gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.35)

ACCENT = '#58a6ff'
GREEN  = '#3fb950'
ORANGE = '#d29922'
RED    = '#f85149'

# ── Panel 1: CV ranking ──
ax1 = fig.add_subplot(gs[0, 0])
sorted_cv = sorted(cv_dict.items(), key=lambda x: x[1])
feats_cv, vals_cv = zip(*sorted_cv)
colors_cv = [RED if v < 0.5 else ORANGE if v < 1.5 else ACCENT if v < 4 else GREEN for v in vals_cv]
bars = ax1.barh(range(len(feats_cv)), vals_cv, color=colors_cv, height=0.7)
ax1.set_yticks(range(len(feats_cv)))
ax1.set_yticklabels(feats_cv, fontsize=8)
ax1.set_xlabel('Coefficient of Variation (stddev/mean)', color='#c9d1d9')
ax1.set_title('Feature CV — Raw Discriminating Power', color='white', fontsize=11, fontweight='bold')
ax1.tick_params(colors='#c9d1d9')
for spine in ax1.spines.values(): spine.set_color('#30363d')
ax1.set_facecolor('#161b22')
# Threshold line at CV=1
ax1.axvline(1.0, color='#f85149', linestyle='--', alpha=0.5, linewidth=1)
ax1.text(1.02, 0, 'CV=1\nthreshold', color='#f85149', fontsize=7, va='bottom')
for i, (bar, v) in enumerate(zip(bars, vals_cv)):
    ax1.text(v + 0.05, i, f'{v:.2f}', va='center', ha='left', color='#c9d1d9', fontsize=7)

# ── Panel 2: Eta² ranking ──
ax2 = fig.add_subplot(gs[0, 1])
sorted_eta = sorted(eta_dict.items(), key=lambda x: x[1])
feats_eta, vals_eta = zip(*sorted_eta)
colors_eta = [RED if v < 0.001 else ORANGE if v < 0.005 else ACCENT if v < 0.02 else GREEN for v in vals_eta]
bars2 = ax2.barh(range(len(feats_eta)), vals_eta, color=colors_eta, height=0.7)
ax2.set_yticks(range(len(feats_eta)))
ax2.set_yticklabels(feats_eta, fontsize=8)
ax2.set_xlabel('η² (between-group variance / total variance)', color='#c9d1d9')
ax2.set_title('Feature η² — Segment Discrimination', color='white', fontsize=11, fontweight='bold')
ax2.tick_params(colors='#c9d1d9')
for spine in ax2.spines.values(): spine.set_color('#30363d')
ax2.set_facecolor('#161b22')
for i, (bar, v) in enumerate(zip(bars2, vals_eta)):
    ax2.text(v + 0.0001, i, f'{v:.4f}', va='center', ha='left', color='#c9d1d9', fontsize=7)

# ── Panel 3: Class imbalance ──
ax3 = fig.add_subplot(gs[1, 0])
seg_labels = [r[0] for r in imbalance_rows]
seg_counts = [r[1] for r in imbalance_rows]
seg_pcts   = [r[2] for r in imbalance_rows]
seg_colors = [GREEN, ACCENT, ORANGE, RED, '#bc8cff', '#ff7b72', '#ffa657'][:len(seg_labels)]
bars3 = ax3.barh(range(len(seg_labels)), seg_counts, color=seg_colors, height=0.6)
ax3.set_yticks(range(len(seg_labels)))
ax3.set_yticklabels(seg_labels, fontsize=9)
ax3.set_xlabel('User Count', color='#c9d1d9')
ax3.set_title('Class Imbalance — v2 Segment Sizes', color='white', fontsize=11, fontweight='bold')
ax3.tick_params(colors='#c9d1d9')
for spine in ax3.spines.values(): spine.set_color('#30363d')
ax3.set_facecolor('#161b22')
for i, (bar, n, pct) in enumerate(zip(bars3, seg_counts, seg_pcts)):
    ax3.text(n + 500, i, f'{n:,} ({pct}%)', va='center', ha='left', color='#c9d1d9', fontsize=8)

# ── Panel 4: Heatmap of feature means per segment (top 8 by eta²) ──
ax4 = fig.add_subplot(gs[1, 1])
top8 = [f for f, _ in sorted(eta_dict.items(), key=lambda x: -x[1])[:8]]

# Build matrix: segments × features, z-scored per feature
matrix = []
for row in seg_rows:
    matrix.append([float(row[i+2]) for i, f in enumerate(top_features) if f in top8])

# Use only top8
top8_idx = [top_features.index(f) for f in top8]
mat8 = np.array([[float(row[i+2]) for i in top8_idx] for row in seg_rows])

# Z-score each column
mat_z = (mat8 - mat8.mean(axis=0)) / (mat8.std(axis=0) + 1e-9)

cmap = LinearSegmentedColormap.from_list('rg', ['#f85149', '#161b22', '#3fb950'])
im = ax4.imshow(mat_z, cmap=cmap, aspect='auto', vmin=-2, vmax=2)
ax4.set_xticks(range(len(top8)))
ax4.set_xticklabels([f.replace('_','\n') for f in top8], fontsize=7, color='#c9d1d9')
ax4.set_yticks(range(len(seg_names)))
ax4.set_yticklabels(seg_names, fontsize=8, color='#c9d1d9')
ax4.set_title('Feature Profiles by Segment\n(z-scored, top 8 by η²)', color='white', fontsize=11, fontweight='bold')
for spine in ax4.spines.values(): spine.set_color('#30363d')
ax4.set_facecolor('#161b22')
# Add value annotations
for i in range(len(seg_names)):
    for j in range(len(top8)):
        ax4.text(j, i, f'{mat_z[i,j]:.1f}', ha='center', va='center',
                 color='white', fontsize=8, fontweight='bold')
plt.colorbar(im, ax=ax4, label='z-score', fraction=0.046, pad=0.04).ax.yaxis.label.set_color('#c9d1d9')

fig.suptitle('Feature Importance & Class Imbalance Analysis\nJustWatch Germany Dec 2025 — 307K Users',
             color='white', fontsize=14, fontweight='bold', y=0.98)

out_path = '/Users/marty/hackathon/berlin-data-ai-hackathon/feature_importance.png'
plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
plt.close()
print(f"  Saved: {out_path}")
print("\nAnalysis complete.")
