import pandas as pd
import os

# Paths (robust)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

DATA_PATH = os.path.join(PROJECT_ROOT, "data", "raw")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "processed")


def process_event_file(file_path, header):
    df = pd.read_excel(file_path, header=header)
    df.columns = df.columns.str.strip()

    df = df.rename(columns={
        "Plate No": "truck_id",
        "Begin Date": "start_time",
        "End Date": "end_time",
        "Duration": "duration",
        "Status": "status",
        "Address": "address"
    })

    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
    df["end_time"] = pd.to_datetime(df["end_time"], errors="coerce")

    df["computed_duration"] = (df["end_time"] - df["start_time"]).dt.total_seconds() / 60
    df["source"] = "EVENTS"

    return df


def process_csh_file(file_path):
    # 👉 Force correct sheet
    df = pd.read_excel(file_path, sheet_name="Lumut")

    df.columns = df.columns.str.strip()

    print("Detected GPS columns:", df.columns.tolist())

    # Rename only what we need
    df = df.rename(columns={
        "Device Name": "truck_id",
        "GPS & Time": "timestamp",
        "Speed (Km/h)": "speed",
        "Lat.&Lng.": "lat_lng"
    })

    # Split lat/lng
    def split_lat_lng(value):
        try:
            lat, lng = value.split(",")
            return float(lat.strip()), float(lng.strip())
        except:
            return None, None

    df[["latitude", "longitude"]] = df["lat_lng"].apply(
        lambda x: pd.Series(split_lat_lng(str(x)))
    )

    # Convert types
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["speed"] = pd.to_numeric(df["speed"], errors="coerce")

    # Clean
    df = df.dropna(subset=["truck_id", "timestamp", "latitude", "longitude"])

    df["source"] = "CSH"

    return df[["truck_id", "timestamp", "latitude", "longitude", "speed", "source"]]


def main():
    gps_data = []
    event_data = []

    files = [
        f for f in os.listdir(DATA_PATH)
        if f.endswith(".xlsx") and not f.startswith("~$")
    ]

    for file in files:
        file_path = os.path.join(DATA_PATH, file)

        print("\nProcessing file:", file)

        try:
            if "CSH" in file or "Movement" in file:
                df = process_csh_file(file_path)
                gps_data.append(df)
                print("GPS rows:", len(df))

            else:
                df_preview = pd.read_excel(file_path, header=None)
                header_row = None
                for i in range(10):
                    row_values = df_preview.iloc[i].astype(str).tolist()
                    if "Plate No" in row_values:
                        header_row = i
                        break

                if header_row is not None:
                    df_event = process_event_file(file_path, header_row)
                    event_data.append(df_event)
                    print("Event rows:", len(df_event))
                else:
                    print("Unknown format")

        except Exception as e:
            print("Error:", e)

    os.makedirs(OUTPUT_PATH, exist_ok=True)

    if gps_data:
        final_gps = pd.concat(gps_data, ignore_index=True)
        final_gps = final_gps.drop_duplicates()
        final_gps = final_gps.sort_values(by=["truck_id", "timestamp"])

        final_gps.to_csv(os.path.join(OUTPUT_PATH, "gps_bronze.csv"), index=False)
        final_gps.to_parquet(os.path.join(OUTPUT_PATH, "gps_bronze.parquet"), index=False)

        print("\nGPS Bronze created")

    if event_data:
        final_events = pd.concat(event_data, ignore_index=True)
        final_events.to_csv(os.path.join(OUTPUT_PATH, "gps_events_bronze.csv"), index=False)

        print("Events Bronze created")


if __name__ == "__main__":
    main()