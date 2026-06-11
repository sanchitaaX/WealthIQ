import os
import sqlite3 # used for local fallback exceptions if needed
try:
    import libsql_client
except ImportError:
    libsql_client = None

from werkzeug.security import generate_password_hash

class LibsqlRow:
    def __init__(self, cols, vals):
        self._cols = cols
        self._vals = vals
        self._dict = {col: val for col, val in zip(cols, vals)}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        return self._dict[key]

    def keys(self):
        return self._cols

    def __iter__(self):
        return iter(self._cols)

class CursorWrapper:
    def __init__(self, result_set=None, client=None):
        self.result_set = result_set
        self.client = client
        self._index = 0
        if result_set:
            self._rows = [LibsqlRow(result_set.columns, row) for row in result_set.rows]
            self.lastrowid = getattr(result_set, 'last_insert_rowid', None)
        else:
            self._rows = []
            self.lastrowid = None

    def execute(self, sql, params=()):
        if self.client:
            rs = self.client.execute(sql, list(params))
            return CursorWrapper(rs, self.client)
        return self

    def fetchone(self):
        if self._index < len(self._rows):
            row = self._rows[self._index]
            self._index += 1
            return row
        return None

    def fetchall(self):
        return self._rows

class ConnectionWrapper:
    def __init__(self, client):
        self.client = client

    def execute(self, sql, params=()):
        rs = self.client.execute(sql, list(params))
        return CursorWrapper(rs, self.client)

    def cursor(self):
        return CursorWrapper(client=self.client)

    def commit(self):
        pass # libsql_client auto-commits HTTP requests

    def close(self):
        self.client.close()

def get_db():
    """Returns a connection to the Turso database or local SQLite using libsql-client."""
    db_url = os.environ.get("TURSO_DATABASE_URL")
    auth_token = os.environ.get("TURSO_AUTH_TOKEN")
    
    if db_url and auth_token:
        # Remote Turso DB (Force HTTP connection to avoid WebSocket handshake errors on Vercel/some networks)
        if db_url.startswith("libsql://"):
            db_url = db_url.replace("libsql://", "https://", 1)
        client = libsql_client.create_client_sync(db_url, auth_token=auth_token)
    else:
        # Fallback to local file using libsql_client if installed
        db_dir = os.path.join(os.path.expanduser("~"), ".spendly")
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "spendly.db")
        # Ensure path uses forward slashes or correct URI format for file scheme
        uri_path = db_path.replace('\\', '/')
        client = libsql_client.create_client_sync(f"file:{uri_path}")
    
    return ConnectionWrapper(client)

