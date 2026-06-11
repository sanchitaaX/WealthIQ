import os
import sqlite3
import functools
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import json, math
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "wealthiq_secure_dev_secret_key_987654321")

# Ensure database is initialized and seeded
init_db()
seed_db()

@app.errorhandler(sqlite3.Error)
def handle_db_error(e):
    """Exposes the exact SQLite error details to the browser to assist debugging."""
    return f"SQLite Operational/Database Error: {e} (Type: {type(e).__name__})", 500

# ------------------------------------------------------------------ #
# Decorators & Middleware                                             #
# ------------------------------------------------------------------ #

@app.before_request
def load_logged_in_user():
    """Retrieves current user details from DB based on session user_id."""
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        conn = get_db()
        g.user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()

def login_required(view):
    """Enforces authentication for protected routes."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please sign in to access that page.", "error")
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view

# ------------------------------------------------------------------ #
# Gamification Helpers                                                 #
# ------------------------------------------------------------------ #

LEVEL_THRESHOLDS = [
    (0, 'Beginner Saver'),
    (200, 'Smart Spender'),
    (500, 'Budget Master'),
    (1000, 'Financial Guru'),
    (2000, 'Wealth Builder'),
]

def get_level_for_points(points):
    """Returns the level name for a given point total."""
    level = LEVEL_THRESHOLDS[0][1]
    for threshold, name in LEVEL_THRESHOLDS:
        if points >= threshold:
            level = name
    return level

def get_level_progress(points):
    """Returns (current_level, current_threshold, next_threshold, progress_percent)."""
    current_threshold = 0
    next_threshold = LEVEL_THRESHOLDS[1][0] if len(LEVEL_THRESHOLDS) > 1 else 0
    current_level = LEVEL_THRESHOLDS[0][1]
    for i, (threshold, name) in enumerate(LEVEL_THRESHOLDS):
        if points >= threshold:
            current_level = name
            current_threshold = threshold
            if i + 1 < len(LEVEL_THRESHOLDS):
                next_threshold = LEVEL_THRESHOLDS[i + 1][0]
            else:
                next_threshold = threshold  # Max level
    if next_threshold == current_threshold:
        progress = 100
    else:
        progress = ((points - current_threshold) / (next_threshold - current_threshold)) * 100
    return current_level, current_threshold, next_threshold, min(progress, 100)

def award_points(user_id, points):
    """Awards XP points to a user, updating level if needed."""
    conn = get_db()
    row = conn.execute("SELECT * FROM user_points WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO user_points (user_id, total_points, current_level) VALUES (?, ?, ?)",
            (user_id, points, get_level_for_points(points))
        )
    else:
        new_total = row['total_points'] + points
        new_level = get_level_for_points(new_total)
        conn.execute(
            "UPDATE user_points SET total_points = ?, current_level = ? WHERE user_id = ?",
            (new_total, new_level, user_id)
        )
    conn.commit()
    conn.close()

def update_streak(user_id):
    """Updates the user's consecutive-day streak."""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    row = conn.execute("SELECT * FROM user_points WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO user_points (user_id, current_streak, longest_streak, last_activity_date) VALUES (?, 1, 1, ?)",
            (user_id, today)
        )
    else:
        last_date = row['last_activity_date']
        current_streak = row['current_streak'] or 0
        longest_streak = row['longest_streak'] or 0
        if last_date == today:
            conn.close()
            return  # Already logged today
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        if last_date == yesterday:
            current_streak += 1
        else:
            current_streak = 1
        longest_streak = max(longest_streak, current_streak)
        conn.execute(
            "UPDATE user_points SET current_streak = ?, longest_streak = ?, last_activity_date = ? WHERE user_id = ?",
            (current_streak, longest_streak, today, user_id)
        )
    conn.commit()
    conn.close()

def check_achievements(user_id):
    """Checks and awards any newly earned achievements."""
    conn = get_db()
    achievements = conn.execute("SELECT * FROM achievements").fetchall()
    earned = [r['achievement_id'] for r in conn.execute(
        "SELECT achievement_id FROM user_achievements WHERE user_id = ?", (user_id,)
    ).fetchall()]
    
    user_points_row = conn.execute("SELECT * FROM user_points WHERE user_id = ?", (user_id,)).fetchone()
    expense_count = conn.execute("SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)).fetchone()[0]
    
    current_month = datetime.now().strftime('%Y-%m')
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    month_spent = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date LIKE ?",
        (user_id, f"{current_month}%")
    ).fetchone()[0] or 0
    
    newly_earned = []
    for ach in achievements:
        if ach['id'] in earned:
            continue
        req_type = ach['requirement_type']
        if req_type == 'first_expense' and expense_count >= 1:
            newly_earned.append(ach)
        elif req_type == 'streak' and user_points_row and user_points_row['current_streak'] >= ach['requirement_value']:
            newly_earned.append(ach)
        elif req_type == 'budget_champion':
            budget = user['budget'] or 20000
            if month_spent > 0 and month_spent <= budget:
                if datetime.now().day >= 28:
                    newly_earned.append(ach)
        elif req_type == 'savings_hero':
            try:
                income = user['monthly_income'] or 50000
            except IndexError:
                income = 50000
            savings_pct = ((income - month_spent) / income * 100) if income > 0 else 0
            if savings_pct >= ach['requirement_value'] and datetime.now().day >= 28:
                newly_earned.append(ach)
        elif req_type == 'challenge_winner':
            completed = conn.execute(
                "SELECT COUNT(*) FROM user_challenges WHERE user_id = ? AND status = 'completed'",
                (user_id,)
            ).fetchone()[0]
            if completed >= 1:
                newly_earned.append(ach)
    
    for ach in newly_earned:
        try:
            conn.execute(
                "INSERT INTO user_achievements (user_id, achievement_id) VALUES (?, ?)",
                (user_id, ach['id'])
            )
            conn.commit()
            award_points(user_id, ach['points_reward'])
        except Exception:
            pass
    
    conn.close()
    return newly_earned

