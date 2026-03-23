"""
Contrast visualizations for user_segments_v5
Highlights opposing segment pairs with multiple chart types.
"""
import snowflake.connector
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from matplotlib.gridspec import GridSpec
import matplotlib.patheffects as pe

conn = snowflake.connector.connect(
    account='OHHGHHL-ZM06890',
    user='martinkaiser.bln@gmail.com',
    password='DM#31BvDJOZxR7',
    warehouse='WH_TEAM_2_XS',
    login_timeout=15
)
cur = conn.cursor()

# ── Fetch segment means ──
print("Fetching segment stats ...")
cur.execute("""
SELECT primary_segment,
    COUNT(*) AS n,
    ROUND(AVG(CAST(seenlist_adds AS FLOAT)), 2)          AS avg_seenlist,
    ROUND(AVG(CAST(watchlist_adds AS FLOAT)), 2)         AS avg_watchlist,
    ROUND(AVG(CAST(trailer_plays AS FLOAT)), 2)          AS avg_trailers,
    ROUND(AVG(CAST(events_per_session AS FLOAT)), 2)     AS avg_eps,
    ROUND(AVG(CAST(free_ratio AS FLOAT)) * 100, 1)       AS avg_free_pct,
    ROUND(AVG(CAST(buyer_ratio AS FLOAT)) * 100, 1)      AS avg_buyer_pct,
    ROUND(AVG(CAST(top2_genre_share AS FLOAT)) * 100, 1) AS avg_top2_pct,
    ROUND(AVG(CAST(login_rate AS FLOAT)) * 100, 1)       AS avg_login_pct,
    ROUND(AVG(CAST(movie_ratio AS FLOAT)) * 100, 1)      AS avg_movie_pct,
    ROUND(AVG(CAST(unique_titles AS FLOAT)), 2)          AS avg_titles,
    ROUND(AVG(CAST(clickout_ratio AS FLOAT)) * 100, 1)   AS avg_clickout_pct,
    ROUND(AVG(CAST(has_clickout AS FLOAT)) * 100, 1)     AS pct_has_clickout
FROM DB_TEAM_2.BASE_MARTS.user_segments_v5
WHERE primary_segment != 'Explorer'
GROUP BY primary_segment
ORDER BY n DESC
""")
rows = cur.fetchall()
cols = [d[0].lower() for d in cur.description]
segs = {r[0]: {cols[i]: r[i] for i in range(len(cols))} for r in rows}

# Fetch scatter data: free_ratio vs buyer_ratio (all clickout users)
print("Fetching scatter data ...")
cur.execute("""
SELECT primary_segment,
    CAST(free_ratio AS FLOAT)   AS free_ratio,
    CAST(buyer_ratio AS FLOAT)  AS buyer_ratio,
    CAST(seenlist_adds AS FLOAT) AS seenlist,
    CAST(trailer_plays AS FLOAT) AS trailers
FROM DB_TEAM_2.BASE_MARTS.user_segments_v5
WHERE primary_segment IN ('Deal Hunter', 'Premium Buyer', 'Binge Watcher', 'Trailer Scout')
  AND has_clickout = 1
QUALIFY ROW_NUMBER() OVER (PARTITION BY primary_segment ORDER BY RANDOM()) <= 800
""")
scatter_rows = cur.fetchall()
scatter_cols = [d[0].lower() for d in cur.description]
cur.close(); conn.close()

scatter = {c: [] for c in scatter_cols}
for r in scatter_rows:
    for i, c in enumerate(scatter_cols):
        scatter[c].append(r[i] if r[i] is not None else 0.0)
scatter_seg = [str(v) for v in scatter.pop("primary_segment")]
scatter = {k: np.array(v, dtype=float) for k, v in scatter.items()}
scatter["primary_segment"] = scatter_seg

print("Plotting ...")

SEG_COLORS = {
    'Binge Watcher':    '#58a6ff',
    'Premium Buyer':    '#e85de0',
    'Deal Hunter':      '#3fb950',
    'Watchlist Hoarder':'#d29922',
    'Genre Loyalist':   '#bc8cff',
    'Trailer Scout':    '#f7c948',
    'Explorer':         '#8b949e',
}

MARKETING = {
    'Binge Watcher':    'The Devoted Viewer',
    'Premium Buyer':    'Premium Buyer',
    'Deal Hunter':      'The Savvy Streamer',
    'Watchlist Hoarder':'The Content Curator',
    'Genre Loyalist':   'The Niche Devotee',
    'Trailer Scout':    'Trailer Scout',
}

