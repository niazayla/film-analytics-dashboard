"""Page 3 — Next Big Hit Predictor (AI / Random Forest)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Next Big Hit", page_icon="🚀", layout="wide")

from styles import inject_css, render_sidebar, page_header, alert_box, section_label
from db import query_df
from ml.train import load as load_model, train as train_model, predict as predict_film, build_features, GENRE_MAP, RATING_MAP, FEATURE_NAMES

inject_css()
with st.sidebar:
    render_sidebar()

page_header("🚀", "Next Big Hit Predictor",
            "AI-powered popularity classifier · Random Forest · Gauge · Feature Importance")

# ─────────────────────────────────────────────────────────────────────────────
# [NEW] Custom CSS for insight cards and AI summary blocks
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.insight-card {
    background: white;
    border: 1px solid #e2e8f4;
    border-radius: 14px;
    padding: 1rem 1.2rem;
    margin-bottom: .75rem;
    display: flex;
    align-items: flex-start;
    gap: .75rem;
    box-shadow: 0 1px 6px rgba(8,17,42,0.04);
}
.insight-icon { font-size: 1.4rem; line-height: 1; margin-top: .1rem; }
.insight-text { flex: 1; }
.insight-label {
    font-size: .65rem; font-weight: 700; letter-spacing: .1em;
    text-transform: uppercase; margin-bottom: .2rem;
}
.insight-label.good  { color: #059669; }
.insight-label.bad   { color: #dc2626; }
.insight-label.ok    { color: #d97706; }
.insight-body { font-size: .85rem; color: #1e2a45; line-height: 1.45; }
.ai-summary-box {
    background: linear-gradient(135deg, #f0fdf4 0%, #eff6ff 100%);
    border: 1.5px solid #a7f3d0;
    border-radius: 18px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1.5rem;
}
.ai-summary-title {
    font-size: .65rem; font-weight: 700; letter-spacing: .12em;
    text-transform: uppercase; color: #059669; margin-bottom: .6rem;
}
.ai-summary-headline {
    font-size: 1.15rem; font-weight: 700; color: #08112a; margin-bottom: .5rem;
}
.ai-summary-body { font-size: .9rem; color: #334155; line-height: 1.6; }
.ai-summary-tips { margin-top: .75rem; }
.ai-tip {
    display: flex; align-items: center; gap: .5rem;
    font-size: .85rem; color: #1e40af; margin-bottom: .3rem;
}
.feat-top-badge {
    display: inline-block;
    background: #dbeafe; color: #1d4ed8;
    border-radius: 6px; padding: .15rem .5rem;
    font-size: .68rem; font-weight: 700;
    letter-spacing: .06em; margin-left: .4rem;
    vertical-align: middle;
}
</style>
""", unsafe_allow_html=True)

# ── Load or train model ────────────────────────────────────────────────────────
@st.cache_resource
def get_model():
    m = load_model()
    if m is None:
        st.info("🔄 No trained model found — training now from database...")
        rows = query_df("SELECT * FROM summary_film_features WHERE genre_name IS NOT NULL")
        if rows:
            train_model(rows)
            m = load_model()
    return m

@st.cache_data(ttl=60)
def load_popular_films(n=10):
    return query_df(
        "SELECT * FROM summary_film_features WHERE is_popular=TRUE AND genre_name IS NOT NULL "
        "ORDER BY total_rental DESC LIMIT %s", (n,)
    )

@st.cache_data(ttl=60)
def load_all_films():
    return query_df("SELECT * FROM summary_film_features WHERE genre_name IS NOT NULL ORDER BY title")

model       = get_model()
popular     = load_popular_films()
all_films   = load_all_films()

if not all_films:
    alert_box("error","No film features data","Run OLAP SQL setup first.")
    st.stop()

