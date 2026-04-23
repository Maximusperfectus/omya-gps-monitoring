import pandas as pd
from geopy.distance import geodesic
import uuid
import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

INPUT_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "gps_bronze.csv")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "gps_silver_trips.csv")

# Zones (based on your data visualization)
QUARRY = (4.53, 101.12)
PORT = (4.25, 100.70)

RADIUS_KM = 3
MAX_TRIP_MIN = 180  # 🚨 critical fix


def is_in_zone(lat, lon, center):
    try:
        return geodesic((lat, lon), center).km <= RADIUS_KM
    except:
        return False


def reconstruct_trips(df):
    trips = []

    df = df.sort_values(by=["truck_id", "timestamp"])

    for truck_id, group in df.groupby("truck_id"):
        group = group.reset_index(drop=True)

        state = "IDLE"
        trip_start = None

        for _, row in group.iterrows():
            lat, lon = row["latitude"], row["longitude"]

            in_quarry = is_in_zone(lat, lon, QUARRY)
            in_port = is_in_zone(lat, lon, PORT)

            # Step 1: detect presence in quarry
            if state == "IDLE" and in_quarry:
                state = "LOADING_ZONE"

            # Step 2: leaving quarry = trip start
            elif state == "LOADING_ZONE" and not in_quarry:
                state = "ON_ROUTE"
                trip_start = row["timestamp"]

            # Step 3: on route logic
            elif state == "ON_ROUTE":

                trip_duration = (row["timestamp"] - trip_start).total_seconds() / 60

                # 🚨 FILTER unrealistic long trips
                if trip_duration > MAX_TRIP_MIN:
                    state = "IDLE"
                    trip_start = None
                    continue

                # Normal arrival at port
                if in_port:
                    trip_end = row["timestamp"]

                    trips.append({
                        "trip_id": str(uuid.uuid4()),
                        "truck_id": truck_id,
                        "start_time": trip_start,
                        "end_time": trip_end,
                        "duration_min": trip_duration
                    })

                    state = "IDLE"

    return pd.DataFrame(trips)


def detect_anomalies(trips):
    if trips.empty:
        return trips

    trips["anomaly"] = "NORMAL"

    avg_duration = trips["duration_min"].mean()

    # Long trips
    trips.loc[trips["duration_min"] > avg_duration * 1.5, "anomaly"] = "LONG_TRIP"

    # Short trips
    trips.loc[trips["duration_min"] < avg_duration * 0.5, "anomaly"] = "SHORT_TRIP"

    return trips


def simulate_anomaly(trips):
    if trips.empty:
        return trips

    idx = trips.sample(1).index[0]

    print("\nSimulating anomaly on trip:", trips.loc[idx, "trip_id"])

    # Force strong anomaly
    trips.loc[idx, "duration_min"] = 200

    trips.loc[idx, "end_time"] = (
        pd.to_datetime(trips.loc[idx, "start_time"]) +
        pd.Timedelta(minutes=200)
    )

    return trips


def main():
    print("Loading Bronze data...")
    df = pd.read_csv(INPUT_PATH)

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    print("Reconstructing trips...")
    trips = reconstruct_trips(df)

    print("Trips created:", len(trips))

    # 👉 simulate anomaly BEFORE detection
    trips = simulate_anomaly(trips)

    print("Detecting anomalies...")
    trips = detect_anomalies(trips)

    print("\nAverage duration:", trips["duration_min"].mean())

    print("\nAnomalies detected:")
    print(trips[trips["anomaly"] != "NORMAL"])

    print("\nSample output:")
    print(trips.head())

    # Save
    trips.to_csv(OUTPUT_PATH, index=False)

    print("\nSaved to:", OUTPUT_PATH)


if __name__ == "__main__":
    main()