def calculate_financial_health(user_id):
    """Calculates a financial health score from 0-100."""
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    current_month = datetime.now().strftime('%Y-%m')
    
    month_spent = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date LIKE ?",
        (user_id, f"{current_month}%")
    ).fetchone()[0] or 0
    
    try:
        income = user['monthly_income'] or 50000
    except IndexError:
        income = 50000
        
    budget = user['budget'] or 20000
    
    # 1. Budget discipline (25 pts)
    if month_spent <= budget:
        budget_score = 25
    else:
        over_ratio = (month_spent / budget) - 1
        budget_score = max(0, 25 - over_ratio * 50)
    
    # 2. Savings percentage (25 pts)
    savings = income - month_spent
    savings_pct = (savings / income * 100) if income > 0 else 0
    savings_score = min(25, max(0, savings_pct * 0.83))  # 30% savings = full 25
    
    # 3. Spending consistency (25 pts) - lower std dev = better
    daily_amounts = conn.execute(
        "SELECT date, SUM(amount) as daily_total FROM expenses WHERE user_id = ? AND date LIKE ? GROUP BY date",
        (user_id, f"{current_month}%")
    ).fetchall()
    if len(daily_amounts) > 1:
        amounts = [r['daily_total'] for r in daily_amounts]
        mean = sum(amounts) / len(amounts)
        variance = sum((x - mean) ** 2 for x in amounts) / len(amounts)
        std_dev = math.sqrt(variance)
        cv = (std_dev / mean) if mean > 0 else 0
        consistency_score = max(0, 25 - cv * 25)
    else:
        consistency_score = 12.5  # Neutral if not enough data
    
    # 4. Goal completion (25 pts) - based on budget adherence
    if budget > 0:
        adherence = min(1, (budget - month_spent) / budget) if month_spent <= budget else 0
        goal_score = adherence * 25
    else:
        goal_score = 12.5
    
    total = round(budget_score + savings_score + consistency_score + goal_score)
    conn.close()
    
    return {
        'total': min(100, max(0, total)),
        'budget_discipline': round(budget_score),
        'savings_percentage': round(savings_score),
        'spending_consistency': round(consistency_score),
        'goal_completion': round(goal_score),
        'savings_pct': round(savings_pct, 1),
        'month_spent': month_spent,
        'income': income,
        'budget': budget
    }

