import importlib.util
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest

spec = importlib.util.spec_from_file_location("cost", Path(__file__).parents[1] / "custom_components/octopus_spain/cost_calculation.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def test_costs_follow_cumulative_energy_across_gaps():
    rows = [{"start": 10000, "state": 2.0, "sum": 102.0}, {"start": 2800, "state": 1, "sum": 100.0}]
    result = c.cost_statistics(rows, 0.153)
    assert [r["sum"] for r in result] == [15.3, 15.606]
    assert result[1]["sum"] - result[0]["sum"] == pytest.approx(2 * 0.153)


def test_exact_tariff_and_zero():
    assert c.cost_statistics([{"start": 0, "state": 12.5, "sum": 12.5}], 0.153)[0]["sum"] == 1.9125
    assert c.cost_statistics([{"start": 0, "state": 12.5, "sum": 12.5}], 0)[0]["sum"] == 0


@pytest.mark.parametrize("price", [-0.1, "NaN", "Infinity", float("nan"), 1001, "bad", True])
def test_reject_invalid_rate(price):
    with pytest.raises(ValueError):
        c.validate_price(price)


def test_timezone_is_preserved_as_utc_and_missing_sums_skipped():
    dt = datetime(2026, 10, 25, 2, tzinfo=timezone(timedelta(hours=2)))
    result = c.cost_statistics([{"start": dt, "state": 1, "sum": 1}, {"start": dt, "sum": None}], 0.153)
    assert len(result) == 1 and result[0]["start"].hour == 0 and result[0]["start"].tzinfo == timezone.utc
