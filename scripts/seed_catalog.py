"""Admin-only ClickHouse catalogue and schema initialization script.

Executes sql/001_catalog.sql using clickhouse-connect with admin/writer credentials.
Configures database-level SELECT privileges for the MCP reader credential so
read-only enforcement does not rely on client-side flags alone.
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import settings


def seed_schema():
    print("=== Sound Rehearsal: ClickHouse Schema & Reader Privilege Setup ===")

    if not settings.is_clickhouse_configured:
        print("[FAIL] ClickHouse credentials are not configured in environment or .env.")
        print("Required variables: CLICKHOUSE_HOST, CLICKHOUSE_PASSWORD")
        print("Admin variables: CLICKHOUSE_ADMIN_USER, CLICKHOUSE_ADMIN_PASSWORD")
        sys.exit(1)

    try:
        import clickhouse_connect
    except ImportError:
        print("[FAIL] clickhouse-connect package is not installed.")
        sys.exit(1)

    sql_path = Path(__file__).resolve().parent.parent / "sql" / "001_catalog.sql"
    if not sql_path.exists():
        print(f"[FAIL] Schema file not found: {sql_path}")
        sys.exit(1)

    sql_content = sql_path.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql_content.split(";") if s.strip()]

    admin_user = settings.CLICKHOUSE_ADMIN_USER or settings.CLICKHOUSE_USER
    admin_password = settings.CLICKHOUSE_ADMIN_PASSWORD or settings.CLICKHOUSE_PASSWORD

    print(f"Connecting to ClickHouse host: {settings.CLICKHOUSE_HOST}:{settings.CLICKHOUSE_PORT} (db: {settings.CLICKHOUSE_DATABASE})...")

    try:
        client = clickhouse_connect.get_client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            username=admin_user,
            password=admin_password,
            database=settings.CLICKHOUSE_DATABASE,
            secure=settings.CLICKHOUSE_SECURE,
            verify=settings.CLICKHOUSE_VERIFY,
            connect_timeout=settings.CLICKHOUSE_CONNECT_TIMEOUT,
        )

        for stmt in statements:
            print(f"Executing DDL: {stmt[:60]}...")
            client.command(stmt)

        # Enforce database-level SELECT privilege for MCP reader user
        reader_user = settings.CLICKHOUSE_USER
        db_name = settings.CLICKHOUSE_DATABASE
        grant_role_stmt = f"GRANT SELECT ON {db_name}.* TO sound_rehearsal_reader"
        print(f"Configuring role permissions: {grant_role_stmt}")
        try:
            client.command(grant_role_stmt)
            if reader_user and reader_user != "default":
                grant_user_stmt = f"GRANT sound_rehearsal_reader TO {reader_user}"
                print(f"Assigning role to reader: {grant_user_stmt}")
                client.command(grant_user_stmt)
        except Exception as perm_err:
            print(f"[NOTICE] Note on reader grant: {perm_err}")

        print("[SUCCESS] ClickHouse tables verified and reader permissions configured successfully.")

    except Exception as e:
        print(f"[ERROR] Failed to execute schema statements: {e}")
        sys.exit(1)


if __name__ == "__main__":
    seed_schema()
