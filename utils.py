"""
utils.py — Data, financial modeling, ML risk model, and simulation logic
for the Road Safety Analytics dashboard.

Honesty notes (read before presenting this as a client deliverable):
  * DfT_COST_MATRIX values are illustrative, citing DfT's published "valuation of
    prevention" figures (2023 prices, approx.). They are casualty-level figures
    applied here at accident-severity level as a simplification — flagged in the UI.
  * EMERGENCY_RESOURCE_WEIGHTS is an illustrative formula we designed for this
    dashboard, not an official DfT resourcing methodology. Flagged in the UI.
  * The risk model is a real scikit-learn GradientBoostingClassifier trained on
    this dataset — not a "mock". It is NOT XGBoost; naming it accurately avoids
    overstating the tech stack.
  * get_data_connection() is a clearly-labeled DEMO stand-in for a real warehouse
    connection (Snowflake/BigQuery/Postgres). It does not connect to anything.
  * check_credentials() is a DEMO auth gate only (hardcoded demo password) — not
    fit for production without a real identity provider.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import OrdinalEncoder

# ----------------------------------------------------------------------------
# Theme constants — light theme (matches the app's actual rendered background;
# Streamlit's per-browser theme preference can override config.toml, so the
# design is built to work correctly under a light background rather than
# fighting that override).
# ----------------------------------------------------------------------------
BG_COLOR = "#FFFFFF"
TEXT_COLOR = "#0F172A"  # near-black, used for body text and sidebar
HEADING_COLOR = "#0F172A"  # black-ish headings, per request
ACCENT_BLUE = "#0369A1"  # accessible accent on white (was neon cyan)
ACCENT_BLUE_LIGHT = "#0EA5E9"
GRID_COLOR = "#E5E7EB"  # light, low-contrast gridlines
SURFACE_COLOR = "#F8FAFC"  # subtle card background, still white-ish

SEVERITY_COLORS = {"Fatal": "#DC2626", "Serious": "#F59E0B", "Slight": "#64748B"}

PLOTLY_LAYOUT = dict(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT_COLOR, family="Inter, sans-serif"),
    xaxis=dict(gridcolor=GRID_COLOR, gridwidth=1, zeroline=False, showline=False),
    yaxis=dict(gridcolor=GRID_COLOR, gridwidth=1, zeroline=False, showline=False),
    title=dict(font=dict(color=HEADING_COLOR, size=16, family="Inter, sans-serif")),
    margin=dict(l=10, r=10, t=50, b=10),
)

# ----------------------------------------------------------------------------
# DfT financial model
# ----------------------------------------------------------------------------
# Approximate 2023-price DfT "valuation of prevention" figures (fatal ~£2.1-2.3m,
# serious ~£237k-280k per published RAS/TAG figures). Applied per accident-severity
# record here as a simplification for illustrative economic-impact estimation.
DFT_COST_MATRIX = {"Fatal": 2_000_000, "Serious": 250_000, "Slight": 15_000}

# Illustrative resourcing weights (NOT an official DfT methodology) — designed to
# give a directional sense of emergency-service load, not a calibrated estimate.
EMERGENCY_RESOURCE_WEIGHTS = {
    "police_hours": {"Fatal": 8.0, "Serious": 3.0, "Slight": 0.5},
    "ambulance_units": {"Fatal": 2.0, "Serious": 1.0, "Slight": 0.2},
    "highways_crew_hours": {"Fatal": 4.0, "Serious": 1.5, "Slight": 0.3},
}


def compute_economic_cost(frame: pd.DataFrame) -> dict:
    """Total and per-severity economic cost using DFT_COST_MATRIX."""
    counts = frame["Accident_Severity_Label"].value_counts()
    breakdown = {
        sev: int(counts.get(sev, 0)) * cost for sev, cost in DFT_COST_MATRIX.items()
    }
    return {"total": sum(breakdown.values()), "breakdown": breakdown, "counts": counts}


def emergency_resource_index(frame: pd.DataFrame) -> dict:
    """Illustrative emergency-service load estimate driven by active filter state."""
    counts = frame["Accident_Severity_Label"].value_counts()
    result = {}
    for resource, weights in EMERGENCY_RESOURCE_WEIGHTS.items():
        result[resource] = sum(counts.get(sev, 0) * w for sev, w in weights.items())
    return result


# ----------------------------------------------------------------------------
# Mock enterprise infrastructure (clearly labeled demo scaffolding)
# ----------------------------------------------------------------------------
@dataclass
class ConnectionInfo:
    backend: str
    status: str
    note: str


@st.cache_resource
def get_data_connection() -> ConnectionInfo:
    """DEMO connection-pool stand-in. Does not connect to a real warehouse."""
    return ConnectionInfo(
        backend="Local CSV (demo)",
        status="connected",
        note="Stand-in for a pooled Snowflake/BigQuery/Postgres connection. "
        "Swap this function for a real driver before production use.",
    )


def _get_admin_password() -> str:
    """Reads the admin password from Streamlit secrets/env, with a clearly-flagged
    fallback for local dev only. Never hardcode real credentials in source control."""
    try:
        if "ADMIN_PASSWORD" in st.secrets:
            return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        pass
    env_pw = os.environ.get("ADMIN_PASSWORD")
    if env_pw:
        return env_pw
    return "__unset__"  # no valid password will ever match this


def check_credentials(password: str) -> bool:
    """DEMO-grade auth check: compares against a secret configured via
    st.secrets / env var, never a value committed to source control.
    Still not a substitute for real SSO/identity provider in production."""
    configured = _get_admin_password()
    if configured == "__unset__":
        return False
    return password == configured


def admin_password_is_configured() -> bool:
    return _get_admin_password() != "__unset__"


# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------
def resolve_data_path() -> Optional[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(here, "accidents_cleaned_v1.csv")
    return candidate if os.path.exists(candidate) else None


@st.cache_data(show_spinner="Loading accident records...")
def load_data(path_or_buffer) -> pd.DataFrame:
    frame = pd.read_csv(path_or_buffer)
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    return frame


MONTHS_ORDER = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
TOD_ORDER = [
    "Morning Rush (5-10)",
    "Midday (10-16)",
    "Evening Rush (16-20)",
    "Night (20-24)",
    "Late Night (0-5)",
]


# ----------------------------------------------------------------------------
# Severity risk model — real scikit-learn model trained on this dataset
# ----------------------------------------------------------------------------
RISK_FEATURES_CAT = [
    "Weather_Conditions_Label",
    "Light_Conditions_Label",
    "Time_of_Day",
]
RISK_FEATURES_NUM = ["Speed_limit"]


@dataclass
class RiskModelBundle:
    model: GradientBoostingClassifier
    encoder: OrdinalEncoder
    cat_features: list
    num_features: list
    auc: float
    base_rate: float


@st.cache_resource(show_spinner="Training severity risk model...")
def train_risk_model(_frame: pd.DataFrame) -> RiskModelBundle:
    """Trains a real gradient-boosted tree classifier (scikit-learn) predicting
    Is_Severe from a small set of conditions. This is an intentionally simple,
    fast-training model for interactive use — not a production risk engine."""
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score

    data = _frame[RISK_FEATURES_CAT + RISK_FEATURES_NUM + ["Is_Severe"]].dropna().copy()
    encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    X_cat = encoder.fit_transform(data[RISK_FEATURES_CAT])
    X = np.hstack([X_cat, data[RISK_FEATURES_NUM].values])
    y = data["Is_Severe"].astype(int).values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    model = GradientBoostingClassifier(
        n_estimators=150, max_depth=3, learning_rate=0.1, random_state=42
    )
    model.fit(X_train, y_train)
    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])

    return RiskModelBundle(
        model=model,
        encoder=encoder,
        cat_features=RISK_FEATURES_CAT,
        num_features=RISK_FEATURES_NUM,
        auc=auc,
        base_rate=float(y.mean()),
    )


def predict_risk(
    bundle: RiskModelBundle,
    weather: str,
    light: str,
    time_of_day: str,
    speed_limit: int,
) -> float:
    row = pd.DataFrame([[weather, light, time_of_day]], columns=bundle.cat_features)
    encoded_cat = bundle.encoder.transform(row)
    X = np.hstack([encoded_cat, [[speed_limit]]])
    return float(bundle.model.predict_proba(X)[0, 1])


# ----------------------------------------------------------------------------
# What-if simulator
# ----------------------------------------------------------------------------
def simulate_whatif(
    frame: pd.DataFrame, roundabout_pct: float, camera_pct: float
) -> dict:
    """
    Illustrative "what-if" simulation grounded in patterns observed in THIS
    dataset (roundabouts vs. other junction types), plus one external assumption
    for speed cameras (not derivable from a single-year dataset with no
    before/after camera deployment data — flagged explicitly).

    roundabout_pct: share of non-roundabout junction accidents assumed converted
                    to roundabout-equivalent severity risk.
    camera_pct:     share of 60mph-road accidents assumed covered by average-speed
                    cameras, each cut by an ASSUMED 20% severe-outcome reduction
                    (illustrative, not derived from this dataset).
    """
    base_counts = frame["Accident_Severity_Label"].value_counts()
    base_fatal = int(base_counts.get("Fatal", 0))
    base_serious = int(base_counts.get("Serious", 0))
    base_slight = int(base_counts.get("Slight", 0))
    base_severe_rate = frame["Is_Severe"].mean()

    # Roundabout effect: derived from this dataset's own observed severe rates
    roundabout_severe_rate = frame.loc[
        frame["Junction_Detail_Label"] == "Roundabout", "Is_Severe"
    ].mean()
    other_junction_mask = frame["Junction_Detail_Label"].isin(
        ["Not at junction/within 20m", "T or staggered junction", "Crossroads"]
    )
    other_junction_severe_rate = frame.loc[other_junction_mask, "Is_Severe"].mean()
    n_convertible = int(other_junction_mask.sum())

    if pd.isna(roundabout_severe_rate) or pd.isna(other_junction_severe_rate):
        roundabout_delta_severe = 0
    else:
        rate_gap = max(other_junction_severe_rate - roundabout_severe_rate, 0)
        roundabout_delta_severe = n_convertible * (roundabout_pct / 100.0) * rate_gap

    # Speed camera effect: illustrative external assumption (20% severity cut)
    CAMERA_ASSUMED_REDUCTION = 0.20
    speed60_mask = frame["Speed_limit"] == 60
    n_speed60_severe = int((speed60_mask & frame["Is_Severe"]).sum())
    camera_delta_severe = (
        n_speed60_severe * (camera_pct / 100.0) * CAMERA_ASSUMED_REDUCTION
    )

    total_severe_reduction = roundabout_delta_severe + camera_delta_severe
    total_severe_reduction = min(total_severe_reduction, base_fatal + base_serious)

    # Distribute the reduction proportionally between fatal/serious, converting
    # those accidents down to "Slight" in the simulated outcome.
    if (base_fatal + base_serious) > 0:
        fatal_share = base_fatal / (base_fatal + base_serious)
    else:
        fatal_share = 0
    sim_fatal = max(base_fatal - total_severe_reduction * fatal_share, 0)
    sim_serious = max(base_serious - total_severe_reduction * (1 - fatal_share), 0)
    sim_slight = base_slight + total_severe_reduction

    sim_counts = {"Fatal": sim_fatal, "Serious": sim_serious, "Slight": sim_slight}
    base_cost = compute_economic_cost(frame)["total"]
    sim_cost = sum(sim_counts[s] * DFT_COST_MATRIX[s] for s in sim_counts)

    return {
        "base_counts": {
            "Fatal": base_fatal,
            "Serious": base_serious,
            "Slight": base_slight,
        },
        "sim_counts": sim_counts,
        "base_cost": base_cost,
        "sim_cost": sim_cost,
        "cost_saved": base_cost - sim_cost,
        "accidents_shifted": total_severe_reduction,
        "base_severe_rate": base_severe_rate,
    }
