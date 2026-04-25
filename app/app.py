import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
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

# ---------------------------------------------------
# CUSTOM STYLING
# ---------------------------------------------------
st.markdown("""
<style>
.main {
    background-color: #0E1117;
}

div[data-testid="metric-container"] {
    background-color: #1E1E1E;
    border: 1px solid #333;
    padding: 15px;
    border-radius: 12px;
}

h1, h2, h3 {
    color: white;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# LOAD DATA
# ---------------------------------------------------
@st.cache_data
def load_data():
    trips = pd.read_csv("data/processed/gps_silver_trips.csv")
    gps = pd.read_csv("data/processed/gps_bronze.csv")

    trips["start_time"] = pd.to_datetime(trips["start_time"])
    trips["end_time"] = pd.to_datetime(trips["end_time"])
    gps["timestamp"] = pd.to_datetime(gps["timestamp"])

    return trips, gps


# ---------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------
def calculate_route_distance(route_df):
    total_distance = 0

    for i in range(len(route_df) - 1):
        point1 = (
            route_df.iloc[i]["latitude"],
            route_df.iloc[i]["longitude"]
        )

        point2 = (
            route_df.iloc[i + 1]["latitude"],
            route_df.iloc[i + 1]["longitude"]
        )

        total_distance += geodesic(point1, point2).km

    return total_distance


def classify_stop_location(lat, lon):
    stop_point = (lat, lon)

    quarry_distance = geodesic(stop_point, QUARRY).km
    port_distance = geodesic(stop_point, PORT).km

    if quarry_distance < 5:
        return "Quarry"

    elif port_distance < 5:
        return "Port"

    else:
        return "Unknown / Deviated Area"


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
st.title("🚛 Omya Logistics Control Tower")
st.caption(
    "Real-time fleet monitoring | anomaly detection | route intelligence | financial impact"
)

# ---------------------------------------------------
# SIDEBAR
# ---------------------------------------------------
st.sidebar.title("Control Panel")
st.sidebar.success("🟢 System Online")

st.sidebar.caption(
    f"Last refresh: {datetime.now().strftime('%H:%M:%S')}"
)

selected_trucks = st.sidebar.multiselect(
    "Select Trucks",
    trips_df["truck_id"].unique(),
    default=trips_df["truck_id"].unique()
)

selected_anomalies = st.sidebar.multiselect(
    "Select Anomaly Type",
    trips_df["anomaly"].unique(),
    default=trips_df["anomaly"].unique()
)

# ---------------------------------------------------
# FILTER DATA
# ---------------------------------------------------
df_filtered = trips_df[
    (trips_df["truck_id"].isin(selected_trucks)) &
    (trips_df["anomaly"].isin(selected_anomalies))
]

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

# Cost calculation
excess_duration = df_filtered.apply(
    lambda row: max(row["duration_min"] - avg_duration, 0)
    if row["anomaly"] in ["LONG_TRIP", "EX_LONG_TRIP"]
    else 0,
    axis=1
).sum()

estimated_loss = (excess_duration / 60) * COST_PER_HOUR

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Total Trips", total_trips)
col2.metric("Avg Duration", f"{avg_duration:.1f} min")
col3.metric("Anomaly Rate", f"{anomaly_rate:.1f}%")
col4.metric("Active Trucks", active_trucks)  # pyright: ignore[reportArgumentType]
col5.metric("Estimated Loss", f"€{estimated_loss:,.0f}")

# ---------------------------------------------------
# ALERT CENTER
# ---------------------------------------------------
if anomaly_rate > 10:
    st.error("🚨 Critical operational anomalies detected")
elif anomaly_rate > 5:
    st.warning("⚠️ Operational anomalies require review")
else:
    st.success("✅ Operations running normally")

# ---------------------------------------------------
# TABS
# ---------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "Executive Overview",
    "Live Operations",
    "Investigation Center"
])

# ===================================================
# TAB 1: EXECUTIVE OVERVIEW
# ===================================================
with tab1:

    st.subheader("Operational Performance Overview")

    colA, colB = st.columns(2)

    # Pie Chart
    with colA:
        fig_pie = px.pie(
            df_filtered,
            names="anomaly",
            title="Anomaly Distribution"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # Trend Chart
    with colB:
        fig_line = px.line(
            df_filtered.sort_values("start_time"),  # pyright: ignore[reportCallIssue]
            x="start_time",
            y="duration_min",
            color="anomaly",
            markers=True,
            title="Trip Duration Trend Over Time",
            color_discrete_map={
                "NORMAL": "#00CC66",
                "SHORT_TRIP": "#FFD700",
                "LONG_TRIP": "#FFA500",
                "EX_LONG_TRIP": "#FF0000"
            }
        )

        fig_line.add_hline(
            y=avg_duration,
            line_dash="dash",
            line_color="white",
            annotation_text="Average Duration"
        )

        st.plotly_chart(fig_line, use_container_width=True)

    # Ranking Table
    st.subheader("Trip Performance Ranking")

    st.markdown("""
    ### Anomaly Legend

    🟥 EX_LONG_TRIP → Critical delay  
    🟧 LONG_TRIP → Delay  
    🟨 SHORT_TRIP → Suspicious fast trip  
    🟩 NORMAL → Normal trip  
    """)

    ranking = df_filtered.sort_values(  # pyright: ignore[reportCallIssue]
        by="duration_min",
        ascending=False
    )

    def highlight_trip_rows(row):
        if row["anomaly"] == "EX_LONG_TRIP":
            return ["background-color:red;color:white"] * len(row)

        elif row["anomaly"] == "LONG_TRIP":
            return ["background-color:orange;color:black"] * len(row)

        elif row["anomaly"] == "SHORT_TRIP":
            return ["background-color:yellow;color:black"] * len(row)

        else:
            return ["background-color:#1E1E1E;color:white"] * len(row)

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

    st.dataframe(
        styled_ranking,
        use_container_width=True
    )

# ===================================================
# TAB 2: LIVE OPERATIONS
# ===================================================
with tab2:

    st.subheader("Expected Route vs Actual Fleet Behavior")

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
        lambda x: "ANOMALY"
        if x in anomaly_trucks else "NORMAL"
    )

    fig_map = go.Figure()

    # Expected route
    fig_map.add_trace(
        go.Scattermapbox(
            mode="lines",
            lon=[101.12, 100.70],
            lat=[4.53, 4.25],
            line=dict(width=5, color="gray"),
            name="Expected Route"
        )
    )

    # Quarry marker
    fig_map.add_trace(
        go.Scattermapbox(
            mode="markers",
            lon=[101.12],
            lat=[4.53],
            marker=dict(size=18, color="green"),
            name="Quarry"
        )
    )

    # Port marker
    fig_map.add_trace(
        go.Scattermapbox(
            mode="markers",
            lon=[100.70],
            lat=[4.25],
            marker=dict(size=18, color="blue"),
            name="Port"
        )
    )

    # Actual truck routes
    for truck in route_df["truck_id"].unique():
        truck_data = route_df[
            route_df["truck_id"] == truck
        ]

        truck_status = truck_data["status"].iloc[0]  # pyright: ignore[reportAttributeAccessIssue]
        color = "red" if truck_status == "ANOMALY" else "lime"

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
# TAB 3: INVESTIGATION CENTER
# ===================================================
with tab3:

    st.subheader("Anomaly Investigation Center")

    anomaly_df = df_filtered[
        df_filtered["anomaly"] != "NORMAL"
    ]

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

        st.write("### Selected Trip Details")

        colA, colB, colC = st.columns(3)

        colA.metric(
            "Truck",
            selected_trip_data["truck_id"]
        )

        colB.metric(
            "Duration",
            f"{selected_trip_data['duration_min']:.1f} min"
        )

        colC.metric(
            "Anomaly",
            selected_trip_data["anomaly"]
        )

        trip_route = gps_df[
            (gps_df["truck_id"] == selected_trip_data["truck_id"]) &
            (gps_df["timestamp"] >= selected_trip_data["start_time"]) &
            (gps_df["timestamp"] <= selected_trip_data["end_time"])
        ].copy()

       
    if not trip_route.empty:  # pyright: ignore[reportPossiblyUnboundVariable]

            # Sort route properly
            trip_route = trip_route.sort_values("timestamp")  # pyright: ignore[reportCallIssue, reportPossiblyUnboundVariable]

            # Create animation frame
            trip_route["time_bucket"] = trip_route["timestamp"].dt.floor("1min")
            trip_route["time_str"] = trip_route["time_bucket"].astype(str)

            # Remove duplicate timestamps
            trip_route = trip_route.drop_duplicates(
                subset=["time_str"]
            )

            # -------------------------------
            # Animated replay
            # -------------------------------
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

            # Actual route = red
            fig_trip.update_traces(
                marker=dict(
                    size=14,
                    color="red"
                )
            )

            # -------------------------------
            # Add expected route
            # -------------------------------
            fig_trip.add_trace(
                go.Scattermapbox(
                    mode="lines",
                    lon=[101.12, 100.70],
                    lat=[4.53, 4.25],
                    line=dict(
                        width=5,
                        color="gray"
                    ),
                    name="Expected Route"
                )
            )

            # Quarry marker
            fig_trip.add_trace(
                go.Scattermapbox(
                    mode="markers",
                    lon=[101.12],
                    lat=[4.53],
                    marker=dict(
                        size=18,
                        color="green"
                    ),
                    name="Quarry"
                )
            )

            # Port marker
            fig_trip.add_trace(
                go.Scattermapbox(
                    mode="markers",
                    lon=[100.70],
                    lat=[4.25],
                    marker=dict(
                        size=18,
                        color="blue"
                    ),
                    name="Port"
                )
            )

            fig_trip.update_layout(
                mapbox_style="open-street-map",
                height=650
            )

            st.plotly_chart(
                fig_trip,
                use_container_width=True
            )


            # Distance analysis
            expected_distance = geodesic(
                QUARRY,
                PORT
            ).km

            actual_distance = calculate_route_distance(
                trip_route
            )

            extra_distance = (
                actual_distance - expected_distance
            )

            # Last stop
            last_point = trip_route.iloc[-1]

            stop_lat = last_point["latitude"]
            stop_lon = last_point["longitude"]

            stop_location = classify_stop_location(
                stop_lat,
                stop_lon
            )

            # Cost
            excess = max(
                selected_trip_data["duration_min"] - avg_duration,  # pyright: ignore[reportPossiblyUnboundVariable]
                0
            )

            trip_cost = (
                excess / 60
            ) * COST_PER_HOUR

            st.subheader("Investigation Insights")

            k1, k2, k3 = st.columns(3)

            k1.metric(
                "Extra Distance",
                f"{extra_distance:.1f} km"
            )

            k2.metric(
                "Stop Location",
                stop_location
            )

            k3.metric(
                "Estimated Loss",
                f"€{trip_cost:,.0f}"
            )

            st.write(
                f"📍 Exact Stop GPS Coordinates: "
                f"({stop_lat:.5f}, {stop_lon:.5f})"
            )

# ---------------------------------------------------
# FOOTER
# ---------------------------------------------------
st.markdown("---")

st.caption(
    "Omya Predictive Logistics Platform | Prototype v1"
)