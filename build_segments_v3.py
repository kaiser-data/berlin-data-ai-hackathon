"""
Step 3: Build user_segments_v3
Multi-label scoring + primary/secondary assignment + Explorer sub-categorisation.
Updated scoring based on eta² analysis:
  - watchlist_adds (η²=0.33) and free_ratio (η²=0.32) are strongest discriminators
  - has_clickout (η²=0.24) is the first-order split for Deal Hunter
  - login_rate (η²=0.14) supplements Binge + Hoarder scores
  - Genre Loyalist: relaxed to top2_genre_share >= 0.70
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

print("Building user_segments_v3 ...")

sql = """
CREATE OR REPLACE TABLE DB_TEAM_2.BASE_MARTS.user_segments_v3 AS

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

-- Percentile-based normalisation to [0,1] for each signal
-- Using p5 as min, p95 as max to reduce outlier sensitivity
pct AS (
    SELECT
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY seenlist_adds)    AS p5_seenlist,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY seenlist_adds)    AS p95_seenlist,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY watchlist_adds)   AS p5_watchlist,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY watchlist_adds)   AS p95_watchlist,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY events_per_session) AS p5_eps,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY events_per_session) AS p95_eps,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY COALESCE(avg_session_mins,0)) AS p5_mins,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY COALESCE(avg_session_mins,0)) AS p95_mins,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY clickout_ratio)   AS p5_cor,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY clickout_ratio)   AS p95_cor,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY COALESCE(buyer_ratio,0)) AS p5_br,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY COALESCE(buyer_ratio,0)) AS p95_br,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY COALESCE(free_ratio,0))  AS p5_fr,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY COALESCE(free_ratio,0))  AS p95_fr,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY COALESCE(login_rate,0))  AS p5_lr,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY COALESCE(login_rate,0))  AS p95_lr,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY top2_genre_share) AS p5_tgs,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY top2_genre_share) AS p95_tgs,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY genre_count)      AS p5_gc,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY genre_count)      AS p95_gc
    FROM features
),

-- Normalised features [0,1]
normed AS (
    SELECT
        f.*,
        -- Helper: GREATEST(LEAST((val - min) / (max - min), 1), 0)
        GREATEST(LEAST((CAST(seenlist_adds AS FLOAT) - p.p5_seenlist) / NULLIF(p.p95_seenlist - p.p5_seenlist, 0), 1), 0) AS seenlist_n,
        GREATEST(LEAST((CAST(watchlist_adds AS FLOAT) - p.p5_watchlist) / NULLIF(p.p95_watchlist - p.p5_watchlist, 0), 1), 0) AS watchlist_n,
        GREATEST(LEAST((CAST(events_per_session AS FLOAT) - p.p5_eps) / NULLIF(p.p95_eps - p.p5_eps, 0), 1), 0) AS eps_n,
        GREATEST(LEAST((CAST(COALESCE(avg_session_mins,0) AS FLOAT) - p.p5_mins) / NULLIF(p.p95_mins - p.p5_mins, 0), 1), 0) AS mins_n,
        GREATEST(LEAST((CAST(clickout_ratio AS FLOAT) - p.p5_cor) / NULLIF(p.p95_cor - p.p5_cor, 0), 1), 0) AS cor_n,
        GREATEST(LEAST((CAST(COALESCE(buyer_ratio,0) AS FLOAT) - p.p5_br) / NULLIF(p.p95_br - p.p5_br, 0), 1), 0) AS buyer_n,
        GREATEST(LEAST((CAST(COALESCE(free_ratio,0) AS FLOAT) - p.p5_fr) / NULLIF(p.p95_fr - p.p5_fr, 0), 1), 0) AS free_n,
        GREATEST(LEAST((CAST(COALESCE(login_rate,0) AS FLOAT) - p.p5_lr) / NULLIF(p.p95_lr - p.p5_lr, 0), 1), 0) AS login_n,
        GREATEST(LEAST((CAST(top2_genre_share AS FLOAT) - p.p5_tgs) / NULLIF(p.p95_tgs - p.p5_tgs, 0), 1), 0) AS tgs_n,
        -- Inverted genre diversity: fewer genres = more loyal
        1.0 - GREATEST(LEAST((CAST(genre_count AS FLOAT) - p.p5_gc) / NULLIF(p.p95_gc - p.p5_gc, 0), 1), 0) AS gc_inv_n,
        -- Inverted seenlist (for Hoarder): low seen = more hoarding
        1.0 - GREATEST(LEAST((CAST(seenlist_adds AS FLOAT) - p.p5_seenlist) / NULLIF(p.p95_seenlist - p.p5_seenlist, 0), 1), 0) AS seenlist_inv_n,
        -- Inverted completion_ratio (for Hoarder)
        1.0 - GREATEST(LEAST(CAST(COALESCE(completion_ratio,0) AS FLOAT), 1), 0) AS compl_inv_n
    FROM features f, pct p
),

