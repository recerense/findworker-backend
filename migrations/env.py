
from logging.config import fileConfig

from alembic import context

from app.core.config import settings
from app.db.base import Base

from app.modules.auth import models as auth_models
from app.modules.auth import credential_models, models, otp_models, session_models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Use the application's database configuration.
database_url = (
    f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

# Escape percent signs for ConfigParser interpolation.
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def get_extension_tables(connection):
    """Return tables owned by PostgreSQL extensions."""

    result = connection.exec_driver_sql(
        """
        SELECT n.nspname, c.relname
        FROM pg_depend d
        JOIN pg_class c ON c.oid = d.objid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_extension e ON e.oid = d.refobjid
        WHERE d.classid = 'pg_class'::regclass
          AND d.refclassid = 'pg_extension'::regclass
          AND d.deptype = 'e'
          AND c.relkind IN ('r', 'p')
        """
    )

    return {(row[0], row[1]) for row in result}


def include_name(name, type_, parent_names):
    """Include only tables registered in application metadata."""

    if type_ == "table":
        return name in target_metadata.tables

    return True


def run_migrations_online() -> None:
    from app.db.session import engine

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_name=include_name,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
