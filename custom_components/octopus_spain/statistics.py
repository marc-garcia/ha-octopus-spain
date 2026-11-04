"""Build and inject consumption/export statistics into the HA recorder."""

from datetime import datetime, timezone

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.core import HomeAssistant

from .cost_calculation import cost_statistics

DOMAIN_SOURCE = "octopus_spain"


def build_statistics(readings: list[dict], start_sum: float = 0.0, after: datetime | None = None) -> list[dict]:
    """Turn hourly readings into cumulative statistics.

    - readings: list of {start, end, value} (value in kWh).
    - start_sum: previous cumulative sum (to continue an existing series).
    - after: if set, drop readings whose start is <= after (UTC).

    Returns [{start(UTC), state, sum}] sorted by time.
    """
    stats: list[dict] = []
    running = start_sum
    for reading in sorted(readings, key=lambda x: x["start"]):
        start = reading["start"].astimezone(timezone.utc)
        if after is not None and start <= after:
            continue
        running += reading["value"]
        stats.append({"start": start, "state": reading["value"], "sum": running})
    return stats


def _row_start_to_datetime(value) -> datetime:
    """A statistics row 'start' may be a timestamp (float) or a datetime."""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromtimestamp(value, tz=timezone.utc)


async def async_import_statistics(hass: HomeAssistant, cups: str, flow: str, readings: list[dict], energy_price=None) -> None:
    """Inject readings as external statistics (flow is one of 'consumo'/'vertido')."""
    if not readings:
        if flow == "consumo" and energy_price is not None:
            await async_import_cost_statistics(hass, cups, energy_price, [])
        return

    statistic_id = f"{DOMAIN_SOURCE}:{flow}_{cups.lower()}"

    last = await get_instance(hass).async_add_executor_job(get_last_statistics, hass, 1, statistic_id, True, {"sum"})
    start_sum = 0.0
    after: datetime | None = None
    if last.get(statistic_id):
        prev = last[statistic_id][0]
        start_sum = prev.get("sum") or 0.0
        after = _row_start_to_datetime(prev["start"])

    stats = build_statistics(readings, start_sum=start_sum, after=after)
    if not stats:
        if flow == "consumo" and energy_price is not None:
            await async_import_cost_statistics(hass, cups, energy_price, [])
        return

    metadata = StatisticMetaData(
        has_mean=False,
        mean_type=StatisticMeanType.NONE,
        has_sum=True,
        name=f"Octopus {flow} {cups}",
        source=DOMAIN_SOURCE,
        statistic_id=statistic_id,
        unit_of_measurement="kWh",
    )
    data = [StatisticData(start=s["start"], state=s["state"], sum=s["sum"]) for s in stats]
    async_add_external_statistics(hass, metadata, data)

    if flow == "consumo" and energy_price is not None:
        await async_import_cost_statistics(hass, cups, energy_price, stats)


async def async_import_cost_statistics(hass, cups, price, pending_energy_rows):
    """Backfill from stored energy and include queued imports without a race."""
    energy_id = f"{DOMAIN_SOURCE}:consumo_{cups.lower()}"
    cost_id = f"{DOMAIN_SOURCE}:coste_sin_impuestos_{cups.lower()}"
    recorder = get_instance(hass)
    stored = await recorder.async_add_executor_job(
        statistics_during_period, hass, datetime(1970, 1, 1, tzinfo=timezone.utc), None, {energy_id}, "hour", None, {"state", "sum"}
    )
    merged = {_row_start_to_datetime(r["start"]): r for r in stored.get(energy_id, [])}
    merged.update({_row_start_to_datetime(r["start"]): r for r in pending_energy_rows})
    costs = cost_statistics(merged.values(), price)
    if not costs:
        return
    previous = await recorder.async_add_executor_job(get_last_statistics, hass, 1, cost_id, True, {"sum"})
    if previous.get(cost_id):
        last = previous[cost_id][0]
        last_time = _row_start_to_datetime(last["start"])
        match = next((r for r in costs if r["start"] == last_time), None)
        # Same rate: only append. Changed fixed rate: explicitly recalculate all history.
        if match and abs(match["sum"] - (last.get("sum") or 0)) < 1e-8:
            costs = [r for r in costs if r["start"] > last_time]
    if costs:
        metadata = StatisticMetaData(
            has_mean=False,
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name="Octopus coste de energía sin impuestos",
            source=DOMAIN_SOURCE,
            statistic_id=cost_id,
            unit_of_measurement="EUR",
        )
        async_add_external_statistics(hass, metadata, [StatisticData(**r) for r in costs])
