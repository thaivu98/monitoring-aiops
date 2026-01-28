from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
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


class MetricValue(Base):
    __tablename__ = 'metric_values'
    id = Column(Integer, primary_key=True)
    metric_id = Column(Integer, ForeignKey('metrics.id', ondelete='CASCADE'), index=True)
    timestamp = Column(DateTime, index=True)
    value = Column(Float)

    # Composite index for faster range queries per metric
    __table_args__ = (
        Index('idx_metric_timestamp', 'metric_id', 'timestamp'),
    )
