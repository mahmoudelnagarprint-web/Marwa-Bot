
def get_customers_stats():
    """
    Returns stats for Client Page:
    - wholesale count
    - retail count
    - total_debt (Sum of all balances displayed in table)
    """
    try:
        clients = get_all_clients()
        
        wholesale = len([c for c in clients if c['type'] == 'Wholesale'])
        retail = len([c for c in clients if c['type'] == 'Retail'])
        total_debt = sum(c.get('balance', 0) for c in clients)
        
        return {
            'wholesale': wholesale,
            'retail': retail,
            'total_debt': total_debt
        }
    except Exception as e:
        print(f"Error in get_customers_stats: {e}")
        return {
            'wholesale': 0,
            'retail': 0,
            'total_debt': 0
        }