# ------------------------------------------------------------------ #
# Authentication Routes                                               #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    """Renders landing page or redirects logged-in user to dashboard."""
    if g.user:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Handles new user account creation."""
    if g.user:
        return redirect(url_for("dashboard"))
        
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.")
            
        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters long.")
            
        conn = get_db()
        try:
            # Check if user already exists
            existing_user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing_user:
                return render_template("register.html", error="Email address is already registered.")
                
            hashed_pass = generate_password_hash(password)
            cursor = conn.execute(
                "INSERT INTO users (name, email, password, budget) VALUES (?, ?, ?, ?)",
                (name, email, hashed_pass, 20000.0) # Default budget limit: ₹20,000
            )
            conn.commit()
            
            # Log the user in
            session.clear()
            session["user_id"] = cursor.lastrowid
            session["user_name"] = name
            
            flash("Account created successfully! Welcome to WealthIQ.", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            return render_template("register.html", error="An error occurred. Please try again.")
        finally:
            conn.close()
            
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Handles user login authentication."""
    if g.user:
        return redirect(url_for("dashboard"))
        
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        if not email or not password:
            return render_template("login.html", error="Please fill in all fields.")
            
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        
        if user is None or not check_password_hash(user["password"], password):
            return render_template("login.html", error="Invalid email address or password.")
            
        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        
        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("dashboard"))
        
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Logs the user out and clears the session."""
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("landing"))

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Handles forgot password requests by sending a reset email."""
    if g.user:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            return render_template("forgot_password.html", error="Please enter your email address.")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user:
            # Generate a unique reset token
            token = str(uuid.uuid4())
            expires_at = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

            # Invalidate any previous tokens for this user
            conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE user_id = ?", (user['id'],))
            conn.execute(
                "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
                (user['id'], token, expires_at)
            )
            conn.commit()

            # Build reset link
            reset_link = url_for('reset_password', token=token, _external=True)

            # Send email
            try:
                _send_reset_email(user['email'], user['name'], reset_link)
            except Exception as e:
                # If email sending fails, still show the link in flash for dev/testing
                flash(f"Email service unavailable. Use this link to reset: {reset_link}", "warning")
                conn.close()
                return render_template("forgot_password.html",
                    success="A password reset link has been generated. Check the notification above.")

        conn.close()
        # Always show success to prevent email enumeration
        return render_template("forgot_password.html",
            success="If an account with that email exists, we've sent a password reset link. Please check your inbox.")

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Handles the actual password reset via a valid token."""
    if g.user:
        return redirect(url_for("dashboard"))

    conn = get_db()
    token_row = conn.execute(
        "SELECT * FROM password_reset_tokens WHERE token = ? AND used = 0", (token,)
    ).fetchone()

    if token_row is None:
        conn.close()
        flash("This reset link is invalid or has already been used.", "error")
        return redirect(url_for("login"))

    # Check expiry
    expires_at = datetime.strptime(token_row['expires_at'], '%Y-%m-%d %H:%M:%S')
    if datetime.now() > expires_at:
        conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = ?", (token_row['id'],))
        conn.commit()
        conn.close()
        flash("This reset link has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(password) < 8:
            conn.close()
            return render_template("reset_password.html", token=token, error="Password must be at least 8 characters long.")

        if password != confirm_password:
            conn.close()
            return render_template("reset_password.html", token=token, error="Passwords do not match.")

        hashed = generate_password_hash(password)
        conn.execute("UPDATE users SET password = ? WHERE id = ?", (hashed, token_row['user_id']))
        conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = ?", (token_row['id'],))
        conn.commit()
        conn.close()

        flash("Your password has been reset successfully! Please sign in.", "success")
        return redirect(url_for("login"))

    conn.close()
    return render_template("reset_password.html", token=token)


import resend

def _send_reset_email(to_email, user_name, reset_link):
    """Sends a password reset email using Resend."""
    resend.api_key = os.environ.get("RESEND_API_KEY")
    
    if not resend.api_key:
        raise RuntimeError("Resend API key not configured. Set RESEND_API_KEY in .env")

    html_body = f"""\
    <html>
    <body style="font-family: 'Inter', sans-serif; background: #F6F5F2; padding: 40px;">
      <div style="max-width: 500px; margin: 0 auto; background: #FFFFFF; border-radius: 16px; padding: 40px; box-shadow: 0 4px 12px rgba(0,0,0,0.06);">
        <h2 style="color: #2C5CFF; margin-bottom: 8px;">WealthIQ</h2>
        <p style="color: #525252;">Hi {user_name},</p>
        <p style="color: #525252;">You requested a password reset. Click the button below to set a new password:</p>
        <a href="{reset_link}" style="display: inline-block; background: #2C5CFF; color: #fff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 20px 0;">Reset Password</a>
        <p style="color: #8C8C8C; font-size: 0.85rem;">This link expires in 1 hour. If you didn't request this, ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #E8E8E4; margin: 24px 0;">
        <p style="color: #8C8C8C; font-size: 0.8rem;">— WealthIQ Team</p>
      </div>
    </body>
    </html>
    """

    try:
        r = resend.Emails.send({
            "from": "WealthIQ <onboarding@resend.dev>",
            "to": to_email,
            "subject": "WealthIQ — Reset Your Password",
            "html": html_body
        })
    except Exception as e:
        raise RuntimeError(f"Failed to send email via Resend: {str(e)}")

# ------------------------------------------------------------------ #
# Dashboard & Filtering                                               #
# ------------------------------------------------------------------ #

@app.route("/dashboard")
@login_required
def dashboard():
    """Renders the main dashboard showing expenses, filters, and budgets."""
    # Filter parameters
    selected_category = request.args.get("category", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    search_query = request.args.get("search", "").strip()
    sort_by = request.args.get("sort_by", "date_desc")
    
    conn = get_db()
    
    # 1. Build and execute expenses query
    query = "SELECT * FROM expenses WHERE user_id = ?"
    params = [g.user["id"]]
    
    if selected_category:
        query += " AND category = ?"
        params.append(selected_category)
        
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
        
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
        
    if search_query:
        query += " AND description LIKE ?"
        params.append(f"%{search_query}%")
        
    # Sort order mapping
    sort_options = {
        "date_desc": " ORDER BY date DESC, id DESC",
        "date_asc": " ORDER BY date ASC, id ASC",
        "amount_desc": " ORDER BY amount DESC",
        "amount_asc": " ORDER BY amount ASC"
    }
    query += sort_options.get(sort_by, sort_options["date_desc"])
    
    expenses = conn.execute(query, params).fetchall()
    
    # 2. Calculate Dashboard Metrics (Unfiltered totals to show true state)
    total_expenses = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ?", 
        (g.user["id"],)
    ).fetchone()[0] or 0.0
    
    total_transactions = conn.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", 
        (g.user["id"],)
    ).fetchone()[0] or 0
    
    # 3. Monthly Budget Progress (Current Calendar Month)
    current_year_month = datetime.now().strftime("%Y-%m")
    current_month_spent = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date LIKE ?",
        (g.user["id"], f"{current_year_month}%")
    ).fetchone()[0] or 0.0
    
    user_budget = g.user["budget"] or 20000.0
    budget_percent = min((current_month_spent / user_budget) * 100, 100.0) if user_budget > 0 else 0
    
    if current_month_spent > user_budget:
        budget_status = "danger"
    elif current_month_spent > (user_budget * 0.8):
        budget_status = "warning"
    else:
        budget_status = "normal"
        
    # 4. Category Breakdown Details
    category_data = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC",
        (g.user["id"],)
    ).fetchall()
    
    # Calculate percentage for each category relative to total expenses
    category_summary = []
    for row in category_data:
        percent = (row["total"] / total_expenses * 100) if total_expenses > 0 else 0
        category_summary.append({
            "category": row["category"],
            "total": row["total"],
            "percent": round(percent, 1)
        })
        
    # Top Category
    top_category = category_summary[0]["category"] if category_summary else "N/A"
    
    # Predefined category list for the dropdown filter and add form
    categories_list = ["Food", "Bills", "Transport", "Health", "Entertainment", "Others"]
    
    conn.close()
    
    return render_template(
        "dashboard.html",
        expenses=expenses,
        selected_category=selected_category,
        start_date=start_date,
        end_date=end_date,
        search_query=search_query,
        sort_by=sort_by,
        total_expenses=total_expenses,
        total_transactions=total_transactions,
        current_month_spent=current_month_spent,
        budget_percent=round(budget_percent, 1),
        budget_status=budget_status,
        category_summary=category_summary,
        top_category=top_category,
        categories_list=categories_list
    )

# ------------------------------------------------------------------ #
# Expense CRUD Operations                                             #
# ------------------------------------------------------------------ #

@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    """Adds a new expense for the logged-in user."""
    categories_list = ["Food", "Bills", "Transport", "Health", "Entertainment", "Others"]
    
    if request.method == "POST":
        amount_raw = request.form.get("amount", "")
        category = request.form.get("category", "")
        date = request.form.get("date", "")
        description = request.form.get("description", "").strip()
        
        # Validation
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError("Amount must be positive.")
        except ValueError:
            return render_template("add_expense.html", categories_list=categories_list, error="Please enter a valid positive amount.")
            
        if not category or category not in categories_list:
            return render_template("add_expense.html", categories_list=categories_list, error="Please select a valid category.")
            
        if not date:
            return render_template("add_expense.html", categories_list=categories_list, error="Please select a valid date.")
            
        conn = get_db()
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            (g.user["id"], amount, category, date, description)
        )
        conn.commit()
        
        # Gamification: award points and update streak
        award_points(g.user['id'], 10)
        update_streak(g.user['id'])
        newly_earned = check_achievements(g.user['id'])
        for ach in newly_earned:
            flash(f"🏆 Achievement Unlocked: {ach['name']}!", "success")
        
        # Check if they went over budget this month
        current_year_month = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m")
        current_month_spent = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date LIKE ?",
            (g.user["id"], f"{current_year_month}%")
        ).fetchone()[0] or 0.0
        
        conn.close()
        
        if current_month_spent > g.user["budget"]:
            flash(f"Expense added! Warning: You have exceeded your monthly budget of ₹{g.user['budget']:,.2f} (Spent: ₹{current_month_spent:,.2f})", "error")
        elif current_month_spent > (g.user["budget"] * 0.8):
            flash(f"Expense added! Note: You have used over 80% of your monthly budget (Spent: ₹{current_month_spent:,.2f})", "warning")
        else:
            flash("Expense added successfully!", "success")
            
        return redirect(url_for("dashboard"))
        
    # Default today's date for user convenience
    today_str = datetime.now().strftime("%Y-%m-%d")
    return render_template("add_expense.html", categories_list=categories_list, today_str=today_str)

@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(id):
    """Edits an existing expense, ensuring user ownership."""
    categories_list = ["Food", "Bills", "Transport", "Health", "Entertainment", "Others"]
    
    conn = get_db()
    expense = conn.execute("SELECT * FROM expenses WHERE id = ? AND user_id = ?", (id, g.user["id"])).fetchone()
    
    if expense is None:
        conn.close()
        flash("Expense not found or unauthorized.", "error")
        return redirect(url_for("dashboard"))
        
    if request.method == "POST":
        amount_raw = request.form.get("amount", "")
        category = request.form.get("category", "")
        date = request.form.get("date", "")
        description = request.form.get("description", "").strip()
        
        # Validation
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            conn.close()
            return render_template("edit_expense.html", expense=expense, categories_list=categories_list, error="Please enter a valid positive amount.")
            
        if not category or category not in categories_list:
            conn.close()
            return render_template("edit_expense.html", expense=expense, categories_list=categories_list, error="Please select a valid category.")
            
        if not date:
            conn.close()
            return render_template("edit_expense.html", expense=expense, categories_list=categories_list, error="Please select a date.")
            
        conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? WHERE id = ? AND user_id = ?",
            (amount, category, date, description, id, g.user["id"])
        )
        conn.commit()
        
        # Budget warning check
        current_year_month = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m")
        current_month_spent = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date LIKE ?",
            (g.user["id"], f"{current_year_month}%")
        ).fetchone()[0] or 0.0
        conn.close()
        
        if current_month_spent > g.user["budget"]:
            flash(f"Expense updated! Warning: You have exceeded your monthly budget of ₹{g.user['budget']:,.2f} (Spent: ₹{current_month_spent:,.2f})", "error")
        else:
            flash("Expense updated successfully!", "success")
            
        return redirect(url_for("dashboard"))
        
    conn.close()
    return render_template("edit_expense.html", expense=expense, categories_list=categories_list)

@app.route("/expenses/<int:id>/delete")
@login_required
def delete_expense(id):
    """Deletes an expense, checking user ownership."""
    conn = get_db()
    expense = conn.execute("SELECT id FROM expenses WHERE id = ? AND user_id = ?", (id, g.user["id"])).fetchone()
    
    if expense is None:
        conn.close()
        flash("Expense not found or unauthorized.", "error")
        return redirect(url_for("dashboard"))
        
    conn.execute("DELETE FROM expenses WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    flash("Expense deleted successfully.", "success")
    return redirect(url_for("dashboard"))

# ------------------------------------------------------------------ #
# User Profile                                                        #
# ------------------------------------------------------------------ #

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Renders user profile details and allows monthly budget updates."""
    conn = get_db()
    
    if request.method == "POST":
        budget_raw = request.form.get("budget", "")
        income_raw = request.form.get("monthly_income", "")
        
        try:
            budget = float(budget_raw)
            if budget < 0:
                raise ValueError()
        except ValueError:
            # Re-fetch stats for rendering the error view
            total_spent = conn.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ?", (g.user["id"],)).fetchone()[0] or 0.0
            total_transactions = conn.execute("SELECT COUNT(*) FROM expenses WHERE user_id = ?", (g.user["id"],)).fetchone()[0] or 0
            conn.close()
            return render_template(
                "profile.html", 
                total_spent=total_spent, 
                total_transactions=total_transactions, 
                error="Please enter a valid positive budget amount."
            )
            
        try:
            try:
                monthly_income = float(income_raw) if income_raw else (g.user['monthly_income'] or 50000)
            except IndexError:
                monthly_income = float(income_raw) if income_raw else 50000
            if monthly_income < 0:
                raise ValueError()
        except (ValueError, TypeError):
            try:
                monthly_income = g.user['monthly_income'] or 50000
            except IndexError:
                monthly_income = 50000
        
        conn.execute("UPDATE users SET budget = ?, monthly_income = ? WHERE id = ?", (budget, monthly_income, g.user["id"]))
        conn.commit()
        
        flash(f"Preferences updated successfully!", "success")
        conn.close()
        return redirect(url_for("profile"))
        
    # GET: Fetch statistics for user profile
    total_spent = conn.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ?", (g.user["id"],)).fetchone()[0] or 0.0
    total_transactions = conn.execute("SELECT COUNT(*) FROM expenses WHERE user_id = ?", (g.user["id"],)).fetchone()[0] or 0
    
    # Find most expensive category
    top_cat_row = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC LIMIT 1",
        (g.user["id"],)
    ).fetchone()
    top_cat = top_cat_row["category"] if top_cat_row else "None"
    
    # Gamification summary for profile
    user_points_row = conn.execute("SELECT * FROM user_points WHERE user_id = ?", (g.user["id"],)).fetchone()
    points_data = {
        'total_points': user_points_row['total_points'] if user_points_row else 0,
        'current_level': user_points_row['current_level'] if user_points_row else 'Beginner Saver',
        'current_streak': user_points_row['current_streak'] if user_points_row else 0
    }
    
    conn.close()
    
    return render_template(
        "profile.html",
        total_spent=total_spent,
        total_transactions=total_transactions,
        top_category=top_cat,
        points_data=points_data
    )

