import requests
import logging
from .base import BaseReceiver

class TelegramReceiver(BaseReceiver):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send(self, subject: str, description: str, metadata: dict) -> bool:
        if not self.bot_token or not self.chat_id:
            logging.warning("Telegram configuration missing. Skipping.")
            return False

        status = metadata.get('status', 'firing')
        icon = "🔥" if status == 'firing' else "✅"
        title = "AI PHÁT HIỆN LỖI!" if status == 'firing' else "SỰ CỐ ĐÃ ĐƯỢC KHẮC PHỤC"
        
        message = (
            f"🤖 <b>{title}</b>\n"
            f"──────────────────\n"
            f"{icon} <b>Trạng thái:</b> {status.upper()}\n"
            f"🖥️ <b>Server:</b> {metadata.get('instance', 'Unknown')}\n"
            f"⚠️ <b>Mức độ:</b> {metadata.get('severity', 'critical')}\n\n"
            f"📝 <b>Phân tích:</b>\n{description}\n\n"
            f"📊 <b>Tóm tắt:</b> {metadata.get('summary', '')}"
        )

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=10)
            response.raise_for_status()
            logging.info(f"Telegram alert sent successfully for {metadata.get('instance')}")
            return True
        except Exception as e:
            logging.error(f"Failed to send Telegram alert: {e}")
            return False
