import requests
import logging
import json

class AlertmanagerClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.alert_url = f"{self.base_url}/api/v1/alerts"

    def send_alert(self, alert_payload):
        """
        Sends an alert to Alertmanager.
        
        Args:
            alert_payload (dict): The alert data.
            Expected format example:
            {
                "labels": {
                    "alertname": "AIOpsAnomalyDetected",
                    "severity": "warning",
                    "instance": "localhost"
                },
                "annotations": {
                    "description": "...",
                    "summary": "..."
                }
            }
        """
        # Wrap payload in a list as Alertmanager expects a list of alerts
        payload_list = [alert_payload]
        
        try:
            response = requests.post(
                self.alert_url, 
                json=payload_list,
                timeout=5
            )
            response.raise_for_status()
            logging.info(f"Alert sent successfully: {alert_payload['labels'].get('alertname')}")
            
        except Exception as e:
            logging.error(f"Failed to send alert to Alertmanager: {e}")