# ------------------------------------------------------------------ #
# Rewards & Achievements                                               #
# ------------------------------------------------------------------ #

@app.route("/rewards")
@login_required
def rewards():
    """Renders the Rewards & Achievements page."""
    conn = get_db()
    
    # User points and level
    user_points_row = conn.execute("SELECT * FROM user_points WHERE user_id = ?", (g.user["id"],)).fetchone()
    if user_points_row is None:
        conn.execute("INSERT INTO user_points (user_id) VALUES (?)", (g.user["id"],))
        conn.commit()
        user_points_row = conn.execute("SELECT * FROM user_points WHERE user_id = ?", (g.user["id"],)).fetchone()
    
    total_points = user_points_row['total_points'] or 0
    current_level, current_threshold, next_threshold, level_progress = get_level_progress(total_points)
    
    # All achievements with earned status
    all_achievements = conn.execute("SELECT * FROM achievements").fetchall()
    earned_ids = [r['achievement_id'] for r in conn.execute(
        "SELECT achievement_id FROM user_achievements WHERE user_id = ?", (g.user["id"],)
    ).fetchall()]
    
    earned_dates = {}
    for r in conn.execute(
        "SELECT achievement_id, earned_at FROM user_achievements WHERE user_id = ?", (g.user["id"],)
    ).fetchall():
        earned_dates[r['achievement_id']] = r['earned_at']
    
    achievements_display = []
    for ach in all_achievements:
        achievements_display.append({
            'id': ach['id'],
            'name': ach['name'],
            'description': ach['description'],
            'icon': ach['icon'],
            'points_reward': ach['points_reward'],
            'earned': ach['id'] in earned_ids,
            'earned_at': earned_dates.get(ach['id'], '')
        })
    
    conn.close()
    
    return render_template(
        "rewards.html",
        total_points=total_points,
        current_level=current_level,
        level_progress=round(level_progress, 1),
        current_threshold=current_threshold,
        next_threshold=next_threshold,
        achievements=achievements_display,
        current_streak=user_points_row['current_streak'] or 0,
        longest_streak=user_points_row['longest_streak'] or 0,
        levels=LEVEL_THRESHOLDS
    )

