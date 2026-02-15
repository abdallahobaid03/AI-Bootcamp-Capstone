from typing import Optional
from langchain_core.tools import tool
from core.models import Customer, ConsumptionRecord

def _get_customer(user_key: str) -> Optional[Customer]:
    return Customer.objects.filter(user_key=user_key).first()

def _get_records(user_key: str, limit: int = 12):
    customer = _get_customer(user_key)
    if not customer:
        return []
    qs = ConsumptionRecord.objects.filter(customer=customer).order_by("-created_at", "-id")[:limit]
    return list(qs)

@tool
def get_consumption_history(user_key: str, limit: int = 6) -> dict:
    """Fetch latest consumption records (newest -> oldest)."""
    records = _get_records(user_key, limit=12)
    if not records:
        return {"ok": False, "error": "no_data", "records": []}

    limit = max(1, min(int(limit), len(records), 12))
    out = [
        {
            "period_label": r.period_label,
            "kwh": r.kwh,
            "saving_percent": r.saving_percent,
        }
        for r in records[:limit]
    ]
    return {"ok": True, "records": out}

@tool
def compare_last_two_months(user_key: str) -> dict:
    """Compare latest 2 months consumption."""
    records = _get_records(user_key, limit=12)
    if len(records) < 2:
        return {"ok": False, "error": "not_enough_data"}

    a, b = records[0], records[1]
    delta = a.kwh - b.kwh
    pct = None
    if b.kwh:
        pct = (delta / b.kwh) * 100

    return {
        "ok": True,
        "latest": {"period_label": a.period_label, "kwh": a.kwh, "saving_percent": a.saving_percent},
        "previous": {"period_label": b.period_label, "kwh": b.kwh, "saving_percent": b.saving_percent},
        "delta_kwh": delta,
        "delta_percent": pct,
    }

@tool
def average_last_n_months(user_key: str, n: int) -> dict:
    """Average kWh and saving percent over last N months."""
    records = _get_records(user_key, limit=12)
    if not records:
        return {"ok": False, "error": "no_data"}

    n = int(n)
    if n <= 0:
        return {"ok": False, "error": "bad_n"}

    n = min(n, len(records), 12)
    subset = records[:n]
    avg_kwh = sum(r.kwh for r in subset) / n
    avg_saving = sum(r.saving_percent for r in subset) / n

    return {
        "ok": True,
        "n": n,
        "avg_kwh": avg_kwh,
        "avg_saving_percent": avg_saving,
        "periods": [r.period_label for r in subset],
    }
