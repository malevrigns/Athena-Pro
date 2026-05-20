from __future__ import annotations

CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def escape_csv_cell(value: object) -> object:
    if not isinstance(value, str):
        return value
    if value.startswith(CSV_FORMULA_PREFIXES):
        return "'" + value
    return value
