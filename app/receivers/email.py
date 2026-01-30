import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .base import BaseReceiver

class EmailReceiver(BaseReceiver):
    def __init__(self, smtp_server, smtp_port, smtp_user, smtp_pass, sender, recipients: list):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.sender = sender
        self.recipients = recipients

    def send(self, subject: str, description: str, metadata: dict) -> bool:
        if not all([self.smtp_server, self.recipients]):
            logging.warning("Email configuration incomplete (missing server or recipients). Skipping.")
            return False

        msg = MIMEMultipart()
        msg['From'] = self.sender
        msg['To'] = ", ".join(self.recipients)
        status = metadata.get('status', 'firing')
        if status == 'firing':
            subject_prefix = "[AIOps Alert]"
        elif status == 'repeating':
            subject_prefix = "[AIOps REMINDER]"
        else:
            subject_prefix = "[AIOps Resolved]"
        
        msg['Subject'] = f"{subject_prefix} {subject}"

        import re
        clean_description = re.sub('<[^<]+?>', '', description)
        
        body = (
            f"AIOps Notification\n"
            f"==================\n"
            f"Status: {status.upper()}\n"
            f"Server: {metadata.get('instance')}\n"
            f"Severity: {metadata.get('severity')}\n"
            f"------------------\n\n"
            f"{clean_description}\n"
        )
        msg.attach(MIMEText(body, 'plain'))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.starttls()
                if self.smtp_user and self.smtp_pass:
                    server.login(self.smtp_user, self.smtp_pass)
                
                # Send to all recipients in the list
                server.send_message(msg)
                
            logging.info(f"Email alert sent successfully to {len(self.recipients)} recipients: {', '.join(self.recipients)}")
            return True
        except Exception as e:
            logging.error(f"Failed to send Email alert: {e}")
            return False
