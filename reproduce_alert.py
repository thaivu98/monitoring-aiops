import os
import sys
import pandas as pd
import logging
from core.database import SessionLocal
from models.metric import MetricModel, MetricValue
from services.anomaly_service import AnomalyEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_detection(pattern_filter=None):
    session = SessionLocal()
    engine_service = AnomalyEngine()
    
    try:
        metrics = session.query(MetricModel).all()
        print(f"Found {len(metrics)} metrics in DB.")
        
        counts = {}
        for m in metrics:
            prefix = m.metric_fingerprint.split('|')[0]
            # Extract __name__ if present
            if '__name__=' in prefix:
                 prefix = prefix.split('=')[1]
            root = prefix.split('_')[0] + '_' + prefix.split('_')[1] if '_' in prefix else prefix
            counts[root] = counts.get(root, 0) + 1
            
        print("\nMetric Counts by Type:")
        for k, v in counts.items():
            print(f"  {k}: {v}")
            
        for m in metrics:
            if pattern_filter and pattern_filter not in m.metric_fingerprint:
                continue
                
            print(f"\n--- Analyzing: {m.metric_fingerprint} ---")
            
            # Fetch history
            history = session.query(MetricValue).filter_by(metric_id=m.id).order_by(MetricValue.timestamp.asc()).all()
            df = pd.DataFrame([{'ds': v.timestamp, 'y': v.value} for v in history])
            
            if df.empty:
                print("No data points found.")
                continue
                
            print(f"Data points: {len(df)}")
            print(f"Last value: {df.iloc[-1]['y']}")
            
            # Run detection
            result = engine_service.train_and_detect(df, fingerprint=m.metric_fingerprint)
            print(f"Result: {result}")
            
            if result['is_anomaly']:
                print(">>> ANOMALY DETECTED! <<<")
            else:
                print("Status: Normal")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    # Filter for 'up' or 'filesystem' metrics to match user's likely test case
    filter_text = sys.argv[1] if len(sys.argv) > 1 else ""
    test_detection(filter_text)
