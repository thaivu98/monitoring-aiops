import os
import time
import json
import logging
from datetime import datetime, timedelta, timezone

from core.config import settings
from clients.prometheus import PrometheusClient
from clients.llm import LLMClient
from receivers import AlertManager
from services.anomaly_service import AnomalyEngine
from core.database import SessionLocal, engine
from models.base import Base
from models.metric import MetricModel, MetricValue
from sqlalchemy import func
import pandas as pd


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


def labels_to_selector(metric_name: str, labels: dict) -> str:
    # Lọc bỏ các nhãn đặc biệt hoặc rỗng
    clean_labels = {k: v for k, v in labels.items() if k != '__name__' and v and str(v) != 'nan'}
    if not clean_labels:
        return metric_name
    
    parts = [f'{k}="{v}"' for k, v in clean_labels.items()]
    return f"{metric_name}{{{','.join(parts)}}}"


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

    prom = PrometheusClient(prometheus_url, verify_ssl=not settings.PROM_SKIP_SSL)
    alert_manager = AlertManager()
    engine_service = AnomalyEngine()
    llm = LLMClient()

    # 1. Fetch current active series labels (Dùng Instant Query để đảm bảo tìm thấy mọi series đang tồn tại)
    now_ts = int(time.time())
    df_active = prom.fetch_instant_metric(query)
    
    if df_active.empty:
        logging.warning(f'No active series found for query: {query}')
        # Cập nhật status rỗng để user biết
        status_payload = {
            'last_run': datetime.now(timezone.utc).isoformat(),
            'total_series': 0,
            'metrics': [],
            'error': 'No active series found'
        }
        with open('status.json', 'w') as f:
            json.dump(status_payload, f, indent=2)
        return
    
    logging.info(f"📥 Received {len(df_active)} unique series from Prometheus.")

    session = SessionLocal()
    state = load_state()
    try:
        # Group by labels to identify unique series
        group_keys = [c for c in df_active.columns if c not in ('ds', 'y')]
        
        if group_keys:
            # Sửa lại: lọc bỏ các cột có toàn giá trị NaN nếu có
            group_keys = [k for k in group_keys if df_active[k].notna().any()]
            # QUAN TRỌNG: set dropna=False để không bị mất series khi có nhãn rỗng
            series_groups = list(df_active.groupby(group_keys, dropna=False))
        else:
            series_groups = [(None, df_active)]

        logging.info(f"📊 Identified {len(series_groups)} unique series to process.")

        for group_val, group_df in series_groups:
            # Reconstruct labels for this series
            if group_keys:
                # group_val can be a single value or a tuple if multiple keys
                if not isinstance(group_val, tuple):
                    tmp_vals = (group_val,)
                else:
                    tmp_vals = group_val
                labels = {k: str(tmp_vals[i]) for i, k in enumerate(group_keys)}
            else:
                labels = {'metric': query}
            
            mid_fingerprint = metric_id_from_labels(labels)
            if mid_fingerprint not in state:
                state[mid_fingerprint] = []
            
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
                fetch_start = int((datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=lookback_hours)).timestamp())
            
            fetch_end = now_ts

            # 4. Fetch Delta from Prometheus
            if fetch_end > fetch_start:
                # Tạo query cụ thể cho series này để tối ưu và tránh nhầm lẫn nhãn
                metric_name = labels.get('__name__', query)
                specific_query = labels_to_selector(metric_name, labels)
                
                logging.info(f"Syncing {mid_fingerprint}: fetching delta via {specific_query}")
                df_delta = prom.fetch_metric_series(specific_query, fetch_start, fetch_end, step)

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
            prune_threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=lookback_hours)
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
            history_count = len(df_analysis)
            if history_count < 20:
                logging.info(f"⚡ [STAGE: LEARNING] {mid_fingerprint}: building local cache ({history_count} points)...")
            else:
                logging.info(f"🔍 [STAGE: MONITORING] {mid_fingerprint}: analyzing {history_count} points for anomalies...")
                
            result = engine_service.train_and_detect(df_analysis, fingerprint=mid_fingerprint)
            
            # 8. Alerting Logic (Stateful)
            full_state = state if isinstance(state.get('windows'), dict) else {"windows": state, "firing": {}}
            windows = full_state.get('windows', {})
            firing_registry = full_state.get('firing', {})

            window = windows.get(mid_fingerprint, [])
            window.append(1 if result['is_anomaly'] else 0)
            window = window[-suppression_window:]
            windows[mid_fingerprint] = window
            
            is_currently_firing = firing_registry.get(mid_fingerprint, False)

            # Trigger Firing Alert
            if not is_currently_firing and sum(window) >= min_anomalies:
                summary = f"AIOps anomaly: {labels.get('job', mid_fingerprint)}"
                description = llm.explain_anomaly(mid_fingerprint, result)
                
                logging.info(f"🚨 [ALERT] Broadcasting anomaly alert for {mid_fingerprint}")
                metadata = {
                    'instance': labels.get('instance', mid_fingerprint),
                    'severity': 'critical',
                    'summary': summary,
                    'status': 'firing'
                }
                success = alert_manager.broadcast(
                    subject='AIOpsAnomalyDetected',
                    description=description,
                    metadata=metadata
                )
                if success:
                    firing_registry[mid_fingerprint] = True
            
            # Trigger Resolve Alert
            # Resolve logic: if firing and last N points are normal (0)
            elif is_currently_firing and sum(window[-min_anomalies:]) == 0:
                summary = f"AIOps resolved: {labels.get('job', mid_fingerprint)}"
                description = f"Metric {mid_fingerprint} has returned to normal state after {min_anomalies} consecutive normal observations."
                
                logging.info(f"✅ [RESOLVE] Broadcasting resolve notification for {mid_fingerprint}")
                metadata = {
                    'instance': labels.get('instance', mid_fingerprint),
                    'severity': 'info',
                    'summary': summary,
                    'status': 'resolved'
                }
                success = alert_manager.broadcast(
                    subject='AIOpsAnomalyResolved',
                    description=description,
                    metadata=metadata
                )
                if success:
                    firing_registry[mid_fingerprint] = False
                    windows[mid_fingerprint] = [] # Reset window after resolve
            
            state = {"windows": windows, "firing": firing_registry}
            
        save_state(state)
        
        # 9. Update Status JSON
        metrics_status = []
        # Lấy tất cả metric hiện có trong DB liên quan đến job này
        active_metrics = session.query(MetricModel).all()
        for m_obj in active_metrics:
            mid = m_obj.metric_fingerprint
            full_state = state if isinstance(state.get('windows'), dict) else {"windows": state, "firing": {}}
            window = full_state.get('windows', {}).get(mid, [])
            is_firing = full_state.get('firing', {}).get(mid, False)
            
            # Count local points
            count = session.query(func.count(MetricValue.id)).filter_by(metric_id=m_obj.id).scalar()
            metrics_status.append({
                'fingerprint': mid,
                'job': m_obj.job,
                'instance': m_obj.instance,
                'points_count': count,
                'stage': 'MONITORING' if count >= 20 else 'LEARNING',
                'is_unstable': sum(window) > 0,
                'is_firing': is_firing
            })
            
        status_payload = {
            'last_run': datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            'total_series': len(metrics_status),
            'metrics': metrics_status
        }
        # Lưu file status
        with open('status.json', 'w') as f:
            json.dump(status_payload, f, indent=2)

        session.commit()
    except Exception as e:
        session.rollback()
        logging.error(f"Error during run_once: {e}")
        raise e
    finally:
        session.close()


def wait_for_db(timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            session = SessionLocal()
            session.execute(func.now())
            session.close()
            logging.info("Database is ready!")
            return True
        except Exception:
            logging.info("Waiting for database...")
            time.sleep(2)
    logging.error("Database connection timeout")
    return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Wait for DB before starting
    if not wait_for_db():
        exit(1)

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
