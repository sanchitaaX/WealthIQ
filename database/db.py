import sqlite3
import os
from werkzeug.security import generate_password_hash

def get_db_path():
    """Returns the path to the SQLite database file.
    
    Uses ~/.spendly/spendly.db by default to avoid write-permission issues
    when the project lives under a Windows junction (e.g. C:\\Windows\\Documents).
    Can be overridden via the SPENDLY_DB_PATH environment variable.
    """
    if "SPENDLY_DB_PATH" in os.environ:
        return os.environ["SPENDLY_DB_PATH"]
    db_dir = os.path.join(os.path.expanduser("~"), ".spendly")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "spendly.db")

def get_db():
    """Returns a SQLite connection with row_factory and foreign keys enabled."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates all tables using CREATE TABLE IF NOT EXISTS."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        budget REAL DEFAULT 20000.0
    )
    """)
    
    # Create expenses table
    cursor.execute("""
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
    """)

    # Create gamification and challenge tables
    cursor.execute("""
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
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        icon TEXT,
        points_reward INTEGER DEFAULT 0,
        requirement_type TEXT,
        requirement_value INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        achievement_id INTEGER NOT NULL,
        earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(achievement_id) REFERENCES achievements(id),
        UNIQUE(user_id, achievement_id)
    )
    """)

    cursor.execute("""
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
    """)

    cursor.execute("""
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
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    conn.close()

def migrate_db():
    """Applies database migrations like adding new columns."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN monthly_income REAL DEFAULT 50000.0")
        conn.commit()
    except Exception:
        pass  # Column already exists or error
    finally:
        conn.close()

def seed_gamification():
    """Seeds predefined achievements and challenges."""
    conn = get_db()
    cursor = conn.cursor()

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
            cursor.execute(
                "INSERT INTO achievements (name, description, icon, points_reward, requirement_type, requirement_value) VALUES (?, ?, ?, ?, ?, ?)",
                ach
            )
        except sqlite3.IntegrityError:
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
        cursor.execute("SELECT id FROM challenges WHERE name = ?", (ch[0],))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO challenges (name, description, icon, challenge_type, target_value, target_category, duration_days, points_reward) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ch
            )

    conn.commit()
    conn.close()

def seed_db():
    """Inserts sample data for development if the database is empty."""
    init_db()  # Ensure tables are created first
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if users table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    
    if count == 0:
        # Create hashed passwords
        hashed_password = generate_password_hash("password123")
        
        # Insert users
        cursor.execute(
            "INSERT INTO users (name, email, password, budget) VALUES (?, ?, ?, ?)",
            ("Nitish Kumar", "nitish@example.com", hashed_password, 25000.0)
        )
        nitish_id = cursor.lastrowid
        
        cursor.execute(
            "INSERT INTO users (name, email, password, budget) VALUES (?, ?, ?, ?)",
            ("Demo User", "demo@example.com", hashed_password, 15000.0)
        )
        demo_id = cursor.lastrowid
        
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
            cursor.execute(
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
            cursor.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (demo_id, amount, category, date, desc)
            )
            
        conn.commit()
        print("Database successfully seeded with sample data.")
    else:
        print("Database already contains data. Seeding skipped.")
        
    conn.close()
    
    # Run migrations and gamification seeds
    migrate_db()
    seed_gamification()
