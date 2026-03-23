"""
Step 1: Build user_features_v2
Adds temporal, content-type, clickout-quality, and session-duration features.
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
cur.execute("USE DATABASE DB_TEAM_2")
cur.execute("USE SCHEMA BASE_BASE")
cur.execute("USE WAREHOUSE WH_TEAM_2_XS")

print("Building user_features_v2 ...")

sql = """
CREATE OR REPLACE TABLE DB_TEAM_2.BASE_BASE.user_features_v2 AS

WITH deduped AS (
    SELECT *
    FROM DB_JW_SHARED.CHALLENGE.T1
    QUALIFY ROW_NUMBER() OVER (PARTITION BY rid ORDER BY collector_tstamp) = 1
),

-- Session duration: per-session span in minutes
session_durations AS (
    SELECT
        session_id,
        DATEDIFF('minute', MIN(derived_tstamp), MAX(derived_tstamp)) AS duration_mins
    FROM deduped
    GROUP BY session_id
),

-- Per-user session stats
user_session_stats AS (
    SELECT
        e.user_id,
        AVG(sd.duration_mins)  AS avg_session_mins,
        MAX(sd.duration_mins)  AS max_session_mins
    FROM deduped e
    JOIN session_durations sd ON e.session_id = sd.session_id
    GROUP BY e.user_id
),

