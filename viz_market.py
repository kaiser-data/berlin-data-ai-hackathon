"""
viz_market.py — Per-market segment contrast charts (all 15 T4 markets)
Reads: data/market_segment_summary.json
Writes: market_viz/market_<CC>.png  (one per market)
Style: dark theme matching viz_contrasts.py
"""
import json, os, sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Config ──────────────────────────────────────────────────────────────────
DATA_FILE = 'data/market_segment_summary.json'
OUT_DIR   = 'market_viz'

SEG_COLORS = {
    'Binge Watcher':    '#58a6ff',
    'Premium Buyer':    '#e85de0',
    'Deal Hunter':      '#3fb950',
    'Watchlist Hoarder':'#d29922',
    'Genre Loyalist':   '#bc8cff',
    'Trailer Scout':    '#f7c948',
    'Explorer':         '#8b949e',
}
BG       = '#0d1117'
PANEL_BG = '#161b22'
SPINE_C  = '#30363d'
TEXT_C   = '#c9d1d9'
SUBTEXT  = '#8b949e'

MARKET_NAMES = {
    'AR': 'Argentina', 'AU': 'Australia', 'BR': 'Brazil',   'CA': 'Canada',
    'DE': 'Germany',   'ES': 'Spain',     'FR': 'France',   'GB': 'United Kingdom',
    'ID': 'Indonesia', 'IN': 'India',     'IT': 'Italy',    'MX': 'Mexico',
    'PH': 'Philippines','TR': 'Turkey',   'US': 'United States',
}

os.makedirs(OUT_DIR, exist_ok=True)

# ── Load data ────────────────────────────────────────────────────────────────
with open(DATA_FILE) as f:
    raw = json.load(f)

# Index: data[geo_country][segment] = row dict
data = {}
for row in raw:
    cc  = row['GEO_COUNTRY']
    seg = row['PRIMARY_SEGMENT']
    if cc not in data:
        data[cc] = {}
    data[cc][seg] = row

markets = sorted(data.keys())
segments = ['Binge Watcher', 'Deal Hunter', 'Genre Loyalist',
            'Premium Buyer', 'Trailer Scout', 'Watchlist Hoarder', 'Explorer']

def get(cc, seg, field, default=0):
    return float(data.get(cc, {}).get(seg, {}).get(field, default) or default)

# Germany baseline (pct per segment)
de_pct = {seg: get('DE', seg, 'PCT') for seg in segments}

