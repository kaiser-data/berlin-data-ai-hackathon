"""
viz_market_comparison_de_norm.py — Country rankings overview
Reads: data/market_segment_summary_de_norm.json
Writes: market_comparison_overview_de_norm.png
"""
import json
import matplotlib
matplotlib.use("Agg")
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

DATA_FILE = 'data/market_segment_summary_de_norm.json'

SEG_COLORS = {
    'Binge Watcher':     '#58a6ff',
    'Premium Buyer':     '#e85de0',
    'Deal Hunter':       '#3fb950',
    'Watchlist Hoarder': '#d29922',
    'Genre Loyalist':    '#bc8cff',
    'Trailer Scout':     '#f7c948',
    'Explorer':          '#8b949e',
}
BG       = '#0d1117'
PANEL_BG = '#161b22'
SPINE_C  = '#30363d'
TEXT_C   = '#c9d1d9'
SUBTEXT  = '#8b949e'
DE_COLOR = '#f0883e'

MARKET_NAMES = {
    'AR': 'Argentina', 'AU': 'Australia', 'BR': 'Brazil',   'CA': 'Canada',
    'DE': 'Germany',   'ES': 'Spain',     'FR': 'France',   'GB': 'United Kingdom',
    'ID': 'Indonesia', 'IN': 'India',     'IT': 'Italy',    'MX': 'Mexico',
    'PH': 'Philippines','TR': 'Turkey',   'US': 'United States',
}

SEGMENTS = ['Binge Watcher', 'Premium Buyer', 'Deal Hunter',
            'Watchlist Hoarder', 'Genre Loyalist', 'Trailer Scout']

# ── Load ──────────────────────────────────────────────────────────────────────
with open(DATA_FILE) as f:
    raw = json.load(f)

data = {}
for row in raw:
    cc  = row['GEO_COUNTRY']
    seg = row['PRIMARY_SEGMENT']
    data.setdefault(cc, {})[seg] = row

all_markets = sorted(data.keys())

def get(cc, seg, field, default=0):
    return float(data.get(cc, {}).get(seg, {}).get(field, default) or default)

def named_pct(cc, seg):
    """Share of named-segment users (Explorer excluded)."""
    total = sum(get(cc, s, 'PCT') for s in SEGMENTS)
    return 0.0 if total == 0 else get(cc, seg, 'PCT') / total * 100.0

def ranked_markets(seg):
    return sorted(all_markets, key=lambda cc: -named_pct(cc, seg))

# ── Choose 6 representative countries ────────────────────────────────────────
chosen = ['DE']
for seg in SEGMENTS:
    for cc in ranked_markets(seg):
        if cc not in chosen:
            chosen.append(cc)
            break
    if len(chosen) >= 6:
        break
for cc in ['IT', 'FR', 'GB', 'US', 'BR']:
    if len(chosen) >= 6:
        break
    if cc not in chosen:
        chosen.append(cc)

# Germany at bottom, rest sorted by peak named-segment %
chosen.sort(key=lambda cc: (cc != 'DE',
                             -max(named_pct(cc, s) for s in SEGMENTS)))

# ── Figure ────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(26, 14))
fig.patch.set_facecolor(BG)

# Title
fig.text(0.50, 0.985,
         'Audience Segment Rankings  |  15 Markets  |  50K users/market  |  v5 Scoring',
         ha='center', va='top', color='white', fontsize=15, fontweight='bold')

# ── Horizontal legend strip ───────────────────────────────────────────────────
ax_leg = fig.add_axes([0.03, 0.925, 0.94, 0.045])
ax_leg.set_facecolor(BG)
ax_leg.axis('off')
handles = [mpatches.Patch(color=SEG_COLORS[s], label=s) for s in SEGMENTS]
ax_leg.legend(handles=handles, ncol=6, loc='center',
              fontsize=11, facecolor=PANEL_BG, edgecolor=SPINE_C,
              labelcolor=TEXT_C, framealpha=0.95,
              handlelength=1.4, handleheight=1.2, columnspacing=1.6)

