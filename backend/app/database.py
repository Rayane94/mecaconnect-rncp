import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def normalize_database_url(url: str) -> str:
    """Adapte les URL PostgreSQL fournies par les hébergeurs à psycopg v3."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


DATABASE_URL = normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite:///./mecaconnect.db")
)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    future=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)
Base = declarative_base()


def ensure_schema_compatibility() -> None:
    """Ajoute les colonnes récentes sans casser une base déjà existante."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    migrations = {
        "vehicles": {
            "motorization": "VARCHAR(80)",
        },
        "garages": {
            "siret": "VARCHAR(14)",
            "siren": "VARCHAR(9)",
            "legal_name": "VARCHAR(180)",
            "verification_source": "VARCHAR(80)",
            "payment_online_enabled": "BOOLEAN DEFAULT TRUE NOT NULL",
            "deposit_rate": "FLOAT DEFAULT 0.20 NOT NULL",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in migrations.items():
            if table_name not in inspector.get_table_names():
                continue
            existing = {item["name"] for item in inspector.get_columns(table_name)}
            for column_name, ddl in columns.items():
                if column_name not in existing:
                    connection.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")
                    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
