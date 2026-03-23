-- build_market_segments.sql
-- Applies v5 segmentation logic to all 15 markets in T4.
-- Samples 50K users per market, computes features inline, applies exact v5 scoring.
-- Output: DB_TEAM_2.BASE_MARTS.market_segments (~750K rows)
-- Run: snow sql -f build_market_segments.sql -c hackathon
-- Warehouse: WH_TEAM_2_M  (~5-10 min)

USE WAREHOUSE WH_TEAM_2_M;

CREATE OR REPLACE TABLE DB_TEAM_2.BASE_MARTS.market_segments AS

WITH

-- 1. Sample 50K users per market (reproducible seed)
sampled AS (
    SELECT user_id, geo_country
    FROM (
        SELECT DISTINCT user_id, geo_country
        FROM DB_JW_SHARED.CHALLENGE.T4
        WHERE geo_country IS NOT NULL
    )
    QUALIFY ROW_NUMBER() OVER (PARTITION BY geo_country ORDER BY RANDOM(42)) <= 50000
),

-- 2. Pull events for sampled users only, deduplicated
evt AS (
    SELECT
        t.user_id,
        t.geo_country,
        t.session_id,
        t.login_id,
        t.collector_tstamp,
        t.se_category,
        t.se_action,
        t.cc_title
    FROM DB_JW_SHARED.CHALLENGE.T4 t
    JOIN sampled s ON t.user_id = s.user_id AND t.geo_country = s.geo_country
    QUALIFY ROW_NUMBER() OVER (PARTITION BY t.rid ORDER BY t.collector_tstamp) = 1
),

-- 3. Per-user feature aggregation
features AS (
    SELECT
        user_id,
        geo_country,
        COUNT(*)                                                                          AS total_events,
        COUNT(DISTINCT session_id)                                                        AS session_count,
        COUNT(DISTINCT DATE(collector_tstamp))                                            AS active_days,
        COUNT(DISTINCT NULLIF(cc_title:jwEntityId::TEXT, ''))                             AS unique_titles,
        COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT session_id), 0)                          AS events_per_session,
        -- Behavioural lists
        COUNT(CASE WHEN se_category = 'seenlist_add'    THEN 1 END)                      AS seenlist_adds,
        COUNT(CASE WHEN se_category = 'watchlist_add'   THEN 1 END)                      AS watchlist_adds,
        COUNT(CASE WHEN se_category = 'youtube_started' THEN 1 END)                      AS trailer_plays,
        -- Content type
        COUNT(CASE WHEN cc_title:objectType::TEXT ILIKE 'movie'  THEN 1 END)             AS movie_events,
        COUNT(CASE WHEN cc_title:objectType::TEXT ILIKE '%show%' THEN 1 END)             AS show_events,
        -- Monetization
        MAX(CASE WHEN se_category = 'clickout' THEN 1 ELSE 0 END)                        AS has_clickout,
        COUNT(CASE WHEN se_category = 'clickout' THEN 1 END)                             AS clickout_events,
        COUNT(DISTINCT CASE WHEN se_category='clickout' THEN session_id END)             AS clickout_sessions,
        COUNT(CASE WHEN se_category='clickout' AND se_action IN ('free','ads') THEN 1 END) AS free_clicks,
        COUNT(CASE WHEN se_category='clickout' AND se_action IN ('rent','buy') THEN 1 END) AS buy_clicks,
        COUNT(DISTINCT CASE WHEN se_category='clickout' THEN se_action END)              AS monetization_diversity,
        -- Login
        COUNT(DISTINCT CASE WHEN login_id IS NOT NULL THEN session_id END)               AS logged_sessions,
        -- Temporal
        AVG(CASE WHEN DAYOFWEEK(collector_tstamp) IN (0,6) THEN 1.0 ELSE 0.0 END)       AS weekend_ratio,
        AVG(CASE WHEN HOUR(collector_tstamp) BETWEEN 18 AND 23 THEN 1.0 ELSE 0.0 END)   AS evening_ratio
    FROM evt
    GROUP BY user_id, geo_country
),

-- 4. Compute derived ratios
feat2 AS (
    SELECT *,
        CASE WHEN movie_events + show_events > 0
             THEN movie_events  * 1.0 / (movie_events + show_events)
             ELSE 0.5 END                                                       AS movie_ratio,
        CASE WHEN movie_events + show_events > 0
             THEN show_events   * 1.0 / (movie_events + show_events)
             ELSE 0.5 END                                                       AS show_ratio,
        CASE WHEN session_count > 0
             THEN clickout_sessions * 1.0 / session_count
             ELSE 0.0 END                                                       AS clickout_ratio,
        CASE WHEN clickout_events > 0
             THEN free_clicks * 1.0 / clickout_events
             ELSE 0.0 END                                                       AS free_ratio,
        CASE WHEN clickout_events > 0
             THEN buy_clicks  * 1.0 / clickout_events
             ELSE 0.0 END                                                       AS buyer_ratio,
        CASE WHEN session_count > 0
             THEN logged_sessions * 1.0 / session_count
             ELSE 0.0 END                                                       AS login_rate
    FROM features
),