-- Raw scores per segment (0–1)
scored AS (
    SELECT
        user_id,
        -- ── Binge Watcher: deep engagement + show depth + logged-in ──
        -- seenlist (CV=9.09), eps (η²=0.10), login (η²=0.14), show_ratio
        0.40 * seenlist_n + 0.30 * eps_n + 0.20 * login_n + 0.10 * CAST(show_ratio AS FLOAT)
            AS binge_score,

        -- ── Deal Hunter: clickout-gated + free preference (η²=0.32) ──
        has_clickout * (
            0.35 * free_n
          + 0.35 * cor_n
          + 0.20 * (CASE WHEN monetization_diversity >= 2 THEN 1.0
                         WHEN monetization_diversity = 1  THEN 0.5
                         ELSE 0.0 END)
          + 0.10 * buyer_n
        ) AS deal_score,

        -- ── Watchlist Hoarder: big watchlist + low consumption ──
        -- watchlist (η²=0.33), login (η²=0.14), low seenlist
        0.45 * watchlist_n + 0.25 * login_n + 0.20 * seenlist_inv_n + 0.10 * compl_inv_n
            AS hoarder_score,

        -- ── Genre Loyalist: top-2 genre concentration + repeated engagement ──
        -- Hard gate: genre_count >= 3 AND top2_genre_share >= 0.70
        -- Without gate: casual browsers trivially score high on 1-2 genre visits
        CASE
            WHEN genre_count < 3 OR top2_genre_share < 0.70 THEN 0.0
            ELSE 0.55 * tgs_n + 0.30 * gc_inv_n + 0.15 * cor_n
        END AS loyalist_score,

        -- Pass through key features for Explorer sub-typing
        weekend_ratio, evening_ratio, holiday_ratio, trailer_plays,
        mobile_ratio, login_rate, page_view_ratio, clickout_ratio,
        events_per_session, avg_session_mins,
        top2_genre_share, genre_count, top_genre, second_genre,
        seenlist_adds, watchlist_adds, active_days, unique_titles,
        buyer_ratio, free_ratio, has_clickout, monetization_diversity,
        completion_ratio, hoard_ratio, show_ratio, movie_ratio
    FROM normed
),

-- Primary segment assignment
primary_assigned AS (
    SELECT
        user_id,
        binge_score, deal_score, hoarder_score, loyalist_score,
        GREATEST(binge_score, deal_score, hoarder_score, loyalist_score) AS max_score,
        CASE
            WHEN GREATEST(binge_score, deal_score, hoarder_score, loyalist_score) < 0.40
                THEN 'Explorer'
            WHEN GREATEST(binge_score, deal_score, hoarder_score, loyalist_score) = binge_score   THEN 'Binge Watcher'
            WHEN GREATEST(binge_score, deal_score, hoarder_score, loyalist_score) = deal_score    THEN 'Deal Hunter'
            WHEN GREATEST(binge_score, deal_score, hoarder_score, loyalist_score) = hoarder_score THEN 'Watchlist Hoarder'
            ELSE 'Genre Loyalist'
        END AS primary_segment,
        weekend_ratio, evening_ratio, holiday_ratio, trailer_plays,
        mobile_ratio, login_rate, page_view_ratio, clickout_ratio,
        events_per_session, avg_session_mins,
        top2_genre_share, genre_count, top_genre, second_genre,
        seenlist_adds, watchlist_adds, active_days, unique_titles,
        buyer_ratio, free_ratio, has_clickout, monetization_diversity,
        completion_ratio, hoard_ratio, show_ratio, movie_ratio
    FROM scored
),

-- Secondary segment: 2nd highest score, only if >= 0.30 AND within 0.15 of primary
assigned AS (
    SELECT
        *,
        -- Compute 2nd highest value first
        CASE
            WHEN primary_segment = 'Binge Watcher'    THEN GREATEST(deal_score, hoarder_score, loyalist_score)
            WHEN primary_segment = 'Deal Hunter'       THEN GREATEST(binge_score, hoarder_score, loyalist_score)
            WHEN primary_segment = 'Watchlist Hoarder' THEN GREATEST(binge_score, deal_score, loyalist_score)
            WHEN primary_segment = 'Genre Loyalist'    THEN GREATEST(binge_score, deal_score, hoarder_score)
            ELSE NULL
        END AS second_score
    FROM primary_assigned
),

