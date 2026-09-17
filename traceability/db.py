"""SQLAlchemy engine/session setup, shared by every process in the system."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from traceability.config import DB_URL

# check_same_thread=False lets SQLite be used from the MQTT callback thread
# in the ingest service. Fine for this sim; a real Postgres deployment
# wouldn't need this flag at all.
_connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

engine = create_engine(DB_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    """Create all tables if they don't already exist."""
    from traceability import models  # noqa: F401  (register models on Base)
    models.Base.metadata.create_all(engine)
