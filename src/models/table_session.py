"""
桌況 Session — Redis-backed
一桌一 session，同桌所有裝置共用同一 token
關閉時機：訂單結帳（completed）或取消（cancelled）、管理員手動關閉
"""
import json
import secrets
from datetime import datetime, timedelta
from src.redis_client import get_redis

DEFAULT_TTL_HOURS = 6
_CLOSE_FLAG_TTL = 300  # 關閉旗標存活 5 分鐘，供 SSE generator 感知


class TableSession:
    _PFX       = 'table_session:'
    _TOK_PFX   = 'table_session_tok:'
    _CLOSE_PFX = 'table_session_closed:'

    @classmethod
    def _r(cls):
        return get_redis()

    @classmethod
    def get_or_create(cls, table_no: str, table_label: str = '',
                      ttl_hours: int = DEFAULT_TTL_HOURS) -> str:
        """
        回傳此桌的 session token。
        已有有效 session → 沿用（同桌共用）；無 → 建新。
        """
        r = cls._r()
        key = cls._PFX + table_no
        raw = r.get(key)
        if raw:
            return json.loads(raw)['token']

        token = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        data = {
            'token':       token,
            'table_no':    table_no,
            'table_label': table_label or table_no,
            'created_at':  now.isoformat(),
            'expires_at':  (now + timedelta(hours=ttl_hours)).isoformat(),
        }
        ttl_sec = ttl_hours * 3600
        pipe = r.pipeline()
        pipe.setex(key, ttl_sec, json.dumps(data))
        pipe.setex(cls._TOK_PFX + token, ttl_sec, table_no)
        pipe.execute()
        return token

    @classmethod
    def get_by_token(cls, token: str):
        """以 session token 反查，回傳 dict 或 None。"""
        r = cls._r()
        table_no = r.get(cls._TOK_PFX + token)
        if not table_no:
            return None
        raw = r.get(cls._PFX + table_no)
        return json.loads(raw) if raw else None

    @classmethod
    def get_by_table(cls, table_no: str):
        """取得桌號的 session 資料，不存在回傳 None。"""
        r = cls._r()
        raw = r.get(cls._PFX + table_no)
        return json.loads(raw) if raw else None

    @classmethod
    def close(cls, table_no: str) -> bool:
        """
        關閉桌況：刪除 session + token，設關閉旗標讓 SSE 感知。
        回傳 True 表示確實關閉了一個存在的 session。
        """
        r = cls._r()
        key = cls._PFX + table_no
        raw = r.get(key)
        if not raw:
            return False
        token = json.loads(raw).get('token', '')
        pipe = r.pipeline()
        pipe.delete(key)
        if token:
            pipe.delete(cls._TOK_PFX + token)
        pipe.setex(cls._CLOSE_PFX + table_no, _CLOSE_FLAG_TTL, '1')
        pipe.execute()
        return True

    @classmethod
    def is_closed(cls, table_no: str) -> bool:
        """SSE generator 用：session 是否已關閉或過期。"""
        r = cls._r()
        if r.exists(cls._CLOSE_PFX + table_no):
            return True
        return not bool(r.exists(cls._PFX + table_no))