# ------------------------------------------------------------------ #
# Advanced Analytics Dashboard                                         #
# ------------------------------------------------------------------ #

@app.route("/analytics")
@login_required
def analytics():
    """Renders the Advanced Analytics Dashboard."""
    health = calculate_financial_health(g.user['id'])
    return render_template("analytics.html", health=health)

@app.route("/api/analytics/monthly-trend")
@login_required
def api_monthly_trend():
    """Returns monthly spending for the last 6 months as JSON."""
    conn = get_db()
    results = []
    for i in range(5, -1, -1):
        d = datetime.now() - timedelta(days=i*30)
        month_key = d.strftime('%Y-%m')
        total = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date LIKE ?",
            (g.user['id'], f"{month_key}%")
        ).fetchone()[0] or 0
        results.append({'month': d.strftime('%b %Y'), 'amount': total})
    conn.close()
    return json.dumps(results), 200, {'Content-Type': 'application/json'}

@app.route("/api/analytics/category-breakdown")
@login_required
def api_category_breakdown():
    """Returns category totals for pie chart as JSON."""
    conn = get_db()
    rows = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC",
        (g.user['id'],)
    ).fetchall()
    result = [{'category': r['category'], 'total': r['total']} for r in rows]
    conn.close()
    return json.dumps(result), 200, {'Content-Type': 'application/json'}

