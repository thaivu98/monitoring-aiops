import requests
import logging
import json

class AlertmanagerClient:
    def __init__(self, base_url, verify_ssl=True):
        # Tự động thêm http:// nếu người dùng quên nhập scheme
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"http://{base_url}"
            
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.alert_url = f"{self.base_url}/api/v2/alerts"
        logging.info(f"Alertmanager Client initialized at {self.base_url} (SSL Verify: {self.verify_ssl})")

    def send_alert(self, alert_payload):
        """
        Sends an alert to Alertmanager.
        """
        # Wrap payload in a list as Alertmanager expects a list of alerts
        payload_list = [alert_payload]
        
        try:
            response = requests.post(
                self.alert_url, 
                json=payload_list,
                timeout=5,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            logging.info(f"Alert sent successfully: {alert_payload['labels'].get('alertname')}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to send alert to Alertmanager: {e}")
            return False
