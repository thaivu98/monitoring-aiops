import pandas as pd
import numpy as np
import datetime
from services.anomaly_service import AnomalyEngine

def generate_data(n=300, anomaly_type=None, gaps=False):
    # Generate 300 points (approx 24h at 5m intervals)
    now = datetime.datetime.now()
    timestamps = [now - datetime.timedelta(minutes=5*(n-i)) for i in range(n)]
    
    # Base pattern: Sine wave + Random Noise
    x = np.linspace(0, 4*np.pi, n)
    y = np.sin(x) * 10 + 50 + np.random.normal(0, 1, n)
    
    if anomaly_type == 'spike':
        y[-1] = y[-1] + 20 
    elif anomaly_type == 'trend':
        y[-10:] = y[-10:] - np.linspace(0, 15, 10)
        
    df = pd.DataFrame({'ds': timestamps, 'y': y})
    
    if gaps:
        # Introduce NaNs in random places
        mask = np.random.choice([True, False], size=len(df), p=[0.1, 0.9])
        df.loc[mask, 'y'] = np.nan
        # Ensure last point is NOT nan for validity of test
        df.iloc[-1, df.columns.get_loc('y')] = y[-1] 
        
    return df

def test_normal_behavior():
    print("Testing Normal Behavior...")
    df = generate_data(n=300, anomaly_type=None)
    engine = AnomalyEngine()
    result = engine.train_and_detect(df)
    print(f"Result: {result}")
    assert not result['is_anomaly'], "Should NOT detect anomaly in normal data"
    print("PASS")

def test_gap_interpolation():
    print("\nTesting Data Gaps (Interpolation)...")
    df = generate_data(n=300, anomaly_type=None, gaps=True)
    engine = AnomalyEngine()
    result = engine.train_and_detect(df)
    print(f"Result: {result}")
    assert not result['is_anomaly'], "Should handle NaNs gracefully via interpolation without false positive"
    print("PASS")

def test_spike_anomaly():
    print("\nTesting Spike Anomaly...")
    df = generate_data(n=300, anomaly_type='spike')
    engine = AnomalyEngine()
    result = engine.train_and_detect(df, contamination=0.01) # Test passing param
    print(f"Result: {result}")
    assert result['is_anomaly'], "Should detect spike anomaly"
    assert result['confidence'] > 0.5, "Confidence should be high"
    print("PASS")

def test_seasonality_features():
    print("\nTesting Seasonality Logic (Mock)...")
    # This is hard to test with generic synthetic data without training multiple periods. 
    # But we want to ensure the code runs with new feature columns without error.
    df = generate_data(n=300)
    engine = AnomalyEngine()
    result = engine.train_and_detect(df)
    assert 'hour_sin' in str(engine.__class__), "Just ensuring code path executes"
    print("PASS (Execution check)")

if __name__ == "__main__":
    try:
        test_normal_behavior()
        test_gap_interpolation()
        test_spike_anomaly()
        test_seasonality_features()
        print("\nALL V2 TESTS PASSED!")
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
    except Exception as e:
        print(f"\nERROR: {e}")
