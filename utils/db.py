import sqlite3
import pandas as pd
import os

DB_NAME = "weekly_data.db"

def init_db():
    """Initialize the SQLite database and create tables if they doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Metrics Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS weekly_metrics (
            week_id TEXT,
            brand TEXT,
            sales_var TEXT,
            margin_var TEXT,
            PRIMARY KEY (week_id, brand)
        )
    ''')
    
    # Settings Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# --- Metrics Functions ---
def save_metrics(week_id, metrics_data):
    """
    Save or replace metrics for a specific week.
    metrics_data is a dict: {"BRAND": {"sales": "X%", "margin": "Y%"}, ...}
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    for brand, data in metrics_data.items():
        sales = data.get("sales", "N/A")
        margin = data.get("margin", "N/A")
        
        c.execute('''
            INSERT OR REPLACE INTO weekly_metrics (week_id, brand, sales_var, margin_var)
            VALUES (?, ?, ?, ?)
        ''', (week_id, brand, sales, margin))
        
    conn.commit()
    conn.close()

def get_metrics(week_id):
    """Retrieve metrics for a specific week as a DataFrame."""
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT brand, sales_var, margin_var FROM weekly_metrics WHERE week_id = ?"
    df = pd.read_sql_query(query, conn, params=(week_id,))
    conn.close()
    return df

def get_all_weeks():
    """Get a list of all available week_ids."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT DISTINCT week_id FROM weekly_metrics ORDER BY week_id DESC")
    weeks = [row[0] for row in c.fetchall()]
    conn.close()
    return weeks

def get_comparison_data(week1_id, week2_id):
    """
    Get comparison data for two weeks.
    Returns a DataFrame with columns: Brand, {week1}_Sales, {week2}_Sales, etc.
    """
    df1 = get_metrics(week1_id)
    df2 = get_metrics(week2_id)
    
    # Rename columns for merge
    df1 = df1.rename(columns={"sales_var": f"{week1_id} Sales", "margin_var": f"{week1_id} Margin"})
    df2 = df2.rename(columns={"sales_var": f"{week2_id} Sales", "margin_var": f"{week2_id} Margin"})
    
    # Merge on Brand
    if not df1.empty and not df2.empty:
        merged = pd.merge(df1, df2, on="brand", how="outer")
        return merged
    elif not df1.empty:
        return df1
    elif not df2.empty:
        return df2
    else:
        return pd.DataFrame()

# --- Settings Functions ---
def save_setting(key, value):
    """Save a single setting."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def load_settings():
    """Load all settings as a dictionary."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('SELECT key, value FROM settings')
        data = dict(c.fetchall())
    except sqlite3.OperationalError:
        data = {}
    conn.close()
    return data