@app.route("/api/analytics/weekly-comparison")
@login_required
def api_weekly_comparison():
    """Returns this week vs last week spending as JSON."""
    conn = get_db()
    today = datetime.now()
    
    # This week (Monday to today)
    start_this_week = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
    this_week = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date >= ?",
        (g.user['id'], start_this_week)
    ).fetchone()[0] or 0
    
    # Last week
    start_last_week = (today - timedelta(days=today.weekday() + 7)).strftime('%Y-%m-%d')
    end_last_week = (today - timedelta(days=today.weekday() + 1)).strftime('%Y-%m-%d')
    last_week = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date >= ? AND date <= ?",
        (g.user['id'], start_last_week, end_last_week)
    ).fetchone()[0] or 0
    
    # Daily breakdown for both weeks
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    this_week_daily = []
    last_week_daily = []
    for i in range(7):
        tw_date = (today - timedelta(days=today.weekday()) + timedelta(days=i)).strftime('%Y-%m-%d')
        lw_date = (today - timedelta(days=today.weekday() + 7) + timedelta(days=i)).strftime('%Y-%m-%d')
        tw_amt = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date = ?",
            (g.user['id'], tw_date)
        ).fetchone()[0] or 0
        lw_amt = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date = ?",
            (g.user['id'], lw_date)
        ).fetchone()[0] or 0
        this_week_daily.append(tw_amt)
        last_week_daily.append(lw_amt)
    
    conn.close()
    return json.dumps({
        'labels': days,
        'this_week': this_week_daily,
        'last_week': last_week_daily,
        'this_week_total': this_week,
        'last_week_total': last_week
    }), 200, {'Content-Type': 'application/json'}