assigned2 AS (
    SELECT
        *,
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
        END AS secondary_segment
    FROM assigned
),

-- Explorer sub-categorisation (only for primary_segment = 'Explorer')
final AS (
    SELECT
        user_id,
        primary_segment,
        secondary_segment,
        CASE
            WHEN primary_segment <> 'Explorer' THEN NULL
            WHEN holiday_ratio > 0.40 THEN 'Holiday Viewer'
            WHEN weekend_ratio > 0.55 THEN 'Weekend Warrior'
            WHEN evening_ratio > 0.60 THEN 'Evening Browser'
            WHEN trailer_plays >= 2 AND clickout_ratio < 0.05 THEN 'Trailer Gazer'
            WHEN mobile_ratio > 0.70 AND events_per_session < 5 THEN 'Mobile Casual'
            WHEN login_rate > 0.30 THEN 'Social Viewer'
            WHEN page_view_ratio > 0.80 THEN 'Passive Browser'
            ELSE 'Explorer'
        END AS explorer_subtype,
        binge_score, deal_score, hoarder_score, loyalist_score, max_score,
        weekend_ratio, evening_ratio, holiday_ratio, trailer_plays,
        mobile_ratio, login_rate, page_view_ratio, clickout_ratio,
        events_per_session, avg_session_mins,
        top2_genre_share, genre_count, top_genre, second_genre,
        seenlist_adds, watchlist_adds, active_days, unique_titles,
        buyer_ratio, free_ratio, has_clickout, monetization_diversity,
        completion_ratio, hoard_ratio, show_ratio, movie_ratio
    FROM assigned2
)

SELECT * FROM final
"""

cur.execute(sql)
print("  Created user_segments_v3")

# ── Validate ──
print("\nValidating ...")

cur.execute("""
SELECT primary_segment, COUNT(*) AS n,
       ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER (),1) AS pct
FROM DB_TEAM_2.BASE_MARTS.user_segments_v3
GROUP BY primary_segment ORDER BY n DESC
""")
rows = cur.fetchall()
print("\n  Primary segment distribution:")
for r in rows:
    bar = "█" * int(float(r[2]) / 2)
    print(f"    {r[0]:22s} {r[1]:>7,}  {r[2]:5.1f}%  {bar}")

print()
cur.execute("""
SELECT explorer_subtype, COUNT(*) AS n,
       ROUND(COUNT(*)*100.0/(SELECT COUNT(*) FROM DB_TEAM_2.BASE_MARTS.user_segments_v3),2) AS pct_total
FROM DB_TEAM_2.BASE_MARTS.user_segments_v3
WHERE primary_segment = 'Explorer'
GROUP BY explorer_subtype ORDER BY n DESC
""")
rows = cur.fetchall()
print("  Explorer sub-type distribution:")
for r in rows:
    bar = "█" * int(float(r[2]) * 2)
    print(f"    {r[0]:22s} {r[1]:>7,}  {r[2]:5.2f}% of total  {bar}")

print()
cur.execute("""
SELECT COUNT(*) AS users_with_secondary,
       ROUND(COUNT(*)*100.0/(SELECT COUNT(*) FROM DB_TEAM_2.BASE_MARTS.user_segments_v3),1) AS pct
FROM DB_TEAM_2.BASE_MARTS.user_segments_v3
WHERE secondary_segment IS NOT NULL
""")
r = cur.fetchone()
print(f"  Users with secondary segment: {r[0]:,} ({r[1]}%)")

# Score distributions per segment
print()
cur.execute("""
SELECT primary_segment,
       ROUND(AVG(binge_score),3) AS avg_binge,
       ROUND(AVG(deal_score),3)  AS avg_deal,
       ROUND(AVG(hoarder_score),3) AS avg_hoarder,
       ROUND(AVG(loyalist_score),3) AS avg_loyalist,
       ROUND(AVG(max_score),3) AS avg_max
FROM DB_TEAM_2.BASE_MARTS.user_segments_v3
WHERE primary_segment <> 'Explorer'
GROUP BY primary_segment
ORDER BY avg_max DESC
""")
rows = cur.fetchall()
print("  Avg scores by segment (named only):")
print(f"    {'Segment':22s}  {'binge':>6}  {'deal':>6}  {'hoarder':>7}  {'loyalist':>8}  {'max':>6}")
for r in rows:
    print(f"    {r[0]:22s}  {r[1]:>6.3f}  {r[2]:>6.3f}  {r[3]:>7.3f}  {r[4]:>8.3f}  {r[5]:>6.3f}")

cur.close()
conn.close()
print("\nDone.")
