import os
import time
import json
import logging
from datetime import datetime, timedelta

from core.config import settings
from clients.prometheus import PrometheusClient
from clients.alertmanager import AlertmanagerClient
from clients.llm import LLMClient
from services.anomaly_service import AnomalyEngine
from core.database import SessionLocal, engine
from models.base import Base
from models.metric import MetricModel, MetricValue
from sqlalchemy import func


STATE_FILE = 'alerts_state.json'


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)


def metric_id_from_labels(labels: dict) -> str:
    items = sorted(labels.items())
    return '|'.join(f"{k}={v}" for k, v in items)


def run_once(
    prometheus_url=None,
    alertmanager_url=None,
    query=None,
    lookback_hours=None,
    step='5m',
    suppression_window=5,
    min_anomalies=3,
):
    prometheus_url = prometheus_url or settings.PROM_URL
    alertmanager_url = alertmanager_url or settings.ALERTMANAGER_URL
    query = query or settings.PROM_QUERY
    lookback_hours = lookback_hours or settings.LOOKBACK_HOURS

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    prom = PrometheusClient(prometheus_url)
    am = AlertmanagerClient(alertmanager_url)
    engine_service = AnomalyEngine()
    llm = LLMClient()

    # 1. Fetch current active series labels (range of 1m is enough to get fingerprints)
    now_ts = int(time.time())
    df_active = prom.fetch_metric_series(query, now_ts - 60, now_ts, step)
    if df_active.empty:
        logging.warning(f'No active series found for query: {query}')
        return

    session = SessionLocal()
    try:
        # Group by labels to identify unique series
        group_keys = [c for c in df_active.columns if c not in ('ds', 'y')]
        if group_keys:
            series_groups = df_active.groupby(group_keys)
        else:
            series_groups = [(None, df_active)]

        for group_val, _ in series_groups:
            # Reconstruct labels for this series
            if group_keys:
                labels = {k: str(df_active[df_active[k] == (group_val[i] if isinstance(group_val, tuple) else group_val)][k].iloc[0]) for i, k in enumerate(group_keys)}
            else:
                labels = {'metric': query}
            
            mid_fingerprint = metric_id_from_labels(labels)
            
            # 2. Get or Create MetricModel
            metric = session.query(MetricModel).filter_by(metric_fingerprint=mid_fingerprint).first()
            if not metric:
                metric = MetricModel(
                    metric_fingerprint=mid_fingerprint,
                    job=labels.get('job'),
                    instance=labels.get('instance')
                )
                session.add(metric)
                session.flush() # Get ID
            
            # 3. Determine delta range
            last_val_ts = session.query(func.max(MetricValue.timestamp)).filter_by(metric_id=metric.id).scalar()
            
            if last_val_ts:
                fetch_start = int(last_val_ts.timestamp()) + 1
            else:
                fetch_start = int((datetime.utcnow() - timedelta(hours=lookback_hours)).timestamp())
            
            fetch_end = now_ts

            # 4. Fetch Delta from Prometheus
            if fetch_end > fetch_start:
                logging.info(f"Syncing {mid_fingerprint}: fetching delta from {fetch_start} to {fetch_end}")
                df_delta = prom.fetch_metric_series(query, fetch_start, fetch_end, step)
                
                # Filter df_delta for this specific series if query returns multiple
                if not df_delta.empty and group_keys:
                    for k, v in labels.items():
                        if k in df_delta.columns:
                            df_delta = df_delta[df_delta[k] == v]

                if not df_delta.empty:
                    # Save delta to DB
                    new_values = [
                        MetricValue(metric_id=metric.id, timestamp=row['ds'], value=row['y'])
                        for _, row in df_delta.iterrows()
                    ]
                    session.add_all(new_values)
                    session.flush()
                    logging.info(f"Saved {len(new_values)} incremental points for {mid_fingerprint}")

            # 5. Prune old data
            prune_threshold = datetime.utcnow() - timedelta(hours=lookback_hours)
            session.query(MetricValue).filter(
                MetricValue.metric_id == metric.id,
                MetricValue.timestamp < prune_threshold
            ).delete()

            # 6. Fetch full window from Local DB for analysis
            history_data = session.query(MetricValue).filter(
                MetricValue.metric_id == metric.id,
                MetricValue.timestamp >= prune_threshold
            ).order_by(MetricValue.timestamp.asc()).all()

            if len(history_data) < 5:
                logging.info(f"Insufficient history in local cache for {mid_fingerprint} ({len(history_data)} points)")
                continue

            df_analysis = pd.DataFrame([{'ds': v.timestamp, 'y': v.value} for v in history_data])
            
            # 7. Run Anomaly Detection
            result = engine_service.train_and_detect(df_analysis, fingerprint=mid_fingerprint)
            
            # 8. Alerting Logic (Sliding Window)
            state = load_state()
            window = state.get(mid_fingerprint, [])
            window.append(1 if result['is_anomaly'] else 0)
            window = window[-suppression_window:]
            state[mid_fingerprint] = window
            
            if sum(window) >= min_anomalies:
                summary = f"AIOps anomaly: {labels.get('job', mid_fingerprint)}"
                description = llm.explain_anomaly(mid_fingerprint, result)
                payload = {
                    'labels': {
                        'alertname': 'AIOpsAnomalyDetected',
                        'severity': 'critical',
                        'instance': labels.get('instance', mid_fingerprint)
                    },
                    'annotations': {
                        'summary': summary,
                        'description': description,
                    }
                }
                am.send_alert(payload)
                state[mid_fingerprint] = [] # Reset window after alerting
            
            save_state(state)
        
        session.commit()
    except Exception as e:
        session.rollback()
        logging.error(f"Error during run_once: {e}")
        raise e
    finally:
        session.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f"Starting AIOps engine. Interval: {settings.CHECK_INTERVAL_MINUTES}m, Lookback: {settings.LOOKBACK_HOURS}h")
    
    while True:
        try:
            logging.info("Starting anomaly detection cycle...")
            run_once()
            logging.info(f"Cycle complete. Sleeping for {settings.CHECK_INTERVAL_MINUTES} minutes...")
        except Exception as e:
            logging.error(f"Error in detection cycle: {e}")
            logging.info("Retrying in 1 minute...")
            time.sleep(60)
            continue
            
        time.sleep(settings.CHECK_INTERVAL_MINUTES * 60)
