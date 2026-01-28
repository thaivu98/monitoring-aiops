import requests
import pandas as pd
import logging


class PrometheusClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.query_range_url = f"{self.base_url}/api/v1/query_range"

    def fetch_metric_series(self, query, start_time, end_time, step='5m'):
        params = {
            'query': query,
            'start': start_time,
            'end': end_time,
            'step': step
        }
        try:
            response = requests.get(self.query_range_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data['status'] != 'success':
                logging.error(f"Prometheus query failed: {data.get('error')}")
                return pd.DataFrame()

            result = data['data']['result']
            if not result:
                logging.warning(f"No data found for query: {query}")
                return pd.DataFrame()

            all_data = []
            for res in result:
                metric_info = res['metric']
                values = res['values']
                df = pd.DataFrame(values, columns=['ds', 'y'])
                df['ds'] = pd.to_datetime(df['ds'], unit='s')
                df['y'] = pd.to_numeric(df['y'], errors='coerce')
                for k, v in metric_info.items():
                    df[k] = v
                all_data.append(df)

            if all_data:
                return pd.concat(all_data, ignore_index=True)
            return pd.DataFrame()

        except Exception as e:
            logging.error(f"Error fetching from Prometheus: {e}")
            return pd.DataFrame()
import requests
import pandas as pd
import time
from datetime import datetime
import logging

class PrometheusClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.query_range_url = f"{self.base_url}/api/v1/query_range"
        
    def fetch_metric_series(self, query, start_time, end_time, step='5m'):
        """
        Fetches time-series data from Prometheus.
        
        Args:
            query (str): PromQL query.
            start_time (int): Start timestamp (seconds).
            end_time (int): End timestamp (seconds).
            step (str): Query resolution (e.g., '15s', '5m').
            
        Returns:
            pd.DataFrame: DataFrame with 'ds' (datetime) and 'y' (value) columns, or empty DataFrame if no data.
        """
        params = {
            'query': query,
            'start': start_time,
            'end': end_time,
            'step': step
        }
        
        try:
            response = requests.get(self.query_range_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'success':
                logging.error(f"Prometheus query failed: {data.get('error')}")
                return pd.DataFrame()
            
            result = data['data']['result']
            if not result:
                logging.warning(f"No data found for query: {query}")
                return pd.DataFrame()
                
            # Assuming we pick the first series if multiple match, 
            # OR we can return a list of series. For simplicity in this base version,
            # we'll aggregate or just pick the first one for the main anomaly engine.
            # Ideally, AIOps should handle multiple series (e.g. per instance).
            # Here we flatten all returned series into a single processing stream per metric name 
            # (assuming the query aggregates, e.g., 'avg by (instance)' -> returns N instances).
            
            # Use the first result series for now or handle list of results
            # For robust multi-series support, we'd need to loop over 'result'
            # But to keep "base code" simple, let's extract values from the first series 
            # and perhaps warn if multiple.
            
            all_data = []
            for res in result:
                metric_info = res['metric'] 
                values = res['values']
                # format: [ [timestamp, "value"], ... ]
                
                df = pd.DataFrame(values, columns=['ds', 'y'])
                df['ds'] = pd.to_datetime(df['ds'], unit='s')
                df['y'] = pd.to_numeric(df['y'], errors='coerce')
                
                # Attach metric labels for context if needed
                for k, v in metric_info.items():
                    df[k] = v
                    
                all_data.append(df)
            
            if all_data:
                # Return combined dataframe (caller needs to handle grouping if query returns multiple streams)
                return pd.concat(all_data, ignore_index=True)
            
            return pd.DataFrame()

        except Exception as e:
            logging.error(f"Error fetching from Prometheus: {e}")
            return pd.DataFrame()
