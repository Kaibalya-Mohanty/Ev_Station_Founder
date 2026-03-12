from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from knn_clustering import EVStationClusterer
import pandas as pd
import json
import math
import os
import sqlite3
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from werkzeug.security import generate_password_hash, check_password_hash
import requests as http_requests

app = Flask(__name__)
app.config['SECRET_KEY'] = "ev_charge_finder_secret_key_2026"

DATABASE = "users.db"

# Load API key from environment
OPENCAGE_API_KEY = os.environ.get("OPENCAGE_API_KEY")

df = None
ml_model = None
clusterer = None


# ==============================
# DATABASE
# ==============================

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


init_db()


# ==============================
# LOAD CSV
# ==============================

csv_file = os.path.join(os.path.dirname(__file__), "india_ev_charging_stations.csv")

if os.path.exists(csv_file):

    try:

        df = pd.read_csv(csv_file)

        df.columns = df.columns.str.strip()

        df['lattitude'] = (
            df['lattitude']
            .astype(str)
            .str.replace(',', '')
            .str.strip()
            .astype(float)
        )

        df['longitude'] = (
            df['longitude']
            .astype(str)
            .str.replace(',', '')
            .str.strip()
            .astype(float)
        )

        print("EV Stations Loaded:", len(df))

    except Exception as e:
        print("CSV Error:", e)
        df = pd.DataFrame()

else:
    print("CSV not found")
    df = pd.DataFrame()


# ==============================
# ML MODEL
# ==============================

def train_demand_model():
    global ml_model

    if df.empty:
        return

    try:

        X = df[['lattitude', 'longitude']].values
        y = np.random.randint(20, 200, size=len(df))

        ml_model = RandomForestRegressor(n_estimators=50)
        ml_model.fit(X, y)

        print("ML model trained")

    except Exception as e:
        print("ML error:", e)


train_demand_model()


def predict_station_demand(lat, lon):

    if ml_model is None:
        return 0

    try:
        pred = ml_model.predict([[lat, lon]])
        return int(pred[0])
    except:
        return 0


# ==============================
# KNN CLUSTERING
# ==============================

def init_clusterer():

    global clusterer

    if df is not None and not df.empty:

        try:

            clusterer = EVStationClusterer(df)
            clusterer.fit(n_clusters=15, n_neighbors=5)

            print("Clusterer ready")

        except Exception as e:
            print("Cluster error:", e)


init_clusterer()


# ==============================
# DISTANCE
# ==============================

def calculate_distance(lat1, lon1, lat2, lon2):

    R = 6371

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2 +
        math.cos(math.radians(lat1)) *
        math.cos(math.radians(lat2)) *
        math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# ==============================
# ROUTES
# ==============================

@app.route('/')
def landing():
    return render_template("home.html")


@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template("index.html", username=session['username'])


# ==============================
# AUTOCOMPLETE
# ==============================

@app.route('/autocomplete')
def autocomplete():

    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify([])

    try:

        params = {
            "q": query,
            "key": OPENCAGE_API_KEY,
            "limit": 6,
            "language": "en",
            "countrycode": "in",
            "no_annotations": 1
        }

        prox_lat = request.args.get("lat")
        prox_lon = request.args.get("lon")

        if prox_lat and prox_lon:
            params["proximity"] = f"{prox_lat},{prox_lon}"

        response = http_requests.get(
            "https://api.opencagedata.com/geocode/v1/json",
            params=params,
            timeout=5
        )

        if response.status_code != 200:
            return jsonify([])

        data = response.json()

        results = []

        for item in data.get("results", []):

            geo = item.get("geometry", {})
            formatted = item.get("formatted", "")

            results.append({
                "display_name": formatted,
                "full_address": formatted,
                "lat": geo.get("lat"),
                "lon": geo.get("lng")
            })

        return jsonify(results)

    except Exception as e:
        print("Autocomplete error:", e)
        return jsonify([])


# ==============================
# RUN APP
# ==============================

if __name__ == "__main__":
    app.run(debug=True)
