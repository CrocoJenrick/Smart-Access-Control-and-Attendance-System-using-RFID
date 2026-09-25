from flask import Flask, request, jsonify, send_from_directory
import mysql.connector

app = Flask(__name__)

# --- CONFIGURATION ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',      # Change this
    'password': '12345678',  # Change this
    'database': 'rfid_system'
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def serialize_logs(logs):
    for log in logs:
        if log.get('scan_time'):
            log['scan_time'] = log['scan_time'].strftime('%Y-%m-%dT%H:%M:%S')
    return logs

# --- ROUTES ---
@app.route('/')
def index():
    return send_from_directory(app.root_path, 'Frontend.html')

@app.route('/style.css')
def stylesheet():
    return send_from_directory(app.root_path, 'style.css')

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
    selected_date = request.args.get('date')
    query = """
        SELECT l.scan_time, l.rfid_uid, u.name, l.status 
        FROM attendance_logs l 
        LEFT JOIN users u ON l.rfid_uid = u.rfid_uid 
    """
    params = []
    if selected_date:
        query += " WHERE DATE(l.scan_time) = %s"
        params.append(selected_date)
    query += " ORDER BY l.scan_time DESC LIMIT 50"
    cursor.execute(query, params)
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(serialize_logs(logs))

@app.route('/api/logs', methods=['DELETE'])
def delete_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance_logs")
    conn.commit()
    deleted_count = cursor.rowcount
    cursor.close()
    conn.close()
    return jsonify({"message": "All activity deleted.", "deleted": deleted_count})

@app.route('/api/logs/granted', methods=['DELETE'])
def delete_granted_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance_logs WHERE status = 'Granted'")
    conn.commit()
    deleted_count = cursor.rowcount
    cursor.close()
    conn.close()
    return jsonify({"message": "Granted scans deleted.", "deleted": deleted_count})

@app.route('/api/logs/denied', methods=['DELETE'])
def delete_denied_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance_logs WHERE status = 'Denied'")
    conn.commit()
    deleted_count = cursor.rowcount
    cursor.close()
    conn.close()
    return jsonify({"message": "Denied scans deleted.", "deleted": deleted_count})

if __name__ == '__main__':
    # Listen on all network interfaces so the ESP8266 can reach it
    app.run(host='0.0.0.0', port=5000)