-- 5. Genre profile (join to OBJECTS, flatten genre_tmdb)
genre_raw AS (
    SELECT e.user_id, e.geo_country, f.value::TEXT AS genre
    FROM evt e
    JOIN DB_JW_SHARED.CHALLENGE.OBJECTS o
      ON e.cc_title:jwEntityId::TEXT = o.object_id
    , LATERAL FLATTEN(input => o.genre_tmdb) f
    WHERE e.cc_title:jwEntityId::TEXT IS NOT NULL
      AND e.cc_title:jwEntityId::TEXT != ''
      AND f.value IS NOT NULL
),
genre_counts AS (
    SELECT user_id, geo_country, genre, COUNT(*) AS cnt
    FROM genre_raw
    GROUP BY user_id, geo_country, genre
),
genre_ranked AS (
    SELECT
        user_id, geo_country, genre, cnt,
        ROW_NUMBER() OVER (PARTITION BY user_id, geo_country ORDER BY cnt DESC) AS rk,
        SUM(cnt) OVER (PARTITION BY user_id, geo_country)                        AS total_cnt
    FROM genre_counts
),
genre_profile AS (
    SELECT
        user_id, geo_country,
        COUNT(DISTINCT genre)                                                               AS genre_count,
        COALESCE(SUM(CASE WHEN rk <= 2 THEN cnt END) * 1.0 / NULLIF(MAX(total_cnt),0), 1) AS top2_genre_share
    FROM genre_ranked
    GROUP BY user_id, geo_country
),

-- 6. Merge features + genre
full_feat AS (
    SELECT
        f.*,
        COALESCE(g.genre_count, 1)        AS genre_count,
        COALESCE(g.top2_genre_share, 1.0) AS top2_genre_share
    FROM feat2 f
    LEFT JOIN genre_profile g USING (user_id, geo_country)
),

-- 7. Global percentile anchors (all 15 markets pooled — ensures cross-market comparability)
pct AS (
    SELECT
        PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY LN(CAST(seenlist_adds  AS FLOAT)+1)) AS p1_log_seen,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY LN(CAST(seenlist_adds  AS FLOAT)+1)) AS p99_log_seen,
        PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY LN(CAST(watchlist_adds AS FLOAT)+1)) AS p1_log_watch,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY LN(CAST(watchlist_adds AS FLOAT)+1)) AS p99_log_watch,
        PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY LN(CAST(unique_titles  AS FLOAT)+1)) AS p1_log_titles,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY LN(CAST(unique_titles  AS FLOAT)+1)) AS p99_log_titles,
        PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY LN(CAST(trailer_plays  AS FLOAT)+1)) AS p1_log_trailer,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY LN(CAST(trailer_plays  AS FLOAT)+1)) AS p99_log_trailer,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY events_per_session)                  AS p5_eps,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY events_per_session)                  AS p95_eps,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY clickout_ratio)                      AS p5_cor,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY clickout_ratio)                      AS p95_cor,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY free_ratio)                          AS p5_fr,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY free_ratio)                          AS p95_fr,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY buyer_ratio)                         AS p5_br,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY buyer_ratio)                         AS p95_br,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY login_rate)                          AS p5_lr,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY login_rate)                          AS p95_lr,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY top2_genre_share)                    AS p5_tgs,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY top2_genre_share)                    AS p95_tgs,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(genre_count AS FLOAT))          AS p5_gc,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(genre_count AS FLOAT))          AS p95_gc
    FROM full_feat
),

