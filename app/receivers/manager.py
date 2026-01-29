import logging
from typing import List
from .base import BaseReceiver
from .telegram import TelegramReceiver
from .email import EmailReceiver
from core.config import settings

class AlertManager:
    def __init__(self):
        self.receivers: List[BaseReceiver] = []
        
        # Initialize Telegram
        logging.info(f"Checking Telegram: ENABLED={settings.TELEGRAM_ENABLED}")
        if settings.TELEGRAM_ENABLED:
            self.receivers.append(TelegramReceiver(
                bot_token=settings.TELEGRAM_BOT_TOKEN,
                chat_id=settings.TELEGRAM_CHAT_ID
            ))
            logging.info("Telegram receiver enabled.")
        else:
            logging.warning("Telegram receiver disabled in settings.")

        # Initialize Email
        logging.info(f"Checking Email: ENABLED={settings.EMAIL_ENABLED}")
        if settings.EMAIL_ENABLED:
            self.receivers.append(EmailReceiver(
                smtp_server=settings.SMTP_SERVER,
                smtp_port=settings.SMTP_PORT,
                smtp_user=settings.SMTP_AUTH_USERNAME,
                smtp_pass=settings.SMTP_AUTH_PASSWORD,
                sender=settings.SMTP_FROM,
                recipients=settings.EMAIL_RECIPIENTS
            ))
            logging.info("Email receiver enabled.")
        else:
            logging.warning("Email receiver disabled in settings.")

    def broadcast(self, subject: str, description: str, metadata: dict) -> bool:
        if not self.receivers:
            logging.warning("No alert receivers enabled!")
            return False

        any_success = False
        for receiver in self.receivers:
            success = receiver.send(subject, description, metadata)
            if success:
                any_success = True
        
        return any_success
