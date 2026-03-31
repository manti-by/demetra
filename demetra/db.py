from collections.abc import AsyncGenerator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


metadata = MetaData()

sessions = Table(
    "sessions",
    metadata,
    Column("task_id", String(), primary_key=True),
    Column("session_id", String(), nullable=False),
    Column("build_plan", Text(), nullable=False, server_default=""),
    Column("posted_to_linear", Boolean(), nullable=False, server_default="false"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

oauth_tokens = Table(
    "oauth_tokens",
    metadata,
    Column("service", String(), primary_key=True),
    Column("access_token", Text(), nullable=False),
    Column("refresh_token", Text(), nullable=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)

task_status = Table(
    "task_status",
    metadata,
    Column("task_id", String(), primary_key=True),
    Column("project_name", String(), nullable=False),
    Column("status", String(), nullable=False, server_default="pending"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

users = Table(
    "users",
    metadata,
    Column("id", String(), primary_key=True),
    Column("github_id", String(), nullable=False, unique=True),
    Column("github_username", String(), nullable=False),
    Column("email", String(), nullable=True),
    Column("role", String(), nullable=False, server_default="user"),
    Column("keys", Text(), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

jwt_tokens = Table(
    "jwt_tokens",
    metadata,
    Column("token", String(), primary_key=True),
    Column("user_id", String(), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

projects = Table(
    "projects",
    metadata,
    Column("id", String(), primary_key=True),
    Column("user_id", String(), nullable=False),
    Column("linear_project_id", String(), nullable=True),
    Column("name", String(), nullable=False),
    Column("repository_url", String(), nullable=False),
    Column("local_path", String(), nullable=True),
    Column("state", String(), server_default="provisioning", nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


def get_async_engine(db_name: str | None = None, echo: bool = False) -> AsyncEngine:
    from demetra.settings import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

    database = db_name if db_name else DB_NAME
    url = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{database}"
    return create_async_engine(url, echo=echo, isolation_level="AUTOCOMMIT")


def get_async_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session(
    engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession]:
    async_session_maker = get_async_session_maker(engine)
    async with async_session_maker() as session:
        yield session


def get_sync_engine(db_name: str | None = None, echo: bool = False):
    from demetra.settings import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

    database = db_name if db_name else DB_NAME
    url = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{database}"
    return create_engine(url, echo=echo)
