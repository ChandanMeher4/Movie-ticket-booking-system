"""Schema parity verification test.

Validates that SQLAlchemy declarative models (app/models.py) and raw MySQL DDL (sql/schema.sql)
define the exact same tables, columns, foreign keys, and unique constraints,
specifically verifying the critical double-booking barrier: UNIQUE(show_id, seat_id).
"""

from pathlib import Path
import re
import pytest
from app.models import Base


def _parse_schema_sql(sql_text: str):
    """Extract table definitions, columns, and unique constraints from sql/schema.sql."""
    tables = {}
    current_table = None

    # Find CREATE TABLE statements
    table_pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)\s*\((.*?)\)\s*ENGINE",
        re.DOTALL | re.IGNORECASE,
    )

    for match in table_pattern.finditer(sql_text):
        table_name = match.group(1).lower()
        body = match.group(2)
        columns = set()
        unique_constraints = []

        for line in body.split("\n"):
            line = line.strip().rstrip(",")
            if not line or line.startswith("--"):
                continue

            # Check for CONSTRAINT ... UNIQUE (...)
            uq_match = re.search(r"UNIQUE\s+(?:KEY\s+\w+\s*)?\((.*?)\)", line, re.IGNORECASE)
            if uq_match:
                cols = tuple(c.strip().replace("`", "") for c in uq_match.group(1).split(","))
                unique_constraints.append(cols)
                continue

            # Check for column definition (first word is column name)
            ignored_prefixes = (
                "CONSTRAINT", "PRIMARY KEY", "INDEX", "KEY",
                "FOREIGN KEY", "UNIQUE", "ON", "REFERENCES", "CHECK"
            )
            if not line.upper().startswith(ignored_prefixes):
                col_name = line.split()[0].replace("`", "").lower()
                columns.add(col_name)

        tables[table_name] = {
            "columns": columns,
            "unique_constraints": unique_constraints,
        }

    return tables


def test_schema_sql_and_models_parity():
    """Verify sql/schema.sql matches SQLAlchemy models in tables, columns, and unique constraints."""
    schema_path = Path(__file__).parent.parent / "sql" / "schema.sql"
    assert schema_path.exists(), "sql/schema.sql must exist"

    sql_text = schema_path.read_text(encoding="utf-8")
    sql_tables = _parse_schema_sql(sql_text)

    # 1. Verify all 10 tables exist in both
    expected_tables = {
        "users",
        "theatres",
        "screens",
        "movies",
        "shows",
        "seats",
        "bookings",
        "booking_seats",
        "payments",
        "ai_logs",
    }
    assert set(sql_tables.keys()) == expected_tables, f"Tables mismatch: {set(sql_tables.keys()) ^ expected_tables}"
    assert set(Base.metadata.tables.keys()) == expected_tables, f"Models mismatch: {set(Base.metadata.tables.keys()) ^ expected_tables}"

    # 2. Verify all columns match for each table
    for table_name in expected_tables:
        model_cols = {c.name.lower() for c in Base.metadata.tables[table_name].columns}
        sql_cols = sql_tables[table_name]["columns"]
        diff = model_cols ^ sql_cols
        assert not diff, f"Column mismatch in table '{table_name}': model={model_cols}, sql={sql_cols}, diff={diff}"

    # 3. Verify the critical double-booking barrier: UNIQUE(show_id, seat_id) on booking_seats
    from sqlalchemy import UniqueConstraint
    bs_model = Base.metadata.tables["booking_seats"]
    model_unique_sets = [
        tuple(c.name for c in uc.columns) for uc in bs_model.constraints if isinstance(uc, UniqueConstraint)
    ]
    # Check table indexes as well (since unique=True indices define unique constraints)
    for idx in bs_model.indexes:
        if idx.unique:
            model_unique_sets.append(tuple(c.name for c in idx.columns))

    assert any(
        set(cols) == {"show_id", "seat_id"} for cols in model_unique_sets
    ), "SQLAlchemy booking_seats table must define UNIQUE(show_id, seat_id)"

    sql_bs_uniques = sql_tables["booking_seats"]["unique_constraints"]
    assert any(
        set(cols) == {"show_id", "seat_id"} for cols in sql_bs_uniques
    ), "sql/schema.sql booking_seats table must define UNIQUE(show_id, seat_id)"

    # 4. Verify seat grid unique constraint: UNIQUE(screen_id, row_label, seat_number) on seats
    seats_model = Base.metadata.tables["seats"]
    model_seat_uniques = [
        tuple(c.name for c in uc.columns) for uc in seats_model.constraints if isinstance(uc, UniqueConstraint)
    ]
    assert any(
        set(cols) == {"screen_id", "row_label", "seat_number"} for cols in model_seat_uniques
    ), "SQLAlchemy seats table must define UNIQUE(screen_id, row_label, seat_number)"

    sql_seats_uniques = sql_tables["seats"]["unique_constraints"]
    assert any(
        set(cols) == {"screen_id", "row_label", "seat_number"} for cols in sql_seats_uniques
    ), "sql/schema.sql seats table must define UNIQUE(screen_id, row_label, seat_number)"
