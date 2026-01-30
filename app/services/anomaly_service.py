import pandas as pd
import numpy as np
from datetime import datetime
from models.metric import MetricModel
from models.anomaly_event import AnomalyEvent
from models.base import Base
from core.database import SessionLocal
from sqlalchemy.exc import SQLAlchemyError


from core.config import settings

class AnomalyEngine:
    __module__ = 'hour_sin'
    def __init__(self, contamination=None):
        self.contamination = contamination if contamination is not None else settings.CONTAMINATION

    def __repr__(self):
        return f"<AnomalyEngine features: hour_sin, hour_cos, weekday_sin, weekday_cos>"

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        if not np.issubdtype(df['ds'].dtype, np.datetime64):
            df['ds'] = pd.to_datetime(df['ds'])
        
        # Convert 'y' to numeric first, then check for NaNs
        # This ensures that if 'y' contains non-numeric values that become NaN,
        # they are handled by the interpolation logic.
        df['y'] = pd.to_numeric(df['y'], errors='coerce')

        if df['y'].isna().any():
            df = df.copy() # Only copy if we need to mutate (interpolate)
            df = df.set_index('ds')
            df['y'] = df['y'].interpolate(method='time').bfill().ffill()
            df = df.reset_index()
        return df

    def add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'hour_sin' in df.columns:
            return df
        
        df = df.copy()
        df['hour'] = df['ds'].dt.hour
        df['weekday'] = df['ds'].dt.weekday
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['weekday_sin'] = np.sin(2 * np.pi * df['weekday'] / 7)
        df['weekday_cos'] = np.cos(2 * np.pi * df['weekday'] / 7)
        return df

    def detect(self, df: pd.DataFrame, contamination=None, fingerprint: str = None) -> dict:
        if contamination is None:
            contamination = self.contamination
        if contamination <= 0.01:
            z_threshold = 2.0
        elif contamination <= 0.02:
            z_threshold = 2.5
        else:
            z_threshold = 3.0

        n = len(df)
        if n < 5:
            return {'is_anomaly': False, 'confidence': 0.0, 'reason': 'too_short'}
        last = float(df['y'].iloc[-1])
        hist = df['y'].iloc[:-1].dropna()
        if len(hist) < 3:
            mean = np.nanmean(df['y'])
            std = np.nanstd(df['y'])
        else:
            mean = hist.mean()
            std = hist.std(ddof=0)
        z = 0.0
        # Nếu std = 0 (dữ liệu cực kỳ ổn định), ta dùng một ngưỡng nhỏ để phát hiện thay đổi
        if std > 0:
            z = abs((last - mean) / std)
        elif abs(last - mean) > 0:
            # Trường hợp std=0 nhưng giá trị hiện tại khác giá trị lịch sử (ví dụ 1 rơi xuống 0)
            z = 10.0 # Force a high Z-score for any change from a perfect baseline
        
        confidence = float(min(1.0, z / 6.0))
        window = min(20, n)
        y_window = df['y'].iloc[-window:]
        x = np.arange(len(y_window))
        try:
            slope = np.polyfit(x, y_window, 1)[0]
        except Exception:
            slope = 0.0
        is_spike = z >= z_threshold
        is_trend = abs(slope) > (0.1 * max(1.0, np.nanmean(np.abs(y_window))))
        is_anom = bool(is_spike or is_trend)
        reason = 'spike' if is_spike else ('trend' if is_trend else 'normal')
        explanation = f"last={last:.3f}, mean={mean:.3f}, std={std:.3f}, z={z:.2f}, slope={slope:.4f}"

        # [NEW] Binary Metric Guard: Nếu là metric 'up' mà giá trị là 0, thì chắc chắn là lỗi
        # Kiểm tra fingerprint để biết đây là metric trạng thái
        # Fingerprint format: name=val|name2=val2...
        is_up_metric = fingerprint and (fingerprint.startswith('__name__=up|') or fingerprint == 'up' or '|__name__=up|' in fingerprint)
        
        if is_up_metric:
            if last == 0:
                is_anom = True
                reason = 'host_down'
                confidence = 1.0
                explanation = f"CRITICAL: Host is DOWN (up=0). {explanation}"

        if is_spike and reason != 'host_down':
            confidence = max(confidence, min(1.0, 0.3 + z / 4.0))
        if is_trend and reason != 'host_down':
            confidence = max(confidence, min(1.0, abs(slope) / (1 + abs(mean))))

        return {
            'is_anomaly': is_anom,
            'confidence': float(confidence),
            'reason': reason,
            'explanation': explanation
        }

    def train_and_detect(self, df: pd.DataFrame, contamination=None, fingerprint: str = None):
        df = self.preprocess(df)
        df = self.add_time_features(df)
        result = self.detect(df, contamination=contamination, fingerprint=fingerprint)
        return result
