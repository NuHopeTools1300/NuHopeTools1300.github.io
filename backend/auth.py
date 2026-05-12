"""Admin protection for mutating API routes."""

import os
from functools import wraps

from flask import request

try:
    from .api_utils import err
except ImportError:
    from api_utils import err


ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY')


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if ADMIN_API_KEY:
            key = request.headers.get('X-API-Key') or request.args.get('api_key')
            if key == ADMIN_API_KEY:
                return f(*args, **kwargs)

            local_override = (
                request.headers.get('X-Admin-Local') == '1'
                or request.args.get('admin_local') == '1'
            )
            remote = request.remote_addr or ''
            local_allowed = (
                remote.startswith('127.')
                or remote == '::1'
                or os.environ.get('ALLOW_LOCAL_ADMIN') == '1'
            )
            if local_override and local_allowed:
                return f(*args, **kwargs)

            return err('Unauthorized', 401)
        return f(*args, **kwargs)
    return wrapper
