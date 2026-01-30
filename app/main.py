import os
import time
import json
import logging
import requests
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
    clean_labels = {k: v for k, v in labels.items() if k != '__name__' and v and str(v) != 'nan'}
    if not clean_labels:
        return metric_name
    
    parts = [f'{k}="{v}"' for k, v in clean_labels.items()]
    return f"{metric_name}{{{','.join(parts)}}}"


def update_status_json(state):
    session = SessionLocal()
    try:
        metrics_status = []
        active_metrics = session.query(MetricModel).all()
        
        for m_obj in active_metrics:
            mid = m_obj.metric_fingerprint
            full_state = state if isinstance(state.get('windows'), dict) else {"windows": state, "firing": {}}
            window = full_state.get('windows', {}).get(mid, [])
            is_firing = full_state.get('firing', {}).get(mid, False)
            
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
        with open('status.json', 'w') as f:
            json.dump(status_payload, f, indent=2)
    except Exception as e:
        logging.error(f"Error updating status.json: {e}")
    finally:
        session.close()


def run_once(prom, alert_manager, engine_service, llm, query=None, lookback_hours=None, step='5m'):
    query = query or settings.PROM_QUERY
    lookback_hours = lookback_hours or settings.LOOKBACK_HOURS
    now_ts = int(time.time())

    df_active = prom.fetch_instant_metric(query)
    if df_active.empty:
        return {}
    
    session = SessionLocal()
    state_updates = {"windows": {}, "firing": {}}
    
    try:
        group_keys = [c for c in df_active.columns if c not in ('ds', 'y')]
        if group_keys:
            group_keys = [k for k in group_keys if df_active[k].notna().any()]
            series_groups = list(df_active.groupby(group_keys, dropna=False))
        else:
            series_groups = [(None, df_active)]

        for group_val, group_df in series_groups:
            if group_keys:
                tmp_vals = (group_val,) if not isinstance(group_val, tuple) else group_val
                labels = {k: str(tmp_vals[i]) for i, k in enumerate(group_keys)}
            else:
                labels = {'metric': query}
            
            mid_fingerprint = metric_id_from_labels(labels)
            
            metric = session.query(MetricModel).filter_by(metric_fingerprint=mid_fingerprint).first()
            if not metric:
                metric = MetricModel(metric_fingerprint=mid_fingerprint, job=labels.get('job'), instance=labels.get('instance'))
                session.add(metric)
                session.flush()
            
            last_val_ts = session.query(func.max(MetricValue.timestamp)).filter_by(metric_id=metric.id).scalar()
            fetch_start = int(last_val_ts.timestamp()) + 1 if last_val_ts else int((datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=lookback_hours)).timestamp())
            
            if now_ts > fetch_start:
                metric_name = labels.get('__name__', query)
                specific_query = labels_to_selector(metric_name, labels)
                df_delta = prom.fetch_metric_series(specific_query, fetch_start, now_ts, step)

                if not df_delta.empty:
                    new_values = [MetricValue(metric_id=metric.id, timestamp=row['ds'], value=row['y']) for _, row in df_delta.iterrows()]
                    session.add_all(new_values)
                    session.flush()

            # 6. Fetch window for analysis (24h baseline)
            analysis_threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
            history_data = session.query(MetricValue).filter(MetricValue.metric_id == metric.id, MetricValue.timestamp >= analysis_threshold).order_by(MetricValue.timestamp.asc()).all()

            if len(history_data) < 20: 
                # Fallback to last 100 points
                history_data = session.query(MetricValue).filter(MetricValue.metric_id == metric.id).order_by(MetricValue.timestamp.desc()).limit(100).all()
                history_data.reverse()

            if len(history_data) < 5:
                continue

            df_analysis = pd.DataFrame([{'ds': v.timestamp, 'y': v.value} for v in history_data])
            result = engine_service.train_and_detect(df_analysis, fingerprint=mid_fingerprint)
            
            state_updates["windows"][mid_fingerprint] = result['is_anomaly']
            state_updates["firing"][mid_fingerprint] = result 

        session.commit()
        logging.info(f"✅ Finished metric: {query}")
    except Exception as e:
        session.rollback()
        logging.error(f"Error in run_once ({query}): {e}")
    finally:
        session.close()

    return state_updates


