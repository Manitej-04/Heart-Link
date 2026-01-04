import sqlite3
from datetime import datetime

DB = "heart_app.db"

def get_db():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        probability REAL,
        risk TEXT,
        created_at TEXT
    )""")

    db.commit()

def add_user(email, pwd_hash, role="patient"):
    db = get_db()
    db.execute("INSERT INTO users VALUES(NULL,?,?,?)", (email, pwd_hash, role))
    db.commit()

def get_user(email):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE email=?", (email,))
    return cur.fetchone()

def save_history(user_id, prob, risk):
    db = get_db()
    db.execute(
        "INSERT INTO history VALUES(NULL,?,?,?,?)",
        (user_id, prob, risk, datetime.utcnow().isoformat())
    )
    db.commit()

def fetch_history(user_id=None):
    db = get_db()
    cur = db.cursor()
    if user_id:
        cur.execute("SELECT * FROM history WHERE user_id=?", (user_id,))
    else:
        cur.execute("SELECT * FROM history")
    return cur.fetchall()
