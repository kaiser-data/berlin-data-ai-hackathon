"""
viz_market_comparison.py — Final 3-panel cross-market overview
Reads: data/market_segment_summary.json
Writes: market_comparison_overview.png
"""
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import TwoSlopeNorm

DATA_FILE = 'data/market_segment_summary.json'

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

markets  = sorted(data.keys())
segments = ['Binge Watcher', 'Deal Hunter', 'Genre Loyalist',
            'Premium Buyer', 'Trailer Scout', 'Watchlist Hoarder', 'Explorer']
named    = [s for s in segments if s != 'Explorer']

# Sort markets by Trailer Scout % (most interesting differentiator)
markets_sorted = sorted(markets, key=lambda cc: -get(cc, 'Trailer Scout', 'PCT'))

# ── Figure ───────────────────────────────────────────────────────────────────
plt.style.use('dark_background')
fig = plt.figure(figsize=(24, 14))
fig.patch.set_facecolor(BG)

# ── Panel 1 (left, tall): Stacked bar — segment mix all markets ─────────────
ax1 = fig.add_axes([0.03, 0.10, 0.38, 0.82])
ax1.set_facecolor(PANEL_BG)

seg_order = ['Binge Watcher', 'Premium Buyer', 'Genre Loyalist',
             'Trailer Scout', 'Deal Hunter', 'Watchlist Hoarder', 'Explorer']

y  = np.arange(len(markets_sorted))
left = np.zeros(len(markets_sorted))
for seg in seg_order:
    vals = np.array([get(cc, seg, 'PCT') for cc in markets_sorted])
    bars = ax1.barh(y, vals, left=left, color=SEG_COLORS[seg], label=seg, alpha=0.88)
    # Label segments ≥ 2%
    for i, (v, l) in enumerate(zip(vals, left)):
        if v >= 2.0:
            ax1.text(l + v/2, i, f'{v:.1f}', ha='center', va='center',
                     color='white', fontsize=7, fontweight='bold')
    left += vals

# Germany highlight
de_idx = markets_sorted.index('DE')
ax1.axhline(de_idx + 0.5, color='#f0883e', linewidth=1.5, linestyle='--', alpha=0.7)
ax1.axhline(de_idx - 0.5, color='#f0883e', linewidth=1.5, linestyle='--', alpha=0.7)

ax1.set_yticks(y)
labels = [f'★ {MARKET_NAMES[cc]} ({cc})' if cc == 'DE' else f'{MARKET_NAMES[cc]} ({cc})'
          for cc in markets_sorted]
ax1.set_yticklabels(labels, color=TEXT_C, fontsize=9)
ax1.set_xlabel('% of Users', color=SUBTEXT)
ax1.set_title('Segment Mix by Market\n(sorted by Trailer Scout %)', color='white',
              fontsize=11, fontweight='bold')
ax1.tick_params(colors=TEXT_C)
for sp in ax1.spines.values(): sp.set_color(SPINE_C)

handles = [mpatches.Patch(color=SEG_COLORS[s], label=s) for s in seg_order]
ax1.legend(handles=handles, loc='lower right', fontsize=8,
           facecolor=PANEL_BG, edgecolor=SPINE_C, labelcolor=TEXT_C)

# ── Panel 2 (top-right): Heatmap — delta vs Germany ─────────────────────────
ax2 = fig.add_axes([0.46, 0.42, 0.52, 0.50])
ax2.set_facecolor(PANEL_BG)

hm_metrics = [
    ('Binge %',    lambda cc: get(cc,'Binge Watcher','PCT')),
    ('Trailer %',  lambda cc: get(cc,'Trailer Scout','PCT')),
    ('Deal %',     lambda cc: get(cc,'Deal Hunter','PCT')),
    ('Premium %',  lambda cc: get(cc,'Premium Buyer','PCT')),
    ('Loyalist %', lambda cc: get(cc,'Genre Loyalist','PCT')),
    ('Explorer %', lambda cc: get(cc,'Explorer','PCT')),
    ('Avg Seenlist (DE)\n[all segments]', lambda cc: np.mean([get(cc,s,'avg_seenlist') for s in named if get(cc,s,'N')>0])),
    ('Avg Trailers\n[all segs]',          lambda cc: np.mean([get(cc,s,'avg_trailers') for s in named if get(cc,s,'N')>0])),
    ('Avg Movie %\n[all segs]',           lambda cc: np.mean([get(cc,s,'pct_movie') for s in named if get(cc,s,'N')>0])),
    ('Deal Free %',  lambda cc: get(cc,'Deal Hunter','pct_free')),
    ('Premium Buy %',lambda cc: get(cc,'Premium Buyer','pct_buy')),
]

hm_labels = [m[0] for m in hm_metrics]
de_vals   = np.array([fn('DE') for _, fn in hm_metrics])
mat = np.array([[fn(cc) - fn('DE') for _, fn in hm_metrics] for cc in markets_sorted])

# Diverging colormap centred at 0
vmax = np.nanpercentile(np.abs(mat), 95)
norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
im = ax2.imshow(mat, aspect='auto', cmap='RdBu_r', norm=norm)

