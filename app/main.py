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
from services.history_cache import history_cache
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

    # 1. Fetch current active series labels
    df_active = prom.fetch_instant_metric(query)
    if df_active.empty:
        return {}
    
    session = SessionLocal()
    state_updates = {"windows": {}, "firing": {}}
    
    try:
        # Load Metric Models for mapping mid -> m_id
        metric_models = session.query(MetricModel).filter(MetricModel.metric_fingerprint.like(f"__name__={query}%")).all()
        mid_map = {m.metric_fingerprint: m for m in metric_models}
        
        # 2. Determine fetch_start (only for the window since last sync)
        earliest_ts = None
        if metric_models:
            ids = [m.id for m in metric_models]
            earliest_ts = session.query(func.max(MetricValue.timestamp)).filter(MetricValue.metric_id.in_(ids)).scalar()
        
        fetch_start = int(earliest_ts.timestamp()) + 1 if earliest_ts else int((datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=lookback_hours)).timestamp())
        
        # 3. Delta Sync from Prometheus
        df_all_deltas = prom.fetch_metric_series(query, fetch_start, now_ts, step)
        
        if not df_all_deltas.empty:
            label_cols = [c for c in df_all_deltas.columns if c not in ('ds', 'y')]
        else:
            label_cols = []

        # Prepare Delta Map for O(1) lookup
        delta_map = {}
        if not df_all_deltas.empty:
            # Pre-convert all labels to string for reliable mapping
            df_lookup = df_all_deltas.copy()
            for col in label_cols:
                df_lookup[col] = df_lookup[col].astype(str)
            
            for name, group in df_lookup.groupby(label_cols, dropna=False):
                name_tuple = (name,) if not isinstance(name, tuple) else name
                delta_map[name_tuple] = group

        # 4. Process each active series
        group_keys = [c for c in df_active.columns if c not in ('ds', 'y')]
        series_groups = list(df_active.groupby(group_keys, dropna=False))

        all_new_values = []
        for group_val, group_df in series_groups:
            # group_val is already a tuple (or single val) and matches label_cols
            group_tuple = (group_val,) if not isinstance(group_val, tuple) else group_val
            group_labels = {k: str(v) for k, v in zip(group_keys, group_tuple)}
            mid_key = metric_id_from_labels(group_labels)
            m_obj = mid_map.get(mid_key)
            if not m_obj: continue

            # O(1) Lookup instead of O(N) Masking
            df_s_delta = delta_map.get(group_tuple, pd.DataFrame())
            if not df_s_delta.empty:
                history_cache.update(m_obj.id, df_s_delta)
                for _, r in df_s_delta.iterrows():
                    all_new_values.append(MetricValue(metric_id=m_obj.id, timestamp=r['ds'], value=r['y']))

            # Analysis
            df_hist = history_cache.get_history(m_obj.id)
            if not df_hist.empty and len(df_hist) >= 5:
                res_anom = engine_service.train_and_detect(df_hist, fingerprint=mid_key)
                state_updates["windows"][mid_key] = res_anom['is_anomaly']
                state_updates["firing"][mid_key] = res_anom

        # Batch Save new points to Postgres for durability
        if all_new_values:
            session.add_all(all_new_values)
            session.flush()
            logging.info(f"Saved {len(all_new_values)} points for {query}")

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

    # PRE-LOAD TurboMode History Cache
    history_cache.initialize(engine, settings.ANALYSIS_WINDOW_HOURS)

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

                    # Use firing_registry as prev_firing and global_state as state for consistency
                    prev_firing = firing_registry
                    state = global_state # This 'state' refers to the global_state loaded at the beginning of the loop

                    firing = (sum(w) >= 3 or res.get('reason') == 'host_down') # Determine if it should be firing

                    if firing:
                        # New anomaly
                        if mid not in prev_firing:
                            firing_registry[mid] = res 
                            firing_registry[mid]["last_alert_at"] = datetime.now().isoformat()
                            alert_manager.async_broadcast("Anomaly Detected", llm.explain_anomaly(mid, res), {'instance': get_inst(mid), 'severity': 'critical', 'status': 'firing'})
                        else:
                            # Repeating anomaly check
                            last_alert_ts = datetime.fromisoformat(prev_firing[mid].get("last_alert_at", "1970-01-01"))
                            if (datetime.now() - last_alert_ts) >= timedelta(minutes=settings.ALERT_REPEAT_INTERVAL_MINUTES):
                                firing_registry[mid] = res 
                                firing_registry[mid]["last_alert_at"] = datetime.now().isoformat()
                                alert_manager.async_broadcast("Anomaly Persisting", llm.explain_anomaly(mid, res), {'instance': get_inst(mid), 'severity': 'critical', 'status': 'repeating'})
                    else:
                        # Resolved
                        if mid in prev_firing:
                            alert_manager.async_broadcast("Anomaly Resolved", f"Metric {mid} returned to normal.", {'instance': get_inst(mid), 'severity': 'info', 'status': 'resolved'})
                            firing_registry.pop(mid, None) # Remove from firing registry
                            windows[mid] = [0] * 5 # Reset window for resolved metric

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
