from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
import pandas as pd
import json
import math
import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# -------------------- DATABASE SETUP --------------------

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB at startup
init_db()

# -------------------- DISTANCE CALCULATION --------------------

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in KM
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# -------------------- LOAD CSV DATA --------------------

df = None
csv_file = 'india_ev_charging_stations.csv'

if os.path.exists(csv_file):
    try:
        df = pd.read_csv(csv_file)
        df.columns = df.columns.str.strip().str.lower()
        print(f"✅ Loaded {len(df)} EV stations")
    except Exception as e:
        print("❌ CSV Load Error:", e)
        df = pd.DataFrame()
else:
    print("❌ CSV file not found!")

# -------------------- AUTH ROUTES --------------------

@app.route('/', methods=['GET'])
def home():
    if 'user_id' in session:
        return render_template("index.html", username=session.get('username'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['username'] = username
            flash('Welcome back!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials!', 'error')

    return render_template("login.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        try:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                      (username, email, generate_password_hash(password)))
            conn.commit()
            conn.close()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or Email already exists!', 'error')

    return render_template("register.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------- MAIN LOGIC ROUTE --------------------

@app.route('/result', methods=['POST'])
def result():
    try:
        user_lat = float(request.form.get('latitude', 0))
        user_lon = float(request.form.get('longitude', 0))
        battery = float(request.form.get('battery_percent', 50))

        if not user_lat or not user_lon:
            flash("Invalid location data.", "error")
            return redirect(url_for('home'))

        safe_battery = max(0, battery - 5)
        max_range = safe_battery * 2.5

        if df is None or df.empty:
            flash("No EV station data available.", "error")
            return redirect(url_for('home'))

        nearby_stations = []

        for _, row in df.iterrows():
            try:
                s_lat = float(row.get('latitude', row.get('lattitude', 0)))
                s_lon = float(row.get('longitude', 0))

                if not s_lat or not s_lon:
                    continue

                distance = calculate_distance(user_lat, user_lon, s_lat, s_lon)

                if distance <= max_range:
                    nearby_stations.append({
                        "name": str(row.get('name', 'Unknown')),
                        "lat": s_lat,
                        "lon": s_lon,
                        "distance": round(distance, 2),
                        "address": str(row.get('address', 'N/A')),
                        "city": str(row.get('city', 'N/A')),
                        "state": str(row.get('state', 'N/A'))
                    })
            except:
                continue

        nearby_stations.sort(key=lambda x: x['distance'])

        return render_template(
            "result.html",
            user_lat=user_lat,
            user_lon=user_lon,
            stations=nearby_stations,
            stations_json=json.dumps(nearby_stations),
            count=len(nearby_stations),
            battery=int(battery),
            max_range=round(max_range, 1),
            username=session.get('username', 'Guest')
        )

    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for('home'))

# -------------------- RUN APP --------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