# ── Re-train button ────────────────────────────────────────────────────────────
with st.expander("🔄 Model Management"):
    col_a, col_b = st.columns([2,1])
    with col_a:
        st.markdown(f"**Model status:** {'✅ Loaded' if model else '❌ Not trained'}  ·  "
                    f"**Training set:** {len(all_films)} films  ·  "
                    f"**Popular threshold:** 60th percentile of rental count")
    with col_b:
        if st.button("🔁 Retrain Model", use_container_width=True):
            st.cache_resource.clear()
            with st.spinner("Training Random Forest..."):
                train_model(all_films)
            st.cache_resource.clear()
            alert_box("success","✅ Model retrained successfully!")
            st.rerun()

st.markdown("---")

# ── Input form ─────────────────────────────────────────────────────────────────
col_form, col_result = st.columns([1, 1.4], gap="large")

with col_form:
    st.markdown("""
    <div style="background:white;border:1px solid #e2e8f4;border-radius:18px;
                padding:1.6rem 1.8rem;box-shadow:0 2px 12px rgba(8,17,42,0.05)">
        <div style="font-size:.65rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
                    color:#059669;margin-bottom:1rem">🎬 Film Characteristics</div>
    """, unsafe_allow_html=True)

    input_mode = st.radio("Input Mode", ["Select an existing film", "Enter manually"], horizontal=True)

    film_data = {}

    if input_mode == "Select an existing film":
        film_titles = {r["title"]: r for r in all_films}
        chosen = st.selectbox("Film Title", list(film_titles.keys()))
        film_data = film_titles[chosen]
        st.markdown(f"""
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;
                    padding:.75rem 1rem;font-size:.82rem;color:#065f46;margin:.5rem 0">
            Rating: <b>{film_data.get('rating')}</b> &nbsp;·&nbsp;
            Genre: <b>{film_data.get('genre_name')}</b> &nbsp;·&nbsp;
            Length: <b>{film_data.get('length')} min</b> &nbsp;·&nbsp;
            Actors: <b>{film_data.get('num_actors')}</b>
        </div>""", unsafe_allow_html=True)
    else:
        c1, c2 = st.columns(2)
        with c1:
            film_data["genre_name"]       = st.selectbox("Genre", list(GENRE_MAP.keys()))
            film_data["rating"]            = st.selectbox("Rating", list(RATING_MAP.keys()))
            film_data["rental_rate"]       = st.number_input("Rental Rate ($)", 0.99, 9.99, 2.99, 0.01)
            film_data["replacement_cost"]  = st.number_input("Replacement Cost ($)", 9.99, 29.99, 19.99, 0.01)
        with c2:
            film_data["length"]          = st.number_input("Duration (min)", 45, 185, 100, 5)
            film_data["rental_duration"] = st.number_input("Rental Period (days)", 1, 7, 3, 1)
            film_data["num_actors"]      = st.number_input("No. of Actors", 1, 20, 5, 1)
        sf_opts = st.multiselect("Special Features", ["Behind the Scenes","Commentaries","Deleted Scenes","Trailers"])
        film_data["special_features"] = ", ".join(sf_opts)

    st.markdown("</div>", unsafe_allow_html=True)

    predict_btn = st.button("🔮 Predict Popularity", use_container_width=True, type="primary")

