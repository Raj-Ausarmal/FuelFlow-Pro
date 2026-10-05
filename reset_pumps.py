import sqlite3

connection = sqlite3.connect("database/fuelflow.db")

connection.execute("""
    UPDATE pumps
    SET status = 'AVAILABLE',
        current_token = NULL
""")

connection.commit()
connection.close()

print("All pumps reset to AVAILABLE")