# ── Build figure for one market ──────────────────────────────────────────────
def build_fig(cc):
    name = MARKET_NAMES.get(cc, cc)
    fig = plt.figure(figsize=(20, 10))
    fig.patch.set_facecolor(BG)

    # ── Panel 1 (top-left): Segment distribution vs Germany ─────────────────
    ax1 = fig.add_axes([0.03, 0.50, 0.42, 0.43])
    ax1.set_facecolor(PANEL_BG)

    segs_sorted = sorted([s for s in segments if s != 'Explorer'],
                         key=lambda s: -get(cc, s, 'PCT')) + ['Explorer']
    y  = np.arange(len(segs_sorted))
    h  = 0.35
    market_pcts = [get(cc, s, 'PCT') for s in segs_sorted]
    de_pcts     = [de_pct[s]         for s in segs_sorted]

    bars1 = ax1.barh(y + h/2, market_pcts, h, color=[SEG_COLORS[s] for s in segs_sorted], alpha=0.9)
    bars2 = ax1.barh(y - h/2, de_pcts,     h, color=[SEG_COLORS[s] for s in segs_sorted], alpha=0.35, hatch='//')

    for bar, pct in zip(bars1, market_pcts):
        if pct > 0.5:
            ax1.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                     f'{pct:.1f}%', va='center', color=TEXT_C, fontsize=8)

    ax1.set_yticks(y)
    ax1.set_yticklabels(segs_sorted, color=TEXT_C, fontsize=9)
    ax1.set_xlabel('% of Users', color=SUBTEXT, fontsize=8)
    ax1.set_title(f'Segment Distribution — {name} vs Germany (//)', color='white', fontsize=10, fontweight='bold')
    ax1.tick_params(colors=TEXT_C)
    for sp in ax1.spines.values(): sp.set_color(SPINE_C)

    # ── Panel 2 (top-right): Key metrics by segment ──────────────────────────
    ax2 = fig.add_axes([0.55, 0.50, 0.43, 0.43])
    ax2.set_facecolor(PANEL_BG)

    named_segs = [s for s in segs_sorted if s != 'Explorer' and get(cc, s, 'N') > 0]
    metrics = [
        ('avg_seenlist',  'Avg Seenlist'),
        ('avg_trailers',  'Avg Trailers'),
        ('pct_free',      'Free% / 10'),
        ('pct_buy',       'Buy% / 10'),
    ]
    x = np.arange(len(named_segs))
    bar_w = 0.18
    for i, (field, label) in enumerate(metrics):
        vals = [get(cc, s, field) / (10 if 'pct' in field else 1) for s in named_segs]
        color = ['#58a6ff', '#f7c948', '#3fb950', '#e85de0'][i]
        ax2.bar(x + i*bar_w - 1.5*bar_w, vals, bar_w, label=label, color=color, alpha=0.85)

    ax2.set_xticks(x)
    ax2.set_xticklabels([s.replace(' ', '\n') for s in named_segs], color=TEXT_C, fontsize=7)
    ax2.set_ylabel('Value (% cols ÷10)', color=SUBTEXT, fontsize=8)
    ax2.set_title('Key Metrics by Segment', color='white', fontsize=10, fontweight='bold')
    ax2.legend(fontsize=7, facecolor=PANEL_BG, edgecolor=SPINE_C, labelcolor=TEXT_C, loc='upper right')
    ax2.tick_params(colors=TEXT_C)
    for sp in ax2.spines.values(): sp.set_color(SPINE_C)

    # ── Panel 3 (bottom-left): Monetization mirror — Deal Hunter vs Premium Buyer
    ax3 = fig.add_axes([0.03, 0.06, 0.42, 0.37])
    ax3.set_facecolor(PANEL_BG)

    mono_metrics = ['pct_free', 'pct_buy', 'pct_has_clickout', 'avg_trailers']
    mono_labels  = ['Free %', 'Buy/Rent %', 'Has Clickout %', 'Avg Trailers']
    mono_scale   = [1, 1, 1, 10]   # trailers ×10 for comparable scale
    dh = [get(cc, 'Deal Hunter',  m) * s for m, s in zip(mono_metrics, mono_scale)]
    pb = [get(cc, 'Premium Buyer', m) * s for m, s in zip(mono_metrics, mono_scale)]

    mx = np.arange(len(mono_labels))
    ax3.bar(mx - 0.2, dh, 0.38, label='Deal Hunter',  color='#3fb950', alpha=0.85)
    ax3.bar(mx + 0.2, pb, 0.38, label='Premium Buyer', color='#e85de0', alpha=0.85)
    ax3.set_xticks(mx)
    ax3.set_xticklabels(mono_labels, color=TEXT_C, fontsize=8)
    ax3.set_title('Monetization Mirror: Deal Hunter vs Premium Buyer', color='white', fontsize=9, fontweight='bold')
    ax3.legend(fontsize=8, facecolor=PANEL_BG, edgecolor=SPINE_C, labelcolor=TEXT_C)
    ax3.tick_params(colors=TEXT_C)
    for sp in ax3.spines.values(): sp.set_color(SPINE_C)
    ax3.text(0.98, 0.97, '* Trailers ×10 for scale', transform=ax3.transAxes,
             ha='right', va='top', color=SUBTEXT, fontsize=7)

    # ── Panel 4 (bottom-right): Delta vs Germany ─────────────────────────────
    ax4 = fig.add_axes([0.55, 0.06, 0.43, 0.37])
    ax4.set_facecolor(PANEL_BG)

    delta_segs = [s for s in segments if s != 'Explorer']
    deltas = [get(cc, s, 'PCT') - de_pct[s] for s in delta_segs]
    colors_d = ['#3fb950' if d >= 0 else '#f85149' for d in deltas]

    ax4.barh(range(len(delta_segs)), deltas, color=colors_d, alpha=0.85)
    ax4.axvline(0, color=SPINE_C, linewidth=1)
    ax4.set_yticks(range(len(delta_segs)))
    ax4.set_yticklabels(delta_segs, color=TEXT_C, fontsize=9)
    ax4.set_xlabel('Δ percentage points vs Germany', color=SUBTEXT, fontsize=8)
    ax4.set_title(f'Segment Share Delta vs Germany', color='white', fontsize=10, fontweight='bold')
    ax4.tick_params(colors=TEXT_C)
    for sp in ax4.spines.values(): sp.set_color(SPINE_C)

    for i, (d, s) in enumerate(zip(deltas, delta_segs)):
        if abs(d) > 0.1:
            ax4.text(d + (0.05 if d >= 0 else -0.05), i,
                     f'{d:+.1f}pp', va='center',
                     ha='left' if d >= 0 else 'right',
                     color=TEXT_C, fontsize=8)

    # ── Title ────────────────────────────────────────────────────────────────
    total_n = sum(get(cc, s, 'N') for s in segments)
    fig.suptitle(
        f'{name} ({cc})  —  {int(total_n):,} sampled users  |  v5 Segmentation on T4',
        color='white', fontsize=13, fontweight='bold', y=0.98
    )
    return fig

# ── Main loop ────────────────────────────────────────────────────────────────
target = sys.argv[1].upper() if len(sys.argv) > 1 else None

plt.style.use('dark_background')
for cc in markets:
    if target and cc != target:
        continue
    fig = build_fig(cc)
    out = f'{OUT_DIR}/market_{cc}.png'
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close()
    print(f'Saved: {out}')
