"""
Step 5: PCA + t-SNE on user_segments_v3 (20 features)
Fetch sample, run sklearn PCA + TSNE, plot dark-theme visualisation.
"""
import snowflake.connector
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

conn = snowflake.connector.connect(
    account='OHHGHHL-ZM06890',
    user='martinkaiser.bln@gmail.com',
    password='DM#31BvDJOZxR7',
    warehouse='WH_TEAM_2_XS',
    login_timeout=15
)
cur = conn.cursor()

FEATURES = [
    'seenlist_adds','watchlist_adds','unique_titles','trailer_plays',
    'events_per_session','active_days','COALESCE(avg_session_mins,0)',
    'COALESCE(completion_ratio,0)',
    'CAST(has_clickout AS FLOAT)','clickout_ratio',
    'COALESCE(buyer_ratio,0)','COALESCE(free_ratio,0)',
    'CAST(monetization_diversity AS FLOAT)',
    'show_ratio','movie_ratio',
    'top2_genre_share','CAST(genre_count AS FLOAT)',
    'weekend_ratio','evening_ratio','holiday_ratio',
]
FEAT_LABELS = [
    'seenlist','watchlist','unique_titles','trailer_plays',
    'eps','active_days','session_mins','completion_ratio',
    'has_clickout','clickout_ratio','buyer_ratio','free_ratio',
    'mon_diversity','show_ratio','movie_ratio',
    'top2_genre_share','genre_count','weekend','evening','holiday',
]

# Segment colours
SEG_COLORS = {
    'Binge Watcher':    '#58a6ff',
    'Deal Hunter':      '#3fb950',
    'Watchlist Hoarder':'#d29922',
    'Genre Loyalist':   '#bc8cff',
    'Holiday Viewer':   '#ff7b72',
    'Evening Browser':  '#ffa657',
    'Weekend Warrior':  '#79c0ff',
    'Trailer Gazer':    '#56d364',
    'Passive Browser':  '#f0883e',
    'Social Viewer':    '#e3b341',
    'Explorer':         '#8b949e',
}

# Effective segment label for Explorer (use sub-type)
label_sql = """
SELECT
    CASE WHEN primary_segment = 'Explorer' THEN COALESCE(explorer_subtype, 'Explorer')
         ELSE primary_segment END AS segment_label,
    {feat_list}
FROM DB_TEAM_2.BASE_MARTS.user_segments_v3
QUALIFY ROW_NUMBER() OVER (PARTITION BY
    CASE WHEN primary_segment = 'Explorer' THEN COALESCE(explorer_subtype, 'Explorer')
         ELSE primary_segment END
    ORDER BY RANDOM()) <= 2000
""".format(feat_list=", ".join(FEATURES))

print("Fetching sample (up to 2K per segment) ...")
cur.execute(label_sql)
rows = cur.fetchall()
cur.close(); conn.close()

labels_raw = [r[0] for r in rows]
X_raw = np.array([[float(v) if v is not None else 0.0 for v in r[1:]] for r in rows])
X_raw = np.nan_to_num(X_raw)
print(f"  Fetched {len(rows):,} users across {len(set(labels_raw))} segments")

# Standardise
scaler = StandardScaler()
X = scaler.fit_transform(X_raw)

# PCA
print("Running PCA (20 features) ...")
pca = PCA(n_components=5)
X_pca = pca.fit_transform(X)
var = pca.explained_variance_ratio_
print(f"  Variance: PC1={var[0]*100:.1f}%  PC2={var[1]*100:.1f}%  PC3={var[2]*100:.1f}%")
print(f"  Cumulative 3 PCs: {sum(var[:3])*100:.1f}%")

# t-SNE on first 10 PCs for speed
print("Running t-SNE (on first 10 PCA components) ...")
pca10 = PCA(n_components=min(10, X.shape[1]))
X10 = pca10.fit_transform(X)
tsne = TSNE(n_components=2, perplexity=40, max_iter=1000, random_state=42,
            learning_rate='auto', init='pca')
X_tsne = tsne.fit_transform(X10)
print("  t-SNE done.")

