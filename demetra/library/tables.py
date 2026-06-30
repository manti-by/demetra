from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)


metadata = MetaData()

sessions = Table(
    "sessions",
    metadata,
    Column("task_id", String(), primary_key=True),
    Column("name", String(), nullable=True),
    Column("session_id", String(), nullable=True),
    Column("build_plan", Text(), nullable=False, server_default=""),
    Column("posted_to_linear", Boolean(), nullable=False, server_default="false"),
    Column("step", String(), nullable=False, server_default="initial"),
    Column("project_id", String(), nullable=True),
    Column("user_id", String(), nullable=True),
    Column("run_attempts", Integer(), nullable=False, server_default="0"),
    Column("pr_link", String(), nullable=True),
    Column("linear_link", String(), nullable=True),
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

users = Table(
    "users",
    metadata,
    Column("id", String(), primary_key=True),
    Column("github_id", String(), nullable=False, unique=True),
    Column("github_username", String(), nullable=False),
    Column("email", String(), nullable=True),
    Column("avatar_url", String(), nullable=True),
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
    Column("repository_name", String(), nullable=False),
    Column("repository_owner", String(), nullable=False),
    Column("local_path", String(), nullable=True),
    Column("state", String(), server_default="provisioning", nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

project_environments = Table(
    "project_environment",
    metadata,
    Column("id", String(), primary_key=True),
    Column("project_id", String(), ForeignKey("projects.id"), nullable=False),
    Column("key", String(), nullable=False),
    Column("value", Text(), nullable=False),
    Column("type", String(), nullable=False, server_default="text"),
    UniqueConstraint("project_id", "key"),
    CheckConstraint("type IN ('text', 'encrypted')", name="ck_project_environment_type"),
)

session_history = Table(
    "session_history",
    metadata,
    Column("id", String(), primary_key=True),
    Column("session_id", String(), nullable=False, index=True),
    Column("step", String(), nullable=False),
    Column("length", Integer(), nullable=True),
    Column("input_tokens", Integer(), nullable=True),
    Column("output_tokens", Integer(), nullable=True),
    Column("reasoning_tokens", Integer(), nullable=True),
    Column("cache_read_tokens", Integer(), nullable=True),
    Column("cache_write_tokens", Integer(), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
)
