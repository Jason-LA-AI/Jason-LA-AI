"""SQLAlchemy session factory and FastAPI dependency."""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.database.database import engine


SessionFactory = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_db_session() -> Generator[Session, None, None]:
    """Yield one request-scoped session and roll back failed transactions."""
    session = SessionFactory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
