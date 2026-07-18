from datetime import datetime, timedelta, timezone
BD_TZ = timezone(timedelta(hours=6))
def bd_now() -> datetime:
    return datetime.now(BD_TZ)
