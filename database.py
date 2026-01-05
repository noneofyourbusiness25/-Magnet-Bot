import sqlite3
import threading

class Database:
    def __init__(self, db_name="evergreen.db"):
        self.db_name = db_name
        self.lock = threading.Lock()
        self.init_db()

    def init_db(self):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            # Forwarding Rules
            c.execute('''
                CREATE TABLE IF NOT EXISTS forwarding_rules (
                    source_id INTEGER,
                    dest_id INTEGER,
                    PRIMARY KEY (source_id, dest_id)
                )
            ''')
            # User Session
            c.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    session_string TEXT
                )
            ''')
            conn.commit()
            conn.close()

    # --- Rules ---
    def add_rule(self, source_id, dest_id):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            try:
                c.execute("INSERT INTO forwarding_rules (source_id, dest_id) VALUES (?, ?)", (source_id, dest_id))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
            finally:
                conn.close()

    def remove_rule(self, source_id, dest_id):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("DELETE FROM forwarding_rules WHERE source_id = ? AND dest_id = ?", (source_id, dest_id))
            deleted = c.rowcount > 0
            conn.commit()
            conn.close()
            return deleted

    def get_rules(self):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("SELECT source_id, dest_id FROM forwarding_rules")
            rows = c.fetchall()
            conn.close()
            return rows

    def get_destinations(self, source_id):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("SELECT dest_id FROM forwarding_rules WHERE source_id = ?", (source_id,))
            rows = c.fetchall()
            conn.close()
            return [row[0] for row in rows]

    # --- Session ---
    def save_session(self, session_string):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO sessions (id, session_string) VALUES (1, ?)", (session_string,))
            conn.commit()
            conn.close()

    def get_session(self):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("SELECT session_string FROM sessions WHERE id = 1")
            row = c.fetchone()
            conn.close()
            return row[0] if row else None

    def delete_session(self):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("DELETE FROM sessions WHERE id = 1")
            conn.commit()
            conn.close()

db = Database()
