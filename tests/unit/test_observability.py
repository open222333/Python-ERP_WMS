# [OPT-N2] 可觀測性（src/observability.py）單元測試
"""
測試項目：
- response 帶有 X-Request-ID（自動產生，16 碼 hex）
- 帶入合法 X-Request-ID 時沿用
- 非法 X-Request-ID 被丟棄並重新產生
- 慢請求超過閾值（SLOW_REQUEST_MS）觸發 warning log
- SSE 路徑（/stream）排除慢請求記錄
- RequestIdFilter 無 request context 時 request_id 為 '-'
- JsonRequestFormatter 輸出必要欄位
"""
import json
import logging

from src.observability import (
    JsonRequestFormatter,
    RequestIdFilter,
    _slow_threshold_ms,
)


# ─────────────────────────────────────────────────────────────
#  Request-ID
# ─────────────────────────────────────────────────────────────
def test_response_has_generated_request_id(client):
    resp = client.get('/')
    rid = resp.headers.get('X-Request-ID')
    assert rid, 'response 應帶有 X-Request-ID header'
    assert len(rid) == 16
    int(rid, 16)  # uuid4().hex[:16] 應為合法 hex


def test_incoming_request_id_is_reused(client):
    resp = client.get('/', headers={'X-Request-ID': 'abc-123_XYZ'})
    assert resp.headers['X-Request-ID'] == 'abc-123_XYZ'


def test_invalid_incoming_request_id_is_regenerated(client):
    bad = 'bad id!!<script>' + 'x' * 100  # 含空白/特殊字元且超長
    resp = client.get('/', headers={'X-Request-ID': bad})
    rid = resp.headers['X-Request-ID']
    assert rid != bad
    assert len(rid) == 16


def test_request_ids_differ_between_requests(client):
    r1 = client.get('/')
    r2 = client.get('/')
    assert r1.headers['X-Request-ID'] != r2.headers['X-Request-ID']


# ─────────────────────────────────────────────────────────────
#  慢請求
# ─────────────────────────────────────────────────────────────
def test_slow_request_logged(client, monkeypatch, caplog):
    monkeypatch.setenv('SLOW_REQUEST_MS', '0')  # 閾值 0 → 任何請求都算慢
    with caplog.at_level(logging.WARNING, logger='src.observability'):
        resp = client.get('/')
    slow_recs = [r for r in caplog.records if 'slow request' in r.getMessage()]
    assert slow_recs, '超過閾值應記 warning'
    msg = slow_recs[0].getMessage()
    assert 'GET' in msg
    assert '/' in msg
    assert f'status={resp.status_code}' in msg
    assert resp.headers['X-Request-ID'] in msg


def test_slow_request_not_logged_under_threshold(client, monkeypatch, caplog):
    monkeypatch.setenv('SLOW_REQUEST_MS', '600000')  # 10 分鐘，不可能超過
    with caplog.at_level(logging.WARNING, logger='src.observability'):
        client.get('/')
    assert not any('slow request' in r.getMessage() for r in caplog.records)


def test_slow_request_excludes_sse_stream_path(client, monkeypatch, caplog):
    monkeypatch.setenv('SLOW_REQUEST_MS', '0')
    with caplog.at_level(logging.WARNING, logger='src.observability'):
        # 路徑含 /stream 即排除（404 也會走 after_request）
        client.get('/no-such-endpoint/stream')
    assert not any('slow request' in r.getMessage() for r in caplog.records)


def test_slow_threshold_default_and_invalid(monkeypatch):
    monkeypatch.delenv('SLOW_REQUEST_MS', raising=False)
    assert _slow_threshold_ms() == 1000
    monkeypatch.setenv('SLOW_REQUEST_MS', 'not-a-number')
    assert _slow_threshold_ms() == 1000
    monkeypatch.setenv('SLOW_REQUEST_MS', '2500')
    assert _slow_threshold_ms() == 2500


# ─────────────────────────────────────────────────────────────
#  logging Filter / Formatter
# ─────────────────────────────────────────────────────────────
def _make_record(msg='hello %s', args=('world',)):
    return logging.LogRecord('test.logger', logging.INFO, __file__, 1,
                             msg, args, None)


def test_request_id_filter_without_context():
    rec = _make_record()
    assert RequestIdFilter().filter(rec) is True
    assert rec.request_id == '-'


def test_request_id_filter_inside_request(app):
    with app.test_request_context('/x', headers={'X-Request-ID': 'rid-in-ctx'}):
        from flask import g
        g.request_id = 'rid-in-ctx'
        rec = _make_record()
        RequestIdFilter().filter(rec)
        assert rec.request_id == 'rid-in-ctx'


def test_json_formatter_fields():
    rec = _make_record()
    rec.request_id = 'rid123'
    out = json.loads(JsonRequestFormatter().format(rec))
    assert out['message'] == 'hello world'
    assert out['level'] == 'INFO'
    assert out['logger'] == 'test.logger'
    assert out['request_id'] == 'rid123'
    assert out['time']