# ── Left panel: stacked bar for 6 countries ───────────────────────────────────
ax1 = fig.add_axes([0.03, 0.07, 0.27, 0.83])
ax1.set_facecolor(PANEL_BG)

y    = np.arange(len(chosen))
left = np.zeros(len(chosen))
for seg in SEGMENTS:
    vals = np.array([named_pct(cc, seg) for cc in chosen])
    ax1.barh(y, vals, left=left, color=SEG_COLORS[seg], alpha=0.9, height=0.68)
    for i, (v, l) in enumerate(zip(vals, left)):
        if v >= 9:
            ax1.text(l + v / 2, i, f'{v:.0f}',
                     ha='center', va='center',
                     color='white', fontsize=10.5, fontweight='bold')
    left += vals

ax1.set_xlim(0, 100)
ax1.set_yticks(y)
ax1.set_yticklabels(
    [f'★ {MARKET_NAMES[cc]}' if cc == 'DE' else MARKET_NAMES[cc] for cc in chosen],
    color=TEXT_C, fontsize=12
)
ax1.set_xlabel('% of named-segment users (Explorer excluded)', color=SUBTEXT, fontsize=10)
ax1.set_title('6 Representative Markets', color='white', fontsize=13,
              fontweight='bold', pad=10)
ax1.tick_params(colors=TEXT_C, labelsize=10)
for sp in ax1.spines.values():
    sp.set_color(SPINE_C)

# ── Right grid: 2×3 leaderboard panels ───────────────────────────────────────
# Each panel shows top-5 countries for that segment
# Layout: columns at 0.33, 0.56, 0.79 — rows at top/bottom
COL_X   = [0.33, 0.555, 0.78]
ROW_Y   = [0.50, 0.07]   # top-row y, bottom-row y
PAN_W   = 0.205
PAN_H   = 0.40

for idx, seg in enumerate(SEGMENTS):
    col = idx % 3
    row = idx // 3
    ax = fig.add_axes([COL_X[col], ROW_Y[row], PAN_W, PAN_H])
    ax.set_facecolor(PANEL_BG)

    top    = ranked_markets(seg)[:5]
    vals   = [named_pct(cc, seg) for cc in top]
    yy     = np.arange(len(top))
    colors = [DE_COLOR if cc == 'DE' else SEG_COLORS[seg] for cc in top]

    ax.barh(yy, vals, color=colors, alpha=0.9, height=0.55)
    ax.invert_yaxis()

    ax.set_yticks(yy)
    ax.set_yticklabels(
        [f'★ {cc}' if cc == 'DE' else cc for cc in top],
        color=TEXT_C, fontsize=11, fontweight='bold'
    )

    x_max = max(vals) if max(vals) > 0 else 1
    ax.set_xlim(0, x_max * 1.55)   # generous right padding so labels never clip
    for i, (cc, v) in enumerate(zip(top, vals)):
        ax.text(v + x_max * 0.05, i, f'{v:.1f}%',
                va='center', color=TEXT_C, fontsize=10.5, fontweight='bold',
                clip_on=False)

    ax.set_title(seg, color=SEG_COLORS[seg], fontsize=13, fontweight='bold', pad=8)
    ax.tick_params(colors=TEXT_C, labelsize=10.5, length=0)
    ax.xaxis.set_visible(False)
    for sp in ax.spines.values():
        sp.set_color(SPINE_C)
        sp.set_linewidth(0.6)

# ── Footer caption ────────────────────────────────────────────────────────────
fig.text(
    0.03, 0.015,
    'All % = share of named-segment users (Explorer excluded).  '
    'Right panels show top 5 markets per segment.  ★ = Germany (baseline).  '
    'Left panel shows Germany + top market per each segment.',
    color=SUBTEXT, fontsize=9
)

out = 'market_comparison_overview_de_norm.png'
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print(f'Saved: {out}')
