"""Energy-only costs and optional dated estimates of total supply costs."""

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


CONF_COST_PERIODS = "estimated_cost_periods"
_PERIOD_FIELDS = {
    "start", "energy_price", "power_per_day", "rental_per_day",
    "electricity_tax_percent", "vat_percent",
}


class CostPeriodError(ValueError):
    """Invalid dated tariff configuration."""


def validate_cost_periods(value):
    """Normalize a dated, piecewise-constant tariff; no personal defaults."""
    from datetime import date

    if not isinstance(value, list) or len(value) > 200:
        raise CostPeriodError("Expected at most 200 dated cost periods")
    result = []
    for period in value:
        if not isinstance(period, dict) or set(period) != _PERIOD_FIELDS:
            raise CostPeriodError("Missing or unknown cost period fields")
        try:
            start = date.fromisoformat(period["start"]).isoformat()
            normalized = {"start": start}
            for field in _PERIOD_FIELDS - {"start"}:
                rate = validate_price(period[field])
                if field.endswith("percent") and rate > 100:
                    raise ValueError
                normalized[field] = float(rate)
        except (ValueError, TypeError, KeyError):
            raise CostPeriodError("Invalid cost period date or amount") from None
        if result and start <= result[-1]["start"]:
            raise CostPeriodError("Cost periods must have unique ascending dates")
        result.append(normalized)
    return result


def total_cost_statistics(rows, periods, timezone_name):
    """Estimate supply costs by hour, using local calendar days for fixed costs.

    Periods start at local midnight and the last period continues until replaced.
    Energy uses cumulative deltas (not the hourly ``state``) across missing rows.
    Fixed costs accrue across missing hours, but only through the last known
    consumption hour. No rounding until display; no payments or wallet credits.
    """
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    periods = validate_cost_periods(periods)
    if not periods:
        return []
    tz = ZoneInfo(timezone_name)
    indexed = {}
    for row in rows:
        if row.get("sum") is None:
            continue
        start = row["start"]
        if not isinstance(start, datetime):
            start = datetime.fromtimestamp(start, timezone.utc)
        if start.tzinfo is None or start.minute or start.second or start.microsecond:
            raise CostPeriodError("Expected timezone-aware hourly energy statistics")
        value = Decimal(str(row["sum"]))
        if not value.is_finite() or value < 0:
            raise CostPeriodError("Invalid cumulative energy")
        indexed[start.astimezone(timezone.utc)] = value
    if not indexed:
        return []
    first, last = min(indexed), max(indexed)
    if first.astimezone(tz).date().isoformat() < periods[0]["start"]:
        raise CostPeriodError("Cost periods do not cover the energy history")
    previous_energy = Decimal(0)
    running = Decimal(0)
    result = []
    cursor = first
    period_index = 0
    while cursor <= last:
        local = cursor.astimezone(tz)
        day = local.date().isoformat()
        while period_index + 1 < len(periods) and periods[period_index + 1]["start"] <= day:
            period_index += 1
        period = periods[period_index]
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0, fold=0)
        following = midnight + timedelta(days=1)
        hours = Decimal(str((following.astimezone(timezone.utc) - midnight.astimezone(timezone.utc)).total_seconds() / 3600))
        cumulative = indexed.get(cursor, previous_energy)
        energy = cumulative - previous_energy
        if energy < Decimal("-0.0000001"):
            raise CostPeriodError("Cumulative consumption decreased")
        energy = max(energy, Decimal(0))
        previous_energy = cumulative
        electricity = energy * Decimal(str(period["energy_price"]))
        power = Decimal(str(period["power_per_day"])) / hours
        rental = Decimal(str(period["rental_per_day"])) / hours
        tax = Decimal(str(period["electricity_tax_percent"])) / 100
        vat = Decimal(str(period["vat_percent"])) / 100
        amount = ((electricity + power) * (1 + tax) + rental) * (1 + vat)
        running += amount
        result.append({"start": cursor, "state": float(amount), "sum": float(running)})
        cursor += timedelta(hours=1)
    return result
