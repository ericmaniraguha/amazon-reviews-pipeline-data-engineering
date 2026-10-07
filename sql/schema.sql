-- Amazon Reviews ClickHouse Schema
-- Engine: ReplacingMergeTree provides automatic deduplication during background merges
-- Ordering by (asin, timestamp) optimises product-level and time-series analytical queries

CREATE DATABASE IF NOT EXISTS amazon;

CREATE TABLE IF NOT EXISTS amazon.reviews (
    review_id        String,     -- Composite key: user_id + asin + timestamp
    user_id          String,
    asin             String,     -- Amazon Standard Identification Number
    parent_asin      String,     -- Product family grouping
    rating           Int32,      -- 1–5 star rating
    title            String,
    text             String,
    images           String,     -- JSON-encoded image URLs
    helpful_vote     Int32,
    verified_purchase UInt8,     -- 1 = verified, 0 = unverified
    timestamp        Int64       -- Unix timestamp (milliseconds)
)
ENGINE = ReplacingMergeTree
PRIMARY KEY review_id
ORDER BY (asin, timestamp);


-- ---------------------------------------------------------------
-- Useful analytical queries
-- ---------------------------------------------------------------

-- Dataset overview
SELECT
    COUNT(*)                              AS total_reviews,
    COUNT(DISTINCT user_id)               AS unique_users,
    COUNT(DISTINCT asin)                  AS unique_products,
    ROUND(AVG(rating), 3)                 AS avg_rating,
    SUM(helpful_vote)                     AS total_helpful_votes,
    SUM(verified_purchase)                AS verified_purchases
FROM amazon.reviews FINAL;

-- Rating distribution
SELECT
    rating,
    COUNT(*)                                          AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS pct,
    ROUND(AVG(helpful_vote), 3)                        AS avg_helpful_votes,
    ROUND(AVG(verified_purchase) * 100, 2)             AS verified_pct,
    ROUND(AVG(length(text)), 1)                        AS avg_text_len
FROM amazon.reviews FINAL
GROUP BY rating
ORDER BY rating;

-- Top products by review volume (min 50 reviews)
SELECT
    asin,
    COUNT(*)              AS review_count,
    ROUND(AVG(rating), 3) AS avg_rating,
    SUM(helpful_vote)     AS total_helpful_votes
FROM amazon.reviews FINAL
GROUP BY asin
HAVING review_count >= 50
ORDER BY review_count DESC, avg_rating DESC
LIMIT 20;

-- Most active reviewers
SELECT
    user_id,
    COUNT(*)              AS review_count,
    ROUND(AVG(rating), 3) AS avg_rating,
    SUM(helpful_vote)     AS total_helpful_votes
FROM amazon.reviews FINAL
GROUP BY user_id
ORDER BY review_count DESC
LIMIT 20;
