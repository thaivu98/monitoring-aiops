import requests
import pandas as pd
import logging
import time
from datetime import datetime, timezone

class PrometheusClient:
    def __init__(self, base_url, verify_ssl=True):
        # Tự động thêm http:// nếu người dùng quên nhập scheme
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"http://{base_url}"
        
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.query_range_url = f"{self.base_url}/api/v1/query"
        self.query_instant_url = f"{self.base_url}/api/v1/query"
        # Sửa lại: query_range_url phải là query_range
        self.query_range_url = f"{self.base_url}/api/v1/query_range"
        logging.info(f"Prometheus Client initialized at {self.base_url} (SSL Verify: {self.verify_ssl})")

    def fetch_instant_metric(self, query):
        """Lấy giá trị hiện tại (Instant Query)"""
        params = {'query': query}
        try:
            response = requests.get(self.query_instant_url, params=params, timeout=10, verify=self.verify_ssl)
            response.raise_for_status()
            data = response.json()
            if data['status'] == 'success':
                result = data['data']['result']
                all_data = []
                for res in result:
                    metric_info = res['metric']
                    val = res['value'] # [timestamp, value]
                    row = {k: v for k, v in metric_info.items()}
                    row['ds'] = datetime.fromtimestamp(val[0], tz=timezone.utc).replace(tzinfo=None)
                    row['y'] = float(val[1])
                    all_data.append(row)
                return pd.DataFrame(all_data)
        except Exception as e:
            logging.error(f"Error in instant query: {e}")
        return pd.DataFrame()

    def fetch_metric_series(self, query, start_time, end_time, step='5m'):
        params = {
            'query': query,
            'start': start_time,
            'end': end_time,
            'step': step
        }
        try:
            response = requests.get(
                self.query_range_url, 
                params=params, 
                timeout=30, 
                verify=self.verify_ssl
            )
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
