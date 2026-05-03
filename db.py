"""
db.py — Central database connection for dvd_fix project.
All pages import from here. Uses st.cache_resource for connection pooling.
"""
import os
import psycopg2
import psycopg2.extras
import streamlit as st
from contextlib import contextmanager

# ── Connection config ─────────────────────────────────────────────────────────
DB_CONFIG = {
    "dbname":   os.getenv("DB_NAME",     "your_database"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "your_password"),
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     os.getenv("DB_PORT",     "5432"),
}


@st.cache_resource
def get_engine():
    """Cached psycopg2 connection. Re-used across reruns."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        return conn
    except Exception as e:
        st.error(f"❌ Cannot connect to database dvd_fix: {e}")
        return None


def query_df(sql: str, params=None):
    """Run SELECT → returns list of dicts."""
    conn = get_engine()
    if conn is None:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        conn.rollback()
        st.error(f"Query error: {e}")
        return []


def execute(sql: str, params=None, fetch=False):
    conn = get_engine()
    if conn is None:
        return None

    try:
        with conn.cursor() as cur:
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)

            if fetch:
                result = cur.fetchall()
            else:
                result = True

        conn.commit()
        return result

    except Exception as e:
        conn.rollback()
        st.error(f"Execute error: {e}")
        return None


def refresh_summaries():
    """Refresh all summary tables after data changes"""
    conn = get_engine()
    if conn is None:
        return False

    try:
        with conn.cursor() as cur:

            # =========================
            # 🔥 SUMMARY GENRE (same as before)
            # =========================
            cur.execute("TRUNCATE TABLE summary_genre;")
            cur.execute("""
                INSERT INTO summary_genre (genre_name, total_rental, total_revenue, best_film, revenue_pct)
                WITH base AS (
                    SELECT c.name AS genre_name, 
                           COUNT(r.rental_id) AS total_rental, 
                           COALESCE(SUM(p.amount), 0) AS total_revenue
                    FROM rental r
                    JOIN inventory i ON r.inventory_id = i.inventory_id
                    JOIN film f ON i.film_id = f.film_id
                    JOIN film_category fc ON f.film_id = fc.film_id
                    JOIN category c ON fc.category_id = c.category_id
                    LEFT JOIN payment p ON r.rental_id = p.rental_id
                    GROUP BY c.name
                ),
                best AS (
                    SELECT DISTINCT ON (c.name) 
                           c.name AS genre_name, 
                           f.title AS best_film,
                           COUNT(r.rental_id) as rental_count
                    FROM rental r
                    JOIN inventory i ON r.inventory_id = i.inventory_id
                    JOIN film f ON i.film_id = f.film_id
                    JOIN film_category fc ON f.film_id = fc.film_id
                    JOIN category c ON fc.category_id = c.category_id
                    GROUP BY c.name, f.title
                    ORDER BY c.name, rental_count DESC
                )
                SELECT base.genre_name, base.total_rental, base.total_revenue, best.best_film,
                       ROUND(base.total_revenue / NULLIF(SUM(base.total_revenue) OVER (), 0) * 100, 2)
                FROM base
                JOIN best ON base.genre_name = best.genre_name
                WHERE base.total_rental > 0;
            """)

            # =========================
            # 🔥 SUMMARY RATING (same as before)
            # =========================
            cur.execute("TRUNCATE TABLE summary_rating;")
            cur.execute("""
                INSERT INTO summary_rating (rating, total_rental, total_revenue, num_films, avg_rental_per_film, rental_pct)
                SELECT 
                    f.rating,
                    COUNT(r.rental_id)::INTEGER,
                    COALESCE(SUM(p.amount), 0),
                    COUNT(DISTINCT f.film_id),
                    ROUND(COUNT(r.rental_id)::DECIMAL / NULLIF(COUNT(DISTINCT f.film_id), 0), 2),
                    ROUND(COUNT(r.rental_id)::DECIMAL / NULLIF(SUM(COUNT(r.rental_id)) OVER (), 0) * 100, 2)
                FROM film f
                LEFT JOIN inventory i ON f.film_id = i.film_id
                LEFT JOIN rental r ON i.inventory_id = r.inventory_id
                LEFT JOIN payment p ON r.rental_id = p.rental_id
                GROUP BY f.rating
                HAVING COUNT(r.rental_id) > 0;
            """)

            # =========================
            # 🔥 SUMMARY INVENTORY - FIXED to only show films with inventory
            # =========================
            cur.execute("TRUNCATE TABLE summary_inventory;")
            
            cur.execute("""
                WITH rental_velocity AS (
                    SELECT 
                        i.film_id,
                        COUNT(r.rental_id)::DECIMAL / 
                        GREATEST(EXTRACT(DAY FROM (COALESCE(MAX(r.rental_date), NOW()) - COALESCE(MIN(r.rental_date), NOW()))), 1) AS rental_per_day
                    FROM inventory i
                    LEFT JOIN rental r ON i.inventory_id = r.inventory_id
                    GROUP BY i.film_id
                ),
                stock_count AS (
                    SELECT film_id, COUNT(*) AS total_copies
                    FROM inventory
                    GROUP BY film_id
                ),
                rented_out AS (
                    SELECT i.film_id, COUNT(*) AS rented_count
                    FROM rental r
                    JOIN inventory i ON r.inventory_id = i.inventory_id
                    WHERE r.return_date IS NULL
                    GROUP BY i.film_id
                )
                INSERT INTO summary_inventory (sk_film, title, current_stock, rental_per_day, days_to_empty, stock_status)
                SELECT 
                    f.film_id,
                    f.title,
                    GREATEST(COALESCE(sc.total_copies, 0) - COALESCE(ro.rented_count, 0), 0) AS current_stock,
                    COALESCE(rv.rental_per_day, 0) AS rental_per_day,
                    CASE 
                        WHEN COALESCE(rv.rental_per_day, 0) = 0 THEN 9999
                        WHEN GREATEST(COALESCE(sc.total_copies, 0) - COALESCE(ro.rented_count, 0), 0) = 0 THEN 9999
                        ELSE (GREATEST(COALESCE(sc.total_copies, 0) - COALESCE(ro.rented_count, 0), 0) / NULLIF(rv.rental_per_day, 0))::INTEGER
                    END AS days_to_empty,
                    CASE 
                        WHEN GREATEST(COALESCE(sc.total_copies, 0) - COALESCE(ro.rented_count, 0), 0) = 0 THEN 'OUT OF STOCK'
                        WHEN GREATEST(COALESCE(sc.total_copies, 0) - COALESCE(ro.rented_count, 0), 0) <= 1 THEN 'CRITICAL'
                        WHEN GREATEST(COALESCE(sc.total_copies, 0) - COALESCE(ro.rented_count, 0), 0) <= 3 THEN 'WARNING'
                        ELSE 'OK'
                    END AS stock_status
                FROM film f
                INNER JOIN stock_count sc ON f.film_id = sc.film_id
                LEFT JOIN rented_out ro ON f.film_id = ro.film_id
                LEFT JOIN rental_velocity rv ON f.film_id = rv.film_id
                WHERE sc.total_copies > 0;  -- Only show films that actually exist in inventory
            """)

            # =========================
            # 🔥 SUMMARY FILM FEATURES - FIXED
            # =========================
            cur.execute("""
                CREATE TABLE IF NOT EXISTS summary_film_features (
                    film_id INTEGER PRIMARY KEY,
                    title TEXT,
                    genre_name TEXT,
                    rating TEXT,
                    length INTEGER,
                    rental_rate DECIMAL,
                    replacement_cost DECIMAL,
                    rental_duration INTEGER,
                    num_actors INTEGER,
                    special_features TEXT,
                    total_rental INTEGER,
                    total_revenue DECIMAL,
                    is_popular BOOLEAN
                );
            """)
            
            cur.execute("TRUNCATE TABLE summary_film_features;")
            
            cur.execute("""
                INSERT INTO summary_film_features
                SELECT 
                    f.film_id,
                    f.title,
                    c.name AS genre_name,
                    f.rating,
                    f.length,
                    f.rental_rate,
                    f.replacement_cost,
                    f.rental_duration,
                    COALESCE(actor_count.num_actors, 0) AS num_actors,
                    f.special_features,
                    COALESCE(rental_stats.total_rental, 0) AS total_rental,
                    COALESCE(rental_stats.total_revenue, 0) AS total_revenue,
                    CASE 
                        WHEN COALESCE(rental_stats.total_rental, 0) >= (
                            SELECT PERCENTILE_CONT(0.6) WITHIN GROUP (ORDER BY rental_count)
                            FROM (
                                SELECT COUNT(r.rental_id) AS rental_count
                                FROM rental r
                                JOIN inventory i ON r.inventory_id = i.inventory_id
                                GROUP BY i.film_id
                            ) sub
                        ) THEN TRUE
                        ELSE FALSE
                    END AS is_popular
                FROM film f
                LEFT JOIN film_category fc ON f.film_id = fc.film_id
                LEFT JOIN category c ON fc.category_id = c.category_id
                LEFT JOIN (
                    SELECT film_id, COUNT(actor_id) AS num_actors
                    FROM film_actor
                    GROUP BY film_id
                ) actor_count ON f.film_id = actor_count.film_id
                LEFT JOIN (
                    SELECT 
                        i.film_id,
                        COUNT(r.rental_id) AS total_rental,
                        COALESCE(SUM(p.amount), 0) AS total_revenue
                    FROM inventory i
                    LEFT JOIN rental r ON i.inventory_id = r.inventory_id
                    LEFT JOIN payment p ON r.rental_id = p.rental_id
                    GROUP BY i.film_id
                ) rental_stats ON f.film_id = rental_stats.film_id
                WHERE EXISTS (SELECT 1 FROM inventory i WHERE i.film_id = f.film_id);
            """)

        conn.commit()
        print("✅ All summaries refreshed successfully!")
        return True

    except Exception as e:
        conn.rollback()
        print(f"REFRESH ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False