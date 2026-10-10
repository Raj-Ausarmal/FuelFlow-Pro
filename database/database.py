import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "fuelflow.db"


def get_connection():
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
            completed_at TEXT
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

    # Safely add profile fields to existing databases.
    customer_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(customers)").fetchall()
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

    for pump_number in range(1, 4):
        cursor.execute("""
            INSERT OR IGNORE INTO pumps (pump_number, status)
            VALUES (?, 'AVAILABLE')
        """, (pump_number,))

    connection.commit()
    connection.close()
