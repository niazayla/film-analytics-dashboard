"""Page 4 — Inventory Stock Forecast with SMA and live stock update form."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="Inventory Forecast", page_icon="📦", layout="wide")

from styles import inject_css, render_sidebar, page_header, alert_box, section_label
from db import query_df, execute, refresh_summaries

inject_css()
with st.sidebar:
    render_sidebar()

page_header("📦", "Inventory Stock Forecast",
            "SMA-based days-to-empty prediction · Critical alerts · Rental velocity metrics · Live stock updates")

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_inventory():
    return query_df("SELECT * FROM summary_inventory ORDER BY days_to_empty ASC")

@st.cache_data(ttl=30)
def load_weekly_rentals(film_id: int = None):
    sql = """
        SELECT fr.sk_film, df.title, dd.week_start_date,
               COUNT(fr.sk_rental) AS weekly_rental
        FROM fact_rental fr
        JOIN dim_film df ON fr.sk_film = df.sk_film
        JOIN dim_date dd ON fr.sk_date = dd.sk_date
        WHERE 1=1
    """
    params = []
    if film_id:
        sql += " AND fr.sk_film = %s"
        params.append(film_id)
    sql += " GROUP BY fr.sk_film, df.title, dd.week_start_date ORDER BY dd.week_start_date"
    return query_df(sql, params if params else None)

@st.cache_data(ttl=60)
def load_films_list():
    """FIXED: Load films that actually have inventory"""
    return query_df("""
        SELECT DISTINCT f.film_id, f.title 
        FROM film f
        INNER JOIN inventory i ON f.film_id = i.film_id
        ORDER BY f.title
    """)

# Load inventory data
data = load_inventory()
if not data:
    alert_box("error","No inventory data","Run OLAP SQL first.")
    st.stop()

df = pd.DataFrame(data)
df["current_stock"]  = df["current_stock"].astype(int)
df["rental_per_day"] = df["rental_per_day"].astype(float)
df["days_to_empty"]  = df["days_to_empty"].astype(int)

critical = df[df["stock_status"] == "CRITICAL"]
warning  = df[df["stock_status"] == "WARNING"]

# ── Critical alerts ────────────────────────────────────────────────────────────
if not critical.empty:
    items = "  ·  ".join([f"<b>{r['title']}</b> ({r['current_stock']} left)" for _, r in critical.head(5).iterrows()])
    alert_box("error", f"🚨 {len(critical)} films at CRITICAL stock (≤1 copy)", items)

if not warning.empty:
    alert_box("warning", f"⚠️ {len(warning)} films at WARNING level (≤3 copies)")

# ── KPIs ──────────────────────────────────────────────────────────────────────
avg_vel = df[df["rental_per_day"] > 0]["rental_per_day"].mean()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Films Tracked",       len(df))
c2.metric("Critical (≤1)",       len(critical))
c3.metric("Warning (≤3)",        len(warning))
c4.metric("OK",                  len(df[df["stock_status"]=="OK"]))
c5.metric("Avg Velocity",        f"{avg_vel:.2f}/day")

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Stock Overview", "📈 SMA Forecast", "🏎️ Velocity", "➕ Stock Update"])

with tab1:
    col_f, _ = st.columns([2, 3])
    with col_f:
        status_filter = st.selectbox("Filter by Status", ["All","CRITICAL","WARNING","OK"])

    filtered = df if status_filter == "All" else df[df["stock_status"] == status_filter]

    col1, col2 = st.columns(2, gap="large")

    with col1:
        section_label("Days to Empty — Top 25 Most Urgent")
        chart_df = filtered[filtered["days_to_empty"] < 999].nsmallest(25, "days_to_empty")
        if not chart_df.empty:
            bar_colors = ["#dc2626" if d<=3 else "#d97706" if d<=7 else "#2563eb" for d in chart_df["days_to_empty"]]
            fig = go.Figure(go.Bar(
                x=chart_df["days_to_empty"], y=chart_df["title"],
                orientation="h", marker_color=bar_colors,
                text=[f"{d}d" for d in chart_df["days_to_empty"]],
                textposition="outside",
            ))
            fig.update_layout(
                xaxis_title="Days", yaxis=dict(autorange="reversed"),
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(l=10,r=30,t=10,b=10), height=560,
                font=dict(family="DM Sans, sans-serif", color="#1e2a45"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No films match the selected filter")

    with col2:
        section_label("Stock Level Progress Bars")
        max_stock = max(df["current_stock"].max(), 1)
        for _, row in filtered.nsmallest(20, "days_to_empty").iterrows():
            pct   = min(int(row["current_stock"] / max_stock * 100), 100)
            color = "#dc2626" if row["stock_status"]=="CRITICAL" else "#d97706" if row["stock_status"]=="WARNING" else "#059669"
            badge = {"CRITICAL":"🔴","WARNING":"🟡","OK":"🟢"}.get(row["stock_status"],"")
            dte   = "∞" if row["days_to_empty"]>=999 else f"{row['days_to_empty']}d"
            st.markdown(f"""
            <div style="background:white;border:1px solid #e2e8f4;border-radius:12px;
                        padding:.8rem 1.1rem;margin-bottom:.5rem">
                <div style="display:flex;justify-content:space-between;margin-bottom:.3rem">
                    <span style="font-weight:600;font-size:.84rem;color:#08112a">{badge} {row['title'][:36]}</span>
                    <span style="font-size:.76rem;color:#7a8aaa">{row['current_stock']} copies · {dte}</span>
                </div>
                <div style="background:#f1f5f9;border-radius:4px;height:5px">
                    <div style="background:{color};width:{pct}%;height:100%;border-radius:4px"></div>
                </div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    with st.expander("📋 Full Inventory Table"):
        disp = filtered[["title","current_stock","rental_per_day","days_to_empty","stock_status"]].copy()
        disp.columns = ["Film","Stock","Rentals/Day","Days to Empty","Status"]
        disp["Rentals/Day"]   = disp["Rentals/Day"].apply(lambda x: f"{x:.3f}")
        disp["Days to Empty"] = disp["Days to Empty"].apply(lambda x: "∞" if x>=999 else str(x))
        st.dataframe(disp.reset_index(drop=True), use_container_width=True, hide_index=True)

