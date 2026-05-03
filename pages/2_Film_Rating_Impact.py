"""Page 2 — Film Rating Impact Analysis with live rental form (Enhanced)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Film Rating Impact", page_icon="⭐", layout="wide")

from styles import inject_css, render_sidebar, page_header, alert_box, section_label
from db import query_df, execute, refresh_summaries

inject_css()

# ── Custom CSS Enhancements ───────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Insight card ── */
.insight-card {
    background: linear-gradient(135deg, #f0f7ff 0%, #e8f0fe 100%);
    border-left: 4px solid #2563eb;
    border-radius: 0 12px 12px 0;
    padding: 1rem 1.25rem;
    margin: .75rem 0;
}
.insight-card .ic-label {
    font-size: .6rem;
    font-weight: 800;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: #2563eb;
    margin-bottom: .3rem;
}
.insight-card .ic-text {
    font-size: .88rem;
    color: #1e2a45;
    line-height: 1.6;
}

/* ── Recommendation card ── */
.rec-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin: .5rem 0;
    display: flex;
    gap: .85rem;
    align-items: flex-start;
    transition: box-shadow .2s;
}
.rec-card:hover { box-shadow: 0 4px 18px rgba(37,99,235,.1); }
.rec-icon {
    background: #2563eb;
    color: white;
    border-radius: 8px;
    width: 34px; height: 34px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem;
    flex-shrink: 0;
}
.rec-title   { font-size: .9rem; font-weight: 700; color: #1e2a45; margin-bottom: .15rem; }
.rec-body    { font-size: .82rem; color: #64748b; line-height: 1.5; }

/* ── Highlight badge row ── */
.badge-row { display: flex; gap: .75rem; flex-wrap: wrap; margin: .5rem 0 1.25rem; }
.badge {
    border-radius: 10px;
    padding: .55rem 1rem;
    font-size: .8rem;
    font-weight: 600;
    display: flex; align-items: center; gap: .4rem;
    white-space: nowrap;
}
.badge-demand  { background: #dbeafe; color: #1d4ed8; border: 1px solid #93c5fd; }
.badge-revenue { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
.badge-low     { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }

/* ── Section header ── */
.section-header {
    font-size: .65rem;
    font-weight: 800;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: #7c3aed;
    margin: 1.25rem 0 .5rem;
}

/* ── Segment pill (quadrant classification) ── */
.seg-pill {
    display: inline-flex; align-items: center; gap: .35rem;
    padding: .28rem .75rem;
    border-radius: 999px;
    font-size: .75rem;
    font-weight: 700;
    white-space: nowrap;
}
.seg-core     { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
.seg-volume   { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
.seg-niche    { background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }
.seg-anomaly  { background: #ffedd5; color: #9a3412; border: 1px solid #fdba74; }
.seg-under    { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
.seg-unknown  { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; }

/* ── Quadrant legend ── */
.quadrant-legend {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: .5rem;
    margin: .75rem 0;
}
.ql-item {
    border-radius: 10px;
    padding: .6rem .85rem;
    font-size: .78rem;
    border: 1px solid;
}
.ql-tr { background:#d1fae5; border-color:#6ee7b7; color:#065f46; }
.ql-tl { background:#dbeafe; border-color:#93c5fd; color:#1e40af; }
.ql-br { background:#fef3c7; border-color:#fcd34d; color:#92400e; }
.ql-bl { background:#fee2e2; border-color:#fca5a5; color:#991b1b; }

/* ── Confidence badge ── */
.conf-ok   { color:#059669; font-size:.75rem; font-weight:600; }
.conf-warn { color:#d97706; font-size:.75rem; font-weight:600; }
.impact-box {
    background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
    border: 1px solid #6ee7b7;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-top: .75rem;
}
.impact-box .imp-title { font-weight: 700; color: #065f46; font-size: .9rem; }
.impact-box .imp-body  { font-size: .83rem; color: #047857; margin-top: .25rem; }
</style>
""", unsafe_allow_html=True)

# ── Rating colour map (consistent across all charts) ─────────────────────────
RATING_COLORS = {
    "G":     "#2563eb",
    "PG":    "#059669",
    "PG-13": "#d97706",
    "R":     "#dc2626",
    "NC-17": "#7c3aed",
}
BRAND = ["#08112a", "#1a3a6b", "#2563eb", "#60a5fa", "#93c5fd"]

BASE = dict(
    plot_bgcolor="white", paper_bgcolor="white",
    margin=dict(l=10, r=10, t=30, b=10), height=360,
    font=dict(family="DM Sans, sans-serif", color="#1e2a45"),
)

with st.sidebar:
    render_sidebar()

page_header("⭐", "Film Rating Impact",
            "How rating classifications (G, PG, PG-13, R, NC-17) affect customer demand & revenue")

# ── Data Loaders (UNCHANGED) ──────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_rating():
    return query_df("SELECT * FROM summary_rating ORDER BY total_rental DESC")

@st.cache_data(ttl=30)
def load_films_by_rating():
    return query_df("""
        SELECT DISTINCT f.film_id, f.title, f.rating, c.name AS genre, f.rental_rate
        FROM film f
        JOIN film_category fc ON f.film_id = fc.film_id
        JOIN category c ON fc.category_id = c.category_id
        JOIN inventory i ON f.film_id = i.film_id
        ORDER BY f.rating, f.title LIMIT 600
    """)

@st.cache_data(ttl=30)
def load_customers():
    return query_df("SELECT customer_id, first_name || ' ' || last_name AS name FROM customer ORDER BY name LIMIT 200")

@st.cache_data(ttl=30)
def load_staff():
    return query_df("SELECT staff_id, first_name || ' ' || last_name AS name FROM staff LIMIT 1")

@st.cache_data(ttl=30)
def load_top_films_per_rating():
    """Top 3 most-rented films per rating using existing schema."""
    return query_df("""
        SELECT f.rating, f.title, COUNT(r.rental_id) AS rental_count, f.rental_rate
        FROM film f
        JOIN inventory i  ON f.film_id = i.film_id
        JOIN rental r     ON i.inventory_id = r.inventory_id
        GROUP BY f.rating, f.film_id, f.title, f.rental_rate
        ORDER BY f.rating, rental_count DESC
    """)

