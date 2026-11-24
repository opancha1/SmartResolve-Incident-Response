from sqlalchemy import inspect, text

ADDITIONS = {
    "tickets": {
        "updated_at": "DATETIME", "demo_key": "VARCHAR(100)",
        "classification_corrected": "BOOLEAN NOT NULL DEFAULT 0",
    },
    "incidents": {
        "updated_at": "DATETIME", "demo_key": "VARCHAR(100)",
        "assigned_technician": "VARCHAR(100)", "resolution": "TEXT", "confirmed_cause": "TEXT",
        "demo_context": "BOOLEAN NOT NULL DEFAULT 0",
    },
    "security_events": {
        "demo_key": "VARCHAR(100)", "status": "VARCHAR(30) NOT NULL DEFAULT 'Open'",
        "assigned_technician": "VARCHAR(100)", "resolution": "TEXT", "evidence_note": "TEXT",
    },
    "technicians": {"demo_key": "VARCHAR(100)"},
    "network_events": {"demo_key": "VARCHAR(100)"},
    "monitored_endpoints": {"scenario_override": "VARCHAR(20)", "demo_key": "VARCHAR(100)"},
    "availability_checks": {"generated_demo": "BOOLEAN NOT NULL DEFAULT 0", "demo_key": "VARCHAR(100)"},
}


def migrate_operations(engine):
    with engine.begin() as connection:
        for table, additions in ADDITIONS.items():
            existing = {column["name"] for column in inspect(connection).get_columns(table)}
            for field, definition in additions.items():
                if field not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {field} {definition}"))
            if "demo_key" in additions:
                connection.execute(text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS ix_{table}_demo_key ON {table} (demo_key)"
                ))
