-- ============================================================
-- DVD Fix Project — OLAP Setup Queries
-- Database: dvd_fix
-- Run ONCE after importing the Sakila/dvdrental dataset
-- ============================================================

-- STEP 1: DIMENSION TABLES
CREATE TABLE IF NOT EXISTS dim_film (
    sk_film          INTEGER PRIMARY KEY,
    film_id          INTEGER,
    title            VARCHAR(255),
    rating           VARCHAR(10),
    rental_rate      DECIMAL(4,2),
    rental_duration  INTEGER,
    replacement_cost DECIMAL(5,2),
    length           INTEGER,
    special_features TEXT
);
TRUNCATE TABLE dim_film;
INSERT INTO dim_film
SELECT film_id, film_id, title, rating, rental_rate,
       rental_duration, replacement_cost, length,
       COALESCE(special_features::TEXT, '')
FROM film;

CREATE TABLE IF NOT EXISTS dim_genre (
    sk_genre   INTEGER PRIMARY KEY,
    genre_id   INTEGER,
    genre_name VARCHAR(25)
);
TRUNCATE TABLE dim_genre;
INSERT INTO dim_genre SELECT category_id, category_id, name FROM category;

CREATE TABLE IF NOT EXISTS dim_date (
    sk_date         SERIAL PRIMARY KEY,
    full_date       DATE NOT NULL,
    year            INTEGER,
    month           INTEGER,
    week_number     INTEGER,
    week_start_date DATE,
    week_end_date   DATE
);
TRUNCATE TABLE dim_date;
INSERT INTO dim_date (full_date, year, month, week_number, week_start_date, week_end_date)
SELECT DISTINCT
    d::DATE,
    EXTRACT(YEAR FROM d)::INTEGER,
    EXTRACT(MONTH FROM d)::INTEGER,
    EXTRACT(WEEK FROM d)::INTEGER,
    DATE_TRUNC('week', d)::DATE,
    (DATE_TRUNC('week', d) + INTERVAL '6 days')::DATE
FROM generate_series(
    (SELECT MIN(rental_date) FROM rental),
    (SELECT MAX(rental_date) FROM rental),
    INTERVAL '1 day'
) AS d;

-- STEP 2: FACT TABLES
CREATE TABLE IF NOT EXISTS fact_rental (
    sk_rental   SERIAL PRIMARY KEY,
    rental_id   INTEGER,
    sk_film     INTEGER,
    sk_genre    INTEGER,
    sk_date     INTEGER,
    rental_date TIMESTAMP,
    return_date TIMESTAMP,
    amount      DECIMAL(5,2),
    customer_id INTEGER,
    staff_id    INTEGER
);
TRUNCATE TABLE fact_rental;
INSERT INTO fact_rental (rental_id, sk_film, sk_genre, sk_date, rental_date, return_date, amount, customer_id, staff_id)
SELECT
    r.rental_id, f.film_id, fc.category_id, dd.sk_date,
    r.rental_date, r.return_date, COALESCE(p.amount, 0),
    r.customer_id, r.staff_id
FROM rental r
JOIN inventory i    ON r.inventory_id = i.inventory_id
JOIN film f         ON i.film_id = f.film_id
JOIN film_category fc ON f.film_id = fc.film_id
JOIN payment p      ON r.rental_id = p.rental_id
JOIN dim_date dd    ON dd.full_date = r.rental_date::DATE;

CREATE TABLE IF NOT EXISTS fact_inventory (
    sk_inventory SERIAL PRIMARY KEY,
    sk_film      INTEGER,
    store_id     INTEGER,
    total_copies INTEGER
);
TRUNCATE TABLE fact_inventory;
INSERT INTO fact_inventory (sk_film, store_id, total_copies)
SELECT film_id, store_id, COUNT(*) FROM inventory GROUP BY film_id, store_id;

-- STEP 3: SUMMARY TABLES

-- Summary Genre
CREATE TABLE IF NOT EXISTS summary_genre (
    genre_name    VARCHAR(25) PRIMARY KEY,
    total_rental  INTEGER,
    total_revenue DECIMAL(10,2),
    best_film     VARCHAR(255),
    revenue_pct   DECIMAL(5,2)
);
TRUNCATE TABLE summary_genre;
INSERT INTO summary_genre
WITH base AS (
    SELECT dg.genre_name, COUNT(fr.sk_rental) AS total_rental, SUM(fr.amount) AS total_revenue
    FROM fact_rental fr JOIN dim_genre dg ON fr.sk_genre = dg.sk_genre
    GROUP BY dg.genre_name
),
best AS (
    SELECT DISTINCT ON (dg.genre_name) dg.genre_name, df.title AS best_film
    FROM fact_rental fr
    JOIN dim_genre dg ON fr.sk_genre = dg.sk_genre
    JOIN dim_film df  ON fr.sk_film  = df.sk_film
    GROUP BY dg.genre_name, df.title
    ORDER BY dg.genre_name, COUNT(*) DESC
)
SELECT base.genre_name, base.total_rental, base.total_revenue, best.best_film,
       ROUND(base.total_revenue / SUM(base.total_revenue) OVER () * 100, 2)
FROM base JOIN best ON base.genre_name = best.genre_name;

