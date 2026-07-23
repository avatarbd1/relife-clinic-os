def analyze(data):

    income = data.get("income",0)
    expense = data.get("expense",0)
    profit = data.get("profit",0)

    recommendation = (
        f"Income: {income} BDT. "
        f"Expense: {expense} BDT. "
        f"Profit: {profit} BDT. "
        "Daily collection and expense monitoring recommended."
    )

    return {
        "module":"Finance Analysis",
        "summary":data,
        "recommendation":recommendation
    }
