#file base db
import sqlite3

def init_db():
    conn = sqlite3.connect("users.db")   # Creates or connects to the database file
   #conn object the bridge btw py and db
    #cursor → tool to run queries
    c = conn.cursor()

    #It avoids error when the table already exists
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()