-- 8. Normalize features to [0, 1]
-- COALESCE(..., 0) handles the case where p1 = p99 (all users have same value → range = 0)
normed AS (
    SELECT f.*,
        -- log1p + p1/p99 (zero-inflated counts)
        COALESCE(GREATEST(LEAST((LN(CAST(f.seenlist_adds  AS FLOAT)+1)-p.p1_log_seen)   /NULLIF(p.p99_log_seen  -p.p1_log_seen,  0),1),0), 0) AS seenlist_n,
        COALESCE(GREATEST(LEAST((LN(CAST(f.watchlist_adds AS FLOAT)+1)-p.p1_log_watch)  /NULLIF(p.p99_log_watch -p.p1_log_watch, 0),1),0), 0) AS watchlist_n,
        COALESCE(GREATEST(LEAST((LN(CAST(f.unique_titles  AS FLOAT)+1)-p.p1_log_titles) /NULLIF(p.p99_log_titles-p.p1_log_titles,0),1),0), 0) AS titles_n,
        COALESCE(GREATEST(LEAST((LN(CAST(f.trailer_plays  AS FLOAT)+1)-p.p1_log_trailer)/NULLIF(p.p99_log_trailer-p.p1_log_trailer,0),1),0),0) AS trailer_n,
        -- p5/p95 (moderate distributions)
        COALESCE(GREATEST(LEAST((f.events_per_session-p.p5_eps)/NULLIF(p.p95_eps-p.p5_eps,0),1),0), 0) AS eps_n,
        COALESCE(GREATEST(LEAST((f.clickout_ratio    -p.p5_cor)/NULLIF(p.p95_cor-p.p5_cor,0),1),0), 0) AS cor_n,
        COALESCE(GREATEST(LEAST((f.free_ratio        -p.p5_fr) /NULLIF(p.p95_fr -p.p5_fr, 0),1),0), 0) AS free_n,
        COALESCE(GREATEST(LEAST((f.buyer_ratio       -p.p5_br) /NULLIF(p.p95_br -p.p5_br, 0),1),0), 0) AS buyer_n,
        COALESCE(GREATEST(LEAST((f.login_rate        -p.p5_lr) /NULLIF(p.p95_lr -p.p5_lr, 0),1),0), 0) AS login_n,
        COALESCE(GREATEST(LEAST((f.top2_genre_share  -p.p5_tgs)/NULLIF(p.p95_tgs-p.p5_tgs,0),1),0), 0) AS tgs_n,
        -- inverted versions
        1.0 - COALESCE(GREATEST(LEAST((LN(CAST(f.seenlist_adds AS FLOAT)+1)-p.p1_log_seen)/NULLIF(p.p99_log_seen-p.p1_log_seen,0),1),0), 0) AS seenlist_inv_n,
        1.0 - COALESCE(GREATEST(LEAST((f.free_ratio-p.p5_fr)/NULLIF(p.p95_fr-p.p5_fr,0),1),0), 0)                                          AS free_inv_n,
        1.0 - COALESCE(GREATEST(LEAST((CAST(f.genre_count AS FLOAT)-p.p5_gc)/NULLIF(p.p95_gc-p.p5_gc,0),1),0), 0)                          AS gc_inv_n
    FROM full_feat f, pct p
),

-- 9. Score — exact v5 formulas (compl_inv_n=0, weight folded into hoarder base)
scored AS (
    SELECT *,
        -- Binge Watcher
        0.40*seenlist_n + 0.35*eps_n + 0.15*login_n + 0.10*show_ratio                   AS binge_score,
        -- Premium Buyer (hard gate)
        CASE WHEN has_clickout=0 OR buyer_ratio<0.30 THEN 0.0
             ELSE 0.60*buyer_n + 0.25*cor_n + 0.15*free_inv_n END                        AS premium_score,
        -- Deal Hunter (soft gate via monetization_diversity)
        CASE WHEN monetization_diversity=0 THEN 0.10
             WHEN monetization_diversity=1 THEN 0.60
             ELSE 1.00 END * (0.40*free_n + 0.35*cor_n + 0.25*buyer_n)                   AS deal_score,
        -- Watchlist Hoarder (compl_inv_n omitted → weight redistributed to watchlist)
        0.50*watchlist_n + 0.25*login_n + 0.25*seenlist_inv_n                            AS hoarder_score,
        -- Genre Loyalist (hard gate)
        CASE WHEN genre_count<3 OR top2_genre_share<0.70 THEN 0.0
             ELSE 0.55*tgs_n + 0.30*gc_inv_n + 0.15*cor_n END                            AS loyalist_score,
        -- Trailer Scout (hard gate)
        CASE WHEN trailer_plays<3 OR seenlist_adds>0 THEN 0.0
             ELSE 0.55*trailer_n + 0.30*titles_n + 0.15*seenlist_inv_n END               AS trailer_score
    FROM normed
),

-- 10. Assign primary segment (threshold 0.40, same priority as v5)
final AS (
    SELECT
        user_id,
        geo_country,
        GREATEST(binge_score,premium_score,deal_score,hoarder_score,loyalist_score,trailer_score) AS max_score,
        binge_score, premium_score, deal_score, hoarder_score, loyalist_score, trailer_score,
        CASE
            WHEN GREATEST(binge_score,premium_score,deal_score,hoarder_score,loyalist_score,trailer_score) < 0.40
                THEN 'Explorer'
            WHEN GREATEST(binge_score,premium_score,deal_score,hoarder_score,loyalist_score,trailer_score) = binge_score
                THEN 'Binge Watcher'
            WHEN GREATEST(binge_score,premium_score,deal_score,hoarder_score,loyalist_score,trailer_score) = premium_score
                THEN 'Premium Buyer'
            WHEN GREATEST(binge_score,premium_score,deal_score,hoarder_score,loyalist_score,trailer_score) = deal_score
                THEN 'Deal Hunter'
            WHEN GREATEST(binge_score,premium_score,deal_score,hoarder_score,loyalist_score,trailer_score) = hoarder_score
                THEN 'Watchlist Hoarder'
            WHEN GREATEST(binge_score,premium_score,deal_score,hoarder_score,loyalist_score,trailer_score) = loyalist_score
                THEN 'Genre Loyalist'
            ELSE 'Trailer Scout'
        END AS primary_segment,
        -- Features
        seenlist_adds, watchlist_adds, trailer_plays, unique_titles, active_days,
        events_per_session, free_ratio, buyer_ratio, has_clickout, monetization_diversity,
        movie_ratio, show_ratio, top2_genre_share, genre_count,
        login_rate, weekend_ratio, evening_ratio, clickout_ratio
    FROM scored
)

SELECT * FROM final;
