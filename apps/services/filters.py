RENTAL_CHARS = ("하", "허", "호")


def is_rental_plate(car_no: str | None) -> bool:
    if not car_no:
        return False
    return any(ch in car_no for ch in RENTAL_CHARS)


def parse_price_manwon(raw: str | int | None) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw).strip().replace(",", "").replace(" ", "").replace("만원", "")
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def is_abnormal_price(price: int | None) -> bool:
    if price is None:
        return True
    return price <= 0 or price >= 9999


def parse_km(raw: str | int | None) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = (
        str(raw)
        .strip()
        .replace(",", "")
        .replace("km", "")
        .replace("KM", "")
        .replace(" ", "")
    )
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def should_reject_row(
    car_no, car_price_raw, site_type, site_id
) -> tuple[bool, str | None]:
    if not site_type or not site_id:
        return True, "missing_site_key"
    if is_rental_plate(car_no):
        return True, "rental_plate"
    price = parse_price_manwon(car_price_raw)
    if is_abnormal_price(price):
        return True, "abnormal_price"
    return False, None
