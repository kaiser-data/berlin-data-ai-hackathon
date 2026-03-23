"""
viz_segment_profiles.py — How each named segment behaves differently across countries
One figure per named segment, showing key metric bars for every market.
Germany is highlighted as the baseline reference.
Reads: data/market_segment_summary.json
Writes: market_viz/segment_profile_<SegmentName>.png  (6 files)
"""
import json, os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

DATA_FILE = 'data/market_segment_summary.json'
OUT_DIR   = 'market_viz'

SEG_COLORS = {
    'Binge Watcher':     '#58a6ff',
    'Premium Buyer':     '#e85de0',
    'Deal Hunter':       '#3fb950',
    'Watchlist Hoarder': '#d29922',
    'Genre Loyalist':    '#bc8cff',
    'Trailer Scout':     '#f7c948',
}
BG       = '#0d1117'
PANEL_BG = '#161b22'
SPINE_C  = '#30363d'
TEXT_C   = '#c9d1d9'
SUBTEXT  = '#8b949e'
DE_COLOR = '#f0883e'

MARKET_LABELS = {
    'AR': 'Argentina', 'AU': 'Australia', 'BR': 'Brazil',   'CA': 'Canada',
    'DE': 'Germany',   'ES': 'Spain',     'FR': 'France',   'GB': 'UK',
    'ID': 'Indonesia', 'IN': 'India',     'IT': 'Italy',    'MX': 'Mexico',
    'PH': 'Philippines','TR': 'Turkey',   'US': 'USA',
}

with open(DATA_FILE) as f:
    raw = json.load(f)

data = {}
for row in raw:
    cc  = row['GEO_COUNTRY']
    seg = row['PRIMARY_SEGMENT']
    if cc not in data: data[cc] = {}
    data[cc][seg] = row

def get(cc, seg, field, default=0):
    return float(data.get(cc, {}).get(seg, {}).get(field, default) or default)

markets = sorted(data.keys())

# Metrics to show for each segment, tuned to what's most discriminating
SEGMENT_METRICS = {
    'Binge Watcher': [
        ('avg_seenlist',           'Avg Seen\n(titles marked)',   1,   '#58a6ff'),
        ('avg_eps',                'Events/Session',              1,   '#79c0ff'),
        ('avg_active_days',        'Active Days',                 1,   '#b3d9ff'),
        ('pct_movie',              'Movie % / 10',               10,   '#d29922'),
        ('pct_login',              'Login Rate %\n/ 10',         10,   '#3fb950'),
        ('avg_unique_titles',      'Unique Titles',               1,   '#bc8cff'),
    ],
    'Deal Hunter': [
        ('pct_free',               'Free Click %',                1,   '#3fb950'),
        ('pct_has_clickout',       'Has Clickout %',              1,   '#56d364'),
        ('pct_buy',                'Buy/Rent %',                  1,   '#f85149'),
        ('avg_eps',                'Events/Session',              1,   '#79c0ff'),
        ('avg_trailers',           'Avg Trailers ×5',             5,   '#f7c948'),
        ('pct_genre_concentration','Genre Conc. %',               1,   '#bc8cff'),
    ],
    'Trailer Scout': [
        ('avg_trailers',           'Avg Trailers',                1,   '#f7c948'),
        ('avg_unique_titles',      'Unique Titles',               1,   '#e3b341'),
        ('pct_movie',              'Movie % / 10',               10,   '#d29922'),
        ('avg_eps',                'Events/Session',              1,   '#79c0ff'),
        ('pct_has_clickout',       'Has Clickout %',              1,   '#3fb950'),
        ('avg_active_days',        'Active Days',                 1,   '#b3d9ff'),
    ],
    'Premium Buyer': [
        ('pct_buy',                'Buy/Rent %',                  1,   '#e85de0'),
        ('pct_free',               'Free Click %',                1,   '#f85149'),
        ('pct_has_clickout',       'Has Clickout %',              1,   '#bc8cff'),
        ('avg_eps',                'Events/Session',              1,   '#79c0ff'),
        ('avg_active_days',        'Active Days',                 1,   '#b3d9ff'),
        ('avg_unique_titles',      'Unique Titles',               1,   '#e3b341'),
    ],
    'Genre Loyalist': [
        ('pct_genre_concentration','Genre Conc. %\n(top-2)',      1,   '#bc8cff'),
        ('avg_unique_titles',      'Unique Titles',               1,   '#e3b341'),
        ('pct_movie',              'Movie % / 10',               10,   '#d29922'),
        ('avg_eps',                'Events/Session',              1,   '#79c0ff'),
        ('pct_has_clickout',       'Has Clickout %',              1,   '#3fb950'),
        ('avg_trailers',           'Avg Trailers ×5',             5,   '#f7c948'),
    ],
    'Watchlist Hoarder': [
        ('avg_seenlist',           'Avg Seenlist',                1,   '#d29922'),
        ('pct_login',              'Login Rate %\n/ 10',         10,   '#3fb950'),
        ('avg_unique_titles',      'Unique Titles',               1,   '#e3b341'),
        ('avg_eps',                'Events/Session',              1,   '#79c0ff'),
        ('pct_has_clickout',       'Has Clickout %',              1,   '#bc8cff'),
        ('avg_active_days',        'Active Days',                 1,   '#b3d9ff'),
    ],
}

