-- build_segments_v5.sql
-- Standalone Snowflake SQL for creating DB_TEAM_2.BASE_MARTS.user_segments_v5
-- Logic mirrors build_segments_v5.py without Python wrapper code.
--
-- Segment conditions overview
-- 1. Binge Watcher
--    score = 0.40*seenlist_n + 0.35*eps_n + 0.15*login_n + 0.10*show_ratio
-- 2. Premium Buyer
--    hard gate: has_clickout = 1 AND buyer_ratio >= 0.30
--    score = 0.60*buyer_n + 0.25*cor_n + 0.15*free_inv_n
-- 3. Deal Hunter
--    soft gate: monetization_diversity multiplier 0.10 / 0.60 / 1.00
--    score = 0.40*free_n + 0.35*cor_n + 0.25*buyer_n
-- 4. Watchlist Hoarder
--    score = 0.45*watchlist_n + 0.25*login_n + 0.20*seenlist_inv_n + 0.10*compl_inv_n
-- 5. Genre Loyalist
--    hard gate: genre_count >= 3 AND top2_genre_share >= 0.70
--    score = 0.55*tgs_n + 0.30*gc_inv_n + 0.15*cor_n
-- 6. Trailer Scout
--    hard gate: trailer_plays >= 3 AND seenlist_adds = 0
--    score = 0.55*trailer_n + 0.30*titles_n + 0.15*seenlist_inv_n
-- Explorer
--    assigned when max named score < 0.40
-- Run:
--   snow sql -c hackathon -f build_segments_v5.sql

USE WAREHOUSE WH_TEAM_2_XS;

CREATE OR REPLACE TABLE DB_TEAM_2.BASE_MARTS.user_segments_v5 AS

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

pct AS (
    SELECT
        PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY LN(CAST(seenlist_adds AS FLOAT) + 1))   AS p1_log_seen,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY LN(CAST(seenlist_adds AS FLOAT) + 1))   AS p99_log_seen,
        PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY LN(CAST(watchlist_adds AS FLOAT) + 1))  AS p1_log_watch,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY LN(CAST(watchlist_adds AS FLOAT) + 1))  AS p99_log_watch,
        PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY LN(CAST(unique_titles AS FLOAT) + 1))   AS p1_log_titles,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY LN(CAST(unique_titles AS FLOAT) + 1))   AS p99_log_titles,
        PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY LN(CAST(trailer_plays AS FLOAT) + 1))   AS p1_log_trailer,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY LN(CAST(trailer_plays AS FLOAT) + 1))   AS p99_log_trailer,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(events_per_session AS FLOAT))       AS p5_eps,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(events_per_session AS FLOAT))       AS p95_eps,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(COALESCE(avg_session_mins,0) AS FLOAT)) AS p5_mins,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(COALESCE(avg_session_mins,0) AS FLOAT)) AS p95_mins,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(clickout_ratio AS FLOAT))           AS p5_cor,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(clickout_ratio AS FLOAT))           AS p95_cor,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(COALESCE(free_ratio,0) AS FLOAT))  AS p5_fr,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(COALESCE(free_ratio,0) AS FLOAT))  AS p95_fr,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(COALESCE(buyer_ratio,0) AS FLOAT)) AS p5_br,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(COALESCE(buyer_ratio,0) AS FLOAT)) AS p95_br,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(COALESCE(login_rate,0) AS FLOAT))  AS p5_lr,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(COALESCE(login_rate,0) AS FLOAT))  AS p95_lr,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(top2_genre_share AS FLOAT))         AS p5_tgs,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(top2_genre_share AS FLOAT))         AS p95_tgs,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY CAST(genre_count AS FLOAT))              AS p5_gc,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CAST(genre_count AS FLOAT))              AS p95_gc
    FROM features
),

