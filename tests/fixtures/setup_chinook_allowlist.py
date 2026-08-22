import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "chinook_test.db")
SQL_PATH = os.path.join(os.path.dirname(__file__), "../../chinook.sql")

def setup_chinook():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    with open(SQL_PATH, "r", encoding="utf8") as f:
        sql = f.read()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript(sql)
    conn.commit()
    conn.close()
    
    print(f"Created {DB_PATH} successfully.")

if __name__ == "__main__":
    setup_chinook()
