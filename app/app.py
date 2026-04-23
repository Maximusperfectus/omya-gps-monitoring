import streamlit as st
import pandas as pd
import plotly.express as px

# -----------------------------
# LOAD DATA (SAFE)
# -----------------------------
try:
    trips_df = pd.read_csv("data/processed/gps_silver_trips.csv")
    gps_df = pd.read_csv("data/processed/gps_bronze.csv")
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# Convert datetime
trips_df["start_time"] = pd.to_datetime(trips_df["start_time"], errors="coerce")
gps_df["timestamp"] = pd.to_datetime(gps_df["timestamp"], errors="coerce")

# -----------------------------
# TITLE
# -----------------------------
st.title("🚛 Omya GPS Monitoring Dashboard")

# -----------------------------
# FILTERS
# -----------------------------
st.sidebar.header("Filters")

selected_truck = st.sidebar.multiselect(
    "Select Truck",
    trips_df["truck_id"].unique(),
    default=trips_df["truck_id"].unique()
)

df_filtered = trips_df[trips_df["truck_id"].isin(selected_truck)]

# -----------------------------
# KPIs (TOP - ALL TOGETHER)
# -----------------------------
total_trips = len(df_filtered)
avg_duration = df_filtered["duration_min"].mean() if not df_filtered.empty else 0
anomaly_rate = (df_filtered["anomaly"] != "NORMAL").mean() * 100 if not df_filtered.empty else 0
long_trips = (df_filtered["anomaly"] == "LONG_TRIP").sum() if not df_filtered.empty else 0

# -----------------------------
# COST IMPACT (MOVED HERE)
# -----------------------------
COST_PER_HOUR = 50

excess_duration = df_filtered.apply(
    lambda row: max(row["duration_min"] - avg_duration, 0)
    if row["anomaly"] == "LONG_TRIP" else 0,
    axis=1
).sum()

estimated_loss = (excess_duration / 60) * COST_PER_HOUR

# -----------------------------
# DISPLAY KPIs
# -----------------------------
col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Total Trips", total_trips)
col2.metric("Avg Duration (min)", round(avg_duration, 1))  # pyright: ignore[reportArgumentType]
col3.metric("Anomaly %", f"{anomaly_rate:.1f}%")
col4.metric("Long Trips", long_trips)
col5.metric("Estimated Loss (€)", round(estimated_loss, 0))


# -----------------------------
# ALERT BANNER
# -----------------------------
if long_trips > 0:
    st.error(f"🚨 {long_trips} anomaly trips detected impacting operations")
if anomaly_rate > 5:
    st.error("🚨 High anomaly rate detected!")
elif anomaly_rate > 0:
    st.warning("⚠️ Some anomalies detected")
else:
    st.success("✅ Operations normal")



# -----------------------------
# DISTRIBUTION
# -----------------------------
st.subheader("Trip Duration Distribution")

fig_hist = px.histogram(
    df_filtered,
    x="duration_min",
    nbins=20,
    title="Trip Duration"
)

st.plotly_chart(fig_hist)

# -----------------------------
# ANOMALY BREAKDOWN
# -----------------------------
st.subheader("Anomaly Breakdown")

fig_pie = px.pie(
    df_filtered,
    names="anomaly",
    title="Anomaly Distribution"
)

st.plotly_chart(fig_pie)

# -----------------------------
# REPLAY MAP (FINAL VERSION)
# -----------------------------
st.subheader("⏱️ Truck Movement Replay")

