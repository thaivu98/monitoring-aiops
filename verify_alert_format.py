import sys
import os

# Add app directory to path
sys.path.append(os.path.join(os.getcwd(), 'app'))

from clients.llm import LLMClient

def test_alerts():
    llm = LLMClient()
    
    scenarios = [
        {
            "name": "up",
            "result": {
                "reason": "host_down",
                "confidence": 1.0,
                "explanation": "CRITICAL: Host is DOWN (up=0). last=0.000, mean=1.000, std=0.000, z=0.00, slope=0.0000"
            }
        },
        {
            "name": "node_cpu_seconds_total",
            "result": {
                "reason": "spike",
                "confidence": 0.85,
                "explanation": "last=85.5, mean=20.2, std=5.1, z=12.8, slope=0.5"
            }
        },
        {
            "name": "node_filesystem_avail_bytes",
            "result": {
                "reason": "trend",
                "confidence": 0.92,
                "explanation": "last=1024.0, mean=5000.0, std=100.0, z=40.0, slope=-500.0"
            }
        }
    ]
    
    for s in scenarios:
        print(f"\n--- Testing Scenario: {s['name']} ---")
        output = llm.explain_anomaly(s['name'], s['result'])
        print(output)
        print("-" * 40)

if __name__ == "__main__":
    test_alerts()
