from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
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
    Column("listener_attempts", Integer(), nullable=False, server_default="0"),
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
    Column("github_id", String(), nullable=True),
    Column("github_username", String(), nullable=True),
    Column("email", String(), nullable=False),
    Column("password_hash", String(), nullable=True),
    Column("password_version", Integer(), nullable=False, server_default="1"),
    Column("avatar_url", String(), nullable=True),
    Column("role", String(), nullable=False, server_default="user"),
    Column("keys", Text(), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("uq_users_github_id", "github_id", unique=True, postgresql_where=text("github_id IS NOT NULL")),
    Index("ix_users_email", "email", unique=True),
    CheckConstraint("password_hash IS NOT NULL OR github_id IS NOT NULL", name="ck_users_has_auth"),
)

jwt_tokens = Table(
    "jwt_tokens",
    metadata,
    Column("token", String(), primary_key=True),
    Column("user_id", String(), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("password_version", Integer(), nullable=False, server_default="1"),
)

allowlist_entries = Table(
    "allowlist_entries",
    metadata,
    Column("id", String(), primary_key=True),
    Column("entry_type", String(), nullable=False),
    Column("value", String(), nullable=False),
    Column("note", String(), nullable=True),
    Column("added_by", String(), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("entry_type", "value", name="uq_allowlist_entries_type_value"),
    Index("ix_allowlist_entries_value", "value"),
    CheckConstraint("entry_type IN ('email', 'github_username')", name="ck_allowlist_entries_type"),
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
    Column("project_id", String(), ForeignKey("projects.id"), nullable=True),
    Column("user_id", String(), ForeignKey("users.id"), nullable=True),
    Column("key", String(), nullable=False),
    Column("value", Text(), nullable=False),
    Column("type", String(), nullable=False, server_default="text"),
    Column("scope", String(), nullable=False, server_default="project"),
    Index(
        "uq_environment_project_key", "project_id", "key", unique=True, postgresql_where=text("project_id IS NOT NULL")
    ),
    Index("uq_environment_user_key", "user_id", "key", unique=True, postgresql_where=text("user_id IS NOT NULL")),
    CheckConstraint("type IN ('text', 'encrypted')", name="ck_project_environment_type"),
    CheckConstraint("scope IN ('project', 'user')", name="ck_environment_scope"),
    CheckConstraint(
        "(scope = 'project' AND project_id IS NOT NULL AND user_id IS NULL) "
        "OR (scope = 'user' AND user_id IS NOT NULL AND project_id IS NULL)",
        name="ck_environment_owner",
    ),
)

session_history = Table(
    "session_history",
    metadata,
    Column(name="id", type_=String(), primary_key=True),
    Column(name="session_id", type_=String(), nullable=False, index=True),
    Column(name="step", type_=String(), nullable=False),
    Column(name="length", type_=Integer(), nullable=True),
    Column(name="input_tokens", type_=Integer(), nullable=True),
    Column(name="output_tokens", type_=Integer(), nullable=True),
    Column(name="reasoning_tokens", type_=Integer(), nullable=True),
    Column(name="cache_read_tokens", type_=Integer(), nullable=True),
    Column(name="cache_write_tokens", type_=Integer(), nullable=True),
    Column(name="context_tokens", type_=Integer(), nullable=True),
    Column(name="model", type_=String(), nullable=True),
    Column(name="created_at", type_=DateTime(timezone=True), server_default=text("now()"), nullable=False),
)