-- Summary Rating
CREATE TABLE IF NOT EXISTS summary_rating (
    rating              VARCHAR(10) PRIMARY KEY,
    total_rental        INTEGER,
    total_revenue       DECIMAL(10,2),
    number_of_films     INTEGER,
    avg_rental_per_film DECIMAL(8,2),
    rental_pct          DECIMAL(5,2)
);
TRUNCATE TABLE summary_rating;
INSERT INTO summary_rating
SELECT df.rating,
    COUNT(fr.sk_rental)::INTEGER,
    SUM(fr.amount),
    COUNT(DISTINCT fr.sk_film),
    ROUND(COUNT(fr.sk_rental)::DECIMAL / NULLIF(COUNT(DISTINCT fr.sk_film),0), 2),
    ROUND(COUNT(fr.sk_rental)::DECIMAL / SUM(COUNT(fr.sk_rental)) OVER () * 100, 2)
FROM fact_rental fr JOIN dim_film df ON fr.sk_film = df.sk_film
GROUP BY df.rating;

-- Summary Weekly Genre
CREATE TABLE IF NOT EXISTS summary_weekly_genre (
    genre_name      VARCHAR(25),
    week_start_date DATE,
    week_number     INTEGER,
    year            INTEGER,
    weekly_rental   INTEGER,
    PRIMARY KEY (genre_name, week_start_date)
);
TRUNCATE TABLE summary_weekly_genre;
INSERT INTO summary_weekly_genre
SELECT dg.genre_name, dd.week_start_date, dd.week_number, dd.year,
       COUNT(fr.sk_rental)::INTEGER
FROM fact_rental fr
JOIN dim_genre dg ON fr.sk_genre = dg.sk_genre
JOIN dim_date dd  ON fr.sk_date  = dd.sk_date
GROUP BY dg.genre_name, dd.week_start_date, dd.week_number, dd.year;

-- Summary Inventory
CREATE TABLE IF NOT EXISTS summary_inventory (
    sk_film        INTEGER PRIMARY KEY,
    title          VARCHAR(255),
    current_stock  INTEGER,
    rental_per_day DECIMAL(8,4),
    days_to_empty  INTEGER,
    stock_status   VARCHAR(10)
);
TRUNCATE TABLE summary_inventory;
INSERT INTO summary_inventory
WITH rrc AS (
    SELECT sk_film,
           COUNT(*)::DECIMAL / GREATEST((SELECT MAX(rental_date::DATE)-MIN(rental_date::DATE) FROM rental),1) AS rpd
    FROM fact_rental GROUP BY sk_film
),
stock AS (SELECT film_id, SUM(total_copies) AS total_copies FROM fact_inventory GROUP BY film_id),
rented AS (SELECT sk_film, COUNT(*) AS cnt FROM fact_rental WHERE return_date IS NULL GROUP BY sk_film)
SELECT df.sk_film, df.title,
    GREATEST(COALESCE(s.total_copies,0) - COALESCE(rv.cnt,0), 0),
    COALESCE(rrc.rpd, 0),
    CASE WHEN COALESCE(rrc.rpd,0)=0 THEN 9999
         ELSE LEAST((GREATEST(COALESCE(s.total_copies,0)-COALESCE(rv.cnt,0),0)/rrc.rpd)::INTEGER, 9999) END,
    CASE WHEN GREATEST(COALESCE(s.total_copies,0)-COALESCE(rv.cnt,0),0)<=1 THEN 'CRITICAL'
         WHEN GREATEST(COALESCE(s.total_copies,0)-COALESCE(rv.cnt,0),0)<=3 THEN 'WARNING'
         ELSE 'OK' END
FROM dim_film df
LEFT JOIN stock s ON df.sk_film = s.film_id
LEFT JOIN rented rv ON df.sk_film = rv.sk_film
LEFT JOIN rrc ON df.sk_film = rrc.sk_film;

-- Summary Film Features (for ML)
CREATE TABLE IF NOT EXISTS summary_film_features (
    sk_film          INTEGER PRIMARY KEY,
    title            VARCHAR(255),
    genre_name       VARCHAR(25),
    rating           VARCHAR(10),
    length           INTEGER,
    rental_rate      DECIMAL(4,2),
    replacement_cost DECIMAL(5,2),
    rental_duration  INTEGER,
    num_actors       INTEGER,
    special_features TEXT,
    total_rental     INTEGER,
    total_revenue    DECIMAL(10,2),
    is_popular       BOOLEAN
);
TRUNCATE TABLE summary_film_features;
INSERT INTO summary_film_features
WITH rpf AS (SELECT sk_film, COUNT(*) AS tr, SUM(amount) AS rev FROM fact_rental GROUP BY sk_film),
     apf AS (SELECT film_id, COUNT(*) AS num_actors FROM film_actor GROUP BY film_id),
     threshold AS (SELECT PERCENTILE_CONT(0.6) WITHIN GROUP (ORDER BY tr) AS val FROM rpf)
SELECT df.sk_film, df.title,
    COALESCE(MAX(dg.genre_name), 'Unknown'),
    df.rating, df.length, df.rental_rate, df.replacement_cost, df.rental_duration,
    COALESCE(apf.num_actors, 0), df.special_features,
    COALESCE(rpf.tr, 0), COALESCE(rpf.rev, 0),
    COALESCE(rpf.tr, 0) >= (SELECT val FROM threshold)
FROM dim_film df
LEFT JOIN fact_rental fr ON df.sk_film = fr.sk_film
LEFT JOIN dim_genre dg   ON fr.sk_genre = dg.sk_genre
LEFT JOIN rpf ON df.sk_film = rpf.sk_film
LEFT JOIN apf ON df.sk_film = apf.film_id
GROUP BY df.sk_film, df.title, df.rating, df.length, df.rental_rate,
         df.replacement_cost, df.rental_duration, apf.num_actors,
         df.special_features, rpf.tr, rpf.rev;

COMMIT;
