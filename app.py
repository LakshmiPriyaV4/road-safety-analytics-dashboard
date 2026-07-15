"""
app.py — Road Safety Analytics | UK Accidents 2018
Clean light-theme UI over a real, working analytics pipeline built on Phases
1-9 of the underlying data project. See utils.py module docstring for an
honest breakdown of what's real (data, model, cost math) vs. illustrative
demo scaffolding (RBAC, connection pooling, alerting).
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import utils as u

# ------------------------------------------------------------------------
# Page config + global CSS
# ------------------------------------------------------------------------
st.set_page_config(
    page_title="Road Safety Analytics | UK Accidents 2018",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
    <style>
        /* Base theme colors come from .streamlit/config.toml (light base) —
           this CSS adds polish: card styling, badge chips, black headings.
           Every selector below was verified against the installed
           Streamlit build's compiled frontend before use. */

        [data-testid="stSidebar"] * {{
            color: {u.TEXT_COLOR} !important;
        }}
        [data-testid="stCaptionContainer"], .stCaption, small {{
            color: #475569 !important;
        }}
        [data-testid="stWidgetLabel"] p {{
            color: {u.TEXT_COLOR} !important;
            font-weight: 500;
        }}
        h1, h2, h3, h4, h5 {{
            color: {u.HEADING_COLOR} !important;
            font-weight: 700 !important;
        }}
        [data-testid="stMetricLabel"] p {{
            color: #475569 !important;
        }}
        [data-testid="stMetricValue"] {{
            color: {u.HEADING_COLOR};
            font-weight: 700;
        }}

        /* Tighten the default top padding so content starts higher */
        div[data-testid="stAppViewContainer"] > div:first-child {{
            padding-top: 1.2rem;
        }}

        /* KPI metric cards */
        [data-testid="stMetric"] {{
            background-color: {u.SURFACE_COLOR};
            border: 1px solid {u.GRID_COLOR};
            border-radius: 12px;
            padding: 16px 18px;
        }}
        [data-testid="stMetricLabel"] {{
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        /* Headings: accent bar for page titles only */
        h1 {{
            border-left: 4px solid {u.ACCENT_BLUE};
            padding-left: 14px;
        }}

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {{ gap: 2px; }}
        .stTabs button[role="tab"] {{
            background-color: {u.SURFACE_COLOR};
            border-radius: 8px 8px 0 0;
            padding: 10px 16px;
        }}
        .stTabs button[role="tab"] p {{
            color: {u.TEXT_COLOR} !important;
            font-weight: 600;
        }}
        .stTabs button[aria-selected="true"] {{
            border-bottom: 3px solid {u.ACCENT_BLUE} !important;
        }}

        /* Badge chips used inline in markdown */
        .demo-badge, .real-badge {{
            display: inline-block;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.05em;
            color: #FFFFFF;
            border-radius: 4px;
            padding: 2px 9px;
            margin-left: 8px;
            vertical-align: middle;
        }}
        .demo-badge {{ background-color: {u.ACCENT_BLUE}; }}
        .real-badge {{ background-color: #059669; }}

        /* Column gutters */
        div[data-testid="stHorizontalBlock"] {{ gap: 1.1rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def chart(fig):
    """Applies the shared light layout and forces a bold, black chart title
    regardless of what title text callers passed in via px.*(title=...)."""
    fig.update_layout(**u.PLOTLY_LAYOUT)
    if fig.layout.title and fig.layout.title.text:
        raw_title = fig.layout.title.text.replace("<b>", "").replace("</b>", "")
        fig.update_layout(
            title=dict(
                text=f"<b>{raw_title}</b>", font=dict(color=u.HEADING_COLOR, size=16)
            )
        )
    return fig


def render_chart(fig, **kwargs):
    """Renders a chart inside exactly ONE bordered card. This is a plain
    local function — it does NOT reassign st.plotly_chart itself.

    The previous version of this file did: `st.plotly_chart = _card_plotly_chart`.
    That reassigns the actual streamlit module's function object. Streamlit
    reruns this entire script top-to-bottom on every widget interaction
    (every filter change) WITHOUT reloading the streamlit module — so on
    rerun #2, `_native_plotly_chart = st.plotly_chart` captured rerun #1's
    already-wrapped version and wrapped it again, rerun #3 wrapped that
    result again, and so on. That is exactly why the border count grew by
    one every time a filter changed. A plain local function has no shared
    state between reruns, so it cannot compound like that."""
    kwargs.setdefault("width", "stretch")
    with st.container(border=True):
        return st.plotly_chart(fig, **kwargs)


# ------------------------------------------------------------------------
# Data connection (demo) + data load (real)
# ------------------------------------------------------------------------
conn = u.get_data_connection()

data_path = u.resolve_data_path()
if data_path:
    df = u.load_data(data_path)
else:
    st.title("Road Safety Analytics")
    st.error(
        f"Couldn't find `accidents_cleaned_v1.csv` next to app.py.\n\n"
        f"Make sure the CSV sits in the same folder as `app.py`, or upload it below."
    )
    uploaded = st.file_uploader("Upload accidents_cleaned_v1.csv", type="csv")
    if uploaded is None:
        st.stop()
    df = u.load_data(uploaded)

# ------------------------------------------------------------------------
# Sidebar — RBAC gate (demo), connection status, filters
# ------------------------------------------------------------------------
st.sidebar.title("⚡ Road Safety Analytics")
st.sidebar.caption("UK Road Accidents 2018 | 59,997 records")

st.sidebar.markdown("---")
st.sidebar.subheader("Access level")
if "role" not in st.session_state:
    st.session_state.role = "Public"

role_choice = st.sidebar.radio("View as", ["Public", "Administrator"], horizontal=True)
if role_choice == "Administrator" and st.session_state.role != "Administrator":
    if not u.admin_password_is_configured():
        st.sidebar.warning(
            "No ADMIN_PASSWORD configured for this deployment (via st.secrets or "
            "environment variable) — Administrator view is disabled until one is set."
        )
    pw = st.sidebar.text_input("Admin password", type="password")
    if pw:
        if u.check_credentials(pw):
            st.session_state.role = "Administrator"
            st.sidebar.success("Administrator view unlocked.")
        else:
            st.sidebar.error("Incorrect password.")
elif role_choice == "Public":
    st.session_state.role = "Public"

is_admin = st.session_state.role == "Administrator"
st.sidebar.caption(
    "Demo authentication only (hardcoded password) — not production security."
)

with st.sidebar.expander("Data connection status"):
    st.write(f"**Backend:** {conn.backend}")
    st.write(f"**Status:** {conn.status}")
    st.caption(conn.note)

st.sidebar.markdown("---")
st.sidebar.subheader("Filters")
month_sel = st.sidebar.multiselect("Month", u.MONTHS_ORDER, default=u.MONTHS_ORDER)
region_sel = st.sidebar.multiselect(
    "Region", ["London", "Rest of England"], default=["London", "Rest of England"]
)
severity_sel = st.sidebar.multiselect(
    "Severity", ["Fatal", "Serious", "Slight"], default=["Fatal", "Serious", "Slight"]
)

fdf = df[
    df["Month_Name"].isin(month_sel)
    & df["Accident_Severity_Label"].isin(severity_sel)
    & (
        (df["Is_London"] & ("London" in region_sel))
        | (~df["Is_London"] & ("Rest of England" in region_sel))
    )
]

if fdf.empty:
    st.warning("No records match the current filters. Adjust the sidebar selections.")
    st.stop()


def severity_bar(data, group_col, order=None, title=""):
    ct = (
        pd.crosstab(data[group_col], data["Accident_Severity_Label"], normalize="index")
        * 100
    )
    ct = ct.reindex(columns=["Slight", "Serious", "Fatal"])
    if order:
        ct = ct.reindex(order)
    ct = ct.reset_index().melt(
        id_vars=group_col, var_name="Severity", value_name="Percent"
    )
    fig = px.bar(
        ct,
        x="Percent",
        y=group_col,
        color="Severity",
        orientation="h",
        color_discrete_map=u.SEVERITY_COLORS,
        title=title,
    )
    fig.update_layout(
        barmode="stack", legend_title="", yaxis_title="", xaxis_title="% of accidents"
    )
    return chart(fig)


# ------------------------------------------------------------------------
# Tabs
# ------------------------------------------------------------------------
tabs = st.tabs(
    [
        "Executive Summary",
        "Time & Conditions",
        "Severity Deep Dive",
        "Spatial Matrix",
        "Road & Vehicle Factors",
        "What-If Simulator",
        "ML Risk Sandbox",
        "Business Insights",
        "Data Quality & Ops",
    ]
)

# ---------------- Executive Summary ----------------
with tabs[0]:
    st.title("Executive summary")
    st.caption("Road safety performance overview — UK, 2018")

    total = len(fdf)
    casualties = int(fdf["Number_of_Casualties"].sum())
    severe_rate = fdf["Is_Severe"].mean() * 100
    police_rate = (
        fdf["Did_Police_Officer_Attend_Scene_of_Accident_Label"] == "Yes"
    ).mean() * 100
    cost = u.compute_economic_cost(fdf)

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns(5, gap="medium")
        c1.metric("Total accidents", f"{total:,}")
        c2.metric("Total casualties", f"{casualties:,}")
        c3.metric("Severe rate", f"{severe_rate:.1f}%")
        c4.metric("Police attendance", f"{police_rate:.1f}%")
        c5.metric(
            "Est. economic cost",
            f"£{cost['total']/1e6:.1f}M",
            help="DfT valuation-of-prevention estimate (2023-price basis, illustrative)",
        )

    st.write("")
    col1, col2 = st.columns([1.4, 1], gap="medium")
    with col1:
        monthly = (
            fdf.groupby("Month_Name")["Accident_Index"]
            .count()
            .reindex([m for m in u.MONTHS_ORDER if m in month_sel])
        )
        fig = px.line(
            x=monthly.index,
            y=monthly.values,
            markers=True,
            title="Monthly accident trend",
            labels={"x": "", "y": "Accidents"},
        )
        fig.update_traces(line_color=u.ACCENT_BLUE)
        render_chart(chart(fig), width="stretch")
    with col2:
        sev = (
            fdf["Accident_Severity_Label"]
            .value_counts()
            .reindex(["Fatal", "Serious", "Slight"])
        )
        fig = px.pie(
            values=sev.values,
            names=sev.index,
            hole=0.5,
            color=sev.index,
            color_discrete_map=u.SEVERITY_COLORS,
            title="Severity mix",
        )
        render_chart(chart(fig), width="stretch")

    st.write("")
    col3, col4 = st.columns(2, gap="medium")
    with col3:
        risk_factor = st.selectbox(
            "Top risk factor breakdown",
            ["Time_of_Day", "Weather_Conditions_Label", "Speed_limit"],
        )
        order = u.TOD_ORDER if risk_factor == "Time_of_Day" else None
        render_chart(
            severity_bar(
                fdf, risk_factor, order, "Severity by " + risk_factor.replace("_", " ")
            ),
            width="stretch",
        )
    with col4:
        la = (
            fdf.groupby("Local_Authority_(District)")
            .agg(n=("Accident_Index", "count"), severe_rate=("Is_Severe", "mean"))
            .reset_index()
        )
        la = la[la["n"] >= 50].sort_values("severe_rate", ascending=False).head(10)
        la["severe_rate"] = (la["severe_rate"] * 100).round(1)
        fig = px.bar(
            la,
            x="severe_rate",
            y="Local_Authority_(District)",
            orientation="h",
            title="Top 10 highest-severity local authorities (min. 50 accidents)",
            labels={
                "severe_rate": "% severe",
                "Local_Authority_(District)": "Authority code",
            },
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        render_chart(chart(fig), width="stretch")

    st.write("")
    with st.container(border=True):
        st.markdown(
            "##### Emergency resource allocation index <span class='demo-badge'>ILLUSTRATIVE FORMULA</span>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Directional estimate of service load from filtered accidents — not an official DfT methodology."
        )
        load = u.emergency_resource_index(fdf)
        r1, r2, r3 = st.columns(3, gap="medium")
        r1.metric("Police hours (est.)", f"{load['police_hours']:,.0f}")
        r2.metric("Ambulance units (est.)", f"{load['ambulance_units']:,.0f}")
        r3.metric("Highways crew hours (est.)", f"{load['highways_crew_hours']:,.0f}")

# ---------------- Time & Conditions ----------------
with tabs[1]:
    st.title("Time & conditions")
    col1, col2 = st.columns(2)
    with col1:
        heat = fdf.pivot_table(
            index="Hour",
            columns="Day_of_Week_Label",
            values="Accident_Index",
            aggfunc="count",
            fill_value=0,
        )
        day_order = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        heat = heat.reindex(columns=[d for d in day_order if d in heat.columns])
        fig = px.imshow(
            heat,
            aspect="auto",
            color_continuous_scale="Teal",
            title="Accidents by hour and weekday",
            labels=dict(color="Accidents"),
        )
        render_chart(chart(fig), width="stretch")
    with col2:
        render_chart(
            severity_bar(fdf, "Time_of_Day", u.TOD_ORDER, "Severity by time of day"),
            width="stretch",
        )

    col3, col4 = st.columns(2)
    with col3:
        render_chart(
            severity_bar(fdf, "Weather_Conditions_Label", title="Severity by weather"),
            width="stretch",
        )
    with col4:
        render_chart(
            severity_bar(
                fdf, "Light_Conditions_Label", title="Severity by light conditions"
            ),
            width="stretch",
        )

    seasonal = (
        fdf.groupby(["Month_Name", "Accident_Severity_Label"])
        .size()
        .reset_index(name="n")
    )
    seasonal = seasonal[seasonal["Month_Name"].isin(u.MONTHS_ORDER)]
    fig = px.line(
        seasonal,
        x="Month_Name",
        y="n",
        color="Accident_Severity_Label",
        category_orders={"Month_Name": u.MONTHS_ORDER},
        color_discrete_map=u.SEVERITY_COLORS,
        title="Seasonal trend by severity",
        markers=True,
    )
    render_chart(chart(fig), width="stretch")

# ---------------- Severity Deep Dive ----------------
with tabs[2]:
    st.title("Severity deep dive")
    col1, col2 = st.columns(2)
    with col1:
        trend = (
            fdf.groupby(
                [fdf["Date"].dt.to_period("M").astype(str), "Accident_Severity_Label"]
            )
            .size()
            .reset_index(name="n")
        )
        trend.columns = ["Month", "Severity", "n"]
        fig = px.line(
            trend,
            x="Month",
            y="n",
            color="Severity",
            color_discrete_map=u.SEVERITY_COLORS,
            title="Fatal / Serious / Slight trend over the year",
            markers=True,
        )
        render_chart(chart(fig), width="stretch")
    with col2:
        fig = px.histogram(
            fdf,
            x="Casualties_per_Vehicle",
            nbins=20,
            title="Casualties per vehicle distribution",
        )
        fig.update_traces(marker_color=u.ACCENT_BLUE_LIGHT)
        render_chart(chart(fig), width="stretch")

    col3, col4 = st.columns(2)
    with col3:
        mv = fdf.copy()
        mv["Vehicle_Group"] = mv["Number_of_Vehicles"].apply(
            lambda x: "Single vehicle" if x == 1 else "Multi-vehicle"
        )
        render_chart(
            severity_bar(
                mv, "Vehicle_Group", title="Single vs. multi-vehicle severity"
            ),
            width="stretch",
        )
    with col4:
        outliers = fdf[fdf["Outlier_High_Vehicles"] | fdf["Outlier_High_Casualties"]]
        st.write(
            f"**{len(outliers)} flagged outlier accidents** (>8 vehicles or >10 casualties)"
        )
        st.dataframe(
            outliers[
                [
                    "Accident_Index",
                    "Number_of_Vehicles",
                    "Number_of_Casualties",
                    "Accident_Severity_Label",
                    "Date",
                ]
            ].reset_index(drop=True),
            width="stretch",
            height=280,
        )

# ---------------- Spatial Matrix ----------------
with tabs[3]:
    st.title("Spatial matrix analytics")
    st.error(
        "The raw `latitude`/`longitude` fields fail UK bounds checks for 100% of records "
        "(see Data Quality & Ops). Rather than plotting fabricated positions on a map, this "
        "page uses Local Authority-level aggregation as an honest substitute for point-level "
        "density mapping. A real map can be added once a valid LSOA-to-coordinate lookup is "
        "joined to this data."
    )

    col1, col2 = st.columns(2)
    with col1:
        la_treemap = (
            fdf.groupby("Local_Authority_(District)")
            .agg(
                Accidents=("Accident_Index", "count"), Severe_Rate=("Is_Severe", "mean")
            )
            .reset_index()
        )
        la_treemap["Severe_Rate_pct"] = (la_treemap["Severe_Rate"] * 100).round(1)
        fig = px.treemap(
            la_treemap,
            path=["Local_Authority_(District)"],
            values="Accidents",
            color="Severe_Rate_pct",
            color_continuous_scale="Turbo",
            title="Accident density by authority (color = % severe)",
        )
        render_chart(chart(fig), width="stretch")
    with col2:
        region_sev = (
            fdf.groupby(
                fdf["Is_London"].map({True: "London", False: "Rest of England"})
            )["Is_Severe"].mean()
            * 100
        )
        fig = px.bar(
            x=region_sev.index,
            y=region_sev.values,
            title="Severe rate: London vs. rest of England",
            labels={"x": "", "y": "% severe"},
            color=region_sev.index,
            color_discrete_sequence=[u.ACCENT_BLUE, u.ACCENT_BLUE_LIGHT],
        )
        render_chart(chart(fig), width="stretch")

    st.markdown(
        "#### Emergency response coverage proxy <span class='demo-badge'>PROXY METRIC</span>",
        unsafe_allow_html=True,
    )
    st.caption(
        "No response-time data exists in this dataset, so true isochrone (5/10/15-min) "
        "response-zone overlays cannot be built honestly here. As a proxy, this compares "
        "police-attendance rate and severe-outcome rate across urban vs. rural areas — "
        "rural areas historically correlate with longer real-world response times."
    )
    proxy = (
        fdf.groupby("Urban_or_Rural_Area_Label")
        .agg(
            Accidents=("Accident_Index", "count"),
            Police_Attendance_Pct=(
                "Did_Police_Officer_Attend_Scene_of_Accident_Label",
                lambda s: (s == "Yes").mean() * 100,
            ),
            Severe_Rate_Pct=("Is_Severe", lambda s: s.mean() * 100),
        )
        .reset_index()
    )
    st.dataframe(proxy.round(1), width="stretch")

    st.subheader("Local authority ranking (min. 100 accidents)")
    la = (
        fdf.groupby("Local_Authority_(District)")
        .agg(Accidents=("Accident_Index", "count"), Severe_Rate=("Is_Severe", "mean"))
        .reset_index()
    )
    la = la[la["Accidents"] >= 100].sort_values("Severe_Rate", ascending=False)
    la["Severe_Rate"] = (la["Severe_Rate"] * 100).round(1)
    st.dataframe(la.reset_index(drop=True), width="stretch", height=350)

# ---------------- Road & Vehicle Factors ----------------
with tabs[4]:
    st.title("Road & vehicle factors")
    col1, col2 = st.columns(2)
    with col1:
        render_chart(
            severity_bar(fdf, "Speed_limit", title="Severity by speed limit"),
            width="stretch",
        )
    with col2:
        render_chart(
            severity_bar(fdf, "Road_Type_Label", title="Severity by road type"),
            width="stretch",
        )

    col3, col4 = st.columns(2)
    with col3:
        render_chart(
            severity_bar(
                fdf, "Urban_or_Rural_Area_Label", title="Severity: urban vs. rural"
            ),
            width="stretch",
        )
    with col4:
        jd = (
            fdf.groupby("Junction_Detail_Label")
            .agg(n=("Accident_Index", "count"), severe=("Is_Severe", "mean"))
            .reset_index()
        )
        jd["severe"] = (jd["severe"] * 100).round(1)
        jd = jd.sort_values("severe", ascending=True)
        fig = px.bar(
            jd,
            x="severe",
            y="Junction_Detail_Label",
            orientation="h",
            title="Severe rate by junction detail (Not Recorded shown as its own category)",
            labels={"severe": "% severe", "Junction_Detail_Label": ""},
        )
        render_chart(chart(fig), width="stretch")

# ---------------- What-If Simulator ----------------
with tabs[5]:
    st.title("Proactive strategy simulator")
    st.markdown(
        "<span class='real-badge'>GROUNDED IN THIS DATASET</span> "
        "junction effect · <span class='demo-badge'>EXTERNAL ASSUMPTION</span> camera effect",
        unsafe_allow_html=True,
    )
    st.caption(
        "The roundabout effect scales from this dataset's own observed severe-rate gap "
        "between roundabouts and comparable junction types. The speed-camera effect uses an "
        "assumed 20% severe-outcome reduction — a simulation input, not something this "
        "single-year dataset can validate (no before/after camera deployment data exists here)."
    )

    s1, s2 = st.columns(2)
    with s1:
        roundabout_pct = st.slider(
            "Convert crossroads/T-junctions to roundabouts (%)", 0, 100, 25
        )
    with s2:
        camera_pct = st.slider(
            "Deploy average speed cameras on 60mph roads (%)", 0, 100, 25
        )

    sim = u.simulate_whatif(fdf, roundabout_pct, camera_pct)

    with st.container(border=True):
        m1, m2, m3 = st.columns(3, gap="medium")
        m1.metric(
            "Accidents shifted from severe to slight", f"{sim['accidents_shifted']:.0f}"
        )
        m2.metric("Estimated cost saved", f"£{sim['cost_saved']/1e6:.2f}M")
        m3.metric(
            "New severe rate (approx.)",
            f"{(1 - sim['sim_counts']['Slight']/sum(sim['sim_counts'].values()))*100:.1f}%",
            delta=f"{-(sim['base_severe_rate']*100 - (1 - sim['sim_counts']['Slight']/sum(sim['sim_counts'].values()))*100):.1f} pp",
        )

    comp = pd.DataFrame(
        {
            "Severity": ["Fatal", "Serious", "Slight"] * 2,
            "Scenario": ["Baseline"] * 3 + ["Simulated"] * 3,
            "Count": [
                sim["base_counts"]["Fatal"],
                sim["base_counts"]["Serious"],
                sim["base_counts"]["Slight"],
                sim["sim_counts"]["Fatal"],
                sim["sim_counts"]["Serious"],
                sim["sim_counts"]["Slight"],
            ],
        }
    )
    fig = px.bar(
        comp,
        x="Scenario",
        y="Count",
        color="Severity",
        barmode="stack",
        color_discrete_map=u.SEVERITY_COLORS,
        title="Baseline vs. simulated severity distribution",
    )
    render_chart(chart(fig), width="stretch")

# ---------------- ML Risk Sandbox ----------------
with tabs[6]:
    st.title("ML risk inference sandbox")
    st.markdown(
        "<span class='real-badge'>REAL MODEL</span> "
        "scikit-learn GradientBoostingClassifier, trained live on this dataset",
        unsafe_allow_html=True,
    )

    bundle = u.train_risk_model(df)
    st.caption(
        f"Model AUC: {bundle.auc:.3f} against a {bundle.base_rate*100:.1f}% base severe rate. "
        f"Useful for relative risk ranking across conditions — not a calibrated, "
        f"production-grade real-time predictor."
    )

    i1, i2, i3, i4 = st.columns(4)
    with i1:
        weather_in = st.selectbox(
            "Weather", sorted(df["Weather_Conditions_Label"].dropna().unique())
        )
    with i2:
        light_in = st.selectbox(
            "Light conditions", sorted(df["Light_Conditions_Label"].dropna().unique())
        )
    with i3:
        tod_in = st.selectbox("Time of day", u.TOD_ORDER)
    with i4:
        speed_in = st.select_slider(
            "Speed limit (mph)", options=sorted(df["Speed_limit"].unique()), value=30
        )

    prob = u.predict_risk(bundle, weather_in, light_in, tod_in, speed_in)

    gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=prob * 100,
            number={"suffix": "%", "font": {"color": u.ACCENT_BLUE}},
            title={
                "text": "Estimated severe-outcome probability",
                "font": {"color": u.TEXT_COLOR},
            },
            gauge={
                "axis": {"range": [0, 100], "tickcolor": u.TEXT_COLOR},
                "bar": {"color": u.ACCENT_BLUE},
                "bgcolor": u.SURFACE_COLOR,
                "borderwidth": 1,
                "bordercolor": u.GRID_COLOR,
                "steps": [
                    {"range": [0, 15], "color": "#1F2937"},
                    {"range": [15, 30], "color": "#3A2E1F"},
                    {"range": [30, 100], "color": "#3A1F26"},
                ],
            },
        )
    )
    gauge.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", font={"color": u.TEXT_COLOR}, height=350
    )
    render_chart(gauge, width="stretch")

# ---------------- Business Insights ----------------
with tabs[7]:
    st.title("Business insights")
    st.caption("31 evidence-backed findings — grouped by theme")

    insights = {
        "Time & seasonality": [
            (
                "Late-night hours (0-3am) reach 20-25% severe rate vs. 8.8% at midday.",
                "A small volume of accidents drives a disproportionate share of deaths/serious injuries.",
                "Target enforcement (speed cameras, drink-drive checks) at 11pm-4am.",
            ),
            (
                "Weekend accidents are 15.4% severe vs. 12.7% on weekdays, peaking on Sunday (15.6%).",
                "Leisure/night-out driving carries materially higher risk per accident.",
                "Time drink-driving and fatigue campaigns to Friday evening through Sunday.",
            ),
            (
                "Q3 (Jul-Sep) has the highest quarterly severe rate at 14.4%.",
                "Summer holiday travel and motorcycling season likely contribute.",
                "Run pre-summer safety campaigns in June.",
            ),
            (
                "Monthly volume is stable; no month exceeds 9.1% of the year, November peaks at 5,435.",
                "This is a distributed risk, not a single event to prepare for.",
                "Run a sustained autumn lighting/awareness campaign rather than a one-off.",
            ),
        ],
        "Speed & road type": [
            (
                "60mph roads have the highest severe rate of any speed limit at 22.9%.",
                "Rural national-speed-limit single carriageways are the biggest severity lever available.",
                "Prioritize average-speed cameras and road-engineering review on high-volume 60mph corridors.",
            ),
            (
                "20mph zones still show 16.4% severe - second highest of any speed limit.",
                "Low speed limits alone don't guarantee safety; likely reflects vulnerable road users.",
                "Pair 20mph zones with pedestrian infrastructure, not speed limit alone.",
            ),
            (
                "8-vehicle pile-ups reach a 42.9% severe rate, the highest of any vehicle-count band.",
                "Multi-vehicle chain collisions are catastrophic when they occur.",
                "Deploy fog/visibility warning systems and variable speed limits on high-speed multi-lane roads.",
            ),
            (
                "Single-vehicle accidents are 21.3% severe, over double the rate for 2-4 vehicle accidents.",
                "Run-off-road and loss-of-control incidents are inherently more dangerous.",
                "Audit roadside barriers/hazards on roads with a history of single-vehicle incidents.",
            ),
            (
                "B-roads have a higher severe rate (14.3%) than A-roads (13.5%).",
                "Minor/rural roads are systematically under-resourced relative to their risk.",
                "Extend A-road safety investment to high-risk B-road corridors.",
            ),
        ],
        "Weather & environment": [
            (
                "Snowing + high winds has the highest severe rate among weather categories at 22.4%.",
                "Compound weather, not any single factor, is the real risk driver.",
                "Weather alerts should flag combined conditions, not single variables.",
            ),
            (
                "Plain snow (no wind) has the lowest severe rate of any weather condition at 8.6%.",
                "Visible hazards prompt self-correcting driver behavior.",
                "Target messaging at 'invisible' risk (wind, dusk, wet-but-clear roads).",
            ),
            (
                "Flooded roads (>3cm) have a 22.0% severe rate, the highest of any road-surface condition.",
                "Flooding is rarer but disproportionately dangerous.",
                "Install real-time flood-warning signage on known flood-prone stretches.",
            ),
            (
                "Fog/mist carries a 14.5% severe rate, above the 'Fine' weather baseline.",
                "Confirms visibility as an independent risk factor.",
                "Deploy fog-activated variable message signs on high-risk routes.",
            ),
            (
                "Darkness with no lighting has a 26.3% severe rate, over double daylight's 12.2%.",
                "This is the largest lighting-related risk gap in the dataset.",
                "Prioritize street-lighting investment on unlit rural roads with high accident counts.",
            ),
        ],
        "Junctions & road features": [
            (
                "Roundabouts are the safest junction type (7.0% severe); 'not at junction' sites reach 17.0%.",
                "Junction design measurably reduces severity, likely via lower speeds.",
                "Consider roundabout conversions at high-severity T-junctions and crossroads.",
            ),
            (
                "Uncontrolled/give-way junctions carry higher severe rates than signal-controlled ones.",
                "Active traffic control measurably reduces severity.",
                "Upgrade signals or give-way controls at high-incident uncontrolled junctions.",
            ),
            (
                "Footbridge/subway crossings show 20.6% severe, higher than zebra crossings (12.1%).",
                "Likely reflects that footbridges are installed on inherently higher-speed roads, not a causal risk.",
                "Treat as a road-context confound; flag for controlled follow-up study.",
            ),
            (
                "Central refuge islands show 18.6% severe, also elevated.",
                "Same likely confound as footbridges - installed where roads are already dangerous.",
                "Don't deprioritize refuge islands without controlling for underlying road speed/type.",
            ),
            (
                "Road-surface defects show a 20.8% severe rate, the highest of any special condition.",
                "Basic road maintenance may be an underrated severity lever.",
                "Fast-track pothole/surface-defect repair on roads with recent severe accidents.",
            ),
        ],
        "Geography": [
            (
                "Rural accidents are 17.9% severe vs. 12.3% urban, a 45% relative gap.",
                "Emergency response time and higher rural speeds combine to raise severity.",
                "Review air ambulance / rapid-response coverage for high-severity rural corridors.",
            ),
            (
                "London has a lower severe rate (12.6%) than the rest of England (14.0%) despite being fully urban.",
                "London's congestion, lighting, and monitoring infrastructure has a genuine safety benefit.",
                "Study which London interventions are replicable in other UK cities.",
            ),
            (
                "The highest-severity local authority (min. 100 accidents) reaches 34.6% severe, 2.5x the national average.",
                "Risk is highly concentrated geographically, not evenly spread.",
                "Direct disproportionate safety funding to the top-5 identified authorities.",
            ),
            (
                "London accounts for 44.6% of all recorded accidents in this dataset.",
                "Volume-based and severity-based resourcing point to different priorities.",
                "Run a two-track strategy: congestion management in London, road engineering in high-severity rural areas.",
            ),
        ],
        "Casualties, policing & data quality": [
            (
                "Only 21.5% of accidents involve 2+ casualties.",
                "Mass-casualty events are not representative of typical risk.",
                "Optimize policy for the common single-casualty case, not just headline incidents.",
            ),
            (
                "Accidents where police did not attend show a lower recorded severe rate (5.1% vs 15.4%).",
                "Very likely a reporting artifact - officers are dispatched preferentially to serious incidents.",
                "Don't use attendance rate as a severity predictor; it's an outcome of severity, not a cause.",
            ),
            (
                "Junction_Control and 2nd_Road_Class are 'Not Recorded' in ~33% of records.",
                "A third of junction-context analysis is built on incomplete data.",
                "Improve data-collection process at point of police reporting.",
            ),
            (
                "100% of geographic coordinates fail UK bounds checks.",
                "No pin-level hotspot mapping is currently possible.",
                "Fix the coordinate pipeline before building spatial decision-making tools.",
            ),
            (
                "'Not Recorded' categories consistently show elevated severe rates across multiple fields.",
                "Missingness itself correlates with severity - chaotic scenes may be harder to document.",
                "Treat high 'Not Recorded' rates as a mild severity signal, not just a data-quality nuisance.",
            ),
            (
                "Motorways (12.2% severe) are safer than standard A-roads (13.5%) despite far higher speeds.",
                "Road design (grade separation, no crossing traffic) outweighs raw speed as a severity driver.",
                "Frame road investment around design features, not blanket speed reduction alone.",
            ),
            (
                "'Give way/uncontrolled' plus 'not at junction' account for the majority of severe junction-related accidents.",
                "Absence of active control is the common thread across the largest severe-accident categories.",
                "A junction-control audit is likely the single highest-leverage infrastructure recommendation.",
            ),
        ],
    }

    for theme, items in insights.items():
        with st.expander(f"{theme} ({len(items)} insights)", expanded=False):
            for i, (obs, impact, rec) in enumerate(items, 1):
                st.markdown(f"**{i}. Observation:** {obs}")
                st.markdown(f"   *Business impact:* {impact}")
                st.markdown(f"   *Recommendation:* {rec}")
                st.markdown("---")

# ---------------- Data Quality & Ops ----------------
with tabs[8]:
    st.title("Data quality & operations")

    with st.container(border=True):
        c1, c2, c3 = st.columns(3, gap="medium")
        c1.metric(
            "Geo-reliability",
            "0%",
            help="100% of lat/long values fail UK bounds checks",
        )
        jc_nr = (df["Junction_Control"] == -1).mean() * 100
        c2.metric("Junction Control not recorded", f"{jc_nr:.1f}%")
        c3.metric("Rows / columns", f"{len(df):,} / {len(df.columns)}")

    st.error(
        "Latitude/longitude are corrupted (100% fail UK bounds checks) — do not use for mapping. "
        "All geographic analysis in this dashboard uses Local Authority codes instead."
    )

    st.subheader("'Not Recorded' rate by field")
    nr_fields = [
        "Junction_Control",
        "2nd_Road_Class",
        "Road_Surface_Conditions",
        "Special_Conditions_at_Site",
        "Carriageway_Hazards",
        "Did_Police_Officer_Attend_Scene_of_Accident",
    ]
    nr = pd.Series({f: (df[f] == -1).mean() * 100 for f in nr_fields}).sort_values(
        ascending=True
    )
    fig = px.bar(
        x=nr.values,
        y=nr.index,
        orientation="h",
        title="Percent 'Not Recorded' (-1) by field",
        labels={"x": "% Not Recorded", "y": ""},
    )
    fig.update_traces(marker_color="#FFB020")
    render_chart(chart(fig), width="stretch")

    st.markdown("---")
    st.markdown(
        "##### Automated alerting <span class='demo-badge'>DEMO</span>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Simulated threshold trigger — no real Slack/email integration is wired up."
    )
    threshold = st.slider(
        "Alert if any authority's severe rate exceeds (%)", 10, 50, 25
    )
    la_alert = (
        fdf.groupby("Local_Authority_(District)")
        .agg(n=("Accident_Index", "count"), severe_rate=("Is_Severe", "mean"))
        .reset_index()
    )
    la_alert = la_alert[la_alert["n"] >= 50]
    breaches = la_alert[la_alert["severe_rate"] * 100 > threshold]
    if len(breaches) > 0:
        st.warning(
            f"{len(breaches)} authorities would trigger an alert at this threshold "
            f"(demo — would notify Slack/email in a production build)."
        )
        st.dataframe(
            breaches.assign(severe_rate=lambda d: (d["severe_rate"] * 100).round(1)),
            width="stretch",
        )
    else:
        st.success("No authorities currently breach this threshold.")

    st.markdown("---")
    st.subheader("Executive report export")
    report_lines = [
        "ROAD SAFETY ANALYTICS - EXECUTIVE SUMMARY EXPORT",
        f"Filters applied: Months={month_sel}, Region={region_sel}, Severity={severity_sel}",
        "",
        f"Total accidents: {total:,}",
        f"Total casualties: {casualties:,}",
        f"Severe rate: {severe_rate:.1f}%",
        f"Police attendance rate: {police_rate:.1f}%",
        f"Estimated economic cost: GBP {cost['total']:,}",
        "",
        "Top recommendation tiers (see Business Insights tab for full detail):",
        "1. Junction control audit at uncontrolled/not-at-junction sites",
        "2. Rural 60mph corridor speed enforcement",
        "3. Late-night (11pm-4am) enforcement window",
    ]
    report_text = "\n".join(report_lines)
    st.download_button(
        "Download executive summary (.txt)",
        data=report_text,
        file_name="executive_summary.txt",
        mime="text/plain",
    )

    if is_admin:
        st.markdown("---")
        st.subheader("🔒 Administrator panel")
        st.caption("Only visible in Administrator view.")
        st.write("**Raw not-recorded counts:**")
        st.dataframe(
            pd.DataFrame(
                {
                    "Field": nr_fields,
                    "Not Recorded Count": [(df[f] == -1).sum() for f in nr_fields],
                }
            ),
            width="stretch",
        )
        st.write("**Model internals:**")
        bundle_admin = u.train_risk_model(df)
        st.write(
            f"Risk model AUC: {bundle_admin.auc:.4f} | Base rate: {bundle_admin.base_rate:.4f}"
        )
        st.write("**Connection pool config (demo):**", conn)

st.sidebar.markdown("---")
st.sidebar.caption(f"View: {st.session_state.role} | UK DfT STATS19-style data, 2018")
