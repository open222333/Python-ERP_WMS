"""
[REFACTOR] SSE 一次性 ticket 流程測試。

流程：POST /customer-order/stream-ticket（header JWT）→ 取得 30 秒 TTL 一次性 ticket
     → GET /customer-order/stream?ticket=（GETDEL 用過即失效）
舊 ?token=JWT query string 路徑保留向下相容（deprecated）。
"""


def _issue_ticket(client, headers):
    r = client.post('/customer-order/stream-ticket', headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['success'] is True
    assert body['ticket']
    return body['ticket']


class TestStreamTicketIssue:
    def test_issue_requires_jwt(self, client):
        assert client.post('/customer-order/stream-ticket').status_code == 401

    def test_issue_returns_ticket(self, client, admin_headers):
        ticket = _issue_ticket(client, admin_headers)
        assert isinstance(ticket, str)
        assert len(ticket) >= 32

    def test_ticket_stored_in_redis_with_ttl(self, client, admin_headers):
        from src.redis_client import get_redis
        ticket = _issue_ticket(client, admin_headers)
        r = get_redis()
        key = f'sse_ticket:{ticket}'
        assert r.exists(key)
        ttl = r.ttl(key)
        assert 0 < ttl <= 30


class TestStreamWithTicket:
    def test_stream_with_valid_ticket_200(self, client, admin_headers):
        ticket = _issue_ticket(client, admin_headers)
        r = client.get(f'/customer-order/stream?ticket={ticket}')
        assert r.status_code == 200
        assert r.content_type.startswith('text/event-stream')
        # 第一筆推播在 sleep 前即 yield，僅取一筆避免阻塞
        first = next(iter(r.response))
        assert b'data:' in first
        r.close()

    def test_ticket_is_single_use(self, client, admin_headers):
        ticket = _issue_ticket(client, admin_headers)
        r1 = client.get(f'/customer-order/stream?ticket={ticket}')
        assert r1.status_code == 200
        r1.close()
        # 同一 ticket 第二次使用 → 401（GETDEL 一次性）
        r2 = client.get(f'/customer-order/stream?ticket={ticket}')
        assert r2.status_code == 401
        assert r2.get_json()['message'] == '未授權'

    def test_stream_invalid_ticket_401(self, client):
        r = client.get('/customer-order/stream?ticket=not-a-real-ticket')
        assert r.status_code == 401

    def test_stream_no_ticket_no_token_401(self, client):
        r = client.get('/customer-order/stream')
        assert r.status_code == 401
        assert r.get_json()['message'] == '未授權'


class TestLegacyTokenPath:
    """deprecated 相容路徑：部署過渡期舊前端仍以 ?token=JWT 連線。"""

    def test_legacy_jwt_token_still_works(self, client, app, db):
        from flask_jwt_extended import create_access_token
        db['users'].insert_one({'username': 'legacy_kitchen', 'password': 'x',
                                'role': 'admin', 'store_ids': []})
        with app.test_request_context():
            token = create_access_token(
                identity='legacy_kitchen',
                additional_claims={'role': 'admin', 'store_ids': []})
        r = client.get(f'/customer-order/stream?token={token}')
        assert r.status_code == 200
        assert r.content_type.startswith('text/event-stream')
        r.close()

    def test_legacy_invalid_jwt_401(self, client):
        r = client.get('/customer-order/stream?token=garbage.jwt.token')
        assert r.status_code == 401
