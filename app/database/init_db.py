"""Local database initialization helpers.

This module creates the tables currently represented by the SQLAlchemy
metadata. Production schema changes should eventually use migrations instead.
"""

from sqlalchemy.engine import Engine

from app.database.database import engine
from app.models import Base


def initialize_database(database_engine: Engine = engine) -> None:
    """Create any missing application tables without deleting existing data."""
    Base.metadata.create_all(bind=database_engine)


if __name__ == "__main__":
    initialize_database()
    print("Database tables initialized.")
