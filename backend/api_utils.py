"""Small API response and parsing helpers."""

import json

from flask import jsonify

try:
    from .config import ALLOWED_EXT
except ImportError:
    from config import ALLOWED_EXT


def rows_to_list(rows):
    return [dict(r) for r in rows]


def ok(data=None, **kwargs):
    payload = {'ok': True}
    if data is not None:
        payload['data'] = data
    payload.update(kwargs)
    return jsonify(payload)


def err(message, status=400):
    return jsonify({'ok': False, 'error': message}), status


def to_int(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value):
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def json_text(value):
    if value in (None, ''):
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def normalize_tags(tags):
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(',') if t.strip()]
    return tags or []


def to_bool_int(value, default=0):
    if value in (None, ''):
        return default
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if int(value) else 0
    text = str(value).strip().lower()
    if text in ('1', 'true', 'yes', 'y', 'on'):
        return 1
    if text in ('0', 'false', 'no', 'n', 'off'):
        return 0
    return default
