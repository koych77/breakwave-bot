from datetime import date

MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


def parse_russian_date(date_str: str):
    """Parse date like '20 апреля 2026' into a date object."""
    if not date_str:
        return None
    parts = date_str.strip().split()
    if len(parts) < 3:
        return None
    try:
        day = int(parts[0])
        month = MONTHS_RU.get(parts[1].lower())
        year = int(parts[2])
        if not month:
            return None
        return date(year, month, day)
    except (ValueError, IndexError):
        return None