BG     = '#0d1117'
PANEL  = '#161b22'
BORDER = '#30363d'
TEXT   = '#c9d1d9'
MUTED  = '#8b949e'

plt.style.use('dark_background')
fig = plt.figure(figsize=(22, 14))
fig.patch.set_facecolor(BG)
gs = GridSpec(2, 3, figure=fig, hspace=0.38, wspace=0.32,
              left=0.05, right=0.97, top=0.92, bottom=0.06)

# ─────────────────────────────────────────────────────────────
# Panel 1 (top-left): Radar / spider chart — all 6 segments
# ─────────────────────────────────────────────────────────────
ax_r = fig.add_subplot(gs[0, 0], projection='polar')
ax_r.set_facecolor(PANEL)

RADAR_LABELS = ['Seenlist\nDepth', 'Watchlist\nSize', 'Trailer\nActivity',
                'Session\nDepth', 'Free\nContent%', 'TVOD\nBuy%',
                'Genre\nFocus', 'Login\nRate']

# Normalise each metric 0-1 across all named segments for radar
raw_matrix = {
    'Binge Watcher':    [segs['Binge Watcher']['avg_seenlist'],  segs['Binge Watcher']['avg_watchlist'],
                         segs['Binge Watcher']['avg_trailers'],  segs['Binge Watcher']['avg_eps'],
                         segs['Binge Watcher']['avg_free_pct'],  segs['Binge Watcher']['avg_buyer_pct'],
                         segs['Binge Watcher']['avg_top2_pct'],  segs['Binge Watcher']['avg_login_pct']],
    'Trailer Scout':    [segs['Trailer Scout']['avg_seenlist'],  segs['Trailer Scout']['avg_watchlist'],
                         segs['Trailer Scout']['avg_trailers'],  segs['Trailer Scout']['avg_eps'],
                         segs['Trailer Scout']['avg_free_pct'],  segs['Trailer Scout']['avg_buyer_pct'],
                         segs['Trailer Scout']['avg_top2_pct'],  segs['Trailer Scout']['avg_login_pct']],
    'Deal Hunter':      [segs['Deal Hunter']['avg_seenlist'],    segs['Deal Hunter']['avg_watchlist'],
                         segs['Deal Hunter']['avg_trailers'],    segs['Deal Hunter']['avg_eps'],
                         segs['Deal Hunter']['avg_free_pct'],    segs['Deal Hunter']['avg_buyer_pct'],
                         segs['Deal Hunter']['avg_top2_pct'],    segs['Deal Hunter']['avg_login_pct']],
    'Premium Buyer':    [segs['Premium Buyer']['avg_seenlist'],  segs['Premium Buyer']['avg_watchlist'],
                         segs['Premium Buyer']['avg_trailers'],  segs['Premium Buyer']['avg_eps'],
                         segs['Premium Buyer']['avg_free_pct'],  segs['Premium Buyer']['avg_buyer_pct'],
                         segs['Premium Buyer']['avg_top2_pct'],  segs['Premium Buyer']['avg_login_pct']],
    'Watchlist Hoarder':[segs['Watchlist Hoarder']['avg_seenlist'], segs['Watchlist Hoarder']['avg_watchlist'],
                         segs['Watchlist Hoarder']['avg_trailers'], segs['Watchlist Hoarder']['avg_eps'],
                         segs['Watchlist Hoarder']['avg_free_pct'], segs['Watchlist Hoarder']['avg_buyer_pct'],
                         segs['Watchlist Hoarder']['avg_top2_pct'], segs['Watchlist Hoarder']['avg_login_pct']],
    'Genre Loyalist':   [segs['Genre Loyalist']['avg_seenlist'], segs['Genre Loyalist']['avg_watchlist'],
                         segs['Genre Loyalist']['avg_trailers'], segs['Genre Loyalist']['avg_eps'],
                         segs['Genre Loyalist']['avg_free_pct'], segs['Genre Loyalist']['avg_buyer_pct'],
                         segs['Genre Loyalist']['avg_top2_pct'], segs['Genre Loyalist']['avg_login_pct']],
}

vals_arr = np.array(list(raw_matrix.values()), dtype=float)
col_min  = vals_arr.min(axis=0)
col_max  = vals_arr.max(axis=0)
norm_matrix = {seg: list((np.array(v, dtype=float) - col_min) / np.where(col_max - col_min > 0, col_max - col_min, 1))
               for seg, v in raw_matrix.items()}

