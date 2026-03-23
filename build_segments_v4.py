"""
user_segments_v4: Fixed distributions + 5 clean labels + explainability
Fixes vs. v3:
  1. Log1p + p1/p99 normalization for heavily right-skewed count features
     (seenlist, watchlist, unique_titles) — 90-94% zero-inflated
  2. Soft gate for Deal Hunter (monetization_diversity weight, not binary has_clickout)
  3. No Explorer sub-types — exactly 5 labels: 4 named + Explorer
  4. primary_driver column: the feature that contributed most to the primary score
"""
import snowflake.connector

conn = snowflake.connector.connect(
    account='OHHGHHL-ZM06890',
    user='martinkaiser.bln@gmail.com',
    password='DM#31BvDJOZxR7',
    warehouse='WH_TEAM_2_XS',
    login_timeout=15
)
cur = conn.cursor()
cur.execute("USE WAREHOUSE WH_TEAM_2_XS")

print("Building user_segments_v4 ...")

sql = """
CREATE OR REPLACE TABLE DB_TEAM_2.BASE_MARTS.user_segments_v4 AS

WITH features AS (
    SELECT
        f.*,
        COALESCE(g.top_genre_share, 0)                             AS top_genre_share,
        COALESCE(g.second_genre_share, 0)                          AS second_genre_share,
        COALESCE(g.top_genre_share, 0) + COALESCE(g.second_genre_share, 0)
                                                                   AS top2_genre_share,
        COALESCE(g.genre_diversity, 1)                             AS genre_count,
        g.top_genre,
        g.second_genre
    FROM DB_TEAM_2.BASE_BASE.user_features_v2 f
    LEFT JOIN DB_TEAM_2.BASE_BASE.user_genre_profile g USING (user_id)
),

-- ── Percentile anchors ──
-- Heavily skewed counts (90%+ zeros): use p1/p99 on LOG scale
-- Ratios and moderate counts:         use p5/p95 on raw scale
pct AS (
    SELECT
        -- Log-scale p1/p99 for zero-inflated counts
        PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY LN(CAST(seenlist_adds AS FLOAT) + 1))  AS p1_log_seen,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY LN(CAST(seenlist_adds AS FLOAT) + 1))  AS p99_log_seen,
        PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY LN(CAST(watchlist_adds AS FLOAT) + 1)) AS p1_log_watch,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY LN(CAST(watchlist_adds AS FLOAT) + 1)) AS p99_log_watch,
        PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY LN(CAST(unique_titles AS FLOAT) + 1))  AS p1_log_titles,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY LN(CAST(unique_titles AS FLOAT) + 1))  AS p99_log_titles,

        -- Raw p5/p95 for moderate distributions
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(events_per_session AS FLOAT)) AS p5_eps,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(events_per_session AS FLOAT)) AS p95_eps,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(COALESCE(avg_session_mins,0) AS FLOAT)) AS p5_mins,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(COALESCE(avg_session_mins,0) AS FLOAT)) AS p95_mins,

        -- Ratios: p5/p95 (already bounded [0,1] but distribution varies)
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(clickout_ratio AS FLOAT))        AS p5_cor,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(clickout_ratio AS FLOAT))        AS p95_cor,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(COALESCE(free_ratio,0) AS FLOAT)) AS p5_fr,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(COALESCE(free_ratio,0) AS FLOAT)) AS p95_fr,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(COALESCE(buyer_ratio,0) AS FLOAT)) AS p5_br,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(COALESCE(buyer_ratio,0) AS FLOAT)) AS p95_br,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(COALESCE(login_rate,0) AS FLOAT)) AS p5_lr,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(COALESCE(login_rate,0) AS FLOAT)) AS p95_lr,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(top2_genre_share AS FLOAT))      AS p5_tgs,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(top2_genre_share AS FLOAT))      AS p95_tgs,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(genre_count AS FLOAT))           AS p5_gc,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(genre_count AS FLOAT))           AS p95_gc
    FROM features
),

-- ── Normalised features [0,1] ──
normed AS (
    SELECT
        f.*,

        -- Log1p + p1/p99 for right-skewed counts
        GREATEST(LEAST(
            (LN(CAST(seenlist_adds AS FLOAT) + 1) - p.p1_log_seen)
            / NULLIF(p.p99_log_seen - p.p1_log_seen, 0)
        , 1), 0) AS seenlist_n,

        GREATEST(LEAST(
            (LN(CAST(watchlist_adds AS FLOAT) + 1) - p.p1_log_watch)
            / NULLIF(p.p99_log_watch - p.p1_log_watch, 0)
        , 1), 0) AS watchlist_n,

        GREATEST(LEAST(
            (LN(CAST(unique_titles AS FLOAT) + 1) - p.p1_log_titles)
            / NULLIF(p.p99_log_titles - p.p1_log_titles, 0)
        , 1), 0) AS titles_n,

        -- Raw p5/p95 for moderate features
        GREATEST(LEAST(
            (CAST(events_per_session AS FLOAT) - p.p5_eps)
            / NULLIF(p.p95_eps - p.p5_eps, 0)
        , 1), 0) AS eps_n,

        GREATEST(LEAST(
            (CAST(COALESCE(avg_session_mins,0) AS FLOAT) - p.p5_mins)
            / NULLIF(p.p95_mins - p.p5_mins, 0)
        , 1), 0) AS mins_n,

        -- Ratios p5/p95
        GREATEST(LEAST(
            (CAST(clickout_ratio AS FLOAT) - p.p5_cor)
            / NULLIF(p.p95_cor - p.p5_cor, 0)
        , 1), 0) AS cor_n,

        GREATEST(LEAST(
            (CAST(COALESCE(free_ratio,0) AS FLOAT) - p.p5_fr)
            / NULLIF(p.p95_fr - p.p5_fr, 0)
        , 1), 0) AS free_n,

        GREATEST(LEAST(
            (CAST(COALESCE(buyer_ratio,0) AS FLOAT) - p.p5_br)
            / NULLIF(p.p95_br - p.p5_br, 0)
        , 1), 0) AS buyer_n,

        GREATEST(LEAST(
            (CAST(COALESCE(login_rate,0) AS FLOAT) - p.p5_lr)
            / NULLIF(p.p95_lr - p.p5_lr, 0)
        , 1), 0) AS login_n,

        GREATEST(LEAST(
            (CAST(top2_genre_share AS FLOAT) - p.p5_tgs)
            / NULLIF(p.p95_tgs - p.p5_tgs, 0)
        , 1), 0) AS tgs_n,

        -- Inverted: higher = fewer genres (more loyal)
        1.0 - GREATEST(LEAST(
            (CAST(genre_count AS FLOAT) - p.p5_gc)
            / NULLIF(p.p95_gc - p.p5_gc, 0)
        , 1), 0) AS gc_inv_n,

        -- Inverted seenlist (for Hoarder: low consumption is bad)
        1.0 - GREATEST(LEAST(
            (LN(CAST(seenlist_adds AS FLOAT) + 1) - p.p1_log_seen)
            / NULLIF(p.p99_log_seen - p.p1_log_seen, 0)
        , 1), 0) AS seenlist_inv_n,

        1.0 - GREATEST(LEAST(
            CAST(COALESCE(completion_ratio,0) AS FLOAT)
        , 1), 0) AS compl_inv_n

    FROM features f, pct p
),

-- ── Segment scores ──
scored AS (
    SELECT
        user_id,

        -- Binge Watcher: seenlist depth (log) + session intensity + logged-in
        0.40 * seenlist_n
        + 0.35 * eps_n
        + 0.15 * login_n
        + 0.10 * CAST(show_ratio AS FLOAT)
            AS binge_score,

        -- Deal Hunter: soft-gated by monetization intensity
        -- Non-clickers (mon_div=0): weight 0.10 — too low to become primary
        -- Single-type (mon_div=1): weight 0.60
        -- Multi-type  (mon_div>=2): weight 1.00 — strongest signal
        CASE
            WHEN monetization_diversity = 0 THEN 0.10
            WHEN monetization_diversity = 1 THEN 0.60
            ELSE 1.00
        END * (
            0.40 * free_n
            + 0.35 * cor_n
            + 0.25 * buyer_n
        ) AS deal_score,

        -- Watchlist Hoarder: large watchlist (log) + low consumption
        0.45 * watchlist_n
        + 0.25 * login_n
        + 0.20 * seenlist_inv_n
        + 0.10 * compl_inv_n
            AS hoarder_score,

        -- Genre Loyalist: top-2 genre concentration
        -- Hard gate: must have genre_count >= 3 AND top2_genre_share >= 0.70
        CASE
            WHEN genre_count < 3 OR top2_genre_share < 0.70 THEN 0.0
            ELSE 0.55 * tgs_n + 0.30 * gc_inv_n + 0.15 * cor_n
        END AS loyalist_score,

        -- Pass through all features for analysis / PCA
        seenlist_n, watchlist_n, eps_n, login_n, free_n, cor_n,
        buyer_n, tgs_n, gc_inv_n, seenlist_inv_n, compl_inv_n,
        weekend_ratio, evening_ratio, holiday_ratio, trailer_plays,
        mobile_ratio, login_rate, page_view_ratio, clickout_ratio,
        events_per_session, COALESCE(avg_session_mins,0) AS avg_session_mins,
        top2_genre_share, genre_count, top_genre, second_genre,
        seenlist_adds, watchlist_adds, active_days, unique_titles,
        COALESCE(buyer_ratio,0) AS buyer_ratio,
        COALESCE(free_ratio,0)  AS free_ratio,
        has_clickout, monetization_diversity,
        COALESCE(completion_ratio,0) AS completion_ratio,
        COALESCE(hoard_ratio,0) AS hoard_ratio,
        show_ratio, movie_ratio
    FROM normed
),

-- ── Primary segment ──
primary_assigned AS (
    SELECT
        *,
        GREATEST(binge_score, deal_score, hoarder_score, loyalist_score) AS max_score,
        CASE
            WHEN GREATEST(binge_score, deal_score, hoarder_score, loyalist_score) < 0.40
                THEN 'Explorer'
            WHEN GREATEST(binge_score, deal_score, hoarder_score, loyalist_score) = binge_score
                THEN 'Binge Watcher'
            WHEN GREATEST(binge_score, deal_score, hoarder_score, loyalist_score) = deal_score
                THEN 'Deal Hunter'
            WHEN GREATEST(binge_score, deal_score, hoarder_score, loyalist_score) = hoarder_score
                THEN 'Watchlist Hoarder'
            ELSE 'Genre Loyalist'
        END AS primary_segment
    FROM scored
),

-- ── Secondary segment ──
with_second AS (
    SELECT *,
        CASE
            WHEN primary_segment = 'Binge Watcher'     THEN GREATEST(deal_score, hoarder_score, loyalist_score)
            WHEN primary_segment = 'Deal Hunter'        THEN GREATEST(binge_score, hoarder_score, loyalist_score)
            WHEN primary_segment = 'Watchlist Hoarder'  THEN GREATEST(binge_score, deal_score, loyalist_score)
            WHEN primary_segment = 'Genre Loyalist'     THEN GREATEST(binge_score, deal_score, hoarder_score)
            ELSE NULL
        END AS second_score
    FROM primary_assigned
),

final AS (
    SELECT
        user_id,
        primary_segment,

        -- Secondary: second-best if >= 0.30 AND within 0.15 of primary
        CASE
            WHEN primary_segment = 'Explorer' THEN NULL
            WHEN second_score IS NULL OR second_score < 0.30 OR max_score - second_score > 0.15 THEN NULL
            WHEN primary_segment = 'Binge Watcher' THEN
                CASE WHEN deal_score >= hoarder_score AND deal_score >= loyalist_score THEN 'Deal Hunter'
                     WHEN hoarder_score >= deal_score AND hoarder_score >= loyalist_score THEN 'Watchlist Hoarder'
                     ELSE 'Genre Loyalist' END
            WHEN primary_segment = 'Deal Hunter' THEN
                CASE WHEN binge_score >= hoarder_score AND binge_score >= loyalist_score THEN 'Binge Watcher'
                     WHEN hoarder_score >= binge_score AND hoarder_score >= loyalist_score THEN 'Watchlist Hoarder'
                     ELSE 'Genre Loyalist' END
            WHEN primary_segment = 'Watchlist Hoarder' THEN
                CASE WHEN binge_score >= deal_score AND binge_score >= loyalist_score THEN 'Binge Watcher'
                     WHEN deal_score >= binge_score AND deal_score >= loyalist_score THEN 'Deal Hunter'
                     ELSE 'Genre Loyalist' END
            WHEN primary_segment = 'Genre Loyalist' THEN
                CASE WHEN binge_score >= deal_score AND binge_score >= hoarder_score THEN 'Binge Watcher'
                     WHEN deal_score >= binge_score AND deal_score >= hoarder_score THEN 'Deal Hunter'
                     ELSE 'Watchlist Hoarder' END
            ELSE NULL
        END AS secondary_segment,

        -- Primary driver: which feature component was largest?
        CASE
            WHEN primary_segment = 'Binge Watcher' THEN
                CASE GREATEST(0.40*seenlist_n, 0.35*eps_n, 0.15*login_n, 0.10*CAST(show_ratio AS FLOAT))
                    WHEN 0.40*seenlist_n                     THEN 'deep_seenlist'
                    WHEN 0.35*eps_n                          THEN 'long_sessions'
                    WHEN 0.15*login_n                        THEN 'logged_in'
                    ELSE 'show_focus' END
            WHEN primary_segment = 'Deal Hunter' THEN
                CASE GREATEST(0.40*free_n, 0.35*cor_n, 0.25*buyer_n)
                    WHEN 0.40*free_n  THEN 'free_content_seeker'
                    WHEN 0.35*cor_n   THEN 'high_clickout'
                    ELSE 'tvod_buyer' END
            WHEN primary_segment = 'Watchlist Hoarder' THEN
                CASE GREATEST(0.45*watchlist_n, 0.25*login_n, 0.20*seenlist_inv_n, 0.10*compl_inv_n)
                    WHEN 0.45*watchlist_n    THEN 'large_watchlist'
                    WHEN 0.25*login_n        THEN 'logged_in_hoarder'
                    WHEN 0.20*seenlist_inv_n THEN 'low_consumption'
                    ELSE 'low_completion' END
            WHEN primary_segment = 'Genre Loyalist' THEN
                CASE GREATEST(0.55*tgs_n, 0.30*gc_inv_n, 0.15*cor_n)
                    WHEN 0.55*tgs_n    THEN 'genre_concentrated'
                    WHEN 0.30*gc_inv_n THEN 'few_genres'
                    ELSE 'genre_clickout' END
            ELSE NULL
        END AS primary_driver,

        binge_score, deal_score, hoarder_score, loyalist_score, max_score,
        weekend_ratio, evening_ratio, holiday_ratio, trailer_plays,
        mobile_ratio, login_rate, page_view_ratio, clickout_ratio,
        events_per_session, avg_session_mins,
        top2_genre_share, genre_count, top_genre, second_genre,
        seenlist_adds, watchlist_adds, active_days, unique_titles,
        buyer_ratio, free_ratio, has_clickout, monetization_diversity,
        completion_ratio, hoard_ratio, show_ratio, movie_ratio
    FROM with_second
)

SELECT * FROM final
"""

