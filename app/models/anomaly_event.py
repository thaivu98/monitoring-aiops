from sqlalchemy import Column, Integer, String, DateTime, Text
from .base import Base
import datetime


class AnomalyEvent(Base):
    __tablename__ = 'anomaly_events'
    id = Column(Integer, primary_key=True)
    metric_fingerprint = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    severity = Column(String, default='warning')
    description = Column(Text)
