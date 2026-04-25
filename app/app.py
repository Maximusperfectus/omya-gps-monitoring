import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from geopy.distance import geodesic

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(
    page_title="Omya Logistics Control Tower",
    layout="wide"
)

# ---------------------------------------------------
# CONSTANTS
# ---------------------------------------------------
QUARRY = (4.53, 101.12)
PORT = (4.25, 100.70)
COST_PER_HOUR = 50

OMYA_BLUE = "#005DAA"
OMYA_RED = "#B32025"
OMYA_DARK_RED = "#7A0000"
OMYA_ORANGE = "#E58E00"
OMYA_GREEN = "#3C8C3A"

# ---------------------------------------------------
# STYLING
# ---------------------------------------------------
st.markdown("""
<style>
.main, .block-container {
    background-color: #FFFFFF;
}

.block-container {
    padding-top: 0.6rem;
    padding-bottom: 1rem;
    max-width: 100%;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #F7F9FB 0%, #EEF4FA 100%);
    border-right: 1px solid #DCE6F2;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #005DAA;
    font-weight: 700;
}

.status-card {
    background-color: #E8F5EE;
    border-left: 5px solid #3C8C3A;
    color: #1F6F3D;
    padding: 14px 16px;
    border-radius: 6px;
    font-weight: 700;
    margin-bottom: 14px;
}

.scope-card {
    background-color: #FFFFFF;
    border: 1px solid #DCE6F2;
    border-left: 5px solid #005DAA;
    color: #4D4D4D;
    padding: 14px 16px;
    border-radius: 6px;
    margin-bottom: 14px;
    line-height: 1.5;
}

/* Header */
.omya-topbar {
    border-bottom: 2px solid #005DAA;
    padding-bottom: 10px;
    margin-bottom: 18px;
}

.omya-logo-wrap {
    display: flex;
    align-items: flex-start;
    justify-content: flex-end;
    height: 120px;
    padding-right: 8px;
    padding-top: 18px;
}

.omya-title-wrap {
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    height: 120px;
    padding-top: 12px;
}

.omya-header-title-centered {
    color: #005DAA;
    font-size: 46px;
    font-weight: 850;
    text-align: center;
    letter-spacing: 0.4px;
    line-height: 1.05;
    margin-bottom: 8px;
}

.omya-header-subtitle-centered {
    color: #4D4D4D;
    font-size: 16px;
    font-weight: 650;
    text-align: center;
    margin-bottom: 4px;
}

.omya-header-subtitle-centered-light {
    color: #6F7782;
    font-size: 13px;
    text-align: center;
}

/* KPI Cards */
div[data-testid="metric-container"] {
    background-color: #F7F9FB;
    border: 1px solid #DCE6F2;
    border-radius: 6px;
    padding: 16px 18px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

div[data-testid="metric-container"] label {
    color: #005DAA !important;
    font-weight: 700;
    font-size: 13px;
}

div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #2F343A;
    font-size: 30px;
    font-weight: 750;
}

/* Sections */
.omya-section {
    color: #005DAA;
    font-weight: 800;
    font-size: 19px;
    margin-top: 18px;
    margin-bottom: 12px;
    border-bottom: 1px solid #DCE6F2;
    padding-bottom: 6px;
}

/* Tabs */
button[data-baseweb="tab"] {
    font-weight: 700;
    color: #4D4D4D;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #005DAA;
    border-bottom: 3px solid #005DAA;
}

/* Filter tags */
span[data-baseweb="tag"] {
    background-color: #005DAA !important;
    color: #FFFFFF !important;
    border-radius: 4px !important;
    font-weight: 600 !important;
}

/* Tables */
div[data-testid="stDataFrame"] {
    border: 1px solid #DCE6F2;
    border-radius: 6px;
}

/* Alerts */
div[data-testid="stAlert"] {
    border-radius: 6px;
    font-weight: 600;
}

/* Footer */
.omya-footer {
    background-color: #005DAA;
    color: #FFFFFF;
    padding: 8px 12px;
    font-size: 12px;
    margin-top: 28px;
    border-radius: 2px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# LOAD DATA
# ---------------------------------------------------
@st.cache_data(ttl=30)
def load_data():
    trips = pd.read_csv("data/processed/gps_silver_trips.csv")
    gps = pd.read_csv("data/processed/gps_bronze.csv")

    trips["start_time"] = pd.to_datetime(trips["start_time"], errors="coerce")
    trips["end_time"] = pd.to_datetime(trips["end_time"], errors="coerce")
    gps["timestamp"] = pd.to_datetime(gps["timestamp"], errors="coerce")

    return trips, gps


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------
def calculate_route_distance(route_df):
    total_distance = 0

    if len(route_df) < 2:
        return 0

    for i in range(len(route_df) - 1):
        p1 = (route_df.iloc[i]["latitude"], route_df.iloc[i]["longitude"])
        p2 = (route_df.iloc[i + 1]["latitude"], route_df.iloc[i + 1]["longitude"])
        total_distance += geodesic(p1, p2).km

    return total_distance


def classify_stop_location(lat, lon):
    stop_point = (lat, lon)
    quarry_distance = geodesic(stop_point, QUARRY).km
    port_distance = geodesic(stop_point, PORT).km

    if quarry_distance < 5:
        return "Quarry"
    if port_distance < 5:
        return "Port"

    return "Unknown / Deviated Area"


def highlight_trip_rows(row):
    if row["anomaly"] == "EX_LONG_TRIP":
        return ["background-color:#7A0000;color:white"] * len(row)

    if row["anomaly"] == "LONG_TRIP":
        return ["background-color:#B32025;color:white"] * len(row)

    if row["anomaly"] == "SHORT_TRIP":
        return ["background-color:#E58E00;color:black"] * len(row)

    return ["background-color:#F7F9FB;color:#4D4D4D"] * len(row)


# ---------------------------------------------------
# LOAD FILES
# ---------------------------------------------------
try:
    trips_df, gps_df = load_data()
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# ---------------------------------------------------
# HEADER
# ---------------------------------------------------
logo_path = "assets/omya_logo.png"

st.markdown('<div class="omya-topbar">', unsafe_allow_html=True)

h1, h2, h3 = st.columns([1.15, 7.2, 2])

with h1:
    if os.path.exists(logo_path):
        st.markdown(
            """
            <div style="
                display:flex;
                justify-content:flex-end;
                align-items:flex-start;
                margin-top:-18px;
                padding-right:8px;
            ">
            """,
            unsafe_allow_html=True
        )

        st.image(
            logo_path,
            width=105
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )

with h2:
    st.markdown(
        """
        <div class="omya-title-wrap">
            <div class="omya-header-title-centered">
                Logistics Control Tower
            </div>
            <div class="omya-header-subtitle-centered">
                End-to-End Fleet Visibility | Route Compliance Monitoring | Operational Risk Detection
            </div>
            <div class="omya-header-subtitle-centered-light">
                Malaysia Operations · Quarry → Lumut Port · Real-Time Intelligence · Financial Exposure Tracking
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with h3:
    st.markdown(
        f"""
        <div style="text-align:right;font-size:12px;color:#4D4D4D;padding-top:18px;">
            Scope: Quarry to Lumut Port<br>
            Last update: {datetime.now().strftime('%d %b %Y %H:%M')}
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------
# SIDEBAR
# ---------------------------------------------------
st.sidebar.markdown("# Control Panel")

st.sidebar.markdown(
    """
    <div class="status-card">
    System Online
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

st.sidebar.markdown("### Monitoring Scope")

st.sidebar.markdown(
    """
    <div class="scope-card">
    <b>Malaysia Operations</b><br>
    Quarry to Lumut Port<br>
    Fleet Route Compliance
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown("### Filters")

truck_options = sorted(trips_df["truck_id"].dropna().unique())

selected_trucks = st.sidebar.multiselect(
    "Truck",
    truck_options,
    default=truck_options
)

anomaly_options = sorted(trips_df["anomaly"].dropna().unique())

selected_anomalies = st.sidebar.multiselect(
    "Anomaly Type",
    anomaly_options,
    default=anomaly_options
)

# ---------------------------------------------------
# FILTER DATA
# ---------------------------------------------------
df_filtered = trips_df[
    (trips_df["truck_id"].isin(selected_trucks)) &
    (trips_df["anomaly"].isin(selected_anomalies))
].copy()

# ---------------------------------------------------
# KPI SECTION
# ---------------------------------------------------
total_trips = len(df_filtered)

avg_duration = (
    df_filtered["duration_min"].mean()
    if not df_filtered.empty else 0
)

anomaly_rate = (
    (df_filtered["anomaly"] != "NORMAL").mean() * 100
    if not df_filtered.empty else 0
)

active_trucks = (
    df_filtered["truck_id"].nunique()  # pyright: ignore[reportAttributeAccessIssue]
    if not df_filtered.empty else 0
)

excess_duration = df_filtered.apply(
    lambda row: max(row["duration_min"] - avg_duration, 0)
    if row["anomaly"] in ["LONG_TRIP", "EX_LONG_TRIP"]
    else 0,
    axis=1
).sum() if not df_filtered.empty else 0

estimated_loss = (excess_duration / 60) * COST_PER_HOUR

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Total Trips", f"{total_trips:,}")
k2.metric("Avg Duration", f"{avg_duration:.1f} min")
k3.metric("Anomaly Rate", f"{anomaly_rate:.1f}%")
k4.metric("Active Trucks", f"{active_trucks:,}")
k5.metric("Estimated Loss", f"€{estimated_loss:,.0f}")

# ---------------------------------------------------
# ALERT CENTER
# ---------------------------------------------------
if anomaly_rate > 10:
    st.error("Critical operational anomalies detected")
elif anomaly_rate > 5:
    st.warning("Operational anomalies require review")
else:
    st.success("Operations running within expected range.")

# ---------------------------------------------------
# TABS
# ---------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "Overview",
    "Live Operations",
    "Investigation Center"
])

# ===================================================
# TAB 1
# ===================================================
with tab1:

    st.markdown(
        '<div class="omya-section">Operational Performance Overview</div>',
        unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)

    with c1:
        fig_pie = px.pie(
            df_filtered,
            names="anomaly",
            color="anomaly",
            title="Anomaly Distribution",
            color_discrete_map={
                "NORMAL": OMYA_GREEN,
                "SHORT_TRIP": OMYA_ORANGE,
                "LONG_TRIP": OMYA_RED,
                "EX_LONG_TRIP": OMYA_DARK_RED
            }
        )

        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        fig_line = px.line(
            df_filtered.sort_values("start_time"),  # pyright: ignore[reportCallIssue]
            x="start_time",
            y="duration_min",
            color="anomaly",
            markers=True,
            title="Trip Duration Trend Over Time",
            color_discrete_map={
                "NORMAL": OMYA_GREEN,
                "SHORT_TRIP": OMYA_ORANGE,
                "LONG_TRIP": OMYA_RED,
                "EX_LONG_TRIP": OMYA_DARK_RED
            }
        )

        fig_line.add_hline(
            y=avg_duration,
            line_dash="dash",
            line_color=OMYA_BLUE,
            annotation_text="Average Duration"
        )

        st.plotly_chart(fig_line, use_container_width=True)

    st.markdown(
        '<div class="omya-section">Trip Performance Ranking</div>',
        unsafe_allow_html=True
    )

    ranking = df_filtered.sort_values(  # pyright: ignore[reportCallIssue]
        by="duration_min",
        ascending=False
    )

    styled_ranking = ranking[
        [
            "truck_id",
            "duration_min",
            "anomaly",
            "start_time",
            "end_time"
        ]
    ].style.apply(
        highlight_trip_rows,
        axis=1
    )

    st.dataframe(styled_ranking, use_container_width=True)

# ===================================================
# TAB 2
# ===================================================
with tab2:

    st.markdown(
        '<div class="omya-section">Live Fleet Route Monitoring</div>',
        unsafe_allow_html=True
    )

    route_df = gps_df.copy()

    route_df = route_df[
        route_df["truck_id"].isin(selected_trucks)
    ]

    route_df = route_df.sort_values(  # pyright: ignore[reportCallIssue]
        by=["truck_id", "timestamp"]
    )

    route_df = route_df.tail(1000)

    anomaly_trucks = df_filtered.loc[
        df_filtered["anomaly"] != "NORMAL",
        "truck_id"
    ].unique()

    route_df["status"] = route_df["truck_id"].apply(
        lambda x: "ANOMALY" if x in anomaly_trucks else "NORMAL"
    )

    fig_map = go.Figure()

    fig_map.add_trace(
        go.Scattermapbox(
            mode="lines",
            lon=[101.12, 100.70],
            lat=[4.53, 4.25],
            line=dict(width=5, color="gray"),
            name="Expected Route"
        )
    )

    fig_map.add_trace(
        go.Scattermapbox(
            mode="markers",
            lon=[101.12],
            lat=[4.53],
            marker=dict(size=18, color=OMYA_GREEN),
            name="Quarry"
        )
    )

    fig_map.add_trace(
        go.Scattermapbox(
            mode="markers",
            lon=[100.70],
            lat=[4.25],
            marker=dict(size=18, color=OMYA_BLUE),
            name="Port"
        )
    )

    for truck in route_df["truck_id"].unique():

        truck_data = route_df[route_df["truck_id"] == truck]
        truck_status = truck_data["status"].iloc[0]  # pyright: ignore[reportAttributeAccessIssue]

        color = OMYA_RED if truck_status == "ANOMALY" else OMYA_GREEN

        fig_map.add_trace(
            go.Scattermapbox(
                mode="markers+lines",
                lon=truck_data["longitude"],
                lat=truck_data["latitude"],
                marker=dict(size=10, color=color),
                line=dict(width=2, color=color),
                name=f"Truck {truck}"
            )
        )

    fig_map.update_layout(
        mapbox_style="open-street-map",
        mapbox_zoom=7,
        mapbox_center={"lat": 4.4, "lon": 100.9},
        height=700
    )

    st.plotly_chart(fig_map, use_container_width=True)

# ===================================================
# TAB 3
# ===================================================
with tab3:

    st.markdown(
        '<div class="omya-section">Anomaly Investigation Center</div>',
        unsafe_allow_html=True
    )

    anomaly_df = df_filtered[df_filtered["anomaly"] != "NORMAL"]

    if anomaly_df.empty:  # pyright: ignore[reportAttributeAccessIssue]
        st.success("No anomalies detected.")

    else:
        selected_trip = st.selectbox(
            "Select Trip to Investigate",
            anomaly_df["trip_id"]
        )

        selected_trip_data = anomaly_df[
            anomaly_df["trip_id"] == selected_trip
        ].iloc[0]  # pyright: ignore[reportAttributeAccessIssue]

        c1, c2, c3 = st.columns(3)

        c1.metric("Truck", selected_trip_data["truck_id"])
        c2.metric("Duration", f"{selected_trip_data['duration_min']:.1f} min")
        c3.metric("Anomaly", selected_trip_data["anomaly"])

        trip_route = gps_df[
            (gps_df["truck_id"] == selected_trip_data["truck_id"]) &
            (gps_df["timestamp"] >= selected_trip_data["start_time"]) &
            (gps_df["timestamp"] <= selected_trip_data["end_time"])
        ].copy()

        if not trip_route.empty:

            trip_route = trip_route.sort_values("timestamp")  # pyright: ignore[reportCallIssue]

            trip_route["time_bucket"] = trip_route["timestamp"].dt.floor("1min")
            trip_route["time_str"] = trip_route["time_bucket"].astype(str)

            trip_route = trip_route.drop_duplicates(subset=["time_str"])

            fig_trip = px.scatter_mapbox(
                trip_route,
                lat="latitude",
                lon="longitude",
                animation_frame="time_str",
                animation_group="truck_id",
                hover_name="truck_id",
                zoom=8,
                height=650
            )

            fig_trip.update_traces(
                marker=dict(size=14, color=OMYA_RED)
            )

            fig_trip.add_trace(
                go.Scattermapbox(
                    mode="lines",
                    lon=[101.12, 100.70],
                    lat=[4.53, 4.25],
                    line=dict(width=5, color="gray"),
                    name="Expected Route"
                )
            )

            fig_trip.add_trace(
                go.Scattermapbox(
                    mode="markers",
                    lon=[101.12],
                    lat=[4.53],
                    marker=dict(size=18, color=OMYA_GREEN),
                    name="Quarry"
                )
            )

            fig_trip.add_trace(
                go.Scattermapbox(
                    mode="markers",
                    lon=[100.70],
                    lat=[4.25],
                    marker=dict(size=18, color=OMYA_BLUE),
                    name="Port"
                )
            )

            fig_trip.update_layout(mapbox_style="open-street-map")

            st.plotly_chart(fig_trip, use_container_width=True)

            expected_distance = geodesic(QUARRY, PORT).km
            actual_distance = calculate_route_distance(trip_route)
            extra_distance = actual_distance - expected_distance

            last_point = trip_route.iloc[-1]

            stop_lat = last_point["latitude"]
            stop_lon = last_point["longitude"]

            stop_location = classify_stop_location(stop_lat, stop_lon)

            excess = max(selected_trip_data["duration_min"] - avg_duration, 0)
            trip_cost = (excess / 60) * COST_PER_HOUR

            i1, i2, i3 = st.columns(3)

            i1.metric("Extra Distance", f"{extra_distance:.1f} km")
            i2.metric("Stop Location", stop_location)
            i3.metric("Estimated Loss", f"€{trip_cost:,.0f}")

            st.write(
                f"📍 Exact Stop GPS Coordinates: "
                f"({stop_lat:.5f}, {stop_lon:.5f})"
            )

# ---------------------------------------------------
# FOOTER
# ---------------------------------------------------
st.markdown(
    f"""
    <div class="omya-footer">
    PTL1.1 · Logistics Control Tower · Version 1.0 ·
    Last update: {datetime.now().strftime('%d %b %Y %H:%M')}
    </div>
    """,
    unsafe_allow_html=True
)