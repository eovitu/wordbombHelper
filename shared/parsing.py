from flask import request


def normalize_capture_region(region):
    """Ensures MSS capture dict shape: x1, y1, width, height (positive ints).

    Accepts regions from calibration overlays that may omit width/height if x2/y2 exist.
    """
    if not isinstance(region, dict):
        return None
    try:
        x1 = int(region["x1"])
        y1 = int(region["y1"])
    except (KeyError, TypeError, ValueError):
        return None

    width = region.get("width")
    height = region.get("height")
    if width is None or height is None:
        try:
            x2 = int(region["x2"])
            y2 = int(region["y2"])
            width = abs(x2 - x1)
            height = abs(y2 - y1)
        except (KeyError, TypeError, ValueError):
            return None
    else:
        try:
            width = int(width)
            height = int(height)
        except (TypeError, ValueError):
            return None

    if width <= 0 or height <= 0:
        return None

    out = {"x1": x1, "y1": y1, "width": width, "height": height}
    for k_pair in ("x2", "y2"):
        if k_pair in region:
            try:
                out[k_pair] = int(region[k_pair])
            except (TypeError, ValueError):
                pass
    return out


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


def to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    return bool(value)
