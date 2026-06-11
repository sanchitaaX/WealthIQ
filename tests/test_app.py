import os
import tempfile
import pytest
from flask import session
from app import app as flask_app
from database.db import get_db, init_db, seed_db

@pytest.fixture
def client():
    # Use a temporary SQLite database for testing
    db_fd, db_path = tempfile.mkstemp()
    os.environ["SPENDLY_DB_PATH"] = db_path
    flask_app.config['TESTING'] = True
    
    with flask_app.test_client() as client:
        with flask_app.app_context():
            init_db()
            seed_db()
        yield client

    os.close(db_fd)
    try:
        os.unlink(db_path)
    except OSError:
        pass
    if "SPENDLY_DB_PATH" in os.environ:
        del os.environ["SPENDLY_DB_PATH"]

def test_landing_page(client):
    """Test that the landing page renders successfully when logged out."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"WealthIQ" in response.data
    assert b"Understand your" in response.data

def test_register_login_logout(client):
    """Test the complete user authentication lifecycle (register, login, logout)."""
    # 1. Register a new user
    response = client.post('/register', data={
        'name': 'Alice Smith',
        'email': 'alice@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Transactions" in response.data or b"WealthIQ" in response.data
    
    # 2. Logout
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b"logged out successfully" in response.data
    assert b"Sign in" in response.data

    # 3. Login
    response = client.post('/login', data={
        'email': 'alice@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Transactions" in response.data or b"WealthIQ" in response.data

def test_login_invalid_credentials(client):
    """Test that login fails with invalid credentials."""
    response = client.post('/login', data={
        'email': 'wrong@example.com',
        'password': 'badpassword'
    })
    assert response.status_code == 200
    assert b"Invalid email address or password" in response.data

def test_dashboard_unauthorized(client):
    """Test that unauthorized users are redirected to login when accessing dashboard."""
    response = client.get('/dashboard', follow_redirects=True)
    assert response.status_code == 200
    assert b"Please sign in to access that page" in response.data
    assert b"Sign in" in response.data

def test_expense_crud(client):
    """Test creating, editing, and deleting an expense."""
    # Login first
    client.post('/login', data={
        'email': 'nitish@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    
    # 1. Add Expense
    response = client.post('/expenses/add', data={
        'amount': '150.00',
        'category': 'Food',
        'date': '2026-06-10',
        'description': 'Test Taco Bell'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Expense added" in response.data or b"exceeded" in response.data or b"used over" in response.data
    assert b"Test Taco Bell" in response.data
    
    # Fetch expense ID from database to edit
    conn = get_db()
    expense = conn.execute("SELECT id FROM expenses WHERE description = ?", ('Test Taco Bell',)).fetchone()
    expense_id = expense['id']
    conn.close()
    
    # 2. Edit Expense
    response = client.post(f'/expenses/{expense_id}/edit', data={
        'amount': '250.00',
        'category': 'Food',
        'date': '2026-06-10',
        'description': 'Updated Taco Feast'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Updated Taco Feast" in response.data
    assert b"250.00" in response.data
    
    # 3. Delete Expense
    response = client.get(f'/expenses/{expense_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    assert b"Expense deleted successfully" in response.data
    assert b"Updated Taco Feast" not in response.data

def test_profile_budget_update(client):
    """Test updating the monthly budget from the profile page."""
    # Login
    client.post('/login', data={
        'email': 'demo@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    
    # Update budget
    response = client.post('/profile', data={
        'budget': '45000',
        'monthly_income': '60000'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Preferences updated successfully" in response.data
    assert b"45000" in response.data
    
    # Verify DB update
    conn = get_db()
    user = conn.execute("SELECT budget FROM users WHERE email = ?", ('demo@example.com',)).fetchone()
    assert user['budget'] == 45000.0
    conn.close()
