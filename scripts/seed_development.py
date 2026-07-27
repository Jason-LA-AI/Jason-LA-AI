"""Initialize PostgreSQL and add local inquiry test data."""

from app.database.init_db import initialize_database
from app.database.seed import seed_development_inquiries
from app.database.session import SessionFactory


def main() -> None:
    initialize_database()
    with SessionFactory() as session:
        inserted = seed_development_inquiries(session)
    print(f"Development seed complete: {inserted} inquiries inserted.")


if __name__ == "__main__":
    main()