N = len(RADAR_LABELS)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]

for seg, vals in norm_matrix.items():
    v = vals + vals[:1]
    ax_r.plot(angles, v, color=SEG_COLORS[seg], linewidth=2, alpha=0.9)
    ax_r.fill(angles, v, color=SEG_COLORS[seg], alpha=0.12)

ax_r.set_xticks(angles[:-1])
ax_r.set_xticklabels(RADAR_LABELS, color=TEXT, fontsize=7.5)
ax_r.set_yticks([0.25, 0.5, 0.75, 1.0])
ax_r.set_yticklabels(['', '', '', ''], color=MUTED)
ax_r.set_ylim(0, 1.0)
ax_r.grid(color=BORDER, linewidth=0.7, alpha=0.8)
ax_r.spines['polar'].set_color(BORDER)
ax_r.set_title('Segment Profiles — Radar View\n(all 6 named segments)', color='white',
               fontsize=10, fontweight='bold', pad=18)

# Radar legend
handles = [mpatches.Patch(color=SEG_COLORS[s], label=MARKETING[s]) for s in norm_matrix]
ax_r.legend(handles=handles, loc='lower center', bbox_to_anchor=(0.5, -0.28),
            ncol=2, fontsize=7, framealpha=0.3, facecolor=PANEL, edgecolor=BORDER,
            labelcolor=TEXT)

# ─────────────────────────────────────────────────────────────
# Panel 2 (top-center): Deal Hunter vs Premium Buyer — monetization mirror
# ─────────────────────────────────────────────────────────────
ax_m = fig.add_subplot(gs[0, 1])
ax_m.set_facecolor(PANEL)

metrics_m = ['Free/AVOD\nclickout %', 'Rent/Buy\nclickout %', 'Any\nClickout %',
             'Mon.\nDiversity', 'Avg\nTrailers']
dh = [segs['Deal Hunter']['avg_free_pct'],   segs['Deal Hunter']['avg_buyer_pct'],
      segs['Deal Hunter']['pct_has_clickout'],
      float(segs['Deal Hunter']['avg_clickout_pct']),
      segs['Deal Hunter']['avg_trailers']]
pb = [segs['Premium Buyer']['avg_free_pct'],  segs['Premium Buyer']['avg_buyer_pct'],
      segs['Premium Buyer']['pct_has_clickout'],
      float(segs['Premium Buyer']['avg_clickout_pct']),
      segs['Premium Buyer']['avg_trailers']]

x = np.arange(len(metrics_m))
w = 0.35
b1 = ax_m.bar(x - w/2, dh, w, color=SEG_COLORS['Deal Hunter'],   alpha=0.85, label='Savvy Streamer (Deal Hunter)')
b2 = ax_m.bar(x + w/2, pb, w, color=SEG_COLORS['Premium Buyer'], alpha=0.85, label='Premium Buyer')
for bar, val in zip(b1, dh):
    ax_m.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8,
              f'{val:.0f}', ha='center', va='bottom', color=SEG_COLORS['Deal Hunter'], fontsize=8, fontweight='bold')
for bar, val in zip(b2, pb):
    ax_m.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8,
              f'{val:.0f}', ha='center', va='bottom', color=SEG_COLORS['Premium Buyer'], fontsize=8, fontweight='bold')

ax_m.set_xticks(x)
ax_m.set_xticklabels(metrics_m, color=TEXT, fontsize=8)
ax_m.set_ylabel('Value (%)', color=TEXT)
ax_m.tick_params(colors=TEXT)
for spine in ax_m.spines.values(): spine.set_color(BORDER)
ax_m.set_title('Savvy Streamer vs Premium Buyer\n"Free-Seeker ↔ Pay-to-Own Mirror"', 
               color='white', fontsize=10, fontweight='bold')
ax_m.legend(fontsize=8, facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT, framealpha=0.5)
ax_m.set_facecolor(PANEL)

# ─────────────────────────────────────────────────────────────
# Panel 3 (top-right): Engagement spectrum — Trailer Scout vs Binge Watcher
# ─────────────────────────────────────────────────────────────
ax_e = fig.add_subplot(gs[0, 2])
ax_e.set_facecolor(PANEL)

metrics_e = ['Avg Seenlist\n(watched)', 'Avg Watchlist\n(saved)', 'Avg Trailer\nPlays',
             'Session\nDepth (eps)', 'Unique Titles\nBrowsed', 'Movie\nRatio %']
