def analyze(data):

    total = data.get("total",0)
    new = data.get("new",0)
    follow = data.get("follow_up",0)

    if total > 0:
        recommendation = (
            f"Total {total} patients connected. "
            f"New registration {new}. "
            f"Follow-up tracking should be improved."
        )
    else:
        recommendation = "No patient data available."

    return {
        "module":"Patient Analysis",
        "summary":data,
        "recommendation":recommendation
    }
