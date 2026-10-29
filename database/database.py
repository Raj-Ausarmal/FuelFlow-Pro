
import sqlite3
import os
from pathlib import Path

DATABASE_PATH = Path(
    os.environ.get("DATABASE_PATH", Path(__file__).parent / "fuelflow.db")
)


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pumps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pump_number INTEGER UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'AVAILABLE',
            current_token TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_code TEXT UNIQUE NOT NULL,
            vehicle_number TEXT NOT NULL,
            fuel_type TEXT NOT NULL,
            amount REAL NOT NULL,
            pump_number INTEGER,
            status TEXT NOT NULL DEFAULT 'WAITING',
            created_at TEXT NOT NULL,
            scanned_at TEXT,
            completed_at TEXT,
            customer_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_code TEXT NOT NULL,
            vehicle_number TEXT NOT NULL,
            fuel_type TEXT NOT NULL,
            amount REAL NOT NULL,
            pump_number INTEGER NOT NULL,
            started_at TEXT,
            completed_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            vehicle_number TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(customer_id, vehicle_number),
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pump_number INTEGER NOT NULL,
            issue_reason TEXT NOT NULL,
            maintenance_date TEXT NOT NULL,
            service_notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (pump_number) REFERENCES pumps (pump_number)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            otp_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_password_reset_otps_customer
        ON password_reset_otps (customer_id, id DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_maintenance_history_pump_date
        ON maintenance_history (pump_number, maintenance_date DESC)
    """)

    # Safely migrate existing databases.
    customer_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(customers)"
        ).fetchall()
    }

    for column, definition in [
        ("full_name", "TEXT"),
        ("email", "TEXT"),
        ("phone", "TEXT"),
    ]:
        if column not in customer_columns:
            cursor.execute(
                f"ALTER TABLE customers ADD COLUMN {column} {definition}"
            )

    token_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(tokens)"
        ).fetchall()
    }

    if "customer_id" not in token_columns:
        cursor.execute(
            "ALTER TABLE tokens ADD COLUMN customer_id INTEGER"
        )

    for pump_number in range(1, 4):
        cursor.execute("""
            INSERT OR IGNORE INTO pumps (pump_number, status)
            VALUES (?, 'AVAILABLE')
        """, (pump_number,))

    connection.commit()
    connection.close()


if __name__ == "__main__":
    initialize_database()
