import importlib.util
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest

spec = importlib.util.spec_from_file_location('total_cost', Path(__file__).parents[1] / 'custom_components/octopus_spain/cost_calculation.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def period(start='2026-01-01', **kwargs):
    return {'start': start, 'energy_price': .2, 'power_per_day': 1.2, 'rental_per_day': .1, 'electricity_tax_percent': 5, 'vat_percent': 21, **kwargs}


def rows_for_day(day):
    z = ZoneInfo('Europe/Madrid')
    midnight = datetime.fromisoformat(day).replace(tzinfo=z)
    a = midnight.astimezone(timezone.utc)
    b = (midnight + timedelta(days=1)).astimezone(timezone.utc)
    return [{'start': a + timedelta(hours=i), 'sum': i+1, 'state': 1} for i in range(int((b-a).total_seconds()/3600))]


@pytest.mark.parametrize('day,hours', [('2026-02-01',24),('2026-03-29',23),('2026-10-25',25)])
def test_calendar_days_charge_one_fixed_day_across_dst(day,hours):
    rows = rows_for_day(day)
    result = c.total_cost_statistics(rows, [period()], 'Europe/Madrid')
    assert len(result) == hours
    assert result[-1]['sum'] == pytest.approx(((hours*.2+1.2)*1.05+.1)*1.21)


def test_gap_charges_fixed_costs_once_and_uses_cumulative_energy():
    rows = rows_for_day('2026-02-01')
    expected = c.total_cost_statistics(rows, [period()], 'Europe/Madrid')
    actual = c.total_cost_statistics([rows[0],rows[-1]], [period()], 'Europe/Madrid')
    assert len(actual)==24
    assert actual[-1]['sum']==pytest.approx(expected[-1]['sum'])
    assert sum(r['state'] for r in actual)==pytest.approx(actual[-1]['sum'])
    assert c.total_cost_statistics([rows[0],rows[-1]], [period()], 'Europe/Madrid')==actual


def test_dated_tariff_change_at_local_midnight():
    a=rows_for_day('2026-02-01');b=rows_for_day('2026-02-02')
    for r in b:r['sum']+=24
    periods=[period(),period('2026-02-02',energy_price=.3,electricity_tax_percent=0,vat_percent=10)]
    result=c.total_cost_statistics(a+b,periods,'Europe/Madrid')
    first=((24*.2+1.2)*1.05+.1)*1.21
    second=(24*.3+1.2+.1)*1.1
    assert result[23]['sum']==pytest.approx(first)
    assert result[-1]['sum']==pytest.approx(first+second)


def test_zero_consumption_and_partial_day_do_not_charge_future_hours():
    rows=rows_for_day('2026-02-01')[:6]
    for r in rows:r['sum']=0
    result=c.total_cost_statistics(rows,[period()],'Europe/Madrid')
    assert len(result)==6
    assert result[-1]['sum']==pytest.approx((1.2*1.05+.1)*1.21/4)


@pytest.mark.parametrize('value',[None,{},[period(),period()],[period('2026-02-01'),period()], [period('bad')],[period(vat_percent=101)], [period(power_per_day=-1)], [period(energy_price='NaN')],[period(extra='unknown')],[{'start':'2026-01-01'}]])
def test_invalid_periods_rejected(value):
    with pytest.raises(c.CostPeriodError):c.validate_cost_periods(value)


def test_uncovered_history_and_reset_are_rejected():
    rows=rows_for_day('2026-02-01')
    with pytest.raises(c.CostPeriodError):c.total_cost_statistics(rows,[period('2026-02-02')],'Europe/Madrid')
    rows[-1]['sum']=0
    with pytest.raises(c.CostPeriodError):c.total_cost_statistics(rows,[period()],'Europe/Madrid')


def test_empty_optional_schedule_disables_new_calculation():
    assert c.total_cost_statistics(rows_for_day('2026-02-01'),[],'Europe/Madrid')==[]