with tab2:
    section_label("SMA (Simple Moving Average) Demand Forecast")
    st.markdown("""
    <p style="font-size:.875rem;color:#64748b;margin-bottom:1rem">
        The SMA model smooths weekly rental history to project future demand.
        A longer window (SMA-8) gives a stable trend; shorter (SMA-3) reacts faster to recent spikes.
    </p>""", unsafe_allow_html=True)

    films_list = load_films_list()
    
    # Debug: Show if films are loaded
    if films_list:
        st.success(f"✅ Loaded {len(films_list)} films with inventory")
        
        # Create selectbox with better formatting
        film_options = {f"{r['title']}": r['film_id'] for r in films_list}
        selected_film_title = st.selectbox(
            "Select Film for SMA Forecast",
            options=list(film_options.keys()),
            help="Choose a film that has inventory in the system"
        )
        
        if selected_film_title:
            film_id_sma = film_options[selected_film_title]
            sma_window = st.slider("SMA Window (weeks)", 2, 12, 4)

            weekly = load_weekly_rentals(film_id_sma)
            if weekly:
                wdf = pd.DataFrame(weekly)
                wdf["week_start_date"] = pd.to_datetime(wdf["week_start_date"])
                wdf = wdf.sort_values("week_start_date")
                wdf[f"SMA-{sma_window}"] = wdf["weekly_rental"].rolling(sma_window).mean()

                # Forecast next 4 weeks
                last_sma = wdf[f"SMA-{sma_window}"].dropna().iloc[-1] if not wdf[f"SMA-{sma_window}"].dropna().empty else 0
                last_date = wdf["week_start_date"].max()
                future_dates = [last_date + timedelta(weeks=i+1) for i in range(4)]
                future_vals = [last_sma * (1 + np.random.normal(0, 0.03)) for _ in range(4)]

                fig_sma = go.Figure()
                fig_sma.add_trace(go.Scatter(
                    x=wdf["week_start_date"], y=wdf["weekly_rental"],
                    mode="lines+markers", name="Actual Rentals",
                    line=dict(color="#94a3b8", width=1.5), marker=dict(size=5),
                ))
                fig_sma.add_trace(go.Scatter(
                    x=wdf["week_start_date"], y=wdf[f"SMA-{sma_window}"],
                    mode="lines", name=f"SMA-{sma_window}",
                    line=dict(color="#2563eb", width=2.5),
                ))
                fig_sma.add_trace(go.Scatter(
                    x=future_dates, y=future_vals,
                    mode="lines+markers", name="Forecast (4 weeks)",
                    line=dict(color="#059669", width=2, dash="dash"),
                    marker=dict(size=8, symbol="diamond"),
                ))
                fig_sma.add_vrect(
                    x0=last_date, x1=future_dates[-1],
                    fillcolor="rgba(5,150,105,0.05)", line_width=0,
                    annotation_text="Forecast Zone", annotation_position="top left",
                )
                fig_sma.update_layout(
                    xaxis_title="Week", yaxis_title="Rentals",
                    plot_bgcolor="white", paper_bgcolor="white",
                    margin=dict(l=10,r=10,t=10,b=10), height=420,
                    font=dict(family="DM Sans, sans-serif", color="#1e2a45"),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.25),
                )
                st.plotly_chart(fig_sma, use_container_width=True)

                # Forecast metrics
                col1, col2, col3 = st.columns(3)
                col1.metric("SMA Trend", f"{last_sma:.1f} rentals/wk")
                col2.metric("Forecast Week 1", f"{future_vals[0]:.0f} rentals")
                col3.metric("Forecast Week 4", f"{future_vals[3]:.0f} rentals")
            else:
                alert_box("info", f"No rental history for '{selected_film_title}'", "Try a different film that has been rented before.")
    else:
        alert_box("error", "No films found with inventory!", "Make sure your database has inventory records.")