cur.execute(sql)
print("  Created user_segments_v4")

# ── Validate ──
print("\nSegment distribution:")
cur.execute("""
SELECT primary_segment, COUNT(*) AS n,
       ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER (),1) AS pct
FROM DB_TEAM_2.BASE_MARTS.user_segments_v4
GROUP BY primary_segment ORDER BY n DESC
""")
rows = cur.fetchall()
for r in rows:
    bar = "█" * int(float(r[2]) / 2)
    print(f"  {r[0]:22s} {r[1]:>7,}  {r[2]:5.1f}%  {bar}")

print("\nSecondary segment overlap:")
cur.execute("""
SELECT COUNT(*) AS with_secondary,
       ROUND(COUNT(*)*100.0/(SELECT COUNT(*) FROM DB_TEAM_2.BASE_MARTS.user_segments_v4),1) AS pct
FROM DB_TEAM_2.BASE_MARTS.user_segments_v4 WHERE secondary_segment IS NOT NULL
""")
r = cur.fetchone()
print(f"  {r[0]:,} users ({r[1]}%) have a secondary segment")

print("\nPrimary driver distribution:")
cur.execute("""
SELECT primary_segment, primary_driver, COUNT(*) AS n
FROM DB_TEAM_2.BASE_MARTS.user_segments_v4
WHERE primary_segment <> 'Explorer'
GROUP BY primary_segment, primary_driver
ORDER BY primary_segment, n DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]:22s}  {r[1]:25s}  {r[2]:>7,}")

print("\nDifferentiation report (feature means per segment):")
cur.execute("""
SELECT
    primary_segment,
    COUNT(*) AS n,
    ROUND(AVG(CAST(seenlist_adds AS FLOAT)),2)       AS avg_seenlist,
    ROUND(AVG(CAST(watchlist_adds AS FLOAT)),2)      AS avg_watchlist,
    ROUND(AVG(CAST(events_per_session AS FLOAT)),1)  AS avg_eps,
    ROUND(AVG(CAST(free_ratio AS FLOAT))*100,1)      AS avg_free_pct,
    ROUND(AVG(CAST(has_clickout AS FLOAT))*100,1)    AS pct_clickout,
    ROUND(AVG(CAST(top2_genre_share AS FLOAT))*100,1) AS avg_top2_pct,
    ROUND(AVG(CAST(unique_titles AS FLOAT)),1)       AS avg_titles,
    ROUND(AVG(CAST(login_rate AS FLOAT))*100,1)      AS avg_login_pct
FROM DB_TEAM_2.BASE_MARTS.user_segments_v4
GROUP BY primary_segment ORDER BY n DESC
""")
rows = cur.fetchall()
print(f"  {'Segment':22s} {'N':>7}  {'seen':>6}  {'watch':>6}  {'eps':>6}  {'free%':>6}  {'click%':>7}  {'genre%':>7}  {'titles':>7}  {'login%':>7}")
for r in rows:
    vals = "  ".join(f"{float(r[i]):>6.1f}" for i in range(2, 10))
    print(f"  {r[0]:22s} {r[1]:>7,}  {vals}")

print("\nAverage scores by segment:")
cur.execute("""
SELECT primary_segment,
       ROUND(AVG(binge_score),3), ROUND(AVG(deal_score),3),
       ROUND(AVG(hoarder_score),3), ROUND(AVG(loyalist_score),3),
       ROUND(AVG(max_score),3)
FROM DB_TEAM_2.BASE_MARTS.user_segments_v4
WHERE primary_segment <> 'Explorer'
GROUP BY primary_segment ORDER BY AVG(max_score) DESC
""")
rows = cur.fetchall()
print(f"  {'Segment':22s}  {'binge':>6}  {'deal':>6}  {'hoarder':>7}  {'loyalist':>8}  {'max':>6}")
for r in rows:
    print(f"  {r[0]:22s}  {float(r[1]):>6.3f}  {float(r[2]):>6.3f}  {float(r[3]):>7.3f}  {float(r[4]):>8.3f}  {float(r[5]):>6.3f}")

cur.close()
conn.close()
print("\nDone.")
