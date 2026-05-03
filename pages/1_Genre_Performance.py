"""Page 1 — Genre Performance Analysis with live transaction form (FINAL CLEAN)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Genre Performance", page_icon="🎭", layout="wide")

from styles import inject_css, render_sidebar, page_header, alert_box, section_label
from db import query_df, execute, refresh_summaries

inject_css()
with st.sidebar:
    render_sidebar()

page_header(
    "🎭",
    "Genre Performance",
    "Revenue and rental volume breakdown across all film genres · Automatically updated"
)

# ── LOAD DATA ─────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_genre():
    return query_df("SELECT * FROM summary_genre")

@st.cache_data(ttl=30)
def load_films():
    return query_df("""
        SELECT DISTINCT f.film_id, f.title, c.name AS genre
        FROM film f
        JOIN film_category fc ON f.film_id = fc.film_id
        JOIN category c ON fc.category_id = c.category_id
        JOIN inventory i ON f.film_id = i.film_id
        ORDER BY f.title LIMIT 500
    """)

@st.cache_data(ttl=30)
def load_customers():
    return query_df("""
        SELECT customer_id, first_name || ' ' || last_name AS name 
        FROM customer ORDER BY name LIMIT 200
    """)

@st.cache_data(ttl=30)
def load_staff():
    return query_df("SELECT staff_id FROM staff LIMIT 1")

df_raw = load_genre()

if not df_raw:
    alert_box("error", "No data found", "Please run the OLAP setup SQL first.")
    st.stop()

df = pd.DataFrame(df_raw)

# ── TYPE FIX ─────────────────────────────────────────────
df["total_revenue"] = df["total_revenue"].astype(float)
df["total_rental"]  = df["total_rental"].astype(int)
df["revenue_pct"]   = df["revenue_pct"].astype(float)

# ── SORT ─────────────────────────────────────────────────
df = df.sort_values("total_revenue", ascending=False).reset_index(drop=True)

top_genre = df.iloc[0]

total_rentals = df["total_rental"].sum()
total_revenue = df["total_revenue"].sum()

# ── KPI ──────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Genres", len(df))

c2.metric(
    f"Rentals ({top_genre['genre_name']})",
    f"{top_genre['total_rental']:,}",
    delta=f"{top_genre['total_rental']/total_rentals*100:.1f}% of total"
)

c3.metric(
    f"Revenue ({top_genre['genre_name']})",
    f"${top_genre['total_revenue']:,.2f}",
    delta=f"{top_genre['total_revenue']/total_revenue*100:.1f}% of total"
)

c4.metric("Top Genre", top_genre["genre_name"])

st.markdown("---")

# ── TABS ─────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Charts", "📋 Data Table", "➕ Add Rental"])

BASE_LAYOUT = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=10, r=20, t=30, b=10),
    height=400
)

# ── TAB 1 ─────────────────────────────────────────────────
with tab1:
    col1, col2 = st.columns(2)

    # Revenue Chart
    with col1:
        section_label("Genre Ranking by Revenue")
        fig = px.bar(
            df.sort_values("total_revenue"),
            x="total_revenue",
            y="genre_name",
            orientation="h",
            color="total_revenue",
            text=df["total_revenue"].apply(lambda x: f"${x:,.0f}")
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(coloraxis_showscale=False, **BASE_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)

    # Rental Chart
    with col2:
        section_label("Genre Ranking by Rental Count")
        fig2 = px.bar(
            df.sort_values("total_rental"),
            x="total_rental",
            y="genre_name",
            orientation="h",
            color="total_rental",
            text=df["total_rental"].apply(lambda x: f"{x:,}")
        )
        fig2.update_traces(textposition="outside")
        fig2.update_layout(coloraxis_showscale=False, **BASE_LAYOUT)
        st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)

    # PIE FIXED
    with col3:
        section_label("Revenue Contribution by Genre (%)")

        fig3 = px.pie(
            df,
            values="revenue_pct",
            names="genre_name",
            hole=0.45,
            color_discrete_sequence=px.colors.sequential.Blues_r
        )

        fig3.update_traces(
            textinfo="percent",              # ONLY percent inside
            textposition="inside",
            insidetextorientation="radial"
        )

        fig3.update_layout(
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1
            ),
            margin=dict(l=10, r=10, t=10, b=10)
        )

        st.plotly_chart(fig3, use_container_width=True)

    # Best Film Table
    with col4:
        section_label("Top Performing Film per Genre")
        best = df[["genre_name", "best_film", "total_revenue"]].copy()
        best.columns = ["Genre", "Best Film", "Revenue ($)"]
        best["Revenue ($)"] = best["Revenue ($)"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(best, use_container_width=True, hide_index=True)

    # ── INSIGHTS ─────────────────────────────────────────
    st.markdown("---")
    st.subheader("Insight Analytics")

    avg = total_revenue / total_rentals if total_rentals else 0
    lowest = df.iloc[-1]

    st.success(
        f"Top genre **{top_genre['genre_name']}** generated "
        f"${top_genre['total_revenue']:,.2f} from {top_genre['total_rental']:,} rentals "
        f"(average ${avg:.2f} per rental)."
    )

    st.warning(
        f"The lowest performing genre is **{lowest['genre_name']}**, "
        f"with only ${lowest['total_revenue']:,.2f} in revenue. "
        f"This may indicate low demand, pricing issues, or limited catalog availability."
    )

# ── TAB 2 ───────────────────────────────────────────────
with tab2:
    st.dataframe(df, use_container_width=True, hide_index=True)

# ── TAB 3 ───────────────────────────────────────────────
with tab3:
    st.subheader("Add New Rental Transaction")

    films = load_films()
    customers = load_customers()
    staff = load_staff()

    if films and customers:
        film_opts = {f"{f['title']} ({f['genre']})": f for f in films}
        cust_opts = {c["name"]: c["customer_id"] for c in customers}
        staff_id = staff[0]["staff_id"]

        with st.form("add"):
            film_choice = st.selectbox("Select Film", list(film_opts.keys()))
            cust_choice = st.selectbox("Select Customer", list(cust_opts.keys()))
            amount = st.number_input("Rental Amount ($)", value=2.99)

            submit = st.form_submit_button("Submit Transaction")

        if submit:
            film_id = film_opts[film_choice]["film_id"]
            cust_id = cust_opts[cust_choice]

            inv = query_df(
                "SELECT inventory_id FROM inventory WHERE film_id=%s LIMIT 1",
                (film_id,)
            )

            if not inv:
                alert_box("error", "No inventory available for this film.")
            else:
                inv_id = inv[0]["inventory_id"]

                rental = execute(
                    "INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id) "
                    "VALUES (NOW(), %s, %s, %s) RETURNING rental_id",
                    (inv_id, cust_id, staff_id),
                    fetch=True
                )

                rental_id = rental[0][0]

                execute(
                    "INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) "
                    "VALUES (%s,%s,%s,%s,NOW())",
                    (cust_id, staff_id, rental_id, amount)
                )

                refresh_summaries()
                st.cache_data.clear()

                st.success("Transaction successfully added. Dashboard updated.")
                st.rerun()