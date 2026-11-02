"""演示数据的独立预期值检查与边界检查。仅使用 Python 标准库。"""
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from clean_orders import parse_date, parse_money, process

base = Path(__file__).resolve().parent
raw = base / 'raw_orders.csv'
before = raw.read_bytes()
assert parse_money('0.00') == Decimal('0.00')
assert parse_money('CNY 1,200.00') == Decimal('1200.00')
assert parse_money('299.00元') == Decimal('299.00')
for invalid in ('', '￥1,20.00', '-1.00', '1.001', '1,2000', 'abc'):
    try:
        parse_money(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f'Invalid money accepted: {invalid}')
assert parse_date('2026年10月02日') == '2026-10-02'
for invalid in ('11/02/2026', '2026-02-30', ''):
    try:
        parse_date(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f'Invalid date accepted: {invalid}')

with TemporaryDirectory() as temporary:
    one = Path(temporary) / 'one'
    two = Path(temporary) / 'two'
    a = process(raw, one)
    b = process(raw, two)
    assert (a['source_rows'], a['clean_rows'], a['exception_rows'], a['duplicate_rows']) == (30, 20, 8, 2)
    assert a['totals'] == {'paid_orders': 18, 'paid_amount_cny': '5254.96', 'refunded_orders': 1, 'refunded_amount_cny': '80.00', 'unpaid_orders': 1, 'unpaid_amount_cny': '188.00'}
    # Independently sum the 18 paid amounts explicitly listed in the fixture.
    expected_paid = sum(map(Decimal, ['128','59.90','1200','89','299','149.50','68','25','199','39.90','49','2345.67','99.99','18.80','399','0','50','35.20']))
    assert Decimal(a['totals']['paid_amount_cny']) == expected_paid
    assert [x['source_line'] for x in a['duplicates']] == [22, 23]
    assert [x['source_line'] for x in a['exceptions']] == list(range(24, 32))
    assert a['conflict_order_ids'] == ['D021']
    assert next(x for x in a['clean_orders'] if x['order_id'] == 'D017')['amount_cny'] == '0.00'
    assert {p.name: p.read_bytes() for p in one.iterdir()} == {p.name: p.read_bytes() for p in two.iterdir()}
assert raw.read_bytes() == before
print('PASS: 30-row partition; independently reconciled paid total; zero preserved; invalid values isolated; duplicate and conflict handling; byte-identical rerun; raw file unchanged.')