ts_vals = [segs['Trailer Scout']['avg_seenlist'],  segs['Trailer Scout']['avg_watchlist'],
           segs['Trailer Scout']['avg_trailers'],   segs['Trailer Scout']['avg_eps'],
           segs['Trailer Scout']['avg_titles'],      segs['Trailer Scout']['avg_movie_pct']]
bw_vals = [segs['Binge Watcher']['avg_seenlist'],  segs['Binge Watcher']['avg_watchlist'],
           segs['Binge Watcher']['avg_trailers'],   segs['Binge Watcher']['avg_eps'],
           segs['Binge Watcher']['avg_titles'],      segs['Binge Watcher']['avg_movie_pct']]

x = np.arange(len(metrics_e))
b3 = ax_e.bar(x - w/2, ts_vals, w, color=SEG_COLORS['Trailer Scout'],  alpha=0.85, label='Trailer Scout')
b4 = ax_e.bar(x + w/2, bw_vals, w, color=SEG_COLORS['Binge Watcher'],  alpha=0.85, label='Devoted Viewer (Binge)')
for bar, val in zip(b3, ts_vals):
    ax_e.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15,
              f'{val:.1f}', ha='center', va='bottom', color=SEG_COLORS['Trailer Scout'], fontsize=8, fontweight='bold')
for bar, val in zip(b4, bw_vals):
    ax_e.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15,
              f'{val:.1f}', ha='center', va='bottom', color=SEG_COLORS['Binge Watcher'], fontsize=8, fontweight='bold')

ax_e.set_xticks(x)
ax_e.set_xticklabels(metrics_e, color=TEXT, fontsize=8)
ax_e.set_ylabel('Value', color=TEXT)
ax_e.tick_params(colors=TEXT)
for spine in ax_e.spines.values(): spine.set_color(BORDER)
ax_e.set_title('Trailer Scout vs Devoted Viewer\n"Research Phase ↔ Full Consumer"',
               color='white', fontsize=10, fontweight='bold')
ax_e.legend(fontsize=8, facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT, framealpha=0.5)
ax_e.set_facecolor(PANEL)

# ─────────────────────────────────────────────────────────────
# Panel 4 (bottom-left): Scatter — free_ratio vs buyer_ratio
# ─────────────────────────────────────────────────────────────
ax_s1 = fig.add_subplot(gs[1, 0])
ax_s1.set_facecolor(PANEL)

segs_scatter = ['Deal Hunter', 'Premium Buyer']
for seg in segs_scatter:
    mask = np.array(scatter['primary_segment']) == seg
    ax_s1.scatter(
        scatter['free_ratio'][mask],
        scatter['buyer_ratio'][mask],
        c=SEG_COLORS[seg], s=12, alpha=0.45, linewidths=0, label=MARKETING[seg]
    )

# Diagonal separation line
ax_s1.plot([0, 1], [1, 0], color=MUTED, linewidth=1, linestyle='--', alpha=0.5)
ax_s1.text(0.75, 0.78, 'Premium\nBuyer zone', color=SEG_COLORS['Premium Buyer'],
           fontsize=8, fontstyle='italic', alpha=0.9)
ax_s1.text(0.05, 0.05, 'Savvy Streamer\nzone', color=SEG_COLORS['Deal Hunter'],
           fontsize=8, fontstyle='italic', alpha=0.9)

ax_s1.set_xlabel('Free/AVOD Ratio', color=TEXT)
ax_s1.set_ylabel('Rent/Buy Ratio', color=TEXT)
ax_s1.set_xlim(-0.02, 1.02); ax_s1.set_ylim(-0.02, 1.02)
ax_s1.tick_params(colors=TEXT)
for spine in ax_s1.spines.values(): spine.set_color(BORDER)
ax_s1.set_title('Monetization Intent Space\n(clickout users only)',
                color='white', fontsize=10, fontweight='bold')
ax_s1.legend(fontsize=8, facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT, framealpha=0.5)

# ─────────────────────────────────────────────────────────────
# Panel 5 (bottom-center): Scatter — seenlist vs trailer_plays
# ─────────────────────────────────────────────────────────────
ax_s2 = fig.add_subplot(gs[1, 1])
ax_s2.set_facecolor(PANEL)

for seg in ['Binge Watcher', 'Trailer Scout']:
    mask = np.array(scatter['primary_segment']) == seg
    # Cap for readability
    x_vals = np.minimum(scatter['seenlist'][mask], 40)
    y_vals = np.minimum(scatter['trailers'][mask], 12)
    ax_s2.scatter(x_vals, y_vals, c=SEG_COLORS[seg], s=14, alpha=0.45,
                  linewidths=0, label=MARKETING[seg])