def wait_for_db(timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            session = SessionLocal()
            session.execute(func.now())
            session.close()
            return True
        except Exception:
            time.sleep(2)
    return False


def wait_for_prometheus(timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            requests.get(f"{settings.PROM_URL}/api/v1/query?query=up", timeout=5, verify=not settings.PROM_SKIP_SSL)
            return True
        except Exception:
            time.sleep(5)
    return False


import concurrent.futures

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    if not wait_for_db(): exit(1)
    wait_for_prometheus(timeout=30)
    Base.metadata.create_all(bind=engine)

    prom_client = PrometheusClient(settings.PROM_URL, verify_ssl=not settings.PROM_SKIP_SSL)
    alert_manager = AlertManager()
    engine_service = AnomalyEngine()
    llm = LLMClient()

    while True:
        try:
            logging.info("Starting anomaly detection cycle...")
            cycle_start = time.time()
            
            queries = []
            if settings.METRIC_DISCOVERY_ENABLED:
                queries = prom_client.discover_metrics(settings.METRIC_DISCOVERY_PATTERN)
                if not queries: queries = [settings.PROM_QUERY]
            else:
                queries = [settings.PROM_QUERY]
                
            all_updates = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as executor:
                futures = {executor.submit(run_once, prom_client, alert_manager, engine_service, llm, q): q for q in queries}
                for f in concurrent.futures.as_completed(futures):
                    res = f.result()
                    if res: all_updates.append(res)
            
            # STATE UPDATE & ALERTING
            global_state = load_state()
            windows = global_state.get('windows', {})
            firing_registry = global_state.get('firing', {})
            last_alert_at = global_state.get('last_alert_at', {})
            
            for update in all_updates:
                for mid, is_anom in update["windows"].items():
                    w = windows.get(mid, [])
                    w.append(1 if is_anom else 0)
                    w = w[-5:]
                    windows[mid] = w
                    
                    res = update["firing"][mid]
                    is_firing = firing_registry.get(mid, False)
                    
                    def get_inst(m): return m.split('|instance=')[1].split('|')[0] if '|instance=' in m else m

                    if is_anom: logging.info(f"⚠️ [DETECTED] {mid} | Window: {sum(w)}/3")

                    if not is_firing and (sum(w) >= 3 or res.get('reason') == 'host_down'):
                        if alert_manager.broadcast("Anomaly Detected", llm.explain_anomaly(mid, res), {'instance': get_inst(mid), 'severity': 'critical', 'status': 'firing'}):
                            firing_registry[mid], last_alert_at[mid] = True, time.time()
                    
                    elif is_firing and is_anom:
                        if (time.time() - last_alert_at.get(mid, 0)) >= settings.ALERT_REPEAT_INTERVAL_MINUTES * 60:
                            if alert_manager.broadcast("Anomaly Persisting", llm.explain_anomaly(mid, res), {'instance': get_inst(mid), 'severity': 'critical', 'status': 'repeating'}):
                                last_alert_at[mid] = time.time()
                    
                    elif is_firing and sum(w[-3:]) == 0:
                        if alert_manager.broadcast("Anomaly Resolved", f"Metric {mid} returned to normal.", {'instance': get_inst(mid), 'severity': 'info', 'status': 'resolved'}):
                            firing_registry[mid] = False
                            last_alert_at.pop(mid, None)
                            windows[mid] = [0] * 5

            save_state({"windows": windows, "firing": firing_registry, "last_alert_at": last_alert_at})
            update_status_json(load_state())

            # GLOBAL PRUNING
            session = SessionLocal()
            try:
                prune_limit = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=settings.LOOKBACK_HOURS)
                session.query(MetricValue).filter(MetricValue.timestamp < prune_limit).delete()
                session.commit()
            finally: session.close()
            
            logging.info(f"Cycle complete in {time.time() - cycle_start:.1f}s. Sleeping {settings.CHECK_INTERVAL_MINUTES}m...")
        except Exception as e:
            logging.error(f"Cycle error: {e}")
            time.sleep(60)
            
        time.sleep(settings.CHECK_INTERVAL_MINUTES * 60)