normed AS (
    SELECT
        f.*,
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
        GREATEST(LEAST(
            (LN(CAST(trailer_plays AS FLOAT) + 1) - p.p1_log_trailer)
            / NULLIF(p.p99_log_trailer - p.p1_log_trailer, 0)
        , 1), 0) AS trailer_n,
        GREATEST(LEAST(
            (CAST(events_per_session AS FLOAT) - p.p5_eps)
            / NULLIF(p.p95_eps - p.p5_eps, 0)
        , 1), 0) AS eps_n,
        GREATEST(LEAST(
            (CAST(COALESCE(avg_session_mins,0) AS FLOAT) - p.p5_mins)
            / NULLIF(p.p95_mins - p.p5_mins, 0)
        , 1), 0) AS mins_n,
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
        1.0 - GREATEST(LEAST(
            (CAST(genre_count AS FLOAT) - p.p5_gc)
            / NULLIF(p.p95_gc - p.p5_gc, 0)
        , 1), 0) AS gc_inv_n,
        1.0 - GREATEST(LEAST(
            (LN(CAST(seenlist_adds AS FLOAT) + 1) - p.p1_log_seen)
            / NULLIF(p.p99_log_seen - p.p1_log_seen, 0)
        , 1), 0) AS seenlist_inv_n,
        1.0 - GREATEST(LEAST(
            CAST(COALESCE(completion_ratio,0) AS FLOAT)
        , 1), 0) AS compl_inv_n,
        1.0 - GREATEST(LEAST(
            (CAST(COALESCE(free_ratio,0) AS FLOAT) - p.p5_fr)
            / NULLIF(p.p95_fr - p.p5_fr, 0)
        , 1), 0) AS free_inv_n
    FROM features f, pct p
),

