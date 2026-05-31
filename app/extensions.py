from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    on_breach=None,
    swallow_errors=True,   # Redis 斷線時放行請求，不回傳 500
)