with col_result:
    if predict_btn and model:
        result = predict_film(model, film_data)
        score  = result["score"]
        color  = result["color"]
        label  = result["label"]

        # ── Gauge ────────────────────────────────────────────────────────────
        section_label("Popularity Score", "#059669")
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=score,
            domain={"x": [0,1], "y": [0,1]},
            title={"text": label, "font": {"size": 18, "color": color, "family": "DM Sans"}},
            delta={"reference": 50, "increasing": {"color": "#059669"}, "decreasing": {"color": "#dc2626"}},
            gauge={
                "axis": {"range": [0,100], "tickwidth": 1, "tickcolor": "#94a3b8"},
                "bar":  {"color": color, "thickness": 0.28},
                "bgcolor": "white",
                "borderwidth": 2,
                "bordercolor": "#e2e8f4",
                "steps": [
                    {"range": [0,40],   "color": "#fee2e2"},
                    {"range": [40,60],  "color": "#fef3c7"},
                    {"range": [60,100], "color": "#d1fae5"},
                ],
                "threshold": {"line":{"color":"#08112a","width":3}, "thickness":0.75, "value":score}
            }
        ))
        fig_gauge.update_layout(height=280, margin=dict(l=20,r=20,t=30,b=10),
                                paper_bgcolor="white",
                                font=dict(family="DM Sans, sans-serif"))
        st.plotly_chart(fig_gauge, use_container_width=True)

        # ─────────────────────────────────────────────────────────────────────
        # [NEW] Feature Importance — with TOP 3 badges and plain-English labels
        # ─────────────────────────────────────────────────────────────────────
        section_label("What drives this prediction")

        feat_labels = {
            "length":           "Duration",
            "rental_rate":      "Rental Price",
            "replacement_cost": "Replacement Cost",
            "rental_duration":  "Rental Period",
            "num_actors":       "No. of Actors",
            "has_behind_scenes":"Behind the Scenes",
            "has_commentaries": "Commentaries",
            "has_deleted_scenes":"Deleted Scenes",
            "has_trailers":     "Trailers",
            "genre_enc":        "Genre",
            "rating_enc":       "Rating",
        }

        # [NEW] Plain-English explanation for each feature
        feat_explanations = {
            "Duration":         "How long the film runs — longer films tend to attract more committed viewers.",
            "Rental Price":     "The cost to rent — pricing affects how many customers choose this film.",
            "Replacement Cost": "How much to replace the disc — reflects perceived film quality.",
            "Rental Period":    "Days the customer keeps the film — longer periods encourage more rentals.",
            "No. of Actors":    "Number of cast members — a larger ensemble can draw broader audiences.",
            "Behind the Scenes":"Bonus content that boosts perceived value for buyers.",
            "Commentaries":     "Director/actor audio commentary — signals quality and production effort.",
            "Deleted Scenes":   "Extra footage — popular with fans and collectors.",
            "Trailers":         "Preview content included — helps market the film.",
            "Genre":            "The film category — some genres are simply more popular overall.",
            "Rating":           "Age classification — broader-rated films (e.g. PG) reach more households.",
        }

        top_feats  = result["feature_importance"][:8]
        feat_names = [feat_labels.get(f[0], f[0]) for f in top_feats]
        feat_vals  = [f[1] for f in top_feats]

        # [NEW] Color: top-1 dark blue, top-2/3 medium blue, rest light blue
        colors_bar = []
        for i, v in enumerate(feat_vals):
            if i == 0:
                colors_bar.append("#1e40af")   # #1 feature — darkest
            elif i in (1, 2):
                colors_bar.append("#2563eb")   # #2-3 — medium
            else:
                colors_bar.append("#93c5fd")   # rest — light

        # [NEW] Tick labels appending badge text for top 3
        y_labels = []
        for i, name in enumerate(feat_names):
            if i == 0:
                y_labels.append(f"⭐ {name}  [#1]")
            elif i == 1:
                y_labels.append(f"🔹 {name}  [#2]")
            elif i == 2:
                y_labels.append(f"🔹 {name}  [#3]")
            else:
                y_labels.append(name)

        fig_bar = go.Figure(go.Bar(
            x=feat_vals, y=y_labels, orientation="h",
            marker_color=colors_bar,
            text=[f"{v:.1%}" for v in feat_vals], textposition="outside",
        ))
        fig_bar.update_layout(
            xaxis_title="Importance", yaxis_title="",
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=10,r=50,t=10,b=10), height=300,
            font=dict(family="DM Sans, sans-serif", color="#1e2a45"),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # ─────────────────────────────────────────────────────────────────────
        # [NEW] Top 3 Feature Callout Cards — plain English
        # ─────────────────────────────────────────────────────────────────────
        st.markdown("<div style='margin-top:.25rem;margin-bottom:.5rem;"
                    "font-size:.65rem;font-weight:700;letter-spacing:.1em;"
                    "text-transform:uppercase;color:#2563eb'>🔑 Top 3 Key Drivers</div>",
                    unsafe_allow_html=True)
        icons = ["⭐", "🔹", "🔸"]
        for i in range(min(3, len(feat_names))):
            expl = feat_explanations.get(feat_names[i], "")
            st.markdown(f"""
            <div class="insight-card" style="border-left:4px solid {'#1e40af' if i==0 else '#2563eb'}">
                <div class="insight-icon">{icons[i]}</div>
                <div class="insight-text">
                    <div style="font-weight:700;color:#08112a;font-size:.9rem">
                        {feat_names[i]}
                        <span class="feat-top-badge">#{i+1} most important · {feat_vals[i]:.1%}</span>
                    </div>
                    <div style="font-size:.82rem;color:#475569;margin-top:.2rem">{expl}</div>
                </div>
            </div>""", unsafe_allow_html=True)

    elif predict_btn and not model:
        alert_box("error","Model not available","Click Retrain Model above.")
    else:
        st.markdown("""
        <div style="background:white;border:2px dashed #e2e8f4;border-radius:18px;
                    height:300px;display:flex;align-items:center;justify-content:center;
                    flex-direction:column;gap:.75rem">
            <div style="font-size:3rem">🎬</div>
            <div style="font-weight:600;color:#7a8aaa;font-size:1rem">Select a film and click Predict</div>
            <div style="color:#94a3b8;font-size:.85rem">Gauge · Feature importance · Radar will appear here</div>
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# [NEW] AI Summary + Radar + Key Insights  (full-width section below)
# ─────────────────────────────────────────────────────────────────────────────
if predict_btn and model:
    st.markdown("---")

    # ── Build radar data (needed by both radar and insights) ─────────────────
    avg_pop = {}
    if popular:
        avg_pop = {
            "length":           np.mean([r.get("length",90) or 90  for r in popular]),
            "rental_rate":      np.mean([float(r.get("rental_rate",2.99) or 2.99) for r in popular]),
            "replacement_cost": np.mean([float(r.get("replacement_cost",19.99) or 19.99) for r in popular]),
            "num_actors":       np.mean([r.get("num_actors",5) or 5 for r in popular]),
            "rental_duration":  np.mean([r.get("rental_duration",3) or 3 for r in popular]),
        }

    dims       = list(avg_pop.keys()) if avg_pop else []
    dim_labels = ["Duration","Rental Price","Replacement Cost","No. Actors","Rental Period"]
    dim_max    = {"length":185,"rental_rate":9.99,"replacement_cost":29.99,"num_actors":20,"rental_duration":7}

    def norm(key, val):
        return round(float(val or 0) / dim_max[key] * 100, 1)

    pop_vals  = [norm(k, avg_pop[k]) for k in dims] if avg_pop else []
    film_vals = [norm(k, film_data.get(k, 0)) for k in dims] if dims else []

    # ─────────────────────────────────────────────────────────────────────────
    # [NEW] AI Summary Card
    # ─────────────────────────────────────────────────────────────────────────
    score = result["score"]
    label = result["label"]

    if score >= 65:
        potential_icon = "🟢"
        potential_text = "High Potential"
        summary_intro  = (f"This film has <b>strong popularity potential</b> with a score of {score:.0f}/100. "
                          "It aligns well with what audiences have historically responded to.")
    elif score >= 45:
        potential_icon = "🟡"
        potential_text = "Moderate Potential"
        summary_intro  = (f"This film has <b>moderate popularity potential</b> with a score of {score:.0f}/100. "
                          "It has some good attributes but there are clear areas to improve.")
    else:
        potential_icon = "🔴"
        potential_text = "Low Potential"
        summary_intro  = (f"This film currently shows <b>lower popularity potential</b> with a score of {score:.0f}/100. "
                          "Several key attributes differ significantly from popular titles.")

    # # [NEW] Generate tips based on radar gaps (film vs popular avg)
    # tips = []
    # if avg_pop and dims:
    #     gap_map = {k: (film_vals[i] - pop_vals[i]) for i, k in enumerate(dims)}
    #     readable = {
    #         "length":           ("duration", "longer", "shorter"),
    #         "rental_rate":      ("rental price", "higher priced", "lower priced"),
    #         "replacement_cost": ("replacement cost", "higher value", "lower value"),
    #         "num_actors":       ("number of actors", "larger cast", "smaller cast"),
    #         "rental_duration":  ("rental period", "longer rental window", "shorter rental window"),
    #     }
    #     for k, gap in sorted(gap_map.items(), key=lambda x: x[1]):
    #         label_str, pos_adj, neg_adj = readable[k]
    #         if gap < -10:
    #             tips.append(f"Consider a <b>{pos_adj} {label_str}</b> — popular films average "
    #                          f"{pop_vals[dims.index(k)]:.0f}% vs this film's {film_vals[dims.index(k)]:.0f}%.")
    #         if len(tips) >= 3:
    #             break

    # tips_html = ""
    # if tips:
    #     tips_html = "<div class='ai-summary-tips'>"
    #     for t in tips:
    #         tips_html += f"<div class='ai-tip'>💡 <span>{t}</span></div>"
    #     tips_html += "</div>"

    # st.markdown(f"""
    # <div class="ai-summary-box">
    #     <div class="ai-summary-title">🤖 AI Summary</div>
    #     <div class="ai-summary-headline">{potential_icon} {potential_text} — Score: {score:.0f} / 100</div>
    #     <div class="ai-summary-body">{summary_intro}{tips_html}</div>
    # </div>""", unsafe_allow_html=True)

    # ── Radar chart + Key Insights side by side ───────────────────────────────
    col_radar, col_insights = st.columns([1.2, 1], gap="large")

    with col_radar:
        section_label("Radar Chart — Comparison with Popular Films")
        if avg_pop:
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=pop_vals+[pop_vals[0]], theta=dim_labels+[dim_labels[0]],
                fill="toself", name="Popular Films Avg",
                line=dict(color="#2563eb",width=2), fillcolor="rgba(37,99,235,0.12)"))
            fig_radar.add_trace(go.Scatterpolar(
                r=film_vals+[film_vals[0]], theta=dim_labels+[dim_labels[0]],
                fill="toself", name="This Film",
                line=dict(color="#059669",width=2), fillcolor="rgba(5,150,105,0.12)"))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0,100])),
                showlegend=True, height=380,
                margin=dict(l=60,r=60,t=40,b=60),
                paper_bgcolor="white",
                font=dict(family="DM Sans, sans-serif"),
                legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5),
            )
            st.plotly_chart(fig_radar, use_container_width=True)

    # ─────────────────────────────────────────────────────────────────────────
    # [NEW] Key Insights Panel — compares film vs popular avg per dimension
    # ─────────────────────────────────────────────────────────────────────────
    with col_insights:
        section_label("Key Insights — This Film vs Popular Films")

        if avg_pop and dims:
            insight_meta = {
                "length": {
                    "name": "Duration",
                    "icon": "⏱️",
                    "good_msg":  lambda fv, pv: (
                        f"At {fv:.0f}% of max runtime, your film is close to what popular films average ({pv:.0f}%). "
                        "Audiences appreciate films of similar length."),
                    "bad_msg":   lambda fv, pv: (
                        f"Your film's runtime ({fv:.0f}%) is quite different from popular films ({pv:.0f}%). "
                        "Consider adjusting duration to match audience preferences."),
                    "ok_msg":    lambda fv, pv: (
                        f"Runtime ({fv:.0f}%) is slightly off from the popular average ({pv:.0f}%) but still acceptable."),
                },
                "rental_rate": {
                    "name": "Rental Price",
                    "icon": "💰",
                    "good_msg":  lambda fv, pv: (
                        f"Competitively priced at {fv:.0f}% of max — similar to popular films ({pv:.0f}%). "
                        "This helps drive rental volume."),
                    "bad_msg":   lambda fv, pv: (
                        f"Priced at {fv:.0f}% of max vs popular films' {pv:.0f}%. "
                        "A pricing adjustment could improve rental pick-up rate."),
                    "ok_msg":    lambda fv, pv: (
                        f"Rental price ({fv:.0f}%) is reasonably close to popular titles ({pv:.0f}%)."),
                },
                "replacement_cost": {
                    "name": "Replacement Cost",
                    "icon": "🏷️",
                    "good_msg":  lambda fv, pv: (
                        f"Replacement cost is aligned with popular titles — signals good perceived value."),
                    "bad_msg":   lambda fv, pv: (
                        f"Replacement cost differs from popular norms. This can signal lower or higher perceived value."),
                    "ok_msg":    lambda fv, pv: (
                        f"Replacement cost is in a reasonable range compared to popular films."),
                },
                "num_actors": {
                    "name": "Number of Actors",
                    "icon": "🎭",
                    "good_msg":  lambda fv, pv: (
                        f"Cast size ({fv:.0f}% of max) matches popular films ({pv:.0f}%). "
                        "A well-sized ensemble helps attract different audience segments."),
                    "bad_msg":   lambda fv, pv: (
                        f"Cast size ({fv:.0f}%) is notably different from popular films ({pv:.0f}%). "
                        "More actors can help broaden appeal."),
                    "ok_msg":    lambda fv, pv: (
                        f"Cast size ({fv:.0f}%) is close to the popular average ({pv:.0f}%)."),
                },
                "rental_duration": {
                    "name": "Rental Period",
                    "icon": "📅",
                    "good_msg":  lambda fv, pv: (
                        f"Rental window ({fv:.0f}%) is on par with popular films ({pv:.0f}%). "
                        "Customers have enough time to watch and enjoy the film."),
                    "bad_msg":   lambda fv, pv: (
                        f"Rental period ({fv:.0f}%) is shorter than popular films ({pv:.0f}%). "
                        "Longer rental windows can encourage more rentals."),
                    "ok_msg":    lambda fv, pv: (
                        f"Rental period ({fv:.0f}%) is fairly close to popular films ({pv:.0f}%)."),
                },
            }

            for i, k in enumerate(dims):
                fv = film_vals[i]
                pv = pop_vals[i]
                diff = fv - pv
                meta = insight_meta.get(k, {})
                name = meta.get("name", k)
                icon = meta.get("icon", "•")

                if abs(diff) <= 12:
                    status = "good"
                    status_label = "✅ On Track"
                    msg = meta["good_msg"](fv, pv)
                elif diff < -12:
                    status = "bad"
                    status_label = "⚠️ Below Average"
                    msg = meta["bad_msg"](fv, pv)
                else:
                    status = "ok"
                    status_label = "🔼 Above Average"
                    msg = meta["ok_msg"](fv, pv)

                st.markdown(f"""
                <div class="insight-card">
                    <div class="insight-icon">{icon}</div>
                    <div class="insight-text">
                        <div class="insight-label {status}">{name} · {status_label}</div>
                        <div class="insight-body">{msg}</div>
                    </div>
                </div>""", unsafe_allow_html=True)

        else:
            st.info("No popular film data available for comparison.")

# ── Popular films table ───────────────────────────────────────────────────────
st.markdown("---")
section_label("Top Popular Films in Database")
if popular:
    pop_df = pd.DataFrame(popular)[["title","genre_name","rating","total_rental","total_revenue"]]
    pop_df.columns = ["Title","Genre","Rating","Total Rentals","Revenue ($)"]
    pop_df["Revenue ($)"] = pop_df["Revenue ($)"].apply(lambda x: f"${float(x):,.2f}")
    st.dataframe(pop_df, use_container_width=True, hide_index=True)