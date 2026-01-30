import pandas as pd
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from models.metric import MetricValue

class HistoryCache:
    """
    Manages internal memory-resident history for all observed series.
    Eliminates the need for heavy DB reads during anomaly detection cycles.
    """
    def __init__(self):
        self._cache = {} # fingerprint -> DataFrame
        self.analysis_window_hours = 168

    def initialize(self, engine, analysis_window_hours=168):
        """Pre-load all data from DB for the last N hours."""
        self.analysis_window_hours = analysis_window_hours
        logging.info(f"🚀 [TurboMode] Loading {analysis_window_hours}h history into RAM...")
        
        threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=analysis_window_hours)
        
        # Load in chunks to avoid memory spikes and long initial response
        query = f"SELECT metric_id, timestamp as ds, value as y FROM metric_values WHERE timestamp >= '{threshold.isoformat()}'"
        
        chunk_count = 0
        total_rows = 0
        for chunk in pd.read_sql(query, engine, parse_dates=['ds'], chunksize=500000):
            chunk_count += 1
            total_rows += len(chunk)
            for m_id, group in chunk.groupby('metric_id'):
                if m_id not in self._cache:
                    self._cache[m_id] = group
                else:
                    self._cache[m_id] = pd.concat([self._cache[m_id], group], ignore_index=True)
            logging.info(f"🚀 [TurboMode] Loaded chunk {chunk_count}... ({total_rows} rows)")

        # Final sort for each cache entry
        for m_id in self._cache:
            self._cache[m_id] = self._cache[m_id].sort_values('ds')
        
        logging.info(f"✅ [TurboMode] Cached {total_rows} points across {len(self._cache)} metrics.")

    def get_history(self, metric_id: int) -> pd.DataFrame:
        return self._cache.get(metric_id, pd.DataFrame())

    def update(self, metric_id: int, df_delta: pd.DataFrame):
        """Append new points and prune old ones in-memory (Optimized)."""
        if df_delta.empty:
            return

        df_existing = self._cache.get(metric_id)
        
        if df_existing is None or df_existing.empty:
            self._cache[metric_id] = df_delta
            return

        # Prometheus data is usually sorted. We can just append.
        # But we check the last timestamp in existing to avoid overlaps
        last_ts = df_existing['ds'].iloc[-1]
        df_new_points = df_delta[df_delta['ds'] > last_ts]
        
        if df_new_points.empty:
            return

        df_combined = pd.concat([df_existing, df_new_points], ignore_index=True)

        # Rolling Prune (Only prune if the window is exceeded)
        threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=self.analysis_window_hours)
        if df_combined['ds'].iloc[0] < threshold:
            df_combined = df_combined[df_combined['ds'] >= threshold]
        
        self._cache[metric_id] = df_combined

history_cache = HistoryCache()
