"""
Step 6: Cortex COMPLETE narratives for all 11 segments (4 named + 7 Explorer sub-types)
Saves to DB_TEAM_2.BASE_MARTS.segment_narratives_v2
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

print("Collecting per-segment stats ...")

cur.execute("""
SELECT
    CASE WHEN primary_segment = 'Explorer' THEN COALESCE(explorer_subtype, 'Explorer')
         ELSE primary_segment END AS segment_label,
    COUNT(*) AS n,
    ROUND(AVG(seenlist_adds),2)      AS avg_seenlist,
    ROUND(AVG(watchlist_adds),2)     AS avg_watchlist,
    ROUND(AVG(events_per_session),2) AS avg_eps,
    ROUND(AVG(COALESCE(free_ratio,0)),3)  AS avg_free_ratio,
    ROUND(AVG(COALESCE(buyer_ratio,0)),3) AS avg_buyer_ratio,
    ROUND(AVG(CAST(has_clickout AS FLOAT)),3) AS pct_has_clickout,
    ROUND(AVG(top2_genre_share),3)   AS avg_top2_genre,
    ROUND(AVG(CAST(genre_count AS FLOAT)),1) AS avg_genre_count,
    ROUND(AVG(active_days),2)        AS avg_active_days,
    ROUND(AVG(weekend_ratio),3)      AS avg_weekend,
    ROUND(AVG(evening_ratio),3)      AS avg_evening,
    ROUND(AVG(holiday_ratio),3)      AS avg_holiday,
    ROUND(AVG(CAST(monetization_diversity AS FLOAT)),3) AS avg_mon_div,
    ROUND(AVG(unique_titles),2)      AS avg_unique_titles,
    ROUND(AVG(CAST(trailer_plays AS FLOAT)),2) AS avg_trailers,
    ROUND(AVG(login_rate),3)         AS avg_login_rate,
    ROUND(AVG(mobile_ratio),3)       AS avg_mobile
FROM DB_TEAM_2.BASE_MARTS.user_segments_v3
GROUP BY 1
ORDER BY n DESC
""")
stats = cur.fetchall()
cols = [d[0].lower() for d in cur.description]
segments = [{c: r[i] for i, c in enumerate(cols)} for r in stats]
total_users = sum(s['n'] for s in segments)

print(f"  Found {len(segments)} segments, {total_users:,} total users\n")

print("Creating segment_narratives_v2 table ...")
cur.execute("USE DATABASE DB_TEAM_2")
cur.execute("""
CREATE OR REPLACE TABLE DB_TEAM_2.BASE_MARTS.segment_narratives_v2 (
    segment_label  TEXT,
    segment_type   TEXT,
    user_count     NUMBER,
    pct_of_total   FLOAT,
    narrative      TEXT,
    targeting_hook TEXT
)
""")

for s in segments:
    seg = s['segment_label']
    pct = round(s['n'] / total_users * 100, 1)

    # Determine segment_type
    named = {'Binge Watcher', 'Deal Hunter', 'Watchlist Hoarder', 'Genre Loyalist'}
    stype = 'named' if seg in named else 'explorer_subtype'

    prompt = f"""You are a streaming media analyst writing a targeting brief for a B2B platform (JustWatch).
Write a 2-paragraph targeting narrative for the '{seg}' audience segment.

Segment statistics ({s['n']:,} users, {pct}% of Germany Dec 2025 audience):
- Avg seenlist (titles watched/marked seen): {s['avg_seenlist']}
- Avg watchlist (titles saved): {s['avg_watchlist']}
- Avg events per session: {s['avg_eps']}
- Avg unique titles engaged: {s['avg_unique_titles']}
- Active days: {s['avg_active_days']}
- Has clickout (any): {int(s['pct_has_clickout']*100)}%
- Free/AVOD clickout ratio: {s['avg_free_ratio']}
- Rent/Buy (TVOD) ratio: {s['avg_buyer_ratio']}
- Monetization diversity (distinct offer types): {s['avg_mon_div']}
- Top-2 genre share: {s['avg_top2_genre']}
- Genre count: {s['avg_genre_count']}
- Weekend activity: {int(s['avg_weekend']*100)}%
- Evening (18-22h) activity: {int(s['avg_evening']*100)}%
- Holiday (Dec 20-31) activity: {int(s['avg_holiday']*100)}%
- Trailer plays: {s['avg_trailers']}
- Login rate: {int(s['avg_login_rate']*100)}%
- Mobile ratio: {int(s['avg_mobile']*100)}%

Paragraph 1: Describe the behavioral profile — who these users are, what they do on JustWatch, and what motivates them.
Paragraph 2: Provide 2-3 specific targeting recommendations for a streaming studio or service wanting to reach this segment (content, timing, offer type, ad format).
Keep both paragraphs concise (3-4 sentences each). Use plain language, no jargon."""

    print(f"  Generating narrative for: {seg} ({s['n']:,} users, {pct}%) ...")

    cur.execute("""
        SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)
    """, (prompt,))
    narrative_row = cur.fetchone()
    narrative = narrative_row[0] if narrative_row else '(no response)'

    # Generate a short targeting hook (one sentence)
    hook_prompt = f"In one punchy sentence (max 15 words), write a targeting hook for '{seg}' streamers: "
    cur.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)", (hook_prompt,))
    hook_row = cur.fetchone()
    hook = hook_row[0].strip().strip('"') if hook_row else ''

    cur.execute("""
        INSERT INTO DB_TEAM_2.BASE_MARTS.segment_narratives_v2
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (seg, stype, int(s['n']), pct, narrative, hook))

    print(f"    → {narrative[:120].strip()}...")

print("\nVerifying ...")
cur.execute("SELECT segment_label, segment_type, user_count FROM DB_TEAM_2.BASE_MARTS.segment_narratives_v2 ORDER BY user_count DESC")
for row in cur.fetchall():
    print(f"  {row[0]:28s} ({row[1]})  {row[2]:>7,}")

cur.close()
conn.close()
print("\nDone.")