if not gps_df.empty:

    # Prepare data
    route_df = gps_df.copy()

    # Filter selected trucks
    route_df = route_df[route_df["truck_id"].isin(selected_truck)]

    # Sort properly
    route_df = route_df.sort_values(by=["truck_id", "timestamp"])  # pyright: ignore[reportCallIssue]

    # -----------------------------
    # SPEED CONTROL (CRITICAL)
    # -----------------------------
    # Reduce time granularity → smoother animation
    route_df["time_bucket"] = route_df["timestamp"].dt.floor("1min")

    # Remove duplicates per minute
    route_df = route_df.drop_duplicates(
        subset=["truck_id", "time_bucket"]
    )

    # Convert to string for animation
    route_df["time_str"] = route_df["time_bucket"].astype(str)

    # -----------------------------
    # LIMIT DATA (PERFORMANCE)
    # -----------------------------
    route_df = route_df.tail(1000)

    # -----------------------------
    # ANOMALY LOGIC
    # -----------------------------
    if "anomaly" in df_filtered.columns:
        anomaly_trucks = df_filtered.loc[
            df_filtered["anomaly"] != "NORMAL", "truck_id"
        ].unique()
    else:
        anomaly_trucks = []

    route_df["status"] = route_df["truck_id"].apply(
        lambda x: "ANOMALY" if x in anomaly_trucks else "NORMAL"
    )

    # -----------------------------
    # MAP (ANIMATED)
    # -----------------------------
    fig_anim = px.scatter_mapbox(
        route_df,
        lat="latitude",
        lon="longitude",
        color="status",
        animation_frame="time_str",
        animation_group="truck_id",
        hover_name="truck_id",
        zoom=7,
        height=600,
      color_discrete_map={
        "NORMAL": "#00CC66",   # softer green
        "ANOMALY": "#FF0000"   # strong red
        }
    )

    # Bigger markers (visibility)
    fig_anim.update_traces(
        marker=dict(size=12, opacity=0.9)
    )

    # Map style
    fig_anim.update_layout(
        mapbox_style="open-street-map",
        legend=dict(font=dict(size=14))
    )

    st.plotly_chart(fig_anim)

else:
    st.warning("No GPS data available")
# -----------------------------
# TABLE
# -----------------------------
st.subheader("🚨 Anomalies Only")

st.dataframe(
    df_filtered[df_filtered["anomaly"] != "NORMAL"]  # pyright: ignore[reportCallIssue]
    .sort_values(by="duration_min", ascending=False),  # pyright: ignore[reportAttributeAccessIssue]
    use_container_width=True
)
st.subheader("Trip Details")

def highlight_anomaly(row):
    if row["anomaly"] == "LONG_TRIP":
        return ["background-color: #FF4B4B; color: white"] * len(row)
    elif row["anomaly"] == "SHORT_TRIP":
        return ["background-color: #FFA500; color: black"] * len(row)
    else:
        return [""] * len(row)

styled_df = df_filtered.sort_values(  # pyright: ignore[reportCallIssue]
    by="duration_min", ascending=False
).style.apply(highlight_anomaly, axis=1)

st.dataframe(styled_df, use_container_width=True)

st.subheader("🎯 Investigate Anomaly")

anomaly_df = df_filtered[df_filtered["anomaly"] != "NORMAL"]

if not anomaly_df.empty:  # pyright: ignore[reportAttributeAccessIssue]
    selected_trip_id = st.selectbox(
        "Select anomaly trip",
        anomaly_df["trip_id"]
    )

    selected_trip = anomaly_df[anomaly_df["trip_id"] == selected_trip_id].iloc[0]  # pyright: ignore[reportAttributeAccessIssue]

    st.write("### Trip Details")
    st.write({
        "Truck": selected_trip["truck_id"],
        "Start": selected_trip["start_time"],
        "End": selected_trip["end_time"],
        "Duration (min)": selected_trip["duration_min"],
        "Anomaly": selected_trip["anomaly"]
    })

    truck_id = selected_trip["truck_id"]

    trip_route = gps_df[
        (gps_df["truck_id"] == truck_id) &
        (gps_df["timestamp"] >= selected_trip["start_time"]) &
        (gps_df["timestamp"] <= selected_trip["end_time"])
    ].copy()

    trip_route = trip_route.sort_values("timestamp")  # pyright: ignore[reportCallIssue]

    st.subheader("⏱️ Replay Selected Trip")

    trip_route["time_str"] = trip_route["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

    fig_trip = px.scatter_mapbox(
        trip_route,
        lat="latitude",
        lon="longitude",
        animation_frame="time_str",
        animation_group="truck_id",
        hover_name="truck_id",
        zoom=7,
        height=500
    )

    fig_trip.update_layout(mapbox_style="open-street-map")

    fig_trip.update_traces(
        marker=dict(size=14, color="red")
    )

    st.plotly_chart(fig_trip)

    st.subheader("💰 Cost Impact")

    excess = max(selected_trip["duration_min"] - avg_duration, 0)
    cost = (excess / 60) * COST_PER_HOUR

    st.metric("Estimated Cost (€)", round(cost, 0))