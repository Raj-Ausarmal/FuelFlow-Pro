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
app.secret_key = "fuelflow-pro-development-secret-key"


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


initialize_database()


def login_required(role=None):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            if "username" not in session:
                if request.path.startswith("/api/"):
                    return jsonify({
                        "error": "Authentication required"
                    }), 401
                return redirect(url_for("login"))

            if role is not None:
                if session.get("role") != role:
                    if request.path.startswith("/api/"):
                        return jsonify({
                            "error": "Access denied"
                        }), 403
                    return redirect(url_for("login"))

            return function(*args, **kwargs)

        return wrapper

    return decorator


def customer_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "customer_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({
                    "error": "Customer authentication required"
                }), 401
            return redirect(url_for("customer_login"))

        return function(*args, **kwargs)

    return wrapper


@app.route("/")
def home():
    if "customer_id" in session:
        return redirect(url_for("customer_dashboard"))

    return redirect(url_for("customer_login"))


@app.route("/customer-login")
def customer_login():
    if "customer_id" in session:
        return redirect(url_for("customer_dashboard"))

    return render_template("customer_login.html")


@app.route("/customer-register")
def customer_register():
    if "customer_id" in session:
        return redirect(url_for("customer_dashboard"))

    return render_template("customer_register.html")


@app.route("/customer-dashboard")
@customer_required
def customer_dashboard():
    return render_template("customer.html")


@app.route("/api/customer/register", methods=["POST"])
def customer_register_api():
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

    if len(username) < 3:
        return jsonify({
            "error": "Username must contain at least 3 characters"
        }), 400

    if len(password) < 6:
        return jsonify({
            "error": "Password must contain at least 6 characters"
        }), 400

    connection = get_connection()

    existing_customer = connection.execute("""
        SELECT id
        FROM customers
        WHERE username = ?
    """, (username,)).fetchone()

    if existing_customer is not None:
        connection.close()

        return jsonify({
            "error": "Username already exists"
        }), 409

    password_hash = generate_password_hash(password)
    created_at = datetime.now().isoformat(timespec="seconds")

    cursor = connection.execute("""
        INSERT INTO customers (
            username,
            password_hash,
            created_at
        )
        VALUES (?, ?, ?)
    """, (
        username,
        password_hash,
        created_at
    ))

    connection.commit()

    customer_id = cursor.lastrowid

    connection.close()

    session.clear()
    session["customer_id"] = customer_id
    session["customer_username"] = username

    return jsonify({
        "message": "Customer registration successful",
        "username": username
    }), 201


@app.route("/api/customer/login", methods=["POST"])
def customer_login_api():
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

    connection = get_connection()

    customer = connection.execute("""
        SELECT id, username, password_hash
        FROM customers
        WHERE username = ?
    """, (username,)).fetchone()

    connection.close()

    if customer is None:
        return jsonify({
            "error": "Invalid username or password"
        }), 401

    if not check_password_hash(customer["password_hash"], password):
        return jsonify({
            "error": "Invalid username or password"
        }), 401

    session.clear()
    session["customer_id"] = customer["id"]
    session["customer_username"] = customer["username"]

    return jsonify({
        "message": "Customer login successful",
        "username": customer["username"]
    }), 200


@app.route("/customer-logout")
def customer_logout():
    session.pop("customer_id", None)
    session.pop("customer_username", None)

    return redirect(url_for("customer_login"))


@app.route("/api/customer/profile", methods=["GET"])
@customer_required
def customer_profile():
    return jsonify({
        "username": session.get("customer_username")
    }), 200


@app.route("/login")
def login():
    if "username" in session:
        if session.get("role") == "operator":
            return redirect(url_for("operator"))

        if session.get("role") == "admin":
            return redirect(url_for("admin"))

    return render_template("login.html")


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

    if not check_password_hash(user["password"], password):
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


@app.route("/logout")
def logout():
    session.clear()

    return redirect(url_for("home"))


@app.route("/operator")
@login_required("operator")
def operator():
    return render_template("operator.html")


@app.route("/admin")
@login_required("admin")
def admin():
    return render_template("analytics.html")


@app.route("/api/pumps")
@login_required("operator")
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
@customer_required
def create_token():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    vehicle_number = data.get("vehicle_number")
    fuel_type = data.get("fuel_type")
    amount = data.get("amount")

    if not vehicle_number or not fuel_type or amount is None:
        return jsonify({
            "error": "vehicle_number, fuel_type and amount are required"
        }), 400

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

    vehicle_number = vehicle_number.strip().upper()
    fuel_type = fuel_type.strip().upper()

    allowed_fuel_types = ["PETROL", "DIESEL"]

    if fuel_type not in allowed_fuel_types:
        return jsonify({
            "error": "Fuel type must be PETROL or DIESEL"
        }), 400

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


@app.route("/api/operator/scan", methods=["POST"])
@login_required("operator")
def operator_scan():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    token_code = data.get("token_code")
    pump_number = data.get("pump_number")

    if not token_code or pump_number is None:
        return jsonify({
            "error": "token_code and pump_number are required"
        }), 400

    token_code = token_code.strip().upper()

    try:
        pump_number = int(pump_number)
    except (ValueError, TypeError):
        return jsonify({
            "error": "pump_number must be a valid number"
        }), 400

    connection = get_connection()

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

    if token["status"] != "WAITING":
        connection.close()

        return jsonify({
            "error": f"Token cannot be scanned because its status is {token['status']}"
        }), 400

    pump = connection.execute("""
        SELECT *
        FROM pumps
        WHERE pump_number = ?
    """, (pump_number,)).fetchone()

    if pump is None:
        connection.close()

        return jsonify({
            "error": "Pump not found"
        }), 404

    if pump["status"] != "AVAILABLE":
        connection.close()

        return jsonify({
            "error": f"Pump {pump_number} is currently {pump['status']}"
        }), 400

    scanned_at = datetime.now().isoformat(timespec="seconds")

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
        "message": "Token verified and assigned to pump successfully",
        "token": {
            "token_code": token_code,
            "vehicle_number": token["vehicle_number"],
            "fuel_type": token["fuel_type"],
            "amount": token["amount"],
            "pump_number": pump_number,
            "status": "AUTHORIZED",
            "scanned_at": scanned_at
        }
    }), 200


@app.route("/api/tokens/<token_code>", methods=["GET"])
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
@login_required("operator")
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


@app.route("/api/transactions", methods=["GET"])
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


@app.route("/api/analytics", methods=["GET"])
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
        "total_transactions": total_transactions,
        "total_revenue": total_revenue,
        "petrol_sales": petrol_sales,
        "diesel_sales": diesel_sales,
        "pump_usage": [
            dict(pump)
            for pump in pump_usage
        ]
    }), 200


if __name__ == "__main__":
    app.run(debug=True)