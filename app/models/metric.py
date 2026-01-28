from sqlalchemy import Column, Integer, String, Float, DateTime
from .base import Base
import datetime


class MetricModel(Base):
    __tablename__ = 'metrics'
    id = Column(Integer, primary_key=True)
    metric_fingerprint = Column(String, unique=True, index=True)
    job = Column(String, nullable=True)
    instance = Column(String, nullable=True)
    mean = Column(Float, nullable=True)
    std = Column(Float, nullable=True)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
