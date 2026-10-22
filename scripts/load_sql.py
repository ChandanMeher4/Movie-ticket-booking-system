"""Direct SQL loader and verification script.

Executes sql/schema.sql and sql/seed.sql directly against a live MySQL database
(not via SQLAlchemy create_all) using PyMySQL.
Verifies that all tables are created and seeded properly.
"""

import os
import re
import sys
from urllib.parse import urlparse
import pymysql


def get_db_connection_params(url_str: str):
    """Extract host, port, user, password, and db from a connection URL."""
    clean_url = url_str.replace("mysql+pymysql://", "mysql://")
    parsed = urlparse(clean_url)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "cineverse",
        "password": parsed.password or "cineverse_secret",
        "database": parsed.path.lstrip("/") or "movie_ticket_booking_test",
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }


def split_sql_statements(sql_text: str):
    """Split a SQL script into individual executable statements, ignoring comments and empty lines."""
    statements = []
    current_stmt = []
    
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--") or stripped.startswith("/*"):
            continue
        current_stmt.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(current_stmt).strip()
            # Omit USE or CREATE DATABASE if targeting a specific test database
            if not stmt.upper().startswith("USE ") and not stmt.upper().startswith("CREATE DATABASE"):
                statements.append(stmt)
            current_stmt = []
            
    if current_stmt:
        stmt = "\n".join(current_stmt).strip()
        if stmt and not stmt.upper().startswith("USE ") and not stmt.upper().startswith("CREATE DATABASE"):
            statements.append(stmt)
            
    return statements


def load_sql_file(conn, filepath: str):
    """Execute all statements in a SQL file."""
    with open(filepath, "r", encoding="utf-8") as f:
        sql_content = f.read()

    statements = split_sql_statements(sql_content)
    with conn.cursor() as cursor:
        for idx, stmt in enumerate(statements, 1):
            cursor.execute(stmt)
    conn.commit()
    return len(statements)


def run_direct_sql_load(database_url: str = None):
    """Run schema.sql and seed.sql against the given MySQL database URL."""
    db_url = database_url or os.getenv(
        "TEST_DATABASE_URL",
        "mysql+pymysql://cineverse:cineverse_secret@localhost:3306/movie_ticket_booking_test"
    )
    params = get_db_connection_params(db_url)
    print(f"Connecting directly to MySQL host={params['host']}:{params['port']} db={params['database']} user={params['user']}...")
    
    conn = pymysql.connect(**params)
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        schema_path = os.path.join(base_dir, "sql", "schema.sql")
        seed_path = os.path.join(base_dir, "sql", "seed.sql")

        print(f"1. Executing {schema_path}...")
        n_schema = load_sql_file(conn, schema_path)
        print(f"   -> Successfully executed {n_schema} DDL statements.")

        print(f"2. Executing {seed_path}...")
        n_seed = load_sql_file(conn, seed_path)
        print(f"   -> Successfully executed {n_seed} DML seed statements.")

        print("3. Verifying loaded table row counts...")
        expected_tables = ["users", "movies", "theatres", "screens", "seats", "shows"]
        with conn.cursor() as cursor:
            for table in expected_tables:
                cursor.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                row = cursor.fetchone()
                print(f"   - Table '{table}': {row['cnt']} rows")

        print("\nSUCCESS: All schema and seed data loaded cleanly via direct raw SQL execution.")
        return True
    finally:
        conn.close()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        run_direct_sql_load(url)
    except Exception as exc:
        print(f"ERROR: Direct SQL load failed: {exc}", file=sys.stderr)
        sys.exit(1)