plt.style.use('dark_background')

for seg, metrics in SEGMENT_METRICS.items():
    seg_color = SEG_COLORS[seg]
    safe_name = seg.replace(' ', '_')

    # Filter to markets that actually have this segment
    present = [cc for cc in markets if get(cc, seg, 'N') >= 50]
    if not present:
        print(f'  Skipping {seg} — too few users in all markets')
        continue

    # Sort markets by segment size (pct)
    present_sorted = sorted(present, key=lambda cc: -get(cc, seg, 'PCT'))

    n_markets = len(present_sorted)
    n_metrics = len(metrics)
    fig_h = max(10, n_markets * 0.55)
    fig = plt.figure(figsize=(22, fig_h))
    fig.patch.set_facecolor(BG)

    # ── Left panel: segment size bar ─────────────────────────────────────────
    ax_size = fig.add_axes([0.02, 0.08, 0.14, 0.83])
    ax_size.set_facecolor(PANEL_BG)

    sizes = [get(cc, seg, 'PCT') for cc in present_sorted]
    y = np.arange(n_markets)
    colors = [DE_COLOR if cc == 'DE' else seg_color for cc in present_sorted]
    ax_size.barh(y, sizes, color=colors, alpha=0.85)
    for i, (cc, pct) in enumerate(zip(present_sorted, sizes)):
        ax_size.text(pct + 0.05, i, f'{pct:.1f}%', va='center', color=TEXT_C, fontsize=8)
    ax_size.set_yticks(y)
    ax_size.set_yticklabels([f'★ {MARKET_LABELS[cc]}' if cc == 'DE' else MARKET_LABELS[cc]
                             for cc in present_sorted], color=TEXT_C, fontsize=8)
    ax_size.set_xlabel('% of market', color=SUBTEXT, fontsize=8)
    ax_size.set_title('Segment\nShare', color='white', fontsize=9, fontweight='bold')
    ax_size.tick_params(colors=TEXT_C)
    for sp in ax_size.spines.values(): sp.set_color(SPINE_C)

    # ── Right panels: one panel per metric ───────────────────────────────────
    panel_w = 0.12
    panel_gap = 0.005
    x_start = 0.20

    for mi, (field, label, divisor, bar_color) in enumerate(metrics):
        x0 = x_start + mi * (panel_w + panel_gap)
        ax = fig.add_axes([x0, 0.08, panel_w, 0.83])
        ax.set_facecolor(PANEL_BG)

        vals = [get(cc, seg, field) / divisor for cc in present_sorted]
        de_val = get('DE', seg, field) / divisor

        bar_colors = [DE_COLOR if cc == 'DE' else bar_color for cc in present_sorted]
        ax.barh(y, vals, color=bar_colors, alpha=0.85)

        # Germany reference line
        ax.axvline(de_val, color=DE_COLOR, linewidth=1.2, linestyle='--', alpha=0.6)

        # Value labels on bars
        for i, v in enumerate(vals):
            if v > 0.05:
                ax.text(v + max(vals)*0.02, i, f'{v:.1f}', va='center',
                        color=TEXT_C, fontsize=7)

        ax.set_yticks(y)
        ax.set_yticklabels([], visible=False)
        ax.set_title(label, color=bar_color, fontsize=8, fontweight='bold')
        ax.tick_params(colors=TEXT_C, labelsize=7)
        for sp in ax.spines.values(): sp.set_color(SPINE_C)
        # Show x ticks only
        ax.set_xlabel('', color=SUBTEXT, fontsize=7)

    # Count labels on right edge
    ax_n = fig.add_axes([x_start + n_metrics*(panel_w + panel_gap) + 0.005, 0.08, 0.04, 0.83])
    ax_n.set_facecolor(PANEL_BG)
    ax_n.barh(y, [get(cc, seg, 'N') for cc in present_sorted],
              color=[DE_COLOR if cc == 'DE' else '#8b949e' for cc in present_sorted], alpha=0.6)
    ax_n.set_yticks(y)
    ax_n.set_yticklabels([], visible=False)
    ax_n.set_title('N users', color=SUBTEXT, fontsize=8)
    ax_n.tick_params(colors=TEXT_C, labelsize=6)
    for sp in ax_n.spines.values(): sp.set_color(SPINE_C)

    # Germany baseline annotation
    fig.text(0.20, 0.025,
             f'★ = Germany baseline  |  Orange dashed line = Germany value  '
             f'|  Markets sorted by {seg} share descending',
             color=SUBTEXT, fontsize=8, ha='left')

    fig.suptitle(
        f'{seg}  —  Cross-Market Profile  |  T4, 50K sample/market, per-market normalisation',
        color=seg_color, fontsize=13, fontweight='bold', y=0.985
    )

    out = f'{OUT_DIR}/segment_profile_{safe_name}.png'
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close()
    print(f'Saved: {out}')