# ── Load Data ─────────────────────────────────────────────────────────────────
data = load_rating()
if not data:
    alert_box("error", "No rating data", "Run OLAP setup SQL first.")
    st.stop()

df = pd.DataFrame(data)
df["total_revenue"]       = df["total_revenue"].astype(float)
df["total_rental"]        = df["total_rental"].astype(int)
df["avg_rental_per_film"] = df["avg_rental_per_film"].astype(float)
df["rental_pct"]          = df["rental_pct"].astype(float)

films_raw     = load_films_by_rating()
top_films_raw = load_top_films_per_rating()

# ── Pre-compute highlights ────────────────────────────────────────────────────
top_demand_row  = df.loc[df["total_rental"].idxmax()]
top_revenue_row = df.loc[df["total_revenue"].idxmax()]
low_demand_row  = df.loc[df["total_rental"].idxmin()]

top_demand_rating  = top_demand_row["rating"]
top_revenue_rating = top_revenue_row["rating"]
low_demand_rating  = low_demand_row["rating"]

# ══════════════════════════════════════════════════════════════════════════════
# ── MULTI-METRIC CLASSIFICATION ENGINE ────────────────────────────────────────
# Uses median splits across 4 dimensions so no single metric can mislead.
# ══════════════════════════════════════════════════════════════════════════════
def classify_ratings(source_df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify each rating into a business segment using median-split logic
    across total_rental, total_revenue, avg_rental_per_film, rental_pct.
    Returns source_df with added columns: segment, segment_label,
    segment_color, quadrant, confidence_note.
    """
    if source_df.empty or len(source_df) < 2:
        result = source_df.copy()
        result["segment"]        = "Insufficient Data"
        result["segment_label"]  = "⚪ Insufficient Data"
        result["segment_color"]  = "#94a3b8"
        result["quadrant"]       = "unknown"
        result["confidence_note"] = "⚠️ Need ≥2 ratings to classify."
        return result

    med_rental  = source_df["total_rental"].median()
    med_revenue = source_df["total_revenue"].median()
    med_avg     = source_df["avg_rental_per_film"].median()

    # Minimum sample size warning threshold (20% of median)
    low_sample_threshold = med_rental * 0.20

    def _classify(row):
        high_demand  = row["total_rental"]  >= med_rental
        high_revenue = row["total_revenue"] >= med_revenue
        high_avg     = row["avg_rental_per_film"] >= med_avg
        low_volume   = row["total_rental"] < low_sample_threshold

        # Confidence note
        if low_volume:
            conf = "⚠️ Low sample volume — interpret with caution."
        elif high_avg and not high_demand:
            conf = "⚠️ High avg driven by small catalogue, not broad demand."
        else:
            conf = "✅ Multi-metric signals are consistent."

        # 4-quadrant classification (demand vs revenue)
        if high_demand and high_revenue:
            segment = "Core Business Driver"
            label   = "🟢 Core Business Driver"
            color   = "#059669"
            quadrant = "top-right"
        elif high_demand and not high_revenue:
            segment = "Volume Driver — Low Monetisation"
            label   = "🟡 Volume Driver — Low Monetisation"
            color   = "#d97706"
            quadrant = "bottom-right"
        elif not high_demand and high_revenue:
            # Split: if avg is also high it's truly niche-efficient;
            # if avg is low, it's a monetisation-only anomaly
            if high_avg:
                segment = "Niche but Efficient"
                label   = "🔵 Niche but Efficient"
                color   = "#2563eb"
                quadrant = "top-left"
            else:
                segment = "Pricing Anomaly"
                label   = "🟠 Pricing Anomaly"
                color   = "#ea580c"
                quadrant = "top-left"
        else:
            segment = "Underperforming Segment"
            label   = "🔴 Underperforming Segment"
            color   = "#dc2626"
            quadrant = "bottom-left"

        return pd.Series({
            "segment":        segment,
            "segment_label":  label,
            "segment_color":  color,
            "quadrant":       quadrant,
            "confidence_note": conf,
        })

    classifications = source_df.apply(_classify, axis=1)
    return pd.concat([source_df.reset_index(drop=True), classifications.reset_index(drop=True)], axis=1)


# Quadrant action map — what to do for each quadrant
QUADRANT_ACTIONS = {
    "top-right":    ("Scale aggressively", "Increase inventory, feature prominently, and maintain pricing. "
                     "This is your highest-ROI segment."),
    "bottom-right": ("Improve monetisation", "Demand exists but revenue is lagging — review pricing, "
                     "introduce premium tiers, or bundle with higher-priced titles."),
    "top-left":     ("Nurture carefully", "Revenue is solid despite modest volume. "
                     "Avoid over-investing in catalogue expansion until demand signals strengthen."),
    "bottom-left":  ("Review or divest", "Both demand and revenue are below median. "
                     "Run a targeted promotion first; if no response, reduce inventory allocation."),
    "unknown":      ("Insufficient data", "Collect more transactions before making strategic decisions."),
}

# Segment description map (for tooltips / insight cards)
SEGMENT_EXPLANATIONS = {
    "Core Business Driver": (
        "High demand AND high revenue — this is the backbone of your rental business. "
        "Every operational decision should protect this segment's performance."
    ),
    "Volume Driver — Low Monetisation": (
        "Many customers rent these films, but revenue per transaction is below average. "
        "There is a pricing opportunity here — customers are already engaged."
    ),
    "Niche but Efficient": (
        "Smaller audience, but each title in this category punches above its weight. "
        "Caution: high avg/film often reflects a small catalogue, not broad market appeal. "
        "Validate before expanding inventory."
    ),
    "Pricing Anomaly": (
        "Revenue is high relative to demand — this could indicate inflated rental rates "
        "or a temporarily small catalogue. Investigate before drawing conclusions."
    ),
    "Underperforming Segment": (
        "Both demand and revenue fall below the median. This segment needs intervention "
        "(targeted marketing or price reduction) or a strategic review."
    ),
    "Insufficient Data": (
        "Not enough ratings selected to compute a meaningful classification."
    ),
}

# Pre-classify on the full (unfiltered) df for global badges
df_classified = classify_ratings(df.copy())

# ── GLOBAL FILTERS ────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">🔍 Global Filters</div>', unsafe_allow_html=True)

filter_col1, filter_col2, _ = st.columns([2, 2, 4])

with filter_col1:
    all_ratings = sorted(df["rating"].unique().tolist())
    selected_ratings = st.multiselect(
        "Filter by Rating",
        options=all_ratings,
        default=all_ratings,
        help="Select one or more ratings to filter charts"
    )

with filter_col2:
    genre_options = []
    if films_raw:
        films_df_full = pd.DataFrame(films_raw)
        genre_options = sorted(films_df_full["genre"].unique().tolist())

    selected_genres = st.multiselect(
        "Filter by Genre (for Film Insights)",
        options=genre_options,
        default=[],
        help="Optionally filter film-level data by genre"
    )

# Apply rating filter to chart dataframe
filtered_df = df[df["rating"].isin(selected_ratings)] if selected_ratings else df.copy()

if len(filtered_df) == 0:
    alert_box("warning", "No data for selected filters", "Please select at least one rating.")
    st.stop()

# Classify filtered set (medians re-computed on the filtered slice)
filtered_classified = classify_ratings(filtered_df.copy())

# ── KPIs ──────────────────────────────────────────────────────────────────────
st.markdown("---")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ratings Tracked",     len(filtered_df))
c2.metric("Total Rentals",       f"{filtered_df['total_rental'].sum():,}")
c3.metric("Total Revenue",       f"${filtered_df['total_revenue'].sum():,.2f}")
c4.metric("Most Popular Rating", filtered_df.sort_values("total_rental", ascending=False).iloc[0]["rating"])

# ── HIGHLIGHT METRICS BADGES ──────────────────────────────────────────────────
st.markdown(f"""
<div class="badge-row">
    <div class="badge badge-demand">
        🏆 Highest Demand: <strong>{top_demand_rating}</strong>
        &nbsp;·&nbsp; {top_demand_row['total_rental']:,} rentals
        ({top_demand_row['rental_pct']:.1f}%)
    </div>
    <div class="badge badge-revenue">
        💰 Highest Revenue: <strong>{top_revenue_rating}</strong>
        &nbsp;·&nbsp; ${top_revenue_row['total_revenue']:,.0f}
    </div>
    <div class="badge badge-low">
        ⚠️ Lowest Demand: <strong>{low_demand_rating}</strong>
        &nbsp;·&nbsp; {low_demand_row['total_rental']:,} rentals
        ({low_demand_row['rental_pct']:.1f}%)
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Demand & Revenue",
    "🏆 Rankings & Film Insights",
    "📌 Recommendations",
    "➕ Add Rental Transaction",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CHARTS + INSIGHTS
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:

    # ── Section A: Demand Analysis ────────────────────────────────────────────
    st.markdown('<div class="section-header">📦 Demand Analysis</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="large")

    with col1:
        section_label("Total Rentals per Rating")
        ds = filtered_df.sort_values("total_rental", ascending=False)
        bar_colors = [RATING_COLORS.get(r, "#2563eb") for r in ds["rating"]]
        fig = go.Figure(go.Bar(
            x=ds["rating"], y=ds["total_rental"],
            marker_color=bar_colors,
            text=ds["rental_pct"].apply(lambda x: f"{x:.1f}%"),
            textposition="outside",
        ))
        fig.update_layout(xaxis_title="Rating", yaxis_title="Total Rentals", **BASE)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        section_label("Rental Share Donut")
        pie_colors = [RATING_COLORS.get(r, "#2563eb") for r in filtered_df["rating"]]
        fig4 = px.pie(filtered_df, values="rental_pct", names="rating",
                      color_discrete_sequence=pie_colors, hole=0.52)
        fig4.update_traces(textposition="inside", textinfo="percent+label", textfont_size=12)
        fig4.update_layout(showlegend=False, height=360,
                           margin=dict(l=10, r=10, t=10, b=10),
                           paper_bgcolor="white",
                           font=dict(family="DM Sans, sans-serif"))
        st.plotly_chart(fig4, use_container_width=True)

    # ── Demand Insight (multi-metric, classification-aware) ──────────────────
    demand_sorted  = filtered_classified.sort_values("total_rental", ascending=False)
    demand_top     = demand_sorted.iloc[0]
    demand_second  = demand_sorted.iloc[1] if len(demand_sorted) > 1 else None
    demand_gap     = (demand_top["rental_pct"] - demand_second["rental_pct"]) if demand_second is not None else 0

    seg            = demand_top.get("segment", "")
    seg_label      = demand_top.get("segment_label", seg)
    conf_note      = demand_top.get("confidence_note", "")
    conf_class     = "conf-warn" if "⚠️" in conf_note else "conf-ok"

    # Segment-specific why/biz text — avoids avg-only conclusions
    if seg == "Core Business Driver":
        why_text = (
            f"{demand_top['rating']} scores above median on <em>both</em> rentals and revenue — "
            "a consistent high performer across all dimensions."
        )
        biz_text = (
            f"Protect this segment: ensure {demand_top['rating']} titles are always in stock. "
            "Stockouts here directly impact top-line revenue."
        )
    elif seg == "Volume Driver — Low Monetisation":
        why_text = (
            f"{demand_top['rating']} drives high rental counts but revenue per transaction lags. "
            "This indicates below-median rental rates for this category."
        )
        biz_text = (
            f"A modest price increase or bundling {demand_top['rating']} titles with "
            "higher-margin categories could meaningfully improve revenue without losing customers."
        )
    elif seg in ("Niche but Efficient", "Pricing Anomaly"):
        why_text = (
            f"⚠️ Caution: {demand_top['rating']} has a high avg-rentals/film figure, "
            "but this likely reflects a <em>small catalogue</em>, not broad market demand. "
            f"Absolute rentals ({demand_top['total_rental']:,}) sit below the dataset median."
        )
        biz_text = (
            "Do not over-invest based on per-film averages alone. "
            f"Validate with absolute volume before expanding {demand_top['rating']} inventory."
        )
    else:
        why_text = (
            f"{demand_top['rating']} leads in raw count here, but both demand and revenue "
            "fall below overall medians when viewed across all ratings."
        )
        biz_text = (
            "Investigate whether this category has growth potential "
            "or whether resources are better reallocated to higher-performing segments."
        )

    gap_note = (
        f", ahead of <strong>{demand_second['rating']}</strong> by "
        f"<strong>{demand_gap:.1f} pp</strong>"
        if demand_second is not None else ""
    )

    # Segment pills for all filtered ratings
    seg_css_map = {
        "Core Business Driver":              "seg-core",
        "Volume Driver — Low Monetisation":  "seg-volume",
        "Niche but Efficient":               "seg-niche",
        "Pricing Anomaly":                   "seg-anomaly",
        "Underperforming Segment":           "seg-under",
        "Insufficient Data":                 "seg-unknown",
    }
    pills_html = "<div style='display:flex;flex-wrap:wrap;gap:.4rem;margin:.5rem 0 .75rem'>"
    for _, pr in demand_sorted.iterrows():
        css   = seg_css_map.get(pr.get("segment", ""), "seg-unknown")
        color = RATING_COLORS.get(pr["rating"], "#1a3a6b")
        pills_html += (
            f'<span class="seg-pill {css}">'
            f'<span style="background:{color};color:white;border-radius:4px;'
            f'padding:.05rem .35rem;font-size:.7rem">{pr["rating"]}</span>'
            f' {pr.get("segment_label","—")}'
            f'</span>'
        )
    pills_html += "</div>"

    st.markdown(f"""
<div class="insight-card">
<div class="ic-label">💡 Demand Insight — Multi-Metric Analysis</div>
<div class="ic-text">
<strong>What's happening:</strong>
<strong>{demand_top['rating']}</strong> leads with
<strong>{demand_top['total_rental']:,} rentals ({demand_top['rental_pct']:.1f}%)</strong>{gap_note}.
Segment: <strong>{seg_label}</strong>.<br><br>
<strong>Why (with trade-off):</strong> {why_text}<br><br>
<strong>Business implication:</strong> {biz_text}<br>
<span class="{conf_class}">{conf_note}</span>
</div>
</div>
""", unsafe_allow_html=True)
    st.markdown("<div style='font-size:.73rem;color:#64748b;font-weight:600;margin-top:.3rem'>Segment classification — all ratings in current filter:</div>", unsafe_allow_html=True)
    st.markdown(pills_html, unsafe_allow_html=True)

    st.markdown("---")

    # ── Section B: Revenue Analysis ───────────────────────────────────────────
    st.markdown('<div class="section-header">💰 Revenue Analysis</div>', unsafe_allow_html=True)
    col3, col4 = st.columns(2, gap="large")

    with col3:
        section_label("Total Revenue per Rating")
        dr = filtered_df.sort_values("total_revenue", ascending=False)
        rev_colors = [RATING_COLORS.get(r, "#2563eb") for r in dr["rating"]]
        fig2 = go.Figure(go.Bar(
            x=dr["rating"], y=dr["total_revenue"],
            marker_color=rev_colors,
            text=[f"${v:,.0f}" for v in dr["total_revenue"]],
            textposition="outside",
        ))
        fig2.update_layout(yaxis_title="Revenue ($)", xaxis_title="Rating", **BASE)
        st.plotly_chart(fig2, use_container_width=True)

    with col4:
        section_label("Avg. Rentals per Film / Rating")
        da = filtered_df.sort_values("avg_rental_per_film", ascending=False)
        eff_colors = [RATING_COLORS.get(r, "#2563eb") for r in da["rating"]]
        fig3 = go.Figure(go.Bar(
            x=da["rating"], y=da["avg_rental_per_film"],
            marker_color=eff_colors,
            text=da["avg_rental_per_film"].apply(lambda x: f"{x:.1f}"),
            textposition="outside",
        ))
        fig3.update_layout(
            yaxis_title="Avg Rentals / Film", xaxis_title="Rating",
            **BASE
        )
        st.plotly_chart(fig3, use_container_width=True)

    # ── Revenue Insight (always renders, multi-metric aware) ─────────────────
    # All variables computed unconditionally — no nesting inside else/if
    _rev_sorted    = filtered_classified.sort_values("total_revenue", ascending=False)
    _eff_sorted    = filtered_classified.sort_values("avg_rental_per_film", ascending=False)
    _dem_sorted    = filtered_classified.sort_values("total_rental", ascending=False)

    rev_top        = _rev_sorted.iloc[0]
    eff_top        = _eff_sorted.iloc[0]
    demand_leader  = _dem_sorted.iloc[0]["rating"]

    total_rev      = float(filtered_classified["total_revenue"].sum())
    rev_share      = (rev_top["total_revenue"] / total_rev * 100) if total_rev > 0 else 0.0

    revenue_mismatch = str(rev_top["rating"]) != str(demand_leader)
    eff_same_as_rev  = str(eff_top["rating"]) == str(rev_top["rating"])
    rev_seg          = rev_top.get("segment", "")
    rev_conf         = rev_top.get("confidence_note", "")
    rev_conf_class   = "conf-warn" if "⚠️" in rev_conf else "conf-ok"

    # Trade-off explanation — revenue leader vs demand leader
    if revenue_mismatch:
        mismatch_text = (
            f"<strong>{rev_top['rating']}</strong> leads in revenue "
            f"(<strong>${rev_top['total_revenue']:,.0f}</strong>) but is <em>not</em> the top renter — "
            f"<strong>{demand_leader}</strong> has more transactions. "
            "This revenue premium is likely driven by higher rental rates, not volume."
        )
        rev_action = (
            f"Investigate whether {rev_top['rating']} pricing can be maintained or raised "
            f"without suppressing demand, while also exploring pricing uplifts for {demand_leader}."
        )
    else:
        mismatch_text = (
            f"<strong>{rev_top['rating']}</strong> leads in <em>both</em> revenue "
            f"(<strong>${rev_top['total_revenue']:,.0f}</strong>) and rental volume — "
            "a strong signal of real market dominance, not a pricing artefact."
        )
        rev_action = (
            f"Double down: protect {rev_top['rating']} availability and consider "
            "modest price testing to see if revenue can be grown without volume loss."
        )

    # Avg/film caveat
    if eff_same_as_rev:
        eff_note = (
            f"The revenue leader <strong>{rev_top['rating']}</strong> also has the highest avg-rentals/film "
            f"({eff_top['avg_rental_per_film']:.1f}), confirming broad efficiency."
        )
    else:
        _eff_dem_row    = filtered_classified[filtered_classified["rating"] == eff_top["rating"]]
        _eff_above_med  = (not _eff_dem_row.empty and
                           _eff_dem_row.iloc[0]["total_rental"] >= filtered_classified["total_rental"].median())
        if _eff_above_med:
            eff_note = (
                f"<strong>{eff_top['rating']}</strong> has the highest avg-rentals/film "
                f"({eff_top['avg_rental_per_film']:.1f}) and also strong absolute demand — "
                "a genuinely efficient segment worth expanding."
            )
        else:
            eff_note = (
                f"⚠️ <strong>{eff_top['rating']}</strong> has the highest avg-rentals/film "
                f"({eff_top['avg_rental_per_film']:.1f}), but its absolute rental count is below median. "
                "This may reflect a small catalogue rather than genuine market efficiency."
            )

    st.markdown(f"""
<div class="insight-card">
<div class="ic-label">💡 Revenue Insight — Multi-Metric Analysis</div>
<div class="ic-text">
<strong>Revenue leader ({rev_top['rating']} — {rev_share:.1f}% of total):</strong><br>
{mismatch_text}<br><br>
<strong>Efficiency signal:</strong><br>
{eff_note}<br><br>
<strong>Business implication:</strong><br>
{rev_action}<br>
<span class="{rev_conf_class}">{rev_conf}</span>
</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Section C: Revenue vs Demand Scatter ─────────────────────────────────
    st.markdown('<div class="section-header">🎯 Efficiency Matrix</div>', unsafe_allow_html=True)
    section_label("Revenue vs Rentals Bubble Chart (size = Avg Rentals/Film)")

    scatter_colors = [RATING_COLORS.get(r, "#2563eb") for r in filtered_df["rating"]]
    fig_scatter = go.Figure()
    for _, row in filtered_df.iterrows():
        fig_scatter.add_trace(go.Scatter(
            x=[row["total_rental"]],
            y=[row["total_revenue"]],
            mode="markers+text",
            marker=dict(
                size=row["avg_rental_per_film"] * 3.5,
                color=RATING_COLORS.get(row["rating"], "#2563eb"),
                opacity=0.85,
                line=dict(width=2, color="white"),
            ),
            text=[row["rating"]],
            textposition="middle center",
            textfont=dict(color="white", size=11, family="DM Sans, sans-serif"),
            name=row["rating"],
            hovertemplate=(
                f"<b>{row['rating']}</b><br>"
                f"Rentals: {row['total_rental']:,}<br>"
                f"Revenue: ${row['total_revenue']:,.2f}<br>"
                f"Avg/Film: {row['avg_rental_per_film']:.1f}<extra></extra>"
            ),
        ))

    fig_scatter.update_layout(
        showlegend=False,
        xaxis_title="Total Rentals",
        yaxis_title="Total Revenue ($)",
        height=380,
        **{k: v for k, v in BASE.items() if k != "height"},
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    # ── Per-rating quadrant interpretation (not generic text) ─────────────────
    quad_css = {
        "top-right":    ("ql-tr", "↗ Top-Right"),
        "top-left":     ("ql-tl", "↖ Top-Left"),
        "bottom-right": ("ql-br", "↘ Bottom-Right"),
        "bottom-left":  ("ql-bl", "↙ Bottom-Left"),
        "unknown":      ("seg-unknown", "—"),
    }

    # Build quadrant cards — use a list then join to avoid f-string re-interpolation
    quadrant_cards = []
    for _, qr in filtered_classified.sort_values("total_rental", ascending=False).iterrows():
        quad              = qr.get("quadrant", "unknown")
        _css, ql          = quad_css.get(quad, ("seg-unknown", "—"))
        action_title, action_body = QUADRANT_ACTIONS.get(quad, ("—", "—"))
        seg_l             = qr.get("segment_label", "—")
        color             = RATING_COLORS.get(str(qr["rating"]), "#1a3a6b")
        conf              = qr.get("confidence_note", "")
        conf_c            = "conf-warn" if "⚠️" in conf else "conf-ok"
        rating_str        = str(qr["rating"])
        card = (
            '<div style="border:1px solid #e2e8f0;border-radius:10px;padding:.75rem 1rem;'
            'margin:.4rem 0;border-left:4px solid ' + color + '">'
            '<div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.4rem">'
            '<div style="background:' + color + ';color:white;border-radius:6px;'
            'padding:.15rem .55rem;font-weight:800;font-size:.8rem">' + rating_str + '</div>'
            '<div style="font-size:.8rem;font-weight:700;color:#1e2a45">' + seg_l + '</div>'
            '<div style="margin-left:auto;font-size:.72rem;font-weight:700;color:#64748b">' + ql + '</div>'
            '</div>'
            '<div style="font-size:.8rem;color:#374151">'
            '<strong>' + action_title + ':</strong> ' + action_body +
            '</div>'
            '<div style="font-size:.72rem;margin-top:.3rem;color:' +
            ('#d97706' if '⚠️' in conf else '#059669') + '">' + conf + '</div>'
            '</div>'
        )
        quadrant_cards.append(card)

    quadrant_rows_html = "".join(quadrant_cards)

    st.markdown(
        '<div class="insight-card">'
        '<div class="ic-label">💡 Quadrant Analysis — Per-Rating Interpretation</div>'
        '<div class="ic-text" style="padding:0">'
        '<div style="margin-bottom:.6rem;font-size:.82rem;color:#475569">'
        'Bubble size = avg rentals/film. Position = demand (x) vs revenue (y). '
        'Each rating is classified by its actual quadrant position.'
        '</div>'
        + quadrant_rows_html +
        '</div></div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — RANKINGS + FILM INSIGHTS
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:

    # ── Rating Performance Rank (UNCHANGED) ──────────────────────────────────
    st.markdown('<div class="section-header">🏅 Rating Performance Rank</div>', unsafe_allow_html=True)
    rank_df = filtered_df.copy()
    rank_df["Rank"] = rank_df["total_revenue"].rank(ascending=False).astype(int)
    rank_df = rank_df.sort_values("Rank")
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    rank_df["Rank"]        = rank_df["Rank"].apply(lambda x: medals.get(x, str(x)))
    rank_df["Revenue ($)"] = rank_df["total_revenue"].apply(lambda x: f"${x:,.2f}")
    rank_df["Avg/Film"]    = rank_df["avg_rental_per_film"].apply(lambda x: f"{x:.1f}")
    rank_df["Rental %"]    = rank_df["rental_pct"].apply(lambda x: f"{x:.1f}%")
    disp = rank_df[["Rank", "rating", "total_rental", "Revenue ($)", "Avg/Film", "Rental %"]].copy()
    disp.columns = ["Rank", "Rating", "Total Rentals", "Revenue ($)", "Avg/Film", "Rental %"]
    st.dataframe(disp.reset_index(drop=True), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Top Films per Rating ──────────────────────────────────────────────────
    st.markdown('<div class="section-header">🎬 Top Films Contributing to Each Rating</div>', unsafe_allow_html=True)

    if top_films_raw:
        top_films_df = pd.DataFrame(top_films_raw)

        # Apply genre filter if selected
        if selected_genres and films_raw:
            films_genre_df = pd.DataFrame(films_raw)[["title", "genre"]]
            top_films_df   = top_films_df.merge(films_genre_df, on="title", how="left")
            top_films_df   = top_films_df[top_films_df["genre"].isin(selected_genres)]

        # Filter by selected ratings
        top_films_df = top_films_df[top_films_df["rating"].isin(selected_ratings)]

        # Top 3 per rating
        top3 = (
            top_films_df
            .sort_values("rental_count", ascending=False)
            .groupby("rating")
            .head(3)
            .reset_index(drop=True)
        )

        if not top3.empty:
            for rating_val in selected_ratings:
                subset = top3[top3["rating"] == rating_val]
                if subset.empty:
                    continue
                color = RATING_COLORS.get(rating_val, "#2563eb")
                st.markdown(f"""
                <div style="margin: .75rem 0 .4rem; display:flex; align-items:center; gap:.6rem">
                    <div style="background:{color};color:white;border-radius:6px;padding:.2rem .65rem;
                                font-weight:800;font-size:.78rem">{rating_val}</div>
                    <div style="font-size:.8rem;color:#64748b;font-weight:600">Top performing films</div>
                </div>
                """, unsafe_allow_html=True)

                cols = st.columns(min(3, len(subset)))
                for idx, (_, row) in enumerate(subset.iterrows()):
                    with cols[idx]:
                        rank_emoji = ["🥇", "🥈", "🥉"][idx]
                        st.markdown(f"""
                        <div style="background:white;border:1px solid #e2e8f0;border-radius:10px;
                                    padding:.75rem 1rem;border-top:3px solid {color}">
                            <div style="font-size:.7rem;color:#94a3b8;margin-bottom:.2rem">{rank_emoji} Rank #{idx+1}</div>
                            <div style="font-size:.85rem;font-weight:700;color:#1e2a45;line-height:1.3;
                                        margin-bottom:.35rem">{row['title']}</div>
                            <div style="display:flex;gap:.4rem;flex-wrap:wrap">
                                <span style="background:#f1f5f9;color:#475569;border-radius:4px;
                                             padding:.1rem .4rem;font-size:.72rem;font-weight:600">
                                    {row['rental_count']:,} rentals
                                </span>
                                <span style="background:#f0fdf4;color:#166534;border-radius:4px;
                                             padding:.1rem .4rem;font-size:.72rem;font-weight:600">
                                    ${row['rental_rate']:.2f}/rental
                                </span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("No film data available for the current filter selection.")
    else:
        st.info("Film-level data not available.")

    st.markdown("---")

    # ── Rating Descriptions (UNCHANGED) ──────────────────────────────────────
    st.markdown('<div class="section-header">📋 Rating Descriptions</div>', unsafe_allow_html=True)
    for r, d in [
        ("G",     "General Audiences — All ages admitted"),
        ("PG",    "Parental Guidance Suggested"),
        ("PG-13", "Parents Strongly Cautioned — Some material inappropriate for children under 13"),
        ("R",     "Restricted — Under 17 requires adult"),
        ("NC-17", "Adults Only — No one 17 and under admitted"),
    ]:
        color = RATING_COLORS.get(r, "#1a3a6b")
        st.markdown(f"""
        <div style="display:flex;gap:.75rem;align-items:flex-start;padding:.65rem 0;
                    border-bottom:1px solid #f1f5f9">
            <div style="background:{color};color:white;border-radius:6px;padding:.2rem .65rem;
                        font-weight:700;font-size:.8rem;min-width:52px;text-align:center">{r}</div>
            <div style="font-size:.875rem;color:#374151">{d}</div>
        </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — BUSINESS RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-header">📌 Business Recommendations</div>', unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:.88rem;color:#64748b;margin-bottom:1rem'>"
        "Data-driven action items derived from the current rating performance metrics.</p>",
        unsafe_allow_html=True,
    )

    # ── Dynamically build recommendations using classification engine ─────────
    # Use full-dataset classifications (not filtered) for recommendations
    _rec_classified = df_classified.copy()
    low_cl   = _rec_classified.sort_values("total_rental").iloc[0]
    high_cl  = _rec_classified.sort_values("total_rental", ascending=False).iloc[0]
    rev_cl   = _rec_classified.sort_values("total_revenue", ascending=False).iloc[0]

    # Efficiency rec: only recommend if avg is backed by above-median demand
    _eff_candidates = _rec_classified[
        _rec_classified["total_rental"] >= _rec_classified["total_rental"].median()
    ].sort_values("avg_rental_per_film", ascending=False)
    eff_cl = _eff_candidates.iloc[0] if not _eff_candidates.empty else high_cl
    eff_caveat = "" if not _eff_candidates.empty else (
        " (Note: all ratings are below median demand — treat efficiency figures cautiously.)"
    )

    # Detect whether revenue leader = demand leader (changes rec wording)
    rev_eq_dem = str(rev_cl["rating"]) == str(high_cl["rating"])

    recs = [
        {
            "icon": "📦",
            "title": f"Expand Inventory for {high_cl['rating']}-Rated Films",
            "body": (
                f"{high_cl['rating']} is classified as <strong>{high_cl.get('segment_label','—')}</strong> "
                f"with {high_cl['total_rental']:,} rentals ({high_cl['rental_pct']:.1f}% share). "
                "This is validated by both rental volume <em>and</em> market share — "
                "not just per-film averages. Increasing stock depth here reduces stockout risk "
                "and captures proven demand."
            ),
        },
        {
            "icon": "📣",
            "title": f"Promote {low_cl['rating']}-Rated Films",
            "body": (
                f"{low_cl['rating']} is classified as <strong>{low_cl.get('segment_label','—')}</strong> "
                f"with only {low_cl['total_rental']:,} rentals ({low_cl['rental_pct']:.1f}%). "
                f"Before cutting investment, test a targeted promotion or bundle — "
                "low share may reflect limited awareness, not low quality."
            ),
        },
        {
            "icon": "💡",
            "title": f"Grow {eff_cl['rating']}'s Catalogue — Demand-Validated",
            "body": (
                f"{eff_cl['rating']} has {eff_cl['avg_rental_per_film']:.1f} avg rentals/film "
                f"<em>and</em> above-median absolute demand ({eff_cl['total_rental']:,} rentals) — "
                "making its efficiency figure reliable, not a small-catalogue artefact. "
                f"Acquiring more {eff_cl['rating']} titles should yield predictable returns.{eff_caveat}"
            ),
        },
        {
            "icon": "💰",
            "title": (
                f"{'Dual-Lever Pricing' if rev_eq_dem else 'Revenue vs Demand Realignment'} — {rev_cl['rating']} Focus"
            ),
            "body": (
                (
                    f"{rev_cl['rating']} leads in both rentals and revenue — "
                    "a rare dual-leader position. Test modest price increases ($0.25–$0.50) "
                    "on top-performing titles; customer stickiness suggests low price sensitivity."
                ) if rev_eq_dem else (
                    f"{rev_cl['rating']} leads in revenue (${rev_cl['total_revenue']:,.0f}) "
                    f"but not in rental volume. This gap signals a pricing premium. "
                    f"Monitor whether the price premium is suppressing demand — "
                    "and whether a small reduction might unlock volume growth."
                )
            ),
        },
    ]

    for rec in recs:
        st.markdown(f"""
        <div class="rec-card">
            <div class="rec-icon">{rec['icon']}</div>
            <div>
                <div class="rec-title">{rec['title']}</div>
                <div class="rec-body">{rec['body']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Summary scorecard with segment classification ─────────────────────────
    st.markdown('<div class="section-header">📊 Comparative Scorecard</div>', unsafe_allow_html=True)
    score_df = df_classified.copy()
    score_df = score_df.sort_values("total_revenue", ascending=False)
    score_df["Revenue Rank"]    = range(1, len(score_df) + 1)
    score_df["Demand Rank"]     = score_df["total_rental"].rank(ascending=False).astype(int)
    score_df["Efficiency Rank"] = score_df["avg_rental_per_film"].rank(ascending=False).astype(int)
    score_df["Revenue ($)"]     = score_df["total_revenue"].apply(lambda x: f"${x:,.2f}")
    score_df["Rental %"]        = score_df["rental_pct"].apply(lambda x: f"{x:.1f}%")
    score_df["Segment"]         = score_df["segment_label"]

    disp_score = score_df[[
        "rating", "total_rental", "Revenue ($)", "Rental %",
        "Demand Rank", "Revenue Rank", "Efficiency Rank", "Segment"
    ]].copy()
    disp_score.columns = [
        "Rating", "Total Rentals", "Revenue ($)", "Rental %",
        "Demand Rank", "Revenue Rank", "Efficiency Rank", "Segment"
    ]
    st.dataframe(disp_score.reset_index(drop=True), use_container_width=True, hide_index=True)
    st.markdown(
        "<div style='font-size:.75rem;color:#94a3b8;margin-top:.35rem'>"
        "Segment uses median-split classification across demand, revenue, and efficiency — "
        "not a single metric. Confidence notes apply where volume is low.</div>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — ADD RENTAL FORM (ALL ORIGINAL LOGIC PRESERVED)
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("""
    <div style="background:white;border:1px solid #e2e8f4;border-radius:16px;
                padding:1.5rem 2rem;margin-bottom:1rem">
        <div style="font-size:.65rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
                    color:#7c3aed;margin-bottom:.75rem">SYSTEM UPDATE — New Rental (updates rating stats)</div>
        <p style="font-size:.88rem;color:#64748b;margin:0">
            Submit a rental here to see rating popularity metrics update in real time.
            Each new rental for a film increases <strong>total_rental</strong> and
            <strong>rental_pct</strong> for that film's rating classification.
        </p>
    </div>
    """, unsafe_allow_html=True)

    custs_raw = load_customers()
    staff     = load_staff()
    staff_id  = staff[0]["staff_id"] if staff else 1

    if films_raw and custs_raw:
        st.info(f"📊 {len(films_raw)} films available for rental (with inventory)")

        rating_choices   = sorted(set(r["rating"] for r in films_raw if r["rating"]))
        selected_rating  = st.selectbox("Filter films by Rating", ["All"] + rating_choices)
        filtered_films   = films_raw if selected_rating == "All" else [r for r in films_raw if r["rating"] == selected_rating]

        if filtered_films:
            film_opts     = {f"{r['title']} [{r['rating']}]": r for r in filtered_films}
            all_cust_opts = {r["name"]: r["customer_id"] for r in custs_raw}

            # ── Customer search filter (outside form, preserves DB integrity) ──
            cust_search = st.text_input(
                "🔍 Search customer by name",
                placeholder="Type to filter customer list…",
                help="Filters the dropdown below — all selected values still map to DB customer IDs.",
            )
            if cust_search.strip():
                filtered_cust_opts = {
                    name: cid for name, cid in all_cust_opts.items()
                    if cust_search.strip().lower() in name.lower()
                }
            else:
                filtered_cust_opts = all_cust_opts

            if not filtered_cust_opts:
                st.warning(f"No customers match '{cust_search}'. Showing all customers.")
                filtered_cust_opts = all_cust_opts

            # Data validation: guard against empty options
            if not film_opts:
                alert_box("warning", "No films match the current filter.", "Try selecting a different rating.")
            else:
                with st.form("add_rental_rating"):
                    c1, c2 = st.columns(2)
                    with c1:
                        film_choice = st.selectbox("Film", list(film_opts.keys()))
                        amount      = st.number_input("Amount ($)", min_value=0.0, value=2.99, step=0.01, format="%.2f")
                    with c2:
                        cust_names  = list(filtered_cust_opts.keys())
                        cust_choice = st.selectbox(
                            f"Customer ({len(cust_names)} shown)",
                            cust_names,
                            help="Full name from the customer table. Use search box above to narrow list.",
                        )
                        rental_date = st.date_input("Rental Date", value=datetime.today())

                    rental_datetime = datetime.combine(rental_date, datetime.now().time())
                    submitted = st.form_submit_button(
                        "💾 Submit Rental & Refresh Rating Stats",
                        use_container_width=True, type="primary"
                    )

                if submitted:
                    film_row = film_opts[film_choice]

                    # Snapshot before for impact message
                    pre_snap = df[df["rating"] == film_row["rating"]]
                    pre_pct  = pre_snap["rental_pct"].values[0] if not pre_snap.empty else 0
                    pre_cnt  = pre_snap["total_rental"].values[0] if not pre_snap.empty else 0

                    # Resolve customer ID from filtered display name (DB integrity preserved)
                    cust_id = filtered_cust_opts.get(cust_choice)
                    if cust_id is None:
                        alert_box("error", "Customer not found", "Please select a valid customer from the list.")
                    else:
                        inv = query_df(
                            "SELECT inventory_id FROM inventory WHERE film_id = %s LIMIT 1",
                            (film_row["film_id"],)
                        )

                        if inv:
                            existing = query_df(
                                "SELECT rental_id FROM rental WHERE customer_id = %s AND inventory_id = %s AND DATE(rental_date) = %s",
                                (cust_id, inv[0]["inventory_id"], rental_date)
                            )

                            if existing:
                                alert_box("warning", "This rental already exists!", "Customer already rented this film today.")
                            else:
                                rental_result = execute(
                                    "INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id, last_update) "
                                    "VALUES (%s, %s, %s, %s, NOW()) RETURNING rental_id",
                                    (rental_datetime, inv[0]["inventory_id"], cust_id, staff_id),
                                    fetch=True
                                )

                                if rental_result:
                                    rental_id = rental_result[0][0]

                                    payment_result = execute(
                                        "INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) "
                                        "VALUES (%s, %s, %s, %s, %s)",
                                        (cust_id, staff_id, rental_id, amount, rental_datetime)
                                    )

                                    if payment_result:
                                        genre_row = query_df(
                                            "SELECT category_id FROM film_category WHERE film_id=%s LIMIT 1",
                                            (film_row["film_id"],)
                                        )
                                        date_row = query_df(
                                            "SELECT sk_date FROM dim_date WHERE full_date=%s LIMIT 1",
                                            (rental_date,)
                                        )

                                        fact_result = execute(
                                            "INSERT INTO fact_rental (rental_id, sk_film, sk_genre, sk_date, rental_date, amount, customer_id, staff_id) "
                                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                                            (rental_id, film_row["film_id"],
                                             genre_row[0]["category_id"] if genre_row else 1,
                                             date_row[0]["sk_date"] if date_row else 1,
                                             rental_datetime, amount, cust_id, staff_id)
                                        )

                                        if fact_result:
                                            with st.spinner("Refreshing rating summaries..."):
                                                refresh_summaries()
                                            st.cache_data.clear()

                                            # ── Enhanced impact message ───────────
                                            new_data = load_rating()
                                            if new_data:
                                                new_df     = pd.DataFrame(new_data)
                                                new_df["rental_pct"]   = new_df["rental_pct"].astype(float)
                                                new_df["total_rental"] = new_df["total_rental"].astype(int)
                                                new_snap   = new_df[new_df["rating"] == film_row["rating"]]
                                                new_pct    = new_snap["rental_pct"].values[0] if not new_snap.empty else 0
                                                new_cnt    = new_snap["total_rental"].values[0] if not new_snap.empty else 0
                                                pct_delta  = new_pct - pre_pct
                                                cnt_delta  = new_cnt - pre_cnt
                                                delta_str  = f"+{pct_delta:.2f}%" if pct_delta >= 0 else f"{pct_delta:.2f}%"
                                                cnt_str    = f"+{cnt_delta}" if cnt_delta >= 0 else str(cnt_delta)
                                                rating_val = str(film_row['rating'])
                                                impact_html = (
                                                    '<div class="impact-box">'
                                                    '<div class="imp-title">✅ Rental Submitted Successfully</div>'
                                                    '<div class="imp-body">'
                                                    '<strong>' + rating_val + '</strong> rental share moved from '
                                                    '<strong>' + f"{pre_pct:.2f}%" + '</strong> → '
                                                    '<strong>' + f"{new_pct:.2f}%" + '</strong> '
                                                    '(<strong>' + delta_str + '</strong>). '
                                                    'Total rentals: ' + f"{pre_cnt:,}" + ' → '
                                                    '<strong>' + f"{new_cnt:,}" + '</strong> (' + cnt_str + ').'
                                                    '</div></div>'
                                                )
                                                st.markdown(impact_html, unsafe_allow_html=True)
                                            else:
                                                alert_box("success", "✅ Rental added!",
                                                          f"Rating stats for [{film_row['rating']}] have been updated.")

                                            st.rerun()
                                        else:
                                            alert_box("error", "Failed to insert fact_rental")
                                    else:
                                        alert_box("error", "Failed to insert payment")
                                else:
                                    alert_box("error", "Failed to insert rental")
                        else:
                            alert_box("error", f"No inventory available for '{film_row['title']}'",
                                      "Please restock this film first.")
        else:
            alert_box("warning", f"No films found with rating: {selected_rating}", "Try a different rating filter.")
    else:
        alert_box("error", "Could not load films or customers", "Check database connection.")
