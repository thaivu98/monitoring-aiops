from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings


engine = create_engine(
    settings.DATABASE_URL, 
    echo=False,
    pool_size=20,          # Tăng pool size để chịu tải 10 luồng parallel
    max_overflow=20,       # Cho phép tràn thêm 20 connection nữa khi cao điểm
    pool_timeout=30        # Chờ tối đa 30s
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
