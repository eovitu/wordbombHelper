from functools import wraps
from flask import request, jsonify


def make_optional_auth_required(api_token):
    """Build optional auth decorator.

    If api_token is empty, all requests are accepted.
    """
    safe_token = (api_token or "").strip()

    def optional_auth_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not safe_token:
                return fn(*args, **kwargs)

            provided = request.headers.get("X-API-Token", "").strip()
            if provided != safe_token:
                return jsonify({"status": "error", "message": "Unauthorized"}), 401
            return fn(*args, **kwargs)

        return wrapper

    return optional_auth_required
