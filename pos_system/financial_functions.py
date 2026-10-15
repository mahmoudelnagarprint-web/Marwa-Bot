
# Financial Stats Functions

def get_financial_stats():
    """
    Returns financial statistics for the accounts page:
    - cash_on_hand: Current total cash (Income - Expenses)
    - income: Total Income (Sales) for current month
    - expense: Total Expenses for current month
    - profit: Net Profit (Income - Expense)
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        import datetime
        # Get current month range
        now = datetime.datetime.now()
        month_start = now.replace(day=1).strftime("%Y-%m-%d")
        
        # Income this month (Payments + Sales)
        income = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type IN ('Income', 'payment') 
            AND date >= ?
        """, (month_start,)).fetchone()[0]
        
        # Expenses this month
        expense = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type = 'Expense' 
            AND date >= ?
        """, (month_start,)).fetchone()[0]
        
        # Cash on Hand (All-Time: Total Income - Total Expenses)
        cash_income = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type IN ('Income', 'payment')
        """).fetchone()[0]
        
        cash_expense = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type = 'Expense'
        """).fetchone()[0]
        
        cash_on_hand = cash_income - cash_expense
        profit = income - expense
        
        # Total Customer Debt = Sum of all displayed client balances
        # (get_all_clients already adds Under Prep to balance)
        from database import get_all_clients
        all_clients = get_all_clients()
        total_debt = sum(client.get('balance', 0) for client in all_clients)
        
        return {
            'cash_on_hand': cash_on_hand,
            'income': income,
            'expense': expense,
            'profit': profit,
            'total_debt': total_debt
        }
        
    except Exception as e:
        print(f"Error in get_financial_stats: {e}")
        return {
            'cash_on_hand': 0,
            'income': 0,
            'expense': 0,
            'profit': 0,
            'total_debt': 0
        }
    finally:
        conn.close()


def get_financial_ledger(start_date=None, end_date=None):
    """
    Returns financial ledger (transaction history) with optional date filtering.
    """
    conn = get_db_connection()
    
    query = """
        SELECT id, date, type, category, amount, notes, user 
        FROM transactions 
        WHERE 1=1
    """
    
    params = []
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND date <= ?"
        params.append(end_date + " 23:59:59")  # Include full end date
    
    query += " ORDER BY date DESC LIMIT 200"
    
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error in get_financial_ledger: {e}")
        return []
    finally:
        conn.close()


def get_unique_categories():
    """Returns list of unique transaction categories."""
    conn = get_db_connection()
    try:
        cats = conn.execute("""
            SELECT DISTINCT category 
            FROM transactions 
            WHERE category IS NOT NULL 
            ORDER BY category
        """).fetchall()
        return [c['category'] for c in cats]
    except:
        return []
    finally:
        conn.close()


def add_general_transaction(t_type, category, amount, description, user):
    """
    Adds a general financial transaction (Income or Expense).
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user)
            VALUES (NULL, ?, ?, ?, ?, ?)
        """, (t_type, category, amount, description, user))
        
        conn.commit()
        return {'success': True, 'message': 'تم إضافة المعاملة بنجاح'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()
