# User Segments v5 — Metrics Reference

**Table:** `DB_TEAM_2.BASE_MARTS.user_segments_v5`
**Rows:** 307,537 users | **Columns:** 37 | **Segments:** 7

---

## Column Reference by Category

### Identity (4 columns)

| Column | Type | Description |
|---|---|---|
| `user_id` | TEXT | Anonymous user identifier carried over from raw event data |
| `primary_segment` | TEXT | Single best-fit label assigned to the user. One of: Binge Watcher, Premium Buyer, Deal Hunter, Watchlist Hoarder, Genre Loyalist, Trailer Scout, Explorer |
| `secondary_segment` | TEXT | Second-strongest segment if score ≥ 0.30, otherwise NULL. Captures overlap (e.g. a Binge Watcher who also hoards) |
| `primary_driver` | TEXT | The specific sub-signal that triggered the primary assignment. Examples: `seenlist_heavy`, `tvod_buyer`, `heavy_trailer_viewer`, `genre_focused` |

---

### Segment Scores (7 columns — FLOAT, range 0–1)

Each user receives a score for every segment. The highest score above 0.40 becomes the primary assignment. Scores below 0.40 on all segments → Explorer.

| Column | Formula Driver | What a High Score Means |
|---|---|---|
| `binge_score` | seenlist depth + session intensity + show preference | Heavy TV-show consumer; watches and marks content at high volume |
| `premium_score` | rent/buy ratio + clickout volume + low free-ratio | Willingly pays for content; prefers TVOD over free streaming |
| `deal_score` | free-streaming share + clickout breadth + offer variety | Actively seeks free/AVOD content; high monetization diversity |
| `hoarder_score` | watchlist adds + inverted seenlist | Saves far more than it watches; intent-rich but low consumption |
| `loyalist_score` | top-2 genre concentration + minimum genre gate (≥3 genres) | Sticks to 1–2 genres obsessively; genre identity is very strong |
| `trailer_score` | trailer plays + unique title breadth + non-consumer gate | Researches content intensively via trailers but hasn't committed to watching |
| `max_score` | `GREATEST(all 6 scores)` | Overall confidence of any segment assignment. Low for Explorer |

> **Hard gates applied before scoring:**
> - `trailer_score = 0` if `trailer_plays < 3` OR `seenlist_adds > 0`
> - `premium_score = 0` if `has_clickout = 0` OR `buyer_ratio < 0.30`
> - `loyalist_score` gated on `genre_count ≥ 3` AND `top2_genre_share ≥ 0.70`

---

### Consumption (4 columns)

| Column | Type | Description |
|---|---|---|
| `seenlist_adds` | NUMBER | Count of "I watched this" marks. Direct signal of actual consumption. Binge Watchers average 18; most other segments average < 1 |
| `watchlist_adds` | NUMBER | Count of "I want to watch this" saves. Measures intent and hoarding tendency. Watchlist Hoarders average 3.3 |
| `unique_titles` | NUMBER | Distinct content pieces the user engaged with. Measures breadth of discovery. Binge Watchers average 33; Deal Hunters average 2 |
| `trailer_plays` | NUMBER | Count of trailer starts. The single strongest discriminating feature (CV = 2.90). Trailer Scouts average 4.6 vs 0.2–0.8 for all other segments |

---

### Session Activity (4 columns)

| Column | Type | Description |
|---|---|---|
| `active_days` | NUMBER | Days with at least one event. Proxy for loyalty and recency. Binge Watchers average 6.4 days; Deal Hunters average 1.4 |
| `events_per_session` | FLOAT | Average events per session. Measures depth of engagement per visit. Binge Watchers average 21.3 vs 5–8 for other segments |
| `avg_session_mins` | NUMBER | Average session duration in minutes. Binge Watchers average 1,991 min; Deal Hunters average 297 min |
| `completion_ratio` | NUMBER | Ratio of fully engaged content items vs started. Measures follow-through behavior |

---

### Monetization (6 columns)

| Column | Type | Description |
|---|---|---|
| `has_clickout` | NUMBER (0/1) | Whether the user ever clicked out to a streaming provider. Basic purchase-intent flag. Deal Hunters and Premium Buyers are 100% |
| `clickout_ratio` | FLOAT | Fraction of sessions containing at least one clickout. Higher = more actively shopping for content |
| `free_ratio` | FLOAT | Share of clickouts directed at free/AVOD offers. Deal Hunter average: 77.4%. Premium Buyer average: 11.6% |
| `buyer_ratio` | FLOAT | Share of clickouts directed at rent/buy (TVOD) offers. Premium Buyer average: 78.8%. Deal Hunter average: 4.1% |
| `monetization_diversity` | NUMBER | Count of distinct monetization types used (flatrate, free, rent, buy, ads, sports, cinema). Range 0–5. Deal Hunters average 1.73 — they try many offer types to find free content |
| `hoard_ratio` | FLOAT | Watchlist adds ÷ seenlist adds. High value = saves much more than watches. Diagnostic for Watchlist Hoarder segment |

