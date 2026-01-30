import os
import sys
import logging
from clients.prometheus import PrometheusClient
from core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_discovery():
    try:
        print(f"Testing discovery with pattern: {settings.METRIC_DISCOVERY_PATTERN}")
        prom = PrometheusClient(settings.PROM_URL, verify_ssl=not settings.PROM_SKIP_SSL)
        
        metrics = prom.discover_metrics(settings.METRIC_DISCOVERY_PATTERN)
        print(f"Total discovered metrics: {len(metrics)}")
        
        counts = {}
        for m in metrics:
            root = m.split('_')[0] + '_' + m.split('_')[1] if '_' in m else m
            counts[root] = counts.get(root, 0) + 1
            
        print("\nDiscovered Counts by Type:")
        for k, v in counts.items():
            print(f"  {k}: {v}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_discovery()
