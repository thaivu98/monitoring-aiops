import unittest
from unittest.mock import patch, MagicMock
from clients.prometheus import PrometheusClient
from main import run_once
from core.config import settings

class TestAutoDiscovery(unittest.TestCase):
    
    @patch('clients.prometheus.requests.get')
    def test_discover_metrics(self, mock_get):
        # Mock Prometheus response for label values
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'status': 'success',
            'data': [
                'up',
                'node_cpu_seconds_total',
                'node_memory_MemAvailable_bytes',
                'process_cpu_seconds_total', # Should be filtered out by default pattern
                'go_goroutines' # Should be filtered out
            ]
        }
        mock_get.return_value = mock_response
        
        client = PrometheusClient("http://localhost:9090")
        
        # Test default pattern
        pattern = "^(up|node_cpu_seconds_total|node_memory_.*)$" 
        discovered = client.discover_metrics(pattern)
        
        self.assertIn('up', discovered)
        self.assertIn('node_cpu_seconds_total', discovered)
        self.assertIn('node_memory_MemAvailable_bytes', discovered)
        self.assertNotIn('process_cpu_seconds_total', discovered)
        self.assertNotIn('go_goroutines', discovered)
        
        print(f"\n[TEST] Discovered metrics: {discovered}")

if __name__ == '__main__':
    unittest.main()
