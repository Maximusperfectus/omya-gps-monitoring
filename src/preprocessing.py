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

def inject_route_deviation(df):
    if df.empty:
        return df

    data = df.copy()

    # Select one truck randomly
    truck_id = data["truck_id"].sample(1, random_state=42).iloc[0]

    print(f"\nInjecting route deviation for truck: {truck_id}")

    # Select part of the journey
    truck_mask = data["truck_id"] == truck_id
    truck_data = data[truck_mask].copy()

    if len(truck_data) < 20:
        return data

    # Take middle segment of the trip
    start_idx = len(truck_data) // 3
    end_idx = start_idx + 10

    deviation_idx = truck_data.iloc[start_idx:end_idx].index

    """ # Apply deviation (shift coordinates)
    data.loc[deviation_idx, "latitude"] += 0.05
    data.loc[deviation_idx, "longitude"] += 0.05 """
    # Apply stronger deviation (more visible on map)
    data.loc[deviation_idx, "latitude"] += 0.1
    data.loc[deviation_idx, "longitude"] += 0.1

    print("Route deviation injected successfully")


    return data
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
def inject_strong_anomalies(trips):
    if trips.empty or len(trips) < 5:
        return trips

    df = trips.copy()

    # Select 3 random trips
    sample_idx = df.sample(5, random_state=42).index

    # 🔴 VERY LONG TRIP
    df.loc[sample_idx[0], "duration_min"] *= 2.5
    df.loc[sample_idx[0], "anomaly"] = "LONG_TRIP"

    # 🟠 VERY SHORT TRIP
    df.loc[sample_idx[1], "duration_min"] = 10
    df.loc[sample_idx[1], "anomaly"] = "SHORT_TRIP"

    # 🔴 EXTREME LONG TRIP
    df.loc[sample_idx[2], "duration_min"] = 300
    df.loc[sample_idx[2], "anomaly"] = "EX_LONG_TRIP"

    # Adjust end_time accordingly
    df.loc[sample_idx, "end_time"] = df.loc[sample_idx].apply(
        lambda row: pd.to_datetime(row["start_time"]) + pd.Timedelta(minutes=row["duration_min"]),
        axis=1
    )

    print("\nInjected strong anomalies on trips:")
    print(df.loc[sample_idx][["trip_id", "duration_min", "anomaly"]])

    return df

def main():
    print("Loading Bronze data...")
    df = pd.read_csv(INPUT_PATH)

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 👉 Inject route deviation BEFORE trip reconstruction
    df = inject_route_deviation(df)

    print("Reconstructing trips...")
    trips = reconstruct_trips(df)

    print("Trips created:", len(trips))

   
  
    print("Detecting anomalies...")
    trips = detect_anomalies(trips)

    # 👉 Inject strong anomalies AFTER detection
    trips = inject_strong_anomalies(trips)

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