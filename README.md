# WealthIQ 💰🚀

Welcome to **WealthIQ**, a next-generation personal finance and expense tracking application. 

While most expense trackers simply record where your money goes, WealthIQ takes a radically different approach: **it turns saving money into an engaging game.** By combining traditional budgeting tools with powerful gamification elements like levels, streaks, badges, and interactive financial challenges, WealthIQ motivates you to build better financial habits.

## 🌟 How It's Different
Traditional expense trackers are often seen as chores. You log in, enter a number, and log out. WealthIQ changes the narrative by introducing:
- **Gamified Savings:** Earn XP (Experience Points) and level up (e.g., from *Beginner Saver* to *Wealth Builder*) just by sticking to your budget and tracking consistently.
- **Achievements & Badges:** Unlock visual trophies for milestones like logging your first expense, maintaining a 7-day streak, or saving 30% of your income.
- **Interactive Challenges:** Opt into specific challenges like "No Food Delivery Week" or "Save ₹100 Daily" to push your financial discipline and earn massive point rewards.
- **Financial Health Score:** Get a dynamically calculated score (0-100) based on your budget discipline, savings percentage, and spending consistency.

## ✨ Key Features
- **Dashboard & Quick Logging:** Easily add, edit, or remove daily expenses with categorized inputs.
- **Deep Analytics:** Visualize your spending through intuitive Chart.js graphs, including category breakdowns, monthly trends, and weekly comparisons.
- **Smart Budgeting:** Set a monthly income and budget limit, and watch your progress update in real-time.
- **User Profiles:** Secure authentication and profile management where you can view your current level, active streak, and overall progress.

## 🛠️ Tech Stack
WealthIQ is built using a robust, lightweight, and easily deployable stack:
- **Backend:** Python with Flask
- **Database:** SQLite (with direct SQL query execution)
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Styling:** Bootstrap 5 (Responsive, clean, and modern light-theme UI)
- **Data Visualization:** Chart.js

## 🚀 Getting Started

### Prerequisites
Make sure you have Python 3.8+ installed on your machine.

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/sanchitaaX/WealthIQ.git
   cd WealthIQ
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: The main requirement is `Flask`)*

3. Run the application:
   ```bash
   python app.py
   ```
   *The database will be automatically initialized and seeded with default achievements and challenges on the first run.*

4. Open your browser and navigate to:
   ```text
   http://127.0.0.1:5001
   ```

## 🎮 The Gamification Engine (Under the Hood)
WealthIQ actively monitors your spending behavior. When you log an expense, the app evaluates your streak. At the end of the month, or when specific criteria are met, the background engine calculates if you've earned any new badges (like "Budget Champion") or completed an active challenge. This immediate feedback loop ensures that you stay motivated to reach your financial goals.