with tab3:
    section_label("Rental Velocity — Top 20 Fastest Moving")
    vel_df = df[df["rental_per_day"]>0].nlargest(20,"rental_per_day").copy()
    if not vel_df.empty:
        fig_v = px.bar(vel_df, x="rental_per_day", y="title",
                       orientation="h", color="rental_per_day",
                       color_continuous_scale=["#bbf7d0","#059669","#064e3b"],
                       text=vel_df["rental_per_day"].apply(lambda x: f"{x:.3f}/d"),
                       labels={"rental_per_day":"Rentals/Day","title":""})
        fig_v.update_traces(textposition="outside", textfont_size=11)
        fig_v.update_layout(
            coloraxis_showscale=False,
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=10,r=30,t=10,b=10), height=520,
            font=dict(family="DM Sans, sans-serif", color="#1e2a45"),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_v, use_container_width=True)

        st.markdown("---")
        section_label("Velocity Metric Cards — Top 5")
        top5 = df[df["rental_per_day"]>0].nlargest(5,"rental_per_day")
        cols = st.columns(5)
        for col, (_, row) in zip(cols, top5.iterrows()):
            col.metric(
                row["title"][:18]+("…" if len(row["title"])>18 else ""),
                f"{row['rental_per_day']:.3f}/day",
                f"{row['current_stock']} in stock",
            )
    else:
        st.info("No rental velocity data available yet")

with tab4:
    st.markdown("""
    <div style="background:white;border:1px solid #e2e8f4;border-radius:16px;
                padding:1.5rem 2rem;margin-bottom:1rem">
        <div style="font-size:.65rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
                    color:#d97706;margin-bottom:.75rem">📦 SYSTEM UPDATE — Add / Restock Inventory</div>
        <p style="font-size:.88rem;color:#64748b;margin:0">
            Use this form to simulate restocking. Adding copies will update
            <code>fact_inventory</code> and <strong>refresh</strong> days-to-empty calculations.
        </p>
    </div>
    """, unsafe_allow_html=True)

    films_list2 = load_films_list()
    if films_list2:
        film_opts2 = {r["title"]: r["film_id"] for r in films_list2}
        
        # Debug info
        st.info(f"📊 Found {len(film_opts2)} films in inventory. Select one to restock.")

        with st.form("restock_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                film_sel = st.selectbox("Film to Restock", list(film_opts2.keys()))
            with col2:
                store_sel = st.selectbox("Store", [1, 2])
            with col3:
                qty = st.number_input("Copies to Add", min_value=1, max_value=50, value=5)

            submitted2 = st.form_submit_button("📦 Add Stock & Refresh Forecast", use_container_width=True, type="primary")

        if submitted2:
            film_id2 = film_opts2[film_sel]
            
            # Add to inventory
            success = True
            for _ in range(qty):
                result = execute(
                    "INSERT INTO inventory (film_id, store_id, last_update) VALUES (%s, %s, NOW())",
                    (film_id2, store_sel)
                )
                if not result:
                    success = False
                    break
            
            # Also update fact_inventory
            existing = query_df(
                "SELECT sk_inventory, total_copies FROM fact_inventory WHERE sk_film=%s AND store_id=%s",
                (film_id2, store_sel)
            )
            if existing:
                execute(
                    "UPDATE fact_inventory SET total_copies = total_copies + %s WHERE sk_film=%s AND store_id=%s",
                    (qty, film_id2, store_sel)
                )
            else:
                execute(
                    "INSERT INTO fact_inventory (sk_film, store_id, total_copies) VALUES (%s,%s,%s)",
                    (film_id2, store_sel, qty)
                )

            if success:
                with st.spinner("Refreshing inventory summaries..."):
                    refresh_summaries()
                st.cache_data.clear()
                alert_box("success", "✅ Stock updated!",
                          f"Added {qty} copies of '{film_sel}' to Store {store_sel}. Forecast refreshed.")
                st.rerun()
            else:
                alert_box("error", "Failed to add stock", "Check database connection")
    else:
        alert_box("error", "No films found in inventory", "Make sure your inventory table has data")