@app.route("/api/analytics/financial-health")
@login_required
def api_financial_health():
    """Returns financial health score and breakdown as JSON."""
    health = calculate_financial_health(g.user['id'])
    
    # Generate improvement suggestions
    suggestions = []
    if health['budget_discipline'] < 20:
        suggestions.append('Try to reduce spending to stay within your monthly budget.')
    if health['savings_percentage'] < 15:
        suggestions.append('Aim to save at least 20-30% of your monthly income.')
    if health['spending_consistency'] < 15:
        suggestions.append('Try to spread your expenses more evenly across the month.')
    if health['goal_completion'] < 15:
        suggestions.append('Set a realistic budget and track progress daily.')
    if not suggestions:
        suggestions.append('Great job! Keep maintaining your excellent financial habits.')
    
    health['suggestions'] = suggestions
    return json.dumps(health), 200, {'Content-Type': 'application/json'}

@app.route("/api/analytics/forecast")
@login_required
def api_forecast():
    """Predicts next month spending using simple moving average."""
    conn = get_db()
    monthly_totals = []
    for i in range(6, 0, -1):
        d = datetime.now() - timedelta(days=i*30)
        month_key = d.strftime('%Y-%m')
        total = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date LIKE ?",
            (g.user['id'], f"{month_key}%")
        ).fetchone()[0] or 0
        monthly_totals.append(total)
    
    user = conn.execute("SELECT * FROM users WHERE id = ?", (g.user['id'],)).fetchone()
    try:
        income = user['monthly_income'] or 50000
    except IndexError:
        income = 50000
    budget = user['budget'] or 20000
    conn.close()
    
    # Simple moving average (last 3 months with data)
    non_zero = [x for x in monthly_totals if x > 0]
    if non_zero:
        predicted_spending = sum(non_zero[-3:]) / len(non_zero[-3:])
    else:
        predicted_spending = 0
    
    predicted_savings = income - predicted_spending
    budget_overrun = predicted_spending > budget
    
    return json.dumps({
        'predicted_spending': round(predicted_spending, 2),
        'predicted_savings': round(predicted_savings, 2),
        'budget_overrun': budget_overrun,
        'budget': budget,
        'income': income,
        'historical': monthly_totals
    }), 200, {'Content-Type': 'application/json'}

# ------------------------------------------------------------------ #
# Challenge Mode                                                       #
# ------------------------------------------------------------------ #

@app.route("/challenges")
@login_required
def challenges():
    """Renders the Challenge Mode page."""
    conn = get_db()
    
    # All available challenges
    all_challenges = conn.execute("SELECT * FROM challenges").fetchall()
    
    # User's active and completed challenges
    user_challenges = conn.execute(
        """SELECT uc.*, c.name, c.description, c.icon, c.challenge_type, 
           c.target_value, c.target_category, c.duration_days, c.points_reward
           FROM user_challenges uc 
           JOIN challenges c ON uc.challenge_id = c.id 
           WHERE uc.user_id = ?
           ORDER BY uc.started_at DESC""",
        (g.user['id'],)
    ).fetchall()
    
    active = [dict(uc) for uc in user_challenges if uc['status'] == 'active']
    completed = [dict(uc) for uc in user_challenges if uc['status'] == 'completed']
    failed = [dict(uc) for uc in user_challenges if uc['status'] == 'failed']
    
    # Determine which challenges are joinable (not currently active)
    active_challenge_ids = [uc['challenge_id'] for uc in user_challenges if uc['status'] == 'active']
    available = [dict(c) for c in all_challenges if c['id'] not in active_challenge_ids]
    
    # Calculate progress for active challenges
    today = datetime.now().strftime('%Y-%m-%d')
    for ch in active:
        started = ch['started_at']
        ends = ch['ends_at']
        total_days = (datetime.strptime(ends, '%Y-%m-%d') - datetime.strptime(started, '%Y-%m-%d')).days
        days_elapsed = (datetime.now() - datetime.strptime(started, '%Y-%m-%d')).days
        ch['days_remaining'] = max(0, total_days - days_elapsed)
        ch['progress_pct'] = min(100, round((days_elapsed / total_days) * 100)) if total_days > 0 else 0
        
        # Check if challenge has expired
        if today > ends and ch['status'] == 'active':
            # Evaluate completion
            _evaluate_challenge(conn, g.user['id'], ch)
    
    conn.close()
    
    return render_template(
        "challenges.html",
        active_challenges=active,
        completed_challenges=completed,
        failed_challenges=failed,
        available_challenges=available
    )

