"""
[REFACTOR] SSE 一次性短效 ticket — Redis-backed
用途：EventSource 不支援自訂 header，過去以 ?token=JWT 傳遞，
     會讓 JWT 進入 nginx access log。改為：
     1. 前端先以一般 header JWT 呼叫 POST /customer-order/stream-ticket 取 ticket
     2. 再以 ?ticket= 連 SSE；後端以 GETDEL 取出即失效（一次性）
TTL 30 秒，僅供「取得後立刻連線」使用。
沿用 table_session 同一個 Redis client。
"""
import json
import secrets
from src.redis_client import get_redis

TICKET_TTL_SECONDS = 30


class SseTicket:
    _PFX = 'sse_ticket:'

    @classmethod
    def _r(cls):
        return get_redis()

    @classmethod
    def issue(cls, identity, claims=None, ttl=TICKET_TTL_SECONDS):
        """
        簽發一次性 ticket：儲存 JWT identity 與必要 claims（JSON 序列化），
        TTL 預設 30 秒。回傳 ticket 字串。
        """
        ticket = secrets.token_urlsafe(32)
        payload = {'identity': identity, 'claims': claims or {}}
        cls._r().setex(cls._PFX + ticket, ttl, json.dumps(payload))
        return ticket

    @classmethod
    def consume(cls, ticket):
        """
        一次性取出 ticket 內容並刪除（redis==5.2.1 支援 GETDEL，原子操作）。
        無效 / 已使用 / 過期 → 回傳 None。
        """
        if not ticket:
            return None
        raw = cls._r().getdel(cls._PFX + ticket)
        return json.loads(raw) if raw else None
