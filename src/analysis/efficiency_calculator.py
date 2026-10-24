# src/analysis/efficiency_calculator.py

import os
import sqlite3
import pandas as pd
import numpy as np

class EfficiencyCalculator:
    def __init__(self, db_path=None):
        if db_path is None:
            data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'OficinaEficiencia', 'data')
            self.db_path = os.path.join(data_dir, 'db', 'local_tracking.db')
        else:
            self.db_path = db_path

    def load_data(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM tracking", conn)
        try:
            snapshots_df = pd.read_sql_query("SELECT * FROM snapshots", conn)
        except pd.io.sql.DatabaseError:
             # Table might not exist yet
            snapshots_df = pd.DataFrame(columns=['track_id', 'timestamp', 'zone', 'snapshot_path', 'employee_name'])
        conn.close()
        return df, snapshots_df

    def calculate_efficiency(self):
        df, snapshots_df = self.load_data()

        if df.empty:
            print("No hay datos en la base de datos.")
            return None

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        if not snapshots_df.empty:
            snapshots_df['timestamp'] = pd.to_datetime(snapshots_df['timestamp'])

        results = []

        # Group by track_id and zone to process visits
        # We need to detect transitions 0 -> 1 (Enter) and 1 -> 0 (Exit)
        grouped = df.sort_values(['track_id', 'zone', 'timestamp']).groupby(['track_id', 'zone'])

        for (track_id, zone), group in grouped:
            # Identify visits
            # We shift inside_zone to detect changes
            group['prev_inside'] = group['inside_zone'].shift(1, fill_value=0)

            # Every time we see 0->1, increment visit counter: a visit ends at its last
            # frame inside, so a track still inside at the end closes there.
            group['visit_start'] = (group['prev_inside'] == 0) & (group['inside_zone'] == 1)
            group['visit_id'] = group['visit_start'].cumsum()

            # Filter only rows inside zone
            visits = group[group['inside_zone'] == 1]

            if visits.empty:
                continue

            for visit_id, visit_data in visits.groupby('visit_id'):
                start_time = visit_data['timestamp'].min()
                end_time = visit_data['timestamp'].max()
                duration = (end_time - start_time).total_seconds()

                # Calculate Productivity / Activity
                # Heuristic: Standard deviation of position (normalized)
                # If std is low, they are standing still. If high, moving.
                std_x = visit_data['x'].std()
                std_y = visit_data['y'].std()
                if np.isnan(std_x): std_x = 0
                if np.isnan(std_y): std_y = 0
                activity_score = round(std_x + std_y, 2)

                # Find snapshot
                snapshot_path = "N/A"
                employee_name = "Unknown"
                if not snapshots_df.empty:
                    # Filter snapshots for this track and zone
                    snaps = snapshots_df[
                        (snapshots_df['track_id'] == track_id) &
                        (snapshots_df['zone'] == zone)
                    ]
                    if not snaps.empty:
                        # Find closest snapshot to start_time
                        # We expect snapshot at start_time exactly (or very close)
                        time_diffs = (snaps['timestamp'] - start_time).abs()
                        idx_min = time_diffs.idxmin()
                        # If the difference is reasonable (e.g. within 5 seconds), take it
                        if time_diffs[idx_min].total_seconds() < 5:
                            snapshot_path = snaps.loc[idx_min, 'snapshot_path']
                            if 'employee_name' in snaps.columns:
                                val = snaps.loc[idx_min, 'employee_name']
                                if val is not None and str(val).strip():
                                    employee_name = val

                results.append({
                    'track_id': track_id,
                    'employee_name': employee_name,
                    'zone': zone,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration_sec': round(duration, 2),
                    'productivity_score': activity_score,
                    'snapshot_path': snapshot_path
                })

        return pd.DataFrame(results)
