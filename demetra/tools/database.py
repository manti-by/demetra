import logging
import re

import asyncpg
from mcp.types import TextContent, Tool

from demetra.tools.result import ToolResult


logger = logging.getLogger(__name__)

TABLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

allowed_tables: set[str] | None = None

SENSITIVE_COLUMNS = frozenset(
    (
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "privatekey",
        "session_token",
        "access_token",
        "refresh_token",
        "credit_card",
        "cc_number",
        "ssn",
        "social_security",
    )
)

db_pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    from demetra.settings import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

    global db_pool
    if db_pool is None:
        if not DB_PASSWORD:
            raise ValueError("DB_PASSWORD environment variable is required")
        db_pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            min_size=1,
            max_size=5,
        )
    return db_pool


async def close_db_pool() -> None:
    global db_pool
    if db_pool is not None:
        await db_pool.close()
        db_pool = None


async def list_tables(pool: asyncpg.Pool) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
    return [{"table_name": row["table_name"]} for row in rows]


async def get_table_definition(pool: asyncpg.Pool, table_name: str) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                kcu.constraint_name,
                kcu.ordinal_position
            FROM information_schema.columns c
            LEFT JOIN information_schema.key_column_usage kcu
                ON c.table_name = kcu.table_name
                AND c.column_name = kcu.column_name
                AND kcu.constraint_name IN (
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE constraint_type = 'PRIMARY KEY'
                )
            WHERE c.table_name = $1 AND c.table_schema = 'public'
            ORDER BY c.ordinal_position
        """,
            table_name,
        )
    return [
        {
            "column_name": row["column_name"],
            "data_type": row["data_type"],
            "is_nullable": row["is_nullable"],
            "column_default": row["column_default"],
            "is_primary_key": row["constraint_name"] is not None,
        }
        for row in rows
    ]


async def _load_allowed_tables(pool: asyncpg.Pool) -> set[str]:
    global allowed_tables
    if allowed_tables is None:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
        allowed_tables = {row["table_name"] for row in rows}
    return allowed_tables


def _validate_table_name(table_name: str, allowed_tables: set[str] | None = None) -> str:
    if not TABLE_NAME_RE.match(table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    if allowed_tables and table_name not in allowed_tables:
        raise ValueError(f"Table not found: {table_name}")
    return table_name


def _validate_column_name(column_name: str, allowed_columns: set[str]) -> str:
    if not TABLE_NAME_RE.match(column_name):
        raise ValueError(f"Invalid column name: {column_name}")
    if column_name not in allowed_columns:
        raise ValueError(f"Column not found: {column_name}")
    return column_name


async def _get_table_columns(pool: asyncpg.Pool, table_name: str) -> set[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
            table_name,
        )
    return {row["column_name"] for row in rows}


def _filter_sensitive_columns(row: dict) -> dict:
    return {k: v for k, v in row.items() if k.lower() not in SENSITIVE_COLUMNS}


async def get_table_count(pool: asyncpg.Pool, table_name: str) -> dict:
    allowed_tables = await _load_allowed_tables(pool)
    validated_name = _validate_table_name(table_name, allowed_tables)
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM quote_ident($1)", validated_name)
    return {"table_name": table_name, "count": count}


async def query_table(
    pool: asyncpg.Pool,
    table_name: str,
    filters: dict | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    limit = min(max(limit, 1), 1000)
    allowed_tables = await _load_allowed_tables(pool)
    validated_name = _validate_table_name(table_name, allowed_tables)
    allowed_columns = await _get_table_columns(pool, validated_name)
    query = "SELECT * FROM quote_ident($1)"
    params = [validated_name]
    if filters:
        where_clauses = []
        for i, (key, value) in enumerate(filters.items()):
            validated_key = _validate_column_name(key, allowed_columns)
            params.append(value)
            where_clauses.append(f'"{validated_key}" = ${i + 2}')
        query += " WHERE " + " AND ".join(where_clauses)
    params.append(limit)
    query += f" LIMIT ${len(params)}"
    params.append(offset)
    query += f" OFFSET ${len(params)}"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [_filter_sensitive_columns(dict(row)) for row in rows]


AVAILABLE_TOOLS = [
    Tool(
        name="list_tables",
        description="List all database tables",
        input_schema={
            "type": "object",
            "properties": {
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
        },
    ),
    Tool(
        name="get_table_definition",
        description="Get the schema definition of a specific table",
        input_schema={
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table"},
            },
            "required": ["table_name"],
        },
    ),
    Tool(
        name="get_table_count",
        description="Get the row count of a specific table",
        input_schema={
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table"},
            },
            "required": ["table_name"],
        },
    ),
    Tool(
        name="query_table",
        description="Query a table with optional filters",
        input_schema={
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table"},
                "filters": {"type": "object", "description": "Optional filters as key-value pairs"},
                "limit": {"type": "integer", "description": "Max rows to return (default 100)"},
                "offset": {"type": "integer", "description": "Row offset for pagination"},
            },
            "required": ["table_name"],
        },
    ),
]


async def list_tools() -> list[Tool]:
    return AVAILABLE_TOOLS


async def call_tool(name: str, arguments: dict | None) -> ToolResult:
    args = arguments or {}
    try:
        pool = await get_db_pool()
        if name == "list_tables":
            tables = await list_tables(pool)
            return ToolResult(content=[TextContent(type="text", text=str(tables))])
        if name == "get_table_definition":
            table_name = args.get("table_name")
            if not table_name:
                return ToolResult(
                    content=[TextContent(type="text", text="Error: table_name is required")],
                    is_error=True,
                )
            definition = await get_table_definition(pool, table_name)
            return ToolResult(content=[TextContent(type="text", text=str(definition))])
        if name == "get_table_count":
            table_name = args.get("table_name")
            if not table_name:
                return ToolResult(
                    content=[TextContent(type="text", text="Error: table_name is required")],
                    is_error=True,
                )
            count = await get_table_count(pool, table_name)
            return ToolResult(content=[TextContent(type="text", text=str(count))])
        if name == "query_table":
            table_name = args.get("table_name")
            if not table_name:
                return ToolResult(
                    content=[TextContent(type="text", text="Error: table_name is required")],
                    is_error=True,
                )
            rows = await query_table(
                pool,
                table_name,
                args.get("filters"),
                args.get("limit", 100),
                args.get("offset", 0),
            )
            return ToolResult(content=[TextContent(type="text", text=str(rows))])
        return ToolResult(
            content=[TextContent(type="text", text=f"Error: Unknown tool {name}")],
            is_error=True,
        )
    except Exception:
        logger.exception(f"Error executing tool {name}")
        return ToolResult(
            content=[TextContent(type="text", text="Error: Database operation failed")],
            is_error=True,
        )