def init_db():
    """Creates all tables using CREATE TABLE IF NOT EXISTS."""
    conn = get_db()
    
    # Execute each statement separately
    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            budget REAL DEFAULT 20000.0,
            monthly_income REAL DEFAULT 50000.0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            total_points INTEGER DEFAULT 0,
            current_level TEXT DEFAULT 'Beginner Saver',
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,
            last_activity_date TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            icon TEXT,
            points_reward INTEGER DEFAULT 0,
            requirement_type TEXT,
            requirement_value INTEGER DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            achievement_id INTEGER NOT NULL,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(achievement_id) REFERENCES achievements(id),
            UNIQUE(user_id, achievement_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            challenge_type TEXT,
            target_value REAL,
            target_category TEXT,
            duration_days INTEGER DEFAULT 7,
            points_reward INTEGER DEFAULT 100
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            challenge_id INTEGER NOT NULL,
            status TEXT DEFAULT 'active',
            started_at TEXT NOT NULL,
            ends_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(challenge_id) REFERENCES challenges(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    ]
    
    for stmt in statements:
        conn.execute(stmt)
        
    conn.close()

def migrate_db():
    pass # Monthly income column is now part of init_db directly to avoid ALTER TABLE errors

def seed_gamification():
    """Seeds predefined achievements and challenges."""
    conn = get_db()

    # Seed Achievements
    achievements = [
        ('First Expense', 'Log your very first expense', '🎯', 50, 'first_expense', 1),
        ('7-Day Streak', 'Log expenses for 7 consecutive days', '🔥', 100, 'streak', 7),
        ('Budget Champion', 'Stay within budget for a full month', '🏆', 200, 'budget_champion', 1),
        ('Savings Hero', 'Save more than 30% of income in a month', '💰', 150, 'savings_hero', 30),
        ('Challenge Winner', 'Complete your first challenge', '⭐', 100, 'challenge_winner', 1)
    ]

    for ach in achievements:
        try:
            conn.execute(
                "INSERT INTO achievements (name, description, icon, points_reward, requirement_type, requirement_value) VALUES (?, ?, ?, ?, ?, ?)",
                ach
            )
        except Exception:
            pass # Already exists

    # Seed Challenges
    challenges = [
        ('No Food Delivery Week', 'Avoid food delivery expenses for 7 days', '🍕', 'no_category', 0, 'Food', 7, 150),
        ('Save ₹100 Daily', 'Keep daily spending under your daily budget allowance', '💵', 'daily_save', 100, None, 7, 100),
        ('Spend Less Than ₹5000', 'Keep total spending under ₹5,000 this month', '📉', 'monthly_limit', 5000, None, 30, 200),
        ('No Impulse Week', 'No Entertainment spending for 7 days', '🧘', 'no_category', 0, 'Entertainment', 7, 120),
        ('Save 20% of Income', 'Save at least 20% of your monthly income', '🎯', 'save_percent', 20, None, 30, 250)
    ]

    for ch in challenges:
        # Check if exists by name
        res = conn.execute("SELECT id FROM challenges WHERE name = ?", (ch[0],)).fetchone()
        if not res:
            conn.execute(
                "INSERT INTO challenges (name, description, icon, challenge_type, target_value, target_category, duration_days, points_reward) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ch
            )

    conn.close()

def seed_db():
    """Inserts sample data for development if the database is empty."""
    init_db()  # Ensure tables are created first
    conn = get_db()
    
    # Check if users table is empty
    count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
    
    if count and count['c'] == 0:
        # Create hashed passwords
        hashed_password = generate_password_hash("password123")
        
        # Insert users
        res1 = conn.execute(
            "INSERT INTO users (name, email, password, budget) VALUES (?, ?, ?, ?) RETURNING id",
            ("Nitish Kumar", "nitish@example.com", hashed_password, 25000.0)
        )
        nitish_id = res1.fetchone()['id']
        
        res2 = conn.execute(
            "INSERT INTO users (name, email, password, budget) VALUES (?, ?, ?, ?) RETURNING id",
            ("Demo User", "demo@example.com", hashed_password, 15000.0)
        )
        demo_id = res2.fetchone()['id']
        
        # Insert sample expenses for Nitish
        expenses_nitish = [
            (5000.0, "Bills", "2026-06-01", "Monthly rent share"),
            (1200.0, "Food", "2026-06-02", "Grocery shopping at store"),
            (350.0, "Transport", "2026-06-03", "Auto ride to office"),
            (1500.0, "Health", "2026-06-04", "Pharmacy medicines"),
            (800.0, "Entertainment", "2026-06-05", "Movie ticket with friends"),
            (450.0, "Others", "2026-06-06", "Stationery and notebooks"),
            (1800.0, "Food", "2026-06-08", "Dinner at restaurant"),
            (2500.0, "Bills", "2026-06-09", "Electricity and Internet bill")
        ]
        
        for amount, category, date, desc in expenses_nitish:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (nitish_id, amount, category, date, desc)
            )
            
        # Insert sample expenses for Demo User
        expenses_demo = [
            (2500.0, "Bills", "2026-06-01", "Mobile recharge and WiFi"),
            (900.0, "Food", "2026-06-03", "Weekly groceries"),
            (450.0, "Transport", "2026-06-04", "Cab booking"),
            (2000.0, "Entertainment", "2026-06-05", "Concert pass"),
            (600.0, "Food", "2026-06-07", "Lunch delivery")
        ]
        
        for amount, category, date, desc in expenses_demo:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (demo_id, amount, category, date, desc)
            )
            
        print("Database successfully seeded with sample data.")
    else:
        print("Database already contains data. Seeding skipped.")
        
    conn.close()
    
    # Run gamification seeds
    seed_gamification()
