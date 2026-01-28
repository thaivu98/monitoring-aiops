import os


class Settings:
    PROM_URL: str = os.environ.get('PROM_URL', 'http://localhost:9090')
    ALERTMANAGER_URL: str = os.environ.get('ALERTMANAGER_URL', 'http://localhost:9093')
    DATABASE_URL: str = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/aiops')
    PROM_QUERY: str = os.environ.get('PROM_QUERY', 'up')


settings = Settings()
