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
from core.database import SessionLocal
from models.base import Base
from core.database import engine


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
    lookback_hours=24,
    step='5m',
    suppression_window=5,
    min_anomalies=3,
):
    prometheus_url = prometheus_url or settings.PROM_URL
    alertmanager_url = alertmanager_url or settings.ALERTMANAGER_URL
    query = query or settings.PROM_QUERY

    # ensure tables
    Base.metadata.create_all(bind=engine)

    prom = PrometheusClient(prometheus_url)
    am = AlertmanagerClient(alertmanager_url)
    engine_service = AnomalyEngine()
    llm = LLMClient()

    end = int(time.time())
    start = int((datetime.utcnow() - timedelta(hours=lookback_hours)).timestamp())

    df_all = prom.fetch_metric_series(query, start, end, step)
    if df_all.empty:
        logging.warning('No series returned from Prometheus')
        return

    state = load_state()
    group_keys = [c for c in df_all.columns if c not in ('ds', 'y')]
    if group_keys:
        groups = [g for _, g in df_all.groupby(group_keys)]
    else:
        groups = [df_all]

    for g in groups:
        labels = {k: str(g[k].iloc[0]) for k in group_keys} if group_keys else {'metric': query}
        mid = metric_id_from_labels(labels)
        fingerprint = mid
        result = engine_service.train_and_detect(g, fingerprint=fingerprint)
        window = state.get(mid, [])
        window.append(1 if result['is_anomaly'] else 0)
        window = window[-suppression_window:]
        state[mid] = window
        anomaly_count = sum(window)
        if anomaly_count >= min_anomalies:
            summary = f"AIOps anomaly: {labels.get('job', mid)}"
            description = llm.explain_anomaly(mid, result)
            payload = {
                'labels': {
                    'alertname': 'AIOpsAnomalyDetected',
                    'severity': 'critical',
                    'instance': labels.get('instance', mid)
                },
                'annotations': {
                    'summary': summary,
                    'description': description,
                }
            }
            am.send_alert(payload)
            state[mid] = []

    save_state(state)


if __name__ == '__main__':
    run_once()
