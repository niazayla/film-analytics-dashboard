"""
app.py — DVD Fix Analytics Dashboard
Entry point: streamlit run app.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

st.set_page_config(
    page_title="DVD Fix Analytics",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

from styles import inject_css, render_sidebar, page_header, status_banner, section_label, alert_box
from db import query_df

inject_css()


with st.sidebar:
    render_sidebar()

# ── Hero ──────────────────────────────────────────────────────────────────────
page_header("🎬", "DVD Rental Film Analytics Dashboard",
            "Real-time insights powered by PostgreSQL · Streamlit · Machine Learning")

# ── Live DB check ─────────────────────────────────────────────────────────────
genre_data = query_df("SELECT * FROM summary_genre ORDER BY total_revenue DESC")
inv_data   = query_df("SELECT * FROM summary_inventory WHERE stock_status = 'CRITICAL' LIMIT 5")

if genre_data:
    total_rev     = sum(float(r["total_revenue"]) for r in genre_data)
    total_rentals = sum(int(r["total_rental"])    for r in genre_data)
    top_genre     = genre_data[0]["genre_name"]
    status_banner(True, f"Database Connected · {len(genre_data)} genres tracked · All systems operational")
else:
    status_banner(False, msg_err="Cannot reach dvd_fix database. Check your .env / connection settings.")
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Genres Tracked",  len(genre_data))
c2.metric("Total Rentals",   f"{total_rentals:,}")
c3.metric("Total Revenue",   f"${total_rev:,.0f}")
c4.metric("Top Genre",       top_genre)
c5.metric("Critical Stock",  f"{len(inv_data)} films")

if inv_data:
    alert_box("error", f"🚨 {len(inv_data)} film(s) at CRITICAL stock level!",
              " · ".join([r["title"][:25] for r in inv_data]))

st.markdown("---")

# Add this temporary button for refreshing
col1, col2, col3 = st.columns([1,1,3])
with col1:
    if st.button("🔄 Refresh All Summaries", type="secondary"):
        with st.spinner("Refreshing summary tables..."):
            from db import refresh_summaries
            if refresh_summaries():
                st.success("✅ All summaries refreshed!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("❌ Refresh failed!")

# ── Feature cards ─────────────────────────────────────────────────────────────
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("""
    <div style="background:white;border:1px solid #e2e8f4;border-radius:20px;
                padding:1.75rem 2rem;box-shadow:0 2px 12px rgba(8,17,42,0.05)">
        <div style="font-size:.62rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;
                    color:#2563eb;margin-bottom:1.1rem">📊 Analytics</div>
        <div style="display:flex;flex-direction:column;gap:.65rem">
            <div style="background:#f8faff;border:1px solid #edf1fb;border-left:4px solid #2563eb;
                        border-radius:10px;padding:.85rem 1.1rem">
                <div style="font-weight:600;font-size:.9rem;color:#08112a">🎭 Genre Performance</div>
                <div style="font-size:.8rem;color:#7a8aaa;margin-top:.15rem">Revenue & rental volume by genre · Live updates on new rentals</div>
            </div>
            <div style="background:#f8faff;border:1px solid #edf1fb;border-left:4px solid #7c3aed;
                        border-radius:10px;padding:.85rem 1.1rem">
                <div style="font-weight:600;font-size:.9rem;color:#08112a">⭐ Film Rating Impact</div>
                <div style="font-size:.8rem;color:#7a8aaa;margin-top:.15rem">G / PG / R classification effect on demand · Auto-updates per rental</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="background:white;border:1px solid #e2e8f4;border-radius:20px;
                padding:1.75rem 2rem;box-shadow:0 2px 12px rgba(8,17,42,0.05)">
        <div style="font-size:.62rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;
                    color:#2563eb;margin-bottom:1.1rem">🤖 AI Predictions</div>
        <div style="display:flex;flex-direction:column;gap:.65rem">
            <div style="background:#f8faff;border:1px solid #edf1fb;border-left:4px solid #059669;
                        border-radius:10px;padding:.85rem 1.1rem">
                <div style="font-weight:600;font-size:.9rem;color:#08112a">🚀 Next Big Hit Predictor</div>
                <div style="font-size:.8rem;color:#7a8aaa;margin-top:.15rem">Random Forest AI · Gauge score · Feature importance · ROI forecast</div>
            </div>
            <div style="background:#f8faff;border:1px solid #edf1fb;border-left:4px solid #d97706;
                        border-radius:10px;padding:.85rem 1.1rem">
                <div style="font-weight:600;font-size:.9rem;color:#08112a">📦 Inventory Stock Forecast</div>
                <div style="font-size:.8rem;color:#7a8aaa;margin-top:.15rem">SMA-based days-to-empty · Critical alerts · Velocity metrics</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

