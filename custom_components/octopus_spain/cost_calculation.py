"""Fixed-rate energy-only costs; no taxes, power charges or invoice totals."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

CONF_ENERGY_PRICE = "energy_price_excl_tax"


def validate_price(value):
    try:
        price = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid fixed energy price") from None
    if not price.is_finite() or price < 0 or price > 1000:
        raise ValueError("Invalid fixed energy price")
    return price


def cost_statistics(rows, price):
    """Use cumulative energy so missing hours cannot double-count consumption."""
    rate = validate_price(price)
    result = []
    for row in rows:
        if row.get("sum") is None:
            continue
        start = row["start"]
        if not isinstance(start, datetime):
            start = datetime.fromtimestamp(start, timezone.utc)
        result.append(
            {
                "start": start.astimezone(timezone.utc),
                "state": float(Decimal(str(row.get("state") or 0)) * rate),
                "sum": float(Decimal(str(row["sum"])) * rate),
            }
        )
    return sorted(result, key=lambda row: row["start"])