ax_s2.axhline(y=3, color=SEG_COLORS['Trailer Scout'], linewidth=1, linestyle='--', alpha=0.4)
ax_s2.axvline(x=3, color=SEG_COLORS['Binge Watcher'], linewidth=1, linestyle='--', alpha=0.4)
ax_s2.text(20, 3.3, 'Trailer gate (≥3)', color=SEG_COLORS['Trailer Scout'], fontsize=7.5, alpha=0.8)
ax_s2.text(3.2, 0.3, 'Binge zone', color=SEG_COLORS['Binge Watcher'], fontsize=7.5, alpha=0.8)

ax_s2.set_xlabel('Seenlist Adds (capped at 40)', color=TEXT)
ax_s2.set_ylabel('Trailer Plays (capped at 12)', color=TEXT)
ax_s2.tick_params(colors=TEXT)
for spine in ax_s2.spines.values(): spine.set_color(BORDER)
ax_s2.set_title('Consumption vs Research Space\n(Devoted Viewer ↔ Trailer Scout)',
                color='white', fontsize=10, fontweight='bold')
ax_s2.legend(fontsize=8, facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT, framealpha=0.5)

# ─────────────────────────────────────────────────────────────
# Panel 6 (bottom-right): Segment size + commercial value summary
# ─────────────────────────────────────────────────────────────
ax_v = fig.add_subplot(gs[1, 2])
ax_v.set_facecolor(PANEL)
ax_v.axis('off')

SEGMENT_ORDER = ['Trailer Scout', 'Watchlist Hoarder', 'Genre Loyalist',
                 'Premium Buyer', 'Deal Hunter', 'Binge Watcher']
COMMERCIAL = {
    'Binge Watcher':    ('★★★★★', 'Retention, subscription'),
    'Premium Buyer':    ('★★★★★', 'TVOD, early access, upsell'),
    'Deal Hunter':      ('★★★☆☆', 'AVOD, free trials, FAST'),
    'Watchlist Hoarder':('★★★☆☆', 'Reminders, new seasons'),
    'Genre Loyalist':   ('★★★★☆', 'Niche titles, franchise'),
    'Trailer Scout':    ('★★★★☆', 'Launch campaigns, day-1 offers'),
}

ax_v.text(0.05, 0.97, 'Segment Commercial Value', color='white', fontsize=11,
          fontweight='bold', transform=ax_v.transAxes, va='top')
ax_v.text(0.05, 0.91, f"{'Segment':<22} {'Size':>7}  {'LTV':>6}  Best Use", color=MUTED,
          fontsize=8, transform=ax_v.transAxes, va='top', family='monospace')
ax_v.axhline(y=0, xmin=0, xmax=1, color=BORDER)

y = 0.84
for seg in SEGMENT_ORDER:
    s = segs[seg]
    stars, use = COMMERCIAL[seg]
    pct = float(s['n']) / 307537 * 100
    line = f"{MARKETING[seg]:<22} {int(s['n']):>7,}  {stars}  {use}"
    ax_v.text(0.05, y, line, color=SEG_COLORS[seg], fontsize=8,
              transform=ax_v.transAxes, va='top', family='monospace')
    y -= 0.115

ax_v.text(0.05, 0.16, '★ = Commercial / marketing value', color=MUTED, fontsize=7.5,
          transform=ax_v.transAxes)
ax_v.text(0.05, 0.09, 'Explorer (45.4%): broad reach, low intent', color=SEG_COLORS['Explorer'],
          fontsize=8, transform=ax_v.transAxes, family='monospace')
ax_v.text(0.05, 0.03,
          'Key insight: Premium Buyer & Deal Hunter are monetization mirrors.\n'
          'Trailer Scout is the consideration-phase pipeline for Devoted Viewers.',
          color='#c9d1d9', fontsize=7.5, transform=ax_v.transAxes, fontstyle='italic')

# ─────────────────────────────────────────────────────────────
fig.suptitle(
    'JustWatch Audience Segmentation v5 — Opposing Group Analysis  |  307K Germany users  |  Dec 2025',
    color='white', fontsize=14, fontweight='bold', y=0.97
)

out = '/Users/marty/hackathon/berlin-data-ai-hackathon/segment_contrasts.png'
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print(f"Saved: {out}")