-- Main per-user aggregation
user_agg AS (
    SELECT
        user_id,
        COUNT(*)                                                        AS total_events,
        COUNT(DISTINCT session_id)                                      AS sessions,
        COUNT(DISTINCT DATE(collector_tstamp))                         AS active_days,
        COUNT(DISTINCT cc_title:jwEntityId::TEXT)                      AS unique_titles,

        -- Session depth
        CAST(COUNT(*) AS FLOAT) / NULLIF(COUNT(DISTINCT session_id), 0) AS events_per_session,

        -- Watchlist / seenlist
        SUM(CASE WHEN se_category = 'watchlist_add' THEN 1 ELSE 0 END) AS watchlist_adds,
        SUM(CASE WHEN se_category = 'seenlist_add'  THEN 1 ELSE 0 END) AS seenlist_adds,

        -- Clickout totals and ratio
        SUM(CASE WHEN se_category = 'clickout' THEN 1 ELSE 0 END)      AS clickouts,
        CAST(SUM(CASE WHEN se_category = 'clickout' THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(COUNT(*), 0)                                         AS clickout_ratio,

        -- has_clickout binary gate
        CASE WHEN SUM(CASE WHEN se_category = 'clickout' THEN 1 ELSE 0 END) > 0
             THEN 1 ELSE 0 END                                          AS has_clickout,

        -- Monetization diversity: distinct clickout action types used
        COUNT(DISTINCT CASE WHEN se_category = 'clickout'
                       THEN se_action ELSE NULL END)                    AS monetization_diversity,

        -- Buyer / free ratios (meaningful only when has_clickout=1)
        CAST(SUM(CASE WHEN se_category='clickout'
                      AND se_action IN ('rent','buy') THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(SUM(CASE WHEN se_category='clickout' THEN 1 ELSE 0 END), 0)
                                                                        AS buyer_ratio,
        CAST(SUM(CASE WHEN se_category='clickout'
                      AND se_action IN ('free','ads') THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(SUM(CASE WHEN se_category='clickout' THEN 1 ELSE 0 END), 0)
                                                                        AS free_ratio,

        -- Trailer plays (high CV = 2.90)
        SUM(CASE WHEN se_category = 'youtube_started' THEN 1 ELSE 0 END) AS trailer_plays,

        -- Engagement extras
        SUM(CASE WHEN se_category = 'likelist_add'  THEN 1 ELSE 0 END) AS likes,
        SUM(CASE WHEN se_category LIKE 'search%'    THEN 1 ELSE 0 END) AS search_events,
        CAST(SUM(CASE WHEN login_id IS NOT NULL THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(COUNT(*), 0)                                         AS login_rate,

        -- Completion ratio: seenlist / (watchlist + clickout)
        DIV0(
          SUM(CASE WHEN se_category = 'seenlist_add' THEN 1 ELSE 0 END),
          NULLIF(
            SUM(CASE WHEN se_category = 'watchlist_add' THEN 1 ELSE 0 END)
            + SUM(CASE WHEN se_category = 'clickout' THEN 1 ELSE 0 END),
          0)
        )                                                               AS completion_ratio,

        -- Hoard ratio: watchlist / max(seenlist,1)
        CAST(SUM(CASE WHEN se_category = 'watchlist_add' THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(SUM(CASE WHEN se_category = 'seenlist_add' THEN 1 ELSE 0 END), 0)
                                                                        AS hoard_ratio,

        -- Content type: show vs movie ratio
        CAST(SUM(CASE WHEN cc_title:objectType::TEXT ILIKE '%show%' THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(COUNT(*), 0)                                         AS show_ratio,
        CAST(SUM(CASE WHEN cc_title:objectType::TEXT ILIKE 'movie' THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(COUNT(*), 0)                                         AS movie_ratio,
        SUM(CASE WHEN cc_title:objectType::TEXT = 'show_episode' THEN 1 ELSE 0 END)
                                                                        AS episode_events,
        MAX(cc_title:episodeNumber::INT)                                AS max_episode_reached,
        COUNT(DISTINCT cc_title:seasonNumber::INT)                      AS seasons_explored,

        -- Mobile ratio
        CAST(SUM(CASE WHEN app_id IN ('jw-android','jw-ios') THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(COUNT(*), 0)                                         AS mobile_ratio,

        -- Page view ratio (for Passive Browser sub-type)
        CAST(SUM(CASE WHEN event = 'page_view' THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(COUNT(*), 0)                                         AS page_view_ratio,

        -- Temporal features
        CAST(SUM(CASE WHEN DAYOFWEEKISO(collector_tstamp) > 5 THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(COUNT(*), 0)                                         AS weekend_ratio,
        CAST(SUM(CASE WHEN EXTRACT(HOUR FROM collector_tstamp) BETWEEN 18 AND 22
                      THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(COUNT(*), 0)                                         AS evening_ratio,
        CAST(SUM(CASE WHEN EXTRACT(MONTH FROM collector_tstamp) = 12
                      AND EXTRACT(DAY FROM collector_tstamp) >= 20
                      THEN 1 ELSE 0 END) AS FLOAT)
          / NULLIF(COUNT(*), 0)                                         AS holiday_ratio

    FROM deduped
    GROUP BY user_id
    HAVING total_events BETWEEN 5 AND 1000   -- same filter as v1: min activity + outlier cap
)

SELECT
    ua.*,
    uss.avg_session_mins,
    uss.max_session_mins
FROM user_agg ua
LEFT JOIN user_session_stats uss ON ua.user_id = uss.user_id
"""

cur.execute(sql)
print("  Created user_features_v2")

# Row count check
cur.execute("SELECT COUNT(*) FROM DB_TEAM_2.BASE_BASE.user_features_v2")
n = cur.fetchone()[0]
print(f"  Rows: {n:,}  (expected ~307K)")

# Quick feature null/zero check
cur.execute("""
SELECT
    COUNT(*) AS total,
    SUM(has_clickout) AS has_clickout_count,
    ROUND(AVG(CAST(has_clickout AS FLOAT))*100, 1) AS pct_with_clickout,
    ROUND(AVG(weekend_ratio)*100, 1) AS avg_weekend_pct,
    ROUND(AVG(evening_ratio)*100, 1) AS avg_evening_pct,
    ROUND(AVG(holiday_ratio)*100, 1) AS avg_holiday_pct,
    ROUND(AVG(COALESCE(avg_session_mins,0)), 2) AS avg_session_mins,
    ROUND(AVG(monetization_diversity), 3) AS avg_mon_diversity
FROM DB_TEAM_2.BASE_BASE.user_features_v2
""")
row = cur.fetchone()
print(f"""
  Feature check:
    total users        : {row[0]:,}
    has_clickout count : {row[1]:,} ({row[2]}%)
    avg weekend %      : {row[3]}%
    avg evening %      : {row[4]}%
    avg holiday %      : {row[5]}%
    avg session mins   : {row[6]}
    avg mon_diversity  : {row[7]}
""")

cur.close()
conn.close()
print("Done.")