---

### Content Type (2 columns)

| Column | Type | Description |
|---|---|---|
| `movie_ratio` | FLOAT | Share of content engagement that is movies (0–1). Trailer Scout average: 77%. Binge Watcher average: 35% |
| `show_ratio` | FLOAT | Share of content engagement that is TV shows. Always = 1 − movie_ratio. Binge Watcher average: 64% — the only show-dominant segment |

---

### Genre (4 columns)

| Column | Type | Description |
|---|---|---|
| `top2_genre_share` | FLOAT | Fraction of all views in the user's top 2 genres. High = genre-concentrated taste. Deal Hunter average: 98.7%. Binge Watcher average: 77.5% |
| `genre_count` | NUMBER | Number of distinct genres engaged. Low = narrow taste. Binge Watcher average: 4.7. Deal Hunter average: 1.4 |
| `top_genre` | TEXT | User's single most-watched genre label (from OBJECTS metadata) |
| `second_genre` | TEXT | User's second most-watched genre label |

---

### Temporal (3 columns — FLOAT ratios)

All temporal columns measure the share of the user's total activity that falls in the given time window.

| Column | Description | Segment Insight |
|---|---|---|
| `weekend_ratio` | Share of activity on Saturday / Sunday | Flat across all segments (~31%) — not a strong discriminator between named segments |
| `evening_ratio` | Share of activity 18:00–23:59 local time | Binge Watchers skew slightly more evening (43.3%). Broad range: 39–43% |
| `holiday_ratio` | Share of activity on public holidays | Watchlist Hoarders peak at 53.5% — they are particularly active during holiday downtime |

---

### Device & Authentication (2 columns)

| Column | Type | Description |
|---|---|---|
| `mobile_ratio` | FLOAT | Share of sessions originating from Phone or Tablet. Currently 0% across all segments — the dataset appears desktop/web dominant |
| `login_rate` | FLOAT | Share of sessions where the user was logged in (has a `login_id`). Critical quality signal: logged-in data is persistent and reliable. Watchlist Hoarders 96%, Binge Watchers 75%, Explorers 0.1% |

---

## Per-Segment Metric Summary

### Segment Size & Score Confidence

| Segment | Users | % of Total | Avg Max Score |
|---|---|---|---|
| Explorer | 139,496 | 45.4% | 0.31 |
| Trailer Scout | 45,379 | 14.8% | 0.58 |
| Watchlist Hoarder | 37,254 | 12.1% | 0.64 |
| Genre Loyalist | 26,457 | 8.6% | 0.54 |
| Premium Buyer | 24,677 | 8.0% | **0.81** |
| Deal Hunter | 23,603 | 7.7% | 0.52 |
| Binge Watcher | 10,671 | 3.5% | 0.66 |

---

### Consumption Behavior

| Segment | Seenlist | Watchlist | Unique Titles | Trailer Plays | Active Days | EPS | Session Mins |
|---|---|---|---|---|---|---|---|
| Explorer | 0.0 | 0.0 | 5 | 0.6 | 2.4 | 5.7 | 421 |
| Trailer Scout | 0.0 | 0.0 | 5 | **4.6** | 2.0 | 8.4 | 373 |
| Watchlist Hoarder | 0.9 | **3.3** | **18** | 0.2 | 5.6 | 6.9 | **1,089** |
| Genre Loyalist | 0.1 | 0.0 | 7 | 0.4 | 3.1 | 6.4 | 752 |
| Premium Buyer | 0.3 | 0.2 | 6 | 0.7 | 2.9 | 5.7 | 748 |
| Deal Hunter | 0.0 | 0.0 | 2 | 0.8 | 1.4 | 6.1 | 297 |
| Binge Watcher | **18.1** | 4.3 | **33** | 0.5 | **6.4** | **21.3** | **1,991** |

> Binge Watcher dominates every consumption metric. Trailer Scout has 7× more trailer plays than any other segment, with zero seenlist — pure research behaviour, no commitment.

---

### Monetization

| Segment | % Free Clicks | % Buy/Rent Clicks | % Has Any Clickout | Avg Mon. Diversity |
|---|---|---|---|---|
| Explorer | 25.3% | 0.1% | 41.5% | 0.44 |
| Trailer Scout | 35.9% | 0.8% | 46.4% | 0.56 |
| Watchlist Hoarder | 12.5% | 2.7% | 35.8% | 0.51 |
| Genre Loyalist | 19.8% | 0.9% | 35.9% | 0.48 |
| **Premium Buyer** | **11.6%** | **78.8%** | **100%** | **1.65** |
| **Deal Hunter** | **77.4%** | **4.1%** | **100%** | **1.73** |
| Binge Watcher | 13.0% | 2.7% | 37.9% | 0.55 |