def _evaluate_challenge(conn, user_id, challenge):
    """Evaluates if a challenge was completed or failed."""
    ch_type = challenge['challenge_type']
    started = challenge['started_at']
    ends = challenge['ends_at']
    target = challenge['target_value']
    category = challenge['target_category']
    
    success = False
    
    if ch_type == 'no_category' and category:
        # Check if user had any expenses in the target category during the period
        count = conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ? AND category = ? AND date >= ? AND date <= ?",
            (user_id, category, started, ends)
        ).fetchone()[0]
        success = (count == 0)
    elif ch_type == 'monthly_limit':
        total = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date >= ? AND date <= ?",
            (user_id, started, ends)
        ).fetchone()[0] or 0
        success = (total <= target)
    elif ch_type == 'daily_save':
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        budget = user['budget'] or 20000
        days = (datetime.strptime(ends, '%Y-%m-%d') - datetime.strptime(started, '%Y-%m-%d')).days or 1
        daily_budget = budget / 30
        total = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date >= ? AND date <= ?",
            (user_id, started, ends)
        ).fetchone()[0] or 0
        avg_daily = total / days if days > 0 else 0
        success = (avg_daily <= daily_budget)
    elif ch_type == 'save_percent':
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        try:
            income = user['monthly_income'] or 50000
        except IndexError:
            income = 50000
        total = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date >= ? AND date <= ?",
            (user_id, started, ends)
        ).fetchone()[0] or 0
        saved_pct = ((income - total) / income * 100) if income > 0 else 0
        success = (saved_pct >= target)
    
    status = 'completed' if success else 'failed'
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        "UPDATE user_challenges SET status = ?, completed_at = ? WHERE id = ?",
        (status, now, challenge['id'])
    )
    conn.commit()
    
    if success:
        award_points(user_id, challenge['points_reward'])
        check_achievements(user_id)

@app.route("/challenges/<int:challenge_id>/join", methods=["POST"])
@login_required
def join_challenge(challenge_id):
    """Joins a challenge."""
    conn = get_db()
    challenge = conn.execute("SELECT * FROM challenges WHERE id = ?", (challenge_id,)).fetchone()
    if challenge is None:
        conn.close()
        flash("Challenge not found.", "error")
        return redirect(url_for('challenges'))
    
    # Check if already active
    existing = conn.execute(
        "SELECT id FROM user_challenges WHERE user_id = ? AND challenge_id = ? AND status = 'active'",
        (g.user['id'], challenge_id)
    ).fetchone()
    if existing:
        conn.close()
        flash("You are already participating in this challenge.", "warning")
        return redirect(url_for('challenges'))
    
    today = datetime.now().strftime('%Y-%m-%d')
    ends = (datetime.now() + timedelta(days=challenge['duration_days'])).strftime('%Y-%m-%d')
    
    conn.execute(
        "INSERT INTO user_challenges (user_id, challenge_id, started_at, ends_at) VALUES (?, ?, ?, ?)",
        (g.user['id'], challenge_id, today, ends)
    )
    conn.commit()
    conn.close()
    
    # Award points for joining
    award_points(g.user['id'], 5)
    
    flash(f"You joined the '{challenge['name']}' challenge! Good luck! 🎯", "success")
    return redirect(url_for('challenges'))

# ------------------------------------------------------------------ #
# Smart Home Dashboard                                                 #
# ------------------------------------------------------------------ #

@app.route("/home")
@login_required
def home():
    """Renders the Smart Home Dashboard."""
    conn = get_db()
    
    user = conn.execute("SELECT * FROM users WHERE id = ?", (g.user['id'],)).fetchone()
    try:
        income = user['monthly_income'] or 50000
    except IndexError:
        income = 50000
    
    current_month = datetime.now().strftime('%Y-%m')
    month_spent = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date LIKE ?",
        (g.user['id'], f"{current_month}%")
    ).fetchone()[0] or 0
    
    savings = income - month_spent
    health = calculate_financial_health(g.user['id'])
    
    # Active challenges count
    active_challenges = conn.execute(
        """SELECT uc.*, c.name, c.icon, c.duration_days, c.points_reward
           FROM user_challenges uc JOIN challenges c ON uc.challenge_id = c.id
           WHERE uc.user_id = ? AND uc.status = 'active'""",
        (g.user['id'],)
    ).fetchall()
    
    # Recent achievements
    recent_achievements = conn.execute(
        """SELECT a.name, a.icon, ua.earned_at 
           FROM user_achievements ua JOIN achievements a ON ua.achievement_id = a.id
           WHERE ua.user_id = ? ORDER BY ua.earned_at DESC LIMIT 3""",
        (g.user['id'],)
    ).fetchall()
    
    # Streak data
    user_points_row = conn.execute("SELECT * FROM user_points WHERE user_id = ?", (g.user['id'],)).fetchone()
    current_streak = user_points_row['current_streak'] if user_points_row else 0
    
    # Category data for pie chart
    category_data = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? AND date LIKE ? GROUP BY category",
        (g.user['id'], f"{current_month}%")
    ).fetchall()
    
    conn.close()
    
    return render_template(
        "home.html",
        income=income,
        month_spent=month_spent,
        savings=savings,
        health_score=health['total'],
        health=health,
        active_challenges=active_challenges,
        recent_achievements=recent_achievements,
        current_streak=current_streak,
        category_data=[dict(r) for r in category_data]
    )

if __name__ == "__main__":
    app.run(debug=True, port=5001)
