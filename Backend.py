from flask import Flask, request, jsonify, render_template
import mysql.connector

app = Flask(__name__)

# --- CONFIGURATION ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'your_username',      # Change this
    'password': 'your_password',  # Change this
    'database': 'rfid_system'
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

# --- HARDWARE API (Called by ESP8266) ---
@app.route('/api/scan', methods=['POST'])
def handle_scan():
    data = request.get_json()
    if not data or 'uid' not in data:
        return jsonify({"status": "Error", "message": "No UID provided"}), 400
        
    uid = data['uid']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Check if active user
    cursor.execute("SELECT * FROM users WHERE rfid_uid = %s AND is_active = TRUE", (uid,))
    user = cursor.fetchone()
    
    status = 'Granted' if user else 'Denied'
    
    # Log the scan
    cursor.execute("INSERT INTO attendance_logs (rfid_uid, status) VALUES (%s, %s)", (uid, status))
    conn.commit()
    
    cursor.close()
    conn.close()
    
    # Return JSON that the ESP8266 will parse
    return jsonify({"status": status, "user": user['name'] if user else "Unknown"})

# --- CRUD APIs (Called by Frontend) ---
@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (rfid_uid, name, role) VALUES (%s, %s, %s)",
            (data['rfid_uid'], data['name'], data.get('role', 'Employee'))
        )
        conn.commit()
        return jsonify({"message": "User added successfully!"}), 201
    except mysql.connector.IntegrityError:
        return jsonify({"error": "UID already exists!"}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET name=%s, role=%s, is_active=%s WHERE id=%s",
        (data['name'], data['role'], data['is_active'], user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "User updated successfully!"})

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "User deleted successfully!"})

@app.route('/api/logs', methods=['GET'])
def get_logs():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Join tables to get the user name alongside the log
    query = """
        SELECT l.scan_time, l.rfid_uid, u.name, l.status 
        FROM attendance_logs l 
        LEFT JOIN users u ON l.rfid_uid = u.rfid_uid 
        ORDER BY l.scan_time DESC LIMIT 50
    """
    cursor.execute(query)
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(logs)

if __name__ == '__main__':
    # Listen on all network interfaces so the ESP8266 can reach it
    app.run(host='0.0.0.0', port=5000)