scored AS (
    SELECT
        user_id,

        -- 1. Binge Watcher
        0.40 * seenlist_n
        + 0.35 * eps_n
        + 0.15 * login_n
        + 0.10 * CAST(show_ratio AS FLOAT) AS binge_score,

        -- 2. Premium Buyer
        CASE
            WHEN has_clickout = 0 OR COALESCE(buyer_ratio, 0) < 0.30 THEN 0.0
            ELSE 0.60 * buyer_n
                 + 0.25 * cor_n
                 + 0.15 * free_inv_n
        END AS premium_score,

        -- 3. Deal Hunter
        CASE
            WHEN monetization_diversity = 0 THEN 0.10
            WHEN monetization_diversity = 1 THEN 0.60
            ELSE 1.00
        END * (
            0.40 * free_n
            + 0.35 * cor_n
            + 0.25 * buyer_n
        ) AS deal_score,

        -- 4. Watchlist Hoarder
        0.45 * watchlist_n
        + 0.25 * login_n
        + 0.20 * seenlist_inv_n
        + 0.10 * compl_inv_n AS hoarder_score,

        -- 5. Genre Loyalist
        CASE
            WHEN genre_count < 3 OR top2_genre_share < 0.70 THEN 0.0
            ELSE 0.55 * tgs_n + 0.30 * gc_inv_n + 0.15 * cor_n
        END AS loyalist_score,

        -- 6. Trailer Scout
        CASE
            WHEN trailer_plays < 3 OR seenlist_adds > 0 THEN 0.0
            ELSE 0.55 * trailer_n
                 + 0.30 * titles_n
                 + 0.15 * seenlist_inv_n
        END AS trailer_score,
        seenlist_n, watchlist_n, eps_n, login_n, free_n, cor_n,
        buyer_n, trailer_n, titles_n, tgs_n, gc_inv_n,
        seenlist_inv_n, compl_inv_n, free_inv_n,
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

primary_assigned AS (
    SELECT
        *,
        -- Explorer fallback when no named segment reaches threshold
        GREATEST(binge_score, premium_score, deal_score, hoarder_score, loyalist_score, trailer_score) AS max_score,
        CASE
            WHEN GREATEST(binge_score, premium_score, deal_score, hoarder_score, loyalist_score, trailer_score) < 0.40
                THEN 'Explorer'
            WHEN GREATEST(binge_score, premium_score, deal_score, hoarder_score, loyalist_score, trailer_score) = binge_score
                THEN 'Binge Watcher'
            WHEN GREATEST(binge_score, premium_score, deal_score, hoarder_score, loyalist_score, trailer_score) = premium_score
                THEN 'Premium Buyer'
            WHEN GREATEST(binge_score, premium_score, deal_score, hoarder_score, loyalist_score, trailer_score) = deal_score
                THEN 'Deal Hunter'
            WHEN GREATEST(binge_score, premium_score, deal_score, hoarder_score, loyalist_score, trailer_score) = hoarder_score
                THEN 'Watchlist Hoarder'
            WHEN GREATEST(binge_score, premium_score, deal_score, hoarder_score, loyalist_score, trailer_score) = loyalist_score
                THEN 'Genre Loyalist'
            WHEN GREATEST(binge_score, premium_score, deal_score, hoarder_score, loyalist_score, trailer_score) = trailer_score
                THEN 'Trailer Scout'
            ELSE 'Explorer'
        END AS primary_segment
    FROM scored
),

with_second AS (
    SELECT *,
        CASE primary_segment
            WHEN 'Binge Watcher'     THEN GREATEST(premium_score, deal_score, hoarder_score, loyalist_score, trailer_score)
            WHEN 'Premium Buyer'     THEN GREATEST(binge_score, deal_score, hoarder_score, loyalist_score, trailer_score)
            WHEN 'Deal Hunter'       THEN GREATEST(binge_score, premium_score, hoarder_score, loyalist_score, trailer_score)
            WHEN 'Watchlist Hoarder' THEN GREATEST(binge_score, premium_score, deal_score, loyalist_score, trailer_score)
            WHEN 'Genre Loyalist'    THEN GREATEST(binge_score, premium_score, deal_score, hoarder_score, trailer_score)
            WHEN 'Trailer Scout'     THEN GREATEST(binge_score, premium_score, deal_score, hoarder_score, loyalist_score)
            ELSE NULL
        END AS second_score
    FROM primary_assigned
),

final AS (
    SELECT
        user_id,
        primary_segment,
        CASE
            WHEN primary_segment = 'Explorer' THEN NULL
            WHEN second_score IS NULL OR second_score < 0.30 OR max_score - second_score > 0.15 THEN NULL
            WHEN primary_segment = 'Binge Watcher' THEN
                CASE GREATEST(premium_score, deal_score, hoarder_score, loyalist_score, trailer_score)
                    WHEN premium_score   THEN 'Premium Buyer'
                    WHEN deal_score      THEN 'Deal Hunter'
                    WHEN hoarder_score   THEN 'Watchlist Hoarder'
                    WHEN loyalist_score  THEN 'Genre Loyalist'
                    ELSE 'Trailer Scout' END
            WHEN primary_segment = 'Premium Buyer' THEN
                CASE GREATEST(binge_score, deal_score, hoarder_score, loyalist_score, trailer_score)
                    WHEN binge_score     THEN 'Binge Watcher'
                    WHEN deal_score      THEN 'Deal Hunter'
                    WHEN hoarder_score   THEN 'Watchlist Hoarder'
                    WHEN loyalist_score  THEN 'Genre Loyalist'
                    ELSE 'Trailer Scout' END
            WHEN primary_segment = 'Deal Hunter' THEN
                CASE GREATEST(binge_score, premium_score, hoarder_score, loyalist_score, trailer_score)
                    WHEN binge_score     THEN 'Binge Watcher'
                    WHEN premium_score   THEN 'Premium Buyer'
                    WHEN hoarder_score   THEN 'Watchlist Hoarder'
                    WHEN loyalist_score  THEN 'Genre Loyalist'
                    ELSE 'Trailer Scout' END
            WHEN primary_segment = 'Watchlist Hoarder' THEN
                CASE GREATEST(binge_score, premium_score, deal_score, loyalist_score, trailer_score)
                    WHEN binge_score     THEN 'Binge Watcher'
                    WHEN premium_score   THEN 'Premium Buyer'
                    WHEN deal_score      THEN 'Deal Hunter'
                    WHEN loyalist_score  THEN 'Genre Loyalist'
                    ELSE 'Trailer Scout' END
            WHEN primary_segment = 'Genre Loyalist' THEN
                CASE GREATEST(binge_score, premium_score, deal_score, hoarder_score, trailer_score)
                    WHEN binge_score     THEN 'Binge Watcher'
                    WHEN premium_score   THEN 'Premium Buyer'
                    WHEN deal_score      THEN 'Deal Hunter'
                    WHEN hoarder_score   THEN 'Watchlist Hoarder'
                    ELSE 'Trailer Scout' END
            WHEN primary_segment = 'Trailer Scout' THEN
                CASE GREATEST(binge_score, premium_score, deal_score, hoarder_score, loyalist_score)
                    WHEN binge_score     THEN 'Binge Watcher'
                    WHEN premium_score   THEN 'Premium Buyer'
                    WHEN deal_score      THEN 'Deal Hunter'
                    WHEN hoarder_score   THEN 'Watchlist Hoarder'
                    ELSE 'Genre Loyalist' END
            ELSE NULL
        END AS secondary_segment,
        CASE
            WHEN primary_segment = 'Binge Watcher' THEN
                CASE GREATEST(0.40*seenlist_n, 0.35*eps_n, 0.15*login_n, 0.10*CAST(show_ratio AS FLOAT))
                    WHEN 0.40*seenlist_n THEN 'deep_seenlist'
                    WHEN 0.35*eps_n THEN 'long_sessions'
                    WHEN 0.15*login_n THEN 'logged_in'
                    ELSE 'show_focus' END
            WHEN primary_segment = 'Premium Buyer' THEN
                CASE GREATEST(0.60*buyer_n, 0.25*cor_n, 0.15*free_inv_n)
                    WHEN 0.60*buyer_n THEN 'tvod_buyer'
                    WHEN 0.25*cor_n THEN 'high_clickout'
                    ELSE 'avoids_free' END
            WHEN primary_segment = 'Deal Hunter' THEN
                CASE GREATEST(0.40*free_n, 0.35*cor_n, 0.25*buyer_n)
                    WHEN 0.40*free_n THEN 'free_content_seeker'
                    WHEN 0.35*cor_n THEN 'high_clickout'
                    ELSE 'tvod_buyer' END
            WHEN primary_segment = 'Watchlist Hoarder' THEN
                CASE GREATEST(0.45*watchlist_n, 0.25*login_n, 0.20*seenlist_inv_n, 0.10*compl_inv_n)
                    WHEN 0.45*watchlist_n THEN 'large_watchlist'
                    WHEN 0.25*login_n THEN 'logged_in_hoarder'
                    WHEN 0.20*seenlist_inv_n THEN 'low_consumption'
                    ELSE 'low_completion' END
            WHEN primary_segment = 'Genre Loyalist' THEN
                CASE GREATEST(0.55*tgs_n, 0.30*gc_inv_n, 0.15*cor_n)
                    WHEN 0.55*tgs_n THEN 'genre_concentrated'
                    WHEN 0.30*gc_inv_n THEN 'few_genres'
                    ELSE 'genre_clickout' END
            WHEN primary_segment = 'Trailer Scout' THEN
                CASE GREATEST(0.55*trailer_n, 0.30*titles_n, 0.15*seenlist_inv_n)
                    WHEN 0.55*trailer_n THEN 'heavy_trailer_viewer'
                    WHEN 0.30*titles_n THEN 'broad_discovery'
                    ELSE 'non_consumer' END
            ELSE NULL
        END AS primary_driver,
        binge_score, premium_score, deal_score, hoarder_score, loyalist_score,
        trailer_score, max_score,
        weekend_ratio, evening_ratio, holiday_ratio, trailer_plays,
        mobile_ratio, login_rate, page_view_ratio, clickout_ratio,
        events_per_session, avg_session_mins,
        top2_genre_share, genre_count, top_genre, second_genre,
        seenlist_adds, watchlist_adds, active_days, unique_titles,
        buyer_ratio, free_ratio, has_clickout, monetization_diversity,
        completion_ratio, hoard_ratio, show_ratio, movie_ratio
    FROM with_second
)

SELECT * FROM final;