> Deal Hunter and Premium Buyer are exact mirrors: both 100% clickout rate, but free vs buy ratios are inverted. They represent opposite ends of willingness to pay.

---

### Content Type & Genre Focus

| Segment | % Movie | % Show | Top-2 Genre Share | Genre Count |
|---|---|---|---|---|
| Explorer | 51.5% | 48.5% | 92.6% | 2.1 |
| **Trailer Scout** | **77.0%** | 23.0% | 95.2% | 1.9 |
| Watchlist Hoarder | 69.2% | 30.8% | 78.3% | 4.1 |
| **Genre Loyalist** | 68.2% | 31.8% | **84.6%** | **3.1** |
| Premium Buyer | 69.5% | 30.5% | 92.6% | 2.2 |
| **Deal Hunter** | 61.1% | 38.9% | **98.7%** | **1.4** |
| **Binge Watcher** | 35.5% | **64.5%** | 77.5% | **4.7** |

> Binge Watcher is the only show-dominant segment (64.5% shows). All others lean movie. Deal Hunter has the narrowest taste of all: 98.7% of views in just 1–2 genres.

---

### Temporal Patterns

| Segment | % Weekend | % Evening | % Holiday |
|---|---|---|---|
| Explorer | 30.5% | 40.0% | 45.1% |
| Trailer Scout | 31.5% | 39.4% | 44.9% |
| Watchlist Hoarder | 31.6% | 42.4% | **53.5%** |
| Genre Loyalist | 31.4% | 41.4% | 48.6% |
| Premium Buyer | 31.5% | 42.1% | 49.1% |
| Deal Hunter | 30.4% | 39.6% | 43.3% |
| Binge Watcher | 31.3% | **43.3%** | 50.3% |

> Weekend ratio is nearly identical across all segments — not useful for targeting. Holiday ratio is the only temporal differentiator: Watchlist Hoarders are most active during holiday downtime (53.5%), suggesting seasonal re-engagement campaigns.

---

### Authentication & Device

| Segment | % Login Rate | % Mobile |
|---|---|---|
| Explorer | 0.1% | 0% |
| Trailer Scout | 1.6% | 0% |
| Watchlist Hoarder | **96.2%** | 0% |
| Genre Loyalist | 10.6% | 0% |
| Premium Buyer | 14.9% | 0% |
| Deal Hunter | 0.8% | 0% |
| Binge Watcher | **75.5%** | 0% |

> Login rate is critical for data quality. Watchlist Hoarders (96%) and Binge Watchers (75%) are almost entirely logged-in, meaning their behaviour is tracked persistently across sessions. Explorer and Deal Hunter are near-fully anonymous — their data reflects individual sessions, not longitudinal user behaviour.

---

## Segment Commercial Summary

| Segment | Marketing Name | Core Signal | Best Campaign Use |
|---|---|---|---|
| Binge Watcher | The Devoted Viewer | 18 seenlists, 21 EPS, 1,991 min sessions, 64% shows | Series launches, binge-bundle promotions, subscription upsell |
| Premium Buyer | The Premium Payer | 79% TVOD, 100% clickout, avg score 0.81 | Theatrical window TVOD, early access offers, premium tier upsell |
| Watchlist Hoarder | The Content Curator | 3.3 watchlist adds, 96% logged in, 1,089 min sessions | "Now available" reminders, re-engagement of saved titles |
| Genre Loyalist | The Niche Devotee | 85% top-2 genre share, genre gate enforced | Genre-curated newsletters, niche franchise launches, fan events |
| Trailer Scout | The Consideration Seeker | 4.6 trailer plays, 77% movie-focused, zero seenlist | Movie launch trailers, "now streaming" conversion nudges |
| Deal Hunter | The Savvy Streamer | 77% free clicks, 100% clickout, 1.73 diversity | AVOD inventory fill, free-tier acquisition, price promotions |
| Explorer | The Open Browser | Low scores, 0.1% login, broad & shallow | Awareness campaigns, content discovery, broad retargeting |

---

## Notes on Interpretation

- **Scores are not probabilities** — they are relative composite signals, not Bayesian likelihoods. A score of 0.80 means "strongly fits this profile", not "80% chance of being this person".
- **Explorer is a catch-all** — 45% of users. Most are genuinely low-engagement (anonymous, short sessions). ~14K are "near-miss" users just below the 0.40 threshold, primarily near Watchlist Hoarder.
- **login_rate predicts data richness** — segments with high login rate have richer, more reliable longitudinal data. Use this when deciding which segments to build lookalike models on.
- **movie_ratio ≠ movie preference** — it reflects the content mix on JustWatch pages visited, which skews movie-heavy across the platform. Show-dominant users (Binge Watchers) are the notable exception.
- **trailer_plays is zero-inflated** — most users play 0 trailers. The high CV (2.90) comes from a small group with very high counts. The log1p normalization in scoring compensates for this.
