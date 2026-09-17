"""Database schema.

units            -- one row per physical unit, links it to its raw-material batch
batches          -- genealogy: which material source a batch came from
station_events   -- one row per scan; a unit gets up to one per station
daily_scores     -- traceability completeness score, computed once per day
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Batch(Base):
    __tablename__ = "batches"

    batch_id = Column(String, primary_key=True)
    material_source = Column(String, nullable=False)

    units = relationship("Unit", back_populates="batch")


class Unit(Base):
    __tablename__ = "units"

    unit_id = Column(String, primary_key=True)
    batch_id = Column(String, ForeignKey("batches.batch_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    batch = relationship("Batch", back_populates="units")
    events = relationship("StationEvent", back_populates="unit")

    __table_args__ = (Index("ix_units_batch_id", "batch_id"),)


class StationEvent(Base):
    __tablename__ = "station_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(String, ForeignKey("units.unit_id"), nullable=False)
    station = Column(String, nullable=False)  # "assembly" | "test" | "pack"
    timestamp = Column(DateTime, nullable=False)
    operator = Column(String, nullable=False)
    cycle_time = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    pass_fail = Column(String, nullable=False)  # "pass" | "fail"

    # Set when the integrity-layer reconciliation script backfills an event
    # for a unit that had a genuinely missing scan. Keeps the audit trail
    # honest about which rows are real sensor data vs. manual re-entry.
    reconciled = Column(Boolean, default=False, nullable=False)

    unit = relationship("Unit", back_populates="events")

    __table_args__ = (
        Index("ix_station_events_unit_id", "unit_id"),
        Index("ix_station_events_unit_station", "unit_id", "station"),
    )


class DailyScore(Base):
    __tablename__ = "daily_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    score_date = Column(String, nullable=False)  # "YYYY-MM-DD"
    total_units = Column(Integer, nullable=False)
    complete_units = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_daily_scores_date", "score_date"),)