# ── Plot ──
plt.style.use('dark_background')
fig = plt.figure(figsize=(20, 9))
fig.patch.set_facecolor('#0d1117')

# PCA loadings reference
ax0 = fig.add_axes([0.00, 0.0, 0.22, 1.0])
ax0.set_facecolor('#0d1117')
ax0.axis('off')
sorted_feat_by_pc1 = sorted(zip(FEAT_LABELS, pca.components_[0]), key=lambda x: -abs(x[1]))
ax0.text(0.05, 0.97, 'PC1 Loadings (top 10)', color='white', fontsize=10,
         fontweight='bold', transform=ax0.transAxes, va='top')
for i, (feat, loading) in enumerate(sorted_feat_by_pc1[:10]):
    color = '#58a6ff' if loading > 0 else '#f85149'
    ax0.text(0.05, 0.91 - i*0.055, f'{"+" if loading>0 else ""}{loading:.3f}  {feat}',
             color=color, fontsize=9, transform=ax0.transAxes, family='monospace')
ax0.text(0.05, 0.35, f'Variance explained:', color='#8b949e', fontsize=9,
         transform=ax0.transAxes)
for i, (pct, label) in enumerate(zip(var[:5]*100, ['PC1','PC2','PC3','PC4','PC5'])):
    ax0.text(0.05, 0.30 - i*0.045, f'  {label}: {pct:.1f}%', color='#c9d1d9', fontsize=9,
             transform=ax0.transAxes, family='monospace')
ax0.text(0.05, 0.08, f'Cumul. 3 PCs: {sum(var[:3])*100:.1f}%', color='#3fb950', fontsize=9,
         fontweight='bold', transform=ax0.transAxes)

# PCA 2D scatter
ax1 = fig.add_axes([0.24, 0.08, 0.35, 0.85])
ax1.set_facecolor('#161b22')
for seg, col in SEG_COLORS.items():
    mask = np.array(labels_raw) == seg
    if mask.sum() > 0:
        ax1.scatter(X_pca[mask, 0], X_pca[mask, 1],
                    c=col, s=8, alpha=0.6, label=seg, linewidths=0)
ax1.set_xlabel(f'PC1 ({var[0]*100:.1f}% var)', color='#c9d1d9')
ax1.set_ylabel(f'PC2 ({var[1]*100:.1f}% var)', color='#c9d1d9')
ax1.set_title('PCA — PC1 vs PC2', color='white', fontsize=12, fontweight='bold')
ax1.tick_params(colors='#c9d1d9')
for spine in ax1.spines.values(): spine.set_color('#30363d')

# t-SNE scatter
ax2 = fig.add_axes([0.62, 0.08, 0.37, 0.85])
ax2.set_facecolor('#161b22')
for seg, col in SEG_COLORS.items():
    mask = np.array(labels_raw) == seg
    if mask.sum() > 0:
        ax2.scatter(X_tsne[mask, 0], X_tsne[mask, 1],
                    c=col, s=8, alpha=0.6, label=seg, linewidths=0)
ax2.set_xlabel('t-SNE 1', color='#c9d1d9')
ax2.set_ylabel('t-SNE 2', color='#c9d1d9')
ax2.set_title('t-SNE (non-linear structure)', color='white', fontsize=12, fontweight='bold')
ax2.tick_params(colors='#c9d1d9')
for spine in ax2.spines.values(): spine.set_color('#30363d')

# Shared legend
handles = [mpatches.Patch(color=c, label=s) for s, c in SEG_COLORS.items()
           if s in set(labels_raw)]
fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.62, 0.07),
           ncol=len(handles), fontsize=8, framealpha=0.3,
           facecolor='#161b22', edgecolor='#30363d',
           labelcolor='#c9d1d9')

fig.suptitle(
    f'Segmentation v3 — PCA & t-SNE  |  307K users (2K sample/segment)  |  20 features\n'
    f'Cumul. variance 3 PCs: {sum(var[:3])*100:.1f}%   (v2 was 32.1%)',
    color='white', fontsize=13, fontweight='bold', y=0.99
)

out = '/Users/marty/hackathon/berlin-data-ai-hackathon/segments_pca_v3.png'
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
plt.close()
print(f"\nSaved: {out}")
