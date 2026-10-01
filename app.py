from flask import Flask, jsonify, request
from database.database import initialize_database, get_connection
from datetime import datetime
import secrets

app = Flask(__name__)

# Initialize database when the application starts
initialize_database()


@app.route("/")
def home():
    return jsonify({
        "project": "FuelFlow Pro",
        "message": "Smart Petrol Pump Management System",
        "status": "Backend running"
    })


@app.route("/api/pumps")
def get_pumps():
    connection = get_connection()

    pumps = connection.execute("""
        SELECT pump_number, status, current_token
        FROM pumps
        ORDER BY pump_number
    """).fetchall()

    connection.close()

    return jsonify([
        {
            "pump_number": pump["pump_number"],
            "status": pump["status"],
            "current_token": pump["current_token"]
        }
        for pump in pumps
    ])


@app.route("/api/tokens", methods=["POST"])
def create_token():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    vehicle_number = data.get("vehicle_number")
    fuel_type = data.get("fuel_type")
    amount = data.get("amount")

    # Validate required fields
    if not vehicle_number or not fuel_type or amount is None:
        return jsonify({
            "error": "vehicle_number, fuel_type and amount are required"
        }), 400

    # Validate amount
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({
            "error": "Amount must be a valid number"
        }), 400

    if amount <= 0:
        return jsonify({
            "error": "Amount must be greater than zero"
        }), 400

    # Normalize values
    vehicle_number = vehicle_number.strip().upper()
    fuel_type = fuel_type.strip().upper()

    allowed_fuel_types = ["PETROL", "DIESEL"]

    if fuel_type not in allowed_fuel_types:
        return jsonify({
            "error": "Fuel type must be PETROL or DIESEL"
        }), 400

    # Generate unique token
    token_code = "FF-" + secrets.token_hex(4).upper()

    created_at = datetime.now().isoformat(timespec="seconds")

    connection = get_connection()

    connection.execute("""
        INSERT INTO tokens (
            token_code,
            vehicle_number,
            fuel_type,
            amount,
            pump_number,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, NULL, 'WAITING', ?)
    """, (
        token_code,
        vehicle_number,
        fuel_type,
        amount,
        created_at
    ))

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Fuel token created successfully",
        "token": {
            "token_code": token_code,
            "vehicle_number": vehicle_number,
            "fuel_type": fuel_type,
            "amount": amount,
            "pump_number": None,
            "status": "WAITING",
            "created_at": created_at
        }
    }), 201

@app.route("/api/tokens/<token_code>", methods=["GET"])
def get_token(token_code):
    connection = get_connection()

    token = connection.execute("""
        SELECT
            token_code,
            vehicle_number,
            fuel_type,
            amount,
            pump_number,
            status,
            created_at,
            scanned_at,
            completed_at
        FROM tokens
        WHERE token_code = ?
    """, (token_code.upper(),)).fetchone()

    connection.close()

    if token is None:
        return jsonify({
            "error": "Token not found"
        }), 404

    return jsonify({
        "token_code": token["token_code"],
        "vehicle_number": token["vehicle_number"],
        "fuel_type": token["fuel_type"],
        "amount": token["amount"],
        "pump_number": token["pump_number"],
        "status": token["status"],
        "created_at": token["created_at"],
        "scanned_at": token["scanned_at"],
        "completed_at": token["completed_at"]
    })

@app.route("/api/operator/complete", methods=["POST"])
def complete_refueling():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    token_code = data.get("token_code")

    if not token_code:
        return jsonify({
            "error": "token_code is required"
        }), 400

    token_code = token_code.strip().upper()

    connection = get_connection()

    # Find the token
    token = connection.execute("""
        SELECT *
        FROM tokens
        WHERE token_code = ?
    """, (token_code,)).fetchone()

    if token is None:
        connection.close()

        return jsonify({
            "error": "Token not found"
        }), 404

    # Token must be AUTHORIZED
    if token["status"] != "AUTHORIZED":
        connection.close()

        return jsonify({
            "error": f"Refueling cannot be completed because token status is {token['status']}"
        }), 400

    pump_number = token["pump_number"]

    if pump_number is None:
        connection.close()

        return jsonify({
            "error": "Token is not assigned to a pump"
        }), 400

    completed_at = datetime.now().isoformat(timespec="seconds")

    # Create completed transaction record
    connection.execute("""
        INSERT INTO transactions (
            token_code,
            vehicle_number,
            fuel_type,
            amount,
            pump_number,
            started_at,
            completed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        token["token_code"],
        token["vehicle_number"],
        token["fuel_type"],
        token["amount"],
        pump_number,
        token["scanned_at"],
        completed_at
    ))

    # Expire the token
    connection.execute("""
        UPDATE tokens
        SET
            status = 'EXPIRED',
            completed_at = ?
        WHERE token_code = ?
    """, (
        completed_at,
        token_code
    ))

    # Make the pump available again
    connection.execute("""
        UPDATE pumps
        SET
            status = 'AVAILABLE',
            current_token = NULL
        WHERE pump_number = ?
    """, (pump_number,))

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Refueling completed successfully. Token expired and pump is available.",
        "transaction": {
            "token_code": token["token_code"],
            "vehicle_number": token["vehicle_number"],
            "fuel_type": token["fuel_type"],
            "amount": token["amount"],
            "pump_number": pump_number,
            "started_at": token["scanned_at"],
            "completed_at": completed_at,
            "token_status": "EXPIRED",
            "pump_status": "AVAILABLE"
        }
    }), 200

if __name__ == "__main__":
    app.run(debug=True)

