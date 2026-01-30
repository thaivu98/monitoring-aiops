import requests
import re
import os
import sys

# Load generic config (simulated)
PROM_URL = os.environ.get('PROM_URL', 'http://localhost:9090')
METRIC_DISCOVERY_PATTERN = os.environ.get('METRIC_DISCOVERY_PATTERN', '^(up|node_cpu_seconds_total|node_memory_.*|node_filesystem_.*|node_network_.*)$')

def debug_discovery():
    print(f"--- Debugging Metric Discovery ---")
    print(f"Target Prometheus: {PROM_URL}")
    print(f"Pattern: {METRIC_DISCOVERY_PATTERN}")
    
    url = f"{PROM_URL}/api/v1/label/__name__/values"
    try:
        print(f"Fetching from {url}...")
        response = requests.get(url, timeout=10)
        print(f"Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Failed to fetch metrics: {response.text}")
            return

        data = response.json()
        if data['status'] == 'success':
            all_metrics = data['data']
            print(f"Total metrics found in Prometheus: {len(all_metrics)}")
            
            # Show first 10 metrics to verify content
            print(f"Example metrics (first 10): {all_metrics[:10]}")
            
            regex = re.compile(METRIC_DISCOVERY_PATTERN)
            matched = [m for m in all_metrics if regex.match(m)]
            
            print(f"\n--- Matching Results ---")
            print(f"Matched {len(matched)} metrics.")
            print(all_metrics)
            if matched:
                print(f"Matches: {matched}")
            else:
                print("❌ NO MATCHES FOUND! Check your regex.")
                
                # Debug: try simpler regex
                print("\n[Debug] Testing simpler regex 'node_.*'...")
                simple_regex = re.compile(r"node_.*")
                simple_matches = [m for m in all_metrics if simple_regex.match(m)]
                print(f"Simple 'node_.*' matches: {len(simple_matches)}")
                if simple_matches:
                    print(f"Examples: {simple_matches[:5]}")
        else:
            print(f"Prometheus API error: {data}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_discovery()
