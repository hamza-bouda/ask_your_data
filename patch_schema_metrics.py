import sqlite3
import os

DB_FILES = [
    "backend/services/catalog/test.db",
    "backend/services/orchestrator/test.db",
    "test.db",
    "test_identity.db",
    "tenant_acme.db",
    "tenant_stark.db"
]

def patch_db(db_path):
    if not os.path.exists(db_path):
        print(f"Skipping {db_path}, not found.")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='semantic_metrics';")
        if cursor.fetchone():
            print(f"Patching semantic_metrics in {db_path}...")
            # Ignore errors if columns already exist
            try:
                cursor.execute("ALTER TABLE semantic_metrics ADD COLUMN format VARCHAR(50) DEFAULT 'number';")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE semantic_metrics ADD COLUMN time_grains JSON DEFAULT '[]';")
            except sqlite3.OperationalError:
                pass
                
            try:
                cursor.execute("ALTER TABLE semantic_metrics ADD COLUMN dimensions JSON DEFAULT '[]';")
            except sqlite3.OperationalError:
                pass
                
            conn.commit()
            print(f"Successfully patched {db_path}.")
        else:
            print(f"semantic_metrics table not found in {db_path}.")
    except Exception as e:
        print(f"Error patching {db_path}: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    for db_path in DB_FILES:
        patch_db(db_path)
