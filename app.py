from flask import (
    Flask,
    jsonify,
    request,
    render_template,
    session,
    redirect,
    url_for
)

from database.database import initialize_database, get_connection
from datetime import datetime
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
import secrets


app = Flask(__name__)

# ============================================================
# FLASK SESSION SECURITY
# ============================================================

app.secret_key = "fuelflow-pro-development-secret-key"


# ============================================================
# LOGIN CREDENTIALS
# ============================================================

USERS = {
    "operator": {
        "password": generate_password_hash("operator123"),
        "role": "operator"
    },

    "admin": {
        "password": generate_password_hash("admin123"),
        "role": "admin"
    }
}


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

initialize_database()


# ============================================================
# AUTHENTICATION HELPERS
# ============================================================

def login_required(role=None):

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            if "username" not in session:

                # API request
                if request.path.startswith("/api/"):
                    return jsonify({
                        "error": "Authentication required"
                    }), 401

                return redirect(url_for("login"))

            if role is not None:

                if session.get("role") != role:

                    # API request
                    if request.path.startswith("/api/"):
                        return jsonify({
                            "error": "Access denied"
                        }), 403

                    return redirect(url_for("login"))

            return function(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# LOGIN PAGE
# ============================================================

@app.route("/login")
def login():

    if "username" in session:

        if session.get("role") == "operator":
            return redirect(url_for("operator"))

        if session.get("role") == "admin":
            return redirect(url_for("admin"))

    return render_template("login.html")


# ============================================================
# LOGIN API
# ============================================================

@app.route("/api/login", methods=["POST"])
def login_api():

    data = request.get_json()

    if not data:

        return jsonify({
            "error": "Request body is required"
        }), 400

    username = data.get("username")
    password = data.get("password")

    if not username or not password:

        return jsonify({
            "error": "Username and password are required"
        }), 400

    username = username.strip().lower()

    user = USERS.get(username)

    if user is None:

        return jsonify({
            "error": "Invalid username or password"
        }), 401

    if not check_password_hash(
        user["password"],
        password
    ):

        return jsonify({
            "error": "Invalid username or password"
        }), 401

    session.clear()

    session["username"] = username
    session["role"] = user["role"]

    return jsonify({
        "message": "Login successful",
        "username": username,
        "role": user["role"]
    }), 200


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# ============================================================
# CUSTOMER PAGE
# ============================================================

@app.route("/")
def home():

    return render_template("customer.html")


# ============================================================
# OPERATOR PAGE
# ============================================================

@app.route("/operator")
@login_required("operator")
def operator():

    return render_template("operator.html")


# ============================================================
# ADMIN / ANALYTICS PAGE
# ============================================================

@app.route("/admin")
@login_required("admin")
def admin():

    return render_template("analytics.html")


# ============================================================
# GET PUMPS
# ============================================================

@app.route("/api/pumps")
@login_required("operator")
def get_pumps():

    connection = get_connection()

    pumps = connection.execute("""
        SELECT
            pump_number,
            status,
            current_token
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


# ============================================================
# CREATE FUEL TOKEN
# ============================================================

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
            "error":
                "vehicle_number, fuel_type and amount are required"
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

    allowed_fuel_types = [
        "PETROL",
        "DIESEL"
    ]

    if fuel_type not in allowed_fuel_types:

        return jsonify({
            "error":
                "Fuel type must be PETROL or DIESEL"
        }), 400

    # Generate unique token

    token_code = (
        "FF-" +
        secrets.token_hex(4).upper()
    )

    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

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
        VALUES (
            ?,
            ?,
            ?,
            ?,
            NULL,
            'WAITING',
            ?
        )
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

        "message":
            "Fuel token created successfully",

        "token": {

            "token_code":
                token_code,

            "vehicle_number":
                vehicle_number,

            "fuel_type":
                fuel_type,

            "amount":
                amount,

            "pump_number":
                None,

            "status":
                "WAITING",

            "created_at":
                created_at
        }

    }), 201


# ============================================================
# OPERATOR SCAN TOKEN
# ============================================================

@app.route(
    "/api/operator/scan",
    methods=["POST"]
)
@login_required("operator")
def operator_scan():

    data = request.get_json()

    if not data:

        return jsonify({
            "error":
                "Request body is required"
        }), 400

    token_code = data.get("token_code")
    pump_number = data.get("pump_number")

    if not token_code or pump_number is None:

        return jsonify({
            "error":
                "token_code and pump_number are required"
        }), 400

    token_code = token_code.strip().upper()

    try:

        pump_number = int(pump_number)

    except (ValueError, TypeError):

        return jsonify({
            "error":
                "pump_number must be a valid number"
        }), 400

    connection = get_connection()

    # Find token

    token = connection.execute("""
        SELECT *
        FROM tokens
        WHERE token_code = ?
    """, (
        token_code,
    )).fetchone()

    if token is None:

        connection.close()

        return jsonify({
            "error": "Token not found"
        }), 404

    # Token must be WAITING

    if token["status"] != "WAITING":

        connection.close()

        return jsonify({
            "error":
                f"Token cannot be scanned because "
                f"its status is {token['status']}"
        }), 400

    # Find physical pump

    pump = connection.execute("""
        SELECT *
        FROM pumps
        WHERE pump_number = ?
    """, (
        pump_number,
    )).fetchone()

    if pump is None:

        connection.close()

        return jsonify({
            "error": "Pump not found"
        }), 404

    # Pump must be available

    if pump["status"] != "AVAILABLE":

        connection.close()

        return jsonify({
            "error":
                f"Pump {pump_number} is currently "
                f"{pump['status']}"
        }), 400

    scanned_at = datetime.now().isoformat(
        timespec="seconds"
    )

    # Assign token to pump

    connection.execute("""
        UPDATE tokens
        SET
            pump_number = ?,
            status = 'AUTHORIZED',
            scanned_at = ?
        WHERE token_code = ?
    """, (
        pump_number,
        scanned_at,
        token_code
    ))

    # Make pump busy

    connection.execute("""
        UPDATE pumps
        SET
            status = 'BUSY',
            current_token = ?
        WHERE pump_number = ?
    """, (
        token_code,
        pump_number
    ))

    connection.commit()
    connection.close()

    return jsonify({

        "message":
            "Token verified and assigned "
            "to pump successfully",

        "token": {

            "token_code":
                token_code,

            "vehicle_number":
                token["vehicle_number"],

            "fuel_type":
                token["fuel_type"],

            "amount":
                token["amount"],

            "pump_number":
                pump_number,

            "status":
                "AUTHORIZED",

            "scanned_at":
                scanned_at
        }

    }), 200


# ============================================================
# GET TOKEN
# ============================================================

@app.route(
    "/api/tokens/<token_code>",
    methods=["GET"]
)
@login_required("operator")
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
    """, (
        token_code.upper(),
    )).fetchone()

    connection.close()

    if token is None:

        return jsonify({
            "error": "Token not found"
        }), 404

    return jsonify({

        "token_code":
            token["token_code"],

        "vehicle_number":
            token["vehicle_number"],

        "fuel_type":
            token["fuel_type"],

        "amount":
            token["amount"],

        "pump_number":
            token["pump_number"],

        "status":
            token["status"],

        "created_at":
            token["created_at"],

        "scanned_at":
            token["scanned_at"],

        "completed_at":
            token["completed_at"]
    })


# ============================================================
# COMPLETE REFUELING
# ============================================================

@app.route(
    "/api/operator/complete",
    methods=["POST"]
)
@login_required("operator")
def complete_refueling():

    data = request.get_json()

    if not data:

        return jsonify({
            "error":
                "Request body is required"
        }), 400

    token_code = data.get("token_code")

    if not token_code:

        return jsonify({
            "error":
                "token_code is required"
        }), 400

    token_code = token_code.strip().upper()

    connection = get_connection()

    # Find token

    token = connection.execute("""
        SELECT *
        FROM tokens
        WHERE token_code = ?
    """, (
        token_code,
    )).fetchone()

    if token is None:

        connection.close()

        return jsonify({
            "error":
                "Token not found"
        }), 404

    # Token must be AUTHORIZED

    if token["status"] != "AUTHORIZED":

        connection.close()

        return jsonify({
            "error":
                f"Refueling cannot be completed "
                f"because token status is "
                f"{token['status']}"
        }), 400

    pump_number = token["pump_number"]

    if pump_number is None:

        connection.close()

        return jsonify({
            "error":
                "Token is not assigned to a pump"
        }), 400

    completed_at = datetime.now().isoformat(
        timespec="seconds"
    )

    # Create transaction

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

    # Expire token

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

    # Free pump

    connection.execute("""
        UPDATE pumps
        SET
            status = 'AVAILABLE',
            current_token = NULL
        WHERE pump_number = ?
    """, (
        pump_number,
    ))

    connection.commit()
    connection.close()

    return jsonify({

        "message":
            "Refueling completed successfully. "
            "Token expired and pump is available.",

        "transaction": {

            "token_code":
                token["token_code"],

            "vehicle_number":
                token["vehicle_number"],

            "fuel_type":
                token["fuel_type"],

            "amount":
                token["amount"],

            "pump_number":
                pump_number,

            "started_at":
                token["scanned_at"],

            "completed_at":
                completed_at,

            "token_status":
                "EXPIRED",

            "pump_status":
                "AVAILABLE"
        }

    }), 200


# ============================================================
# TRANSACTION HISTORY
# ============================================================

@app.route(
    "/api/transactions",
    methods=["GET"]
)
@login_required("admin")
def get_transactions():

    connection = get_connection()

    transactions = connection.execute("""
        SELECT
            id,
            token_code,
            vehicle_number,
            fuel_type,
            amount,
            pump_number,
            started_at,
            completed_at
        FROM transactions
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return jsonify([
        dict(transaction)
        for transaction in transactions
    ]), 200


# ============================================================
# ANALYTICS
# ============================================================

@app.route(
    "/api/analytics",
    methods=["GET"]
)
@login_required("admin")
def get_analytics():

    connection = get_connection()

    total_transactions = connection.execute("""
        SELECT COUNT(*) AS total
        FROM transactions
    """).fetchone()["total"]

    total_revenue = connection.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
    """).fetchone()["total"]

    petrol_sales = connection.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE fuel_type = 'PETROL'
    """).fetchone()["total"]

    diesel_sales = connection.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE fuel_type = 'DIESEL'
    """).fetchone()["total"]

    pump_usage = connection.execute("""
        SELECT
            pump_number,
            COUNT(*) AS transactions,
            COALESCE(SUM(amount), 0) AS revenue
        FROM transactions
        GROUP BY pump_number
        ORDER BY pump_number
    """).fetchall()

    connection.close()

    return jsonify({

        "total_transactions":
            total_transactions,

        "total_revenue":
            total_revenue,

        "petrol_sales":
            petrol_sales,

        "diesel_sales":
            diesel_sales,

        "pump_usage": [
            dict(pump)
            for pump in pump_usage
        ]
    }), 200


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(debug=True)