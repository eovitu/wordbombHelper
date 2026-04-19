from flask import request


def json_or_empty():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def to_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def to_float(value, default):
    try:
        return float(value)
    except Exception:
        return default