ax2.set_xticks(range(len(hm_labels)))
ax2.set_xticklabels(hm_labels, rotation=35, ha='right', color=TEXT_C, fontsize=8)
ax2.set_yticks(range(len(markets_sorted)))
ax2.set_yticklabels([f'{MARKET_NAMES[cc]} ({cc})' for cc in markets_sorted], color=TEXT_C, fontsize=8)
ax2.set_title('Δ vs Germany Baseline  (blue = above DE, red = below DE)',
              color='white', fontsize=10, fontweight='bold')

# Annotate cells
for i in range(len(markets_sorted)):
    for j in range(len(hm_labels)):
        v = mat[i, j]
        if abs(v) > 0.3:
            ax2.text(j, i, f'{v:+.1f}', ha='center', va='center',
                     color='white' if abs(v) > vmax*0.5 else TEXT_C, fontsize=7)

plt.colorbar(im, ax=ax2, fraction=0.025, pad=0.01).ax.yaxis.set_tick_params(color=TEXT_C)

# ── Panel 3 (bottom-right): Key insights text panel ──────────────────────────
ax3 = fig.add_axes([0.46, 0.10, 0.52, 0.28])
ax3.set_facecolor(PANEL_BG)
ax3.axis('off')

# Compute key insights
trailer_rank  = sorted(markets, key=lambda cc: -get(cc, 'Trailer Scout', 'PCT'))
binge_rank    = sorted(markets, key=lambda cc: -get(cc, 'Binge Watcher',  'PCT'))
deal_rank     = sorted(markets, key=lambda cc: -get(cc, 'Deal Hunter',    'PCT'))
premium_rank  = sorted(markets, key=lambda cc: -get(cc, 'Premium Buyer',  'PCT'))
explorer_rank = sorted(markets, key=lambda cc: -get(cc, 'Explorer',       'PCT'))
de_trailer    = get('DE','Trailer Scout','PCT')
de_binge      = get('DE','Binge Watcher','PCT')
de_deal       = get('DE','Deal Hunter','PCT')

lines = [
    ('TRAILER SCOUT — most research-phase users:', '#f7c948'),
    (f'  1st {MARKET_NAMES[trailer_rank[0]]} ({trailer_rank[0]}): {get(trailer_rank[0],"Trailer Scout","PCT"):.1f}%'
     f'   2nd {MARKET_NAMES[trailer_rank[1]]} ({trailer_rank[1]}): {get(trailer_rank[1],"Trailer Scout","PCT"):.1f}%'
     f'   Germany: {de_trailer:.1f}%', TEXT_C),
    ('', TEXT_C),
    ('BINGE WATCHER — highest loyal consumption:', '#58a6ff'),
    (f'  1st {MARKET_NAMES[binge_rank[0]]} ({binge_rank[0]}): {get(binge_rank[0],"Binge Watcher","PCT"):.1f}%'
     f'   2nd {MARKET_NAMES[binge_rank[1]]} ({binge_rank[1]}): {get(binge_rank[1],"Binge Watcher","PCT"):.1f}%'
     f'   Germany: {de_binge:.1f}%', TEXT_C),
    ('', TEXT_C),
    ('DEAL HUNTER — highest free-content seeking:', '#3fb950'),
    (f'  1st {MARKET_NAMES[deal_rank[0]]} ({deal_rank[0]}): {get(deal_rank[0],"Deal Hunter","PCT"):.1f}%'
     f'   2nd {MARKET_NAMES[deal_rank[1]]} ({deal_rank[1]}): {get(deal_rank[1],"Deal Hunter","PCT"):.1f}%'
     f'   Germany: {de_deal:.1f}%', TEXT_C),
    ('', TEXT_C),
    ('PREMIUM BUYER — TVOD willingness-to-pay:', '#e85de0'),
    (f'  1st {MARKET_NAMES[premium_rank[0]]} ({premium_rank[0]}): {get(premium_rank[0],"Premium Buyer","PCT"):.1f}%'
     f'   2nd {MARKET_NAMES[premium_rank[1]]} ({premium_rank[1]}): {get(premium_rank[1],"Premium Buyer","PCT"):.1f}%'
     f'   Germany: {get("DE","Premium Buyer","PCT"):.1f}%', TEXT_C),
    ('', TEXT_C),
    ('NOTE: Watchlist Hoarder = 0% across all T4 markets. Global normalization', SUBTEXT),
    ('pushes watchlist_n lower — this segment requires a market-local recalibration.', SUBTEXT),
]

y_pos = 0.97
for text, color in lines:
    if text == '':
        y_pos -= 0.04
        continue
    ax3.text(0.02, y_pos, text, transform=ax3.transAxes, color=color,
             fontsize=8.5, va='top', fontfamily='monospace')
    y_pos -= 0.085

# ── Supertitle ───────────────────────────────────────────────────────────────
fig.suptitle(
    'Multi-Market Segment Analysis  |  15 Markets from T4  |  50K users/market sampled  |  v5 Scoring (global normalisation)',
    color='white', fontsize=13, fontweight='bold', y=0.99
)

out = 'market_comparison_overview.png'
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print(f'Saved: {out}')
