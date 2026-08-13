from apps.services.filters import (
    is_abnormal_price,
    is_rental_plate,
    parse_price_manwon,
    should_reject_row,
)


def test_rental_ha_heo_ho():
    assert is_rental_plate("12하3456")
    assert is_rental_plate("88허1234")
    assert is_rental_plate("01호9999")
    assert not is_rental_plate("12가3456")
    assert not is_rental_plate(None)


def test_price_parse_and_reject():
    assert parse_price_manwon("1,740") == 1740
    assert parse_price_manwon(3250) == 3250
    assert is_abnormal_price(0)
    assert is_abnormal_price(-1)
    assert is_abnormal_price(9999)
    assert is_abnormal_price(10000)
    assert not is_abnormal_price(9998)
    assert not is_abnormal_price(1)


def test_should_reject():
    assert should_reject_row("12하1111", "1000", "encar", "1")[0]
    assert should_reject_row("12가1111", "9999", "encar", "1")[0]
    assert should_reject_row("12가1111", "1000", "", "1")[0]
    ok, reason = should_reject_row("12가1111", "1000", "encar", "1")
    assert ok is False and reason is None
