# ruff: noqa: F401, F403

import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine

from migrations.env_utils import create_folder_if_not_exists, load_models
from src._core.infrastructure.persistence.rdb.database import Base, create_sync_dsn

# Load Alembic configuration file
config = context.config

# Resolve environment: ENV variable > alembic.ini > default "local"
env = os.getenv("ENV") or config.get_main_option("env") or "local"
valid_envs = {"quickstart", "local", "dev", "stg", "prod"}
if env not in valid_envs:
    raise RuntimeError(
        f"Invalid ENV '{env}'. Expected one of: {', '.join(sorted(valid_envs))}. "
        "Usage: ENV=local alembic upgrade head"
    )

# A dotenv file is the local workflow, not a hard requirement. Containers and
# CI supply DATABASE_* through the process environment and never ship
# `_env/*.env` — it is gitignored, and baking one into an image layer is what
# the Dockerfile was changed to stop doing. Hard-failing here made
# `alembic upgrade head` impossible inside the image even after `migrations/`
# was copied in.
env_file = f"_env/{env}.env"
env_file_present = os.path.exists(env_file)
if not env_file_present and not os.getenv("DATABASE_ENGINE"):
    raise RuntimeError(
        f"Environment file not found: {env_file}, and DATABASE_ENGINE is not "
        "set in the process environment. Provide one or the other."
    )

print("=" * 100)
print(f"Alembic ENV: {env} (source: {'file' if env_file_present else 'environment'})")
print("=" * 100)

create_folder_if_not_exists("migrations/versions")

load_models()

if env_file_present:
    # override=True keeps the local workflow's precedence: the dotenv file wins
    # over whatever is already exported in the shell. When no file exists the
    # process environment is the only source, so skip the call rather than rely
    # on load_dotenv silently returning False.
    load_dotenv(dotenv_path=env_file, override=True)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

engine_type = os.getenv("DATABASE_ENGINE") or "postgresql"

url = create_sync_dsn(
    engine=engine_type,
    database_user=quote_plus(os.getenv("DATABASE_USER") or ""),
    database_password=quote_plus(os.getenv("DATABASE_PASSWORD") or ""),
    database_host=os.getenv("DATABASE_HOST") or "",
    database_port=int(os.getenv("DATABASE_PORT") or "5432"),
    database_name=os.getenv("DATABASE_NAME") or "",
)

# Set target_metadata to Base.metadata
target_metadata = Base.metadata


# Migration execution functions
def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        url=url,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=False,
            )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
