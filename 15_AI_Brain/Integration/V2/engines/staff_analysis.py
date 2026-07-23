def analyze(data):

    total = data.get("total",0)
    active = data.get("active",0)

    recommendation = (
        f"Staff registered: {total}, "
        f"Active staff: {active}. "
        "Attendance and performance tracking recommended."
    )

    return {
        "module":"Staff Analysis",
        "summary":data,
        "recommendation":recommendation
    }
