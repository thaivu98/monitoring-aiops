import os


class Settings:
    PROM_URL: str = os.environ.get('PROM_URL', 'http://localhost:9090')
    ALERTMANAGER_URL: str = os.environ.get('ALERTMANAGER_URL', 'http://localhost:9093')
    DATABASE_URL: str = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/aiops')
    PROM_QUERY: str = os.environ.get('PROM_QUERY', 'up')
    LOOKBACK_HOURS: int = int(os.environ.get('LOOKBACK_HOURS', 720))
    CHECK_INTERVAL_MINUTES: int = int(os.environ.get('CHECK_INTERVAL_MINUTES', 5))
    PROM_SKIP_SSL: bool = os.environ.get('PROM_SKIP_SSL', 'false').lower() == 'true'
    AM_SKIP_SSL: bool = os.environ.get('AM_SKIP_SSL', 'false').lower() == 'true'
    ALERT_REPEAT_INTERVAL_MINUTES: int = int(os.environ.get('ALERT_REPEAT_INTERVAL_MINUTES', 60))
    CONTAMINATION: float = float(os.environ.get('CONTAMINATION', 0.05))

    # Auto Discovery
    METRIC_DISCOVERY_ENABLED: bool = os.environ.get('METRIC_DISCOVERY_ENABLED', 'true').lower() == 'true'
    METRIC_DISCOVERY_PATTERN: str = os.environ.get('METRIC_DISCOVERY_PATTERN', '^(up|node_cpu_seconds_total|node_memory_.*|node_filesystem_.*|node_network_.*)$')
    MAX_WORKERS: int = int(os.environ.get('MAX_WORKERS', 10))
    ANALYSIS_WINDOW_HOURS: int = int(os.environ.get('ANALYSIS_WINDOW_HOURS', 168)) # Default 7 days

    # Telegram alerts
    TELEGRAM_ENABLED: bool = os.environ.get('TELEGRAM_ENABLED', 'false').lower() == 'true'
    TELEGRAM_BOT_TOKEN: str = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID: str = os.environ.get('TELEGRAM_CHAT_ID', '')

    # Email alerts
    EMAIL_ENABLED: bool = os.environ.get('EMAIL_ENABLED', 'false').lower() == 'true'
    # List of recipients, comma separated
    EMAIL_RECIPIENTS: list = [x.strip() for x in os.environ.get('EMAIL_RECIPIENTS', '').split(',') if x.strip()]
    
    SMTP_FROM: str = os.environ.get('SMTP_FROM', 'aiops@domain.com')
    _smarthost = os.environ.get('SMTP_SMARTHOST', 'smtp.gmail.com:587')
    if ':' in _smarthost:
        SMTP_SERVER, SMTP_PORT = _smarthost.split(':')
        SMTP_PORT = int(SMTP_PORT)
    else:
        SMTP_SERVER = _smarthost
        SMTP_PORT = 587
        
    SMTP_AUTH_USERNAME: str = os.environ.get('SMTP_AUTH_USERNAME', '')
    SMTP_AUTH_PASSWORD: str = os.environ.get('SMTP_AUTH_PASSWORD', '')


settings = Settings()
