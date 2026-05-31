"""
顧客訂單 Blueprint  /customer-order
公開（掃碼後）：
- GET  /menu              取得點單菜單（?t=QR_TOKEN），回傳共享 session_token
- GET  /session           驗證 session token（?token=SESSION_TOKEN）
- POST /                  顧客建立訂單（body.session_token）
- GET  /customer-stream   SSE 即時推播訂單狀態（?token=SESSION_TOKEN）

管理員操作：
- GET  /                  查詢訂單列表（需登入）
- GET  /active            待處理 + 處理中訂單（廚房用，需登入）
- GET  /stats             今日統計（需登入）
- GET  /stream            SSE 廚房訂單推送（需登入，?token=JWT）
- GET  /<oid>             取得單筆訂單（需登入）
- PUT  /<oid>/status      更新訂單狀態（operator+；完成/取消時自動關閉桌況）
- DELETE /session/<table_no>  手動關閉桌況 session（admin）

QR Token 管理：
- GET  /tokens            取得 QR Token 清單與設定（admin）
- POST /tokens/refresh    手動刷新所有 QR Token（admin）
- PUT  /tokens/tables     更新桌位清單（admin）
"""
import time
import json
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_jwt_extended import (
    jwt_required, get_jwt_identity, verify_jwt_in_request,
    decode_token, get_jwt,
)
from src.models.customer_order import CustomerOrder, ORDER_STATUS_LABEL
from src.models.table_session import TableSession
from src.models.menu import Menu
from src.models.settings import SystemSettings
from src.models.log import Log
from src.permissions import require_role

app_customer_order = Blueprint('app_customer_order', __name__)


# ── QR Token 工具函式 ─────────────────────────────

def _get_ttl_hours() -> int:
    return max(1, int(SystemSettings.get('qr_token_ttl_hours', 24) or 24))


def _validate_qr_token(token: str):
    """
    驗證 QR token，回傳 (table_no, label)。
    - 系統未啟用 token 模式（table_tokens 為空）→ 回傳 (None, None)
    - token 無效或停用 → 拋出 ValueError
    - token 已過期    → 拋出 ValueError
    """
    table_tokens = SystemSettings.get('table_tokens', {})
    if not table_tokens:
        return None, None  # token 模式未啟用，允許舊 ?table= 行為

    for table_no, info in table_tokens.items():
        if info.get('token') == token:
            if not info.get('enabled', True):
                raise ValueError('此桌位目前停用')
            expires_at = datetime.fromisoformat(info['expires_at'].replace('Z', ''))
            if datetime.utcnow() > expires_at:
                raise ValueError('QR 碼已過期，請洽服務人員重新掃描')
            return table_no, info.get('label', table_no)
    raise ValueError('無效的 QR 碼')


def _maybe_auto_refresh_tokens():
    """懶觸發：若距上次刷新已超過 TTL，自動重產全部 token。"""
    ttl_hours = _get_ttl_hours()
    last_refresh = SystemSettings.get('qr_token_last_refresh', '')
    if last_refresh:
        last_dt = datetime.fromisoformat(last_refresh.replace('Z', ''))
        if datetime.utcnow() < last_dt + timedelta(hours=ttl_hours):
            return  # 尚未到期

    table_tokens = SystemSettings.get('table_tokens', {})
    if not table_tokens:
        return

    expires_at = (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat()
    new_tokens = {
        tn: {**info, 'token': secrets.token_urlsafe(24), 'expires_at': expires_at}
        for tn, info in table_tokens.items()
    }
    SystemSettings.set('table_tokens', new_tokens)
    SystemSettings.set('qr_token_last_refresh', datetime.utcnow().isoformat())


# ── 公開：取得點單菜單 ─────────────────────────────
@app_customer_order.route('/menu', methods=['GET'])
def get_order_menu():
    """
    公開 API：取得顧客點單用菜單（不需登入）
    若系統已啟用 QR Token 模式，必須帶 ?t=TOKEN；驗證通過後回傳 table_no。
    """
    qr_token = request.args.get('t', '').strip()
    resolved_table = None
    resolved_label = None

    if qr_token:
        _maybe_auto_refresh_tokens()
        try:
            resolved_table, resolved_label = _validate_qr_token(qr_token)
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 401
    else:
        # 無 token：若 token 模式已啟用則拒絕
        if SystemSettings.get('table_tokens', {}):
            return jsonify({'success': False, 'message': '請使用 QR Code 掃描進入'}), 401

    # 取得（或建立）此桌的共享 session token
    session_token = None
    if resolved_table:
        session_token = TableSession.get_or_create(
            resolved_table,
            table_label=resolved_label or resolved_table,
        )

    menu_id = request.args.get('menu_id') or SystemSettings.get('order_menu_id', '')
    if menu_id:
        m = Menu.find_by_id(menu_id)
        if m and m.get('status', 1) == 1:
            return jsonify({
                'success': True, 'data': m,
                'table_no': resolved_table, 'table_label': resolved_label,
                'session_token': session_token,
            })

    # fallback：第一個啟用菜單
    menus = Menu.find_all(status=1)
    if not menus:
        return jsonify({'success': False, 'message': '目前無可用菜單'}), 404
    m = Menu.find_by_id(menus[0]['_id'])
    return jsonify({
        'success': True, 'data': m,
        'table_no': resolved_table, 'table_label': resolved_label,
        'session_token': session_token,
    })


# ── 公開：顧客建立訂單 ────────────────────────────
@app_customer_order.route('/', methods=['POST'])
def create_order():
    """
    公開 API：顧客建立點餐訂單
    若攜帶有效 JWT，以帳號 identity 作識別；否則必須帶 table_no 或 qr_token。
    body: { qr_token, table_no, items, total, remark, menu_id }
    items: [{item_id, item_name, qty, price, customizations, note}]
    """
    # 嘗試取得 JWT identity（選用）
    customer_id = None
    jwt_claims  = {}
    try:
        verify_jwt_in_request(optional=True)
        customer_id = get_jwt_identity()
        if customer_id:
            jwt_claims = get_jwt()
    except Exception:
        pass

    data          = request.get_json(silent=True) or {}
    session_token = (data.get('session_token') or '').strip()
    qr_token      = (data.get('qr_token') or '').strip()
    table_no      = (data.get('table_no') or '').strip()
    items         = data.get('items', [])
    total         = data.get('total', 0)
    remark        = data.get('remark', '')
    menu_id       = data.get('menu_id', '')

    # 優先使用桌況 session token（掃碼後由 /menu 回傳）
    if session_token:
        session = TableSession.get_by_token(session_token)
        if not session:
            return jsonify({'success': False, 'message': '桌況已結束，請重新掃描 QR Code'}), 401
        table_no = session['table_no']
    # 舊版 guest JWT 相容
    elif customer_id == '__guest__':
        table_no = jwt_claims.get('table_no', '') or table_no
    elif qr_token:
        # 舊模式相容：body 帶 qr_token
        try:
            resolved, _ = _validate_qr_token(qr_token)
            if resolved:
                table_no = resolved
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 401
    elif SystemSettings.get('table_tokens', {}):
        # Token 模式已啟用但未提供任何憑據
        if not customer_id:
            return jsonify({'success': False, 'message': '請使用 QR Code 掃描進入'}), 401

    # 一般已登入帳號（非 guest）
    if customer_id and customer_id != '__guest__':
        table_no = table_no or customer_id

    if not table_no:
        return jsonify({'success': False, 'message': '請登入或輸入桌號/姓名'}), 400
    if not items:
        return jsonify({'success': False, 'message': '請至少選擇一個品項'}), 400
    if not isinstance(items, list):
        return jsonify({'success': False, 'message': '品項格式錯誤'}), 400

    # 基本欄位驗證
    for i, it in enumerate(items):
        if not it.get('item_name'):
            return jsonify({'success': False,
                            'message': f'第 {i+1} 筆品項缺少名稱'}), 400
        if not isinstance(it.get('qty', 0), (int, float)) or it.get('qty', 0) <= 0:
            return jsonify({'success': False,
                            'message': f'第 {i+1} 筆品項數量無效'}), 400

    oid = CustomerOrder.create(
        table_no=table_no,
        items=items,
        total=float(total),
        remark=remark,
        menu_id=menu_id,
    )
    order = CustomerOrder.find_by_id(oid)
    return jsonify({
        'success':  True,
        'order_id': oid,
        'order_no': order['order_no'],
    }), 201


# ── SSE：即時訂單推送 ─────────────────────────────
@app_customer_order.route('/stream', methods=['GET'])
def stream_orders():
    """
    SSE 推送廚房訂單（每 2 秒檢查，有變更才推送）
    JWT 以 ?token= query string 傳遞（EventSource 不支援自訂 header）
    """
    raw_token = request.args.get('token', '')
    if not raw_token:
        return jsonify({'success': False, 'message': '未授權'}), 401
    try:
        decode_token(raw_token)
    except Exception:
        return jsonify({'success': False, 'message': '未授權'}), 401

    def generate():
        last_hash = None
        while True:
            try:
                orders = CustomerOrder.find_active()
                stats  = CustomerOrder.today_stats()
                payload = {'orders': orders, 'stats': stats}
                h = hashlib.md5(
                    json.dumps(payload, sort_keys=True, default=str).encode()
                ).hexdigest()
                if h != last_hash:
                    last_hash = h
                    yield f"data: {json.dumps(payload, default=str)}\n\n"
                time.sleep(1)
            except GeneratorExit:
                break
            except Exception:
                break

    return Response(
        stream_with_context(generate()),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection':  'keep-alive',
        },
    )


# ── 需登入：查詢訂單列表 ──────────────────────────
@app_customer_order.route('/', methods=['GET'])
@jwt_required()
def list_orders():
    """查詢訂單（可依 status / date 篩選）"""
    status = request.args.get('status', '')
    date   = request.args.get('date', '')
    limit  = int(request.args.get('limit', 100))
    data = CustomerOrder.find_all(
        status=status or None,
        date=date or None,
        limit=limit,
    )
    return jsonify({'success': True, 'data': data})


# ── 需登入：廚房用（待處理 + 處理中）────────────────
@app_customer_order.route('/active', methods=['GET'])
@jwt_required()
def active_orders():
    """取得待處理 + 處理中的訂單（廚房顯示，先進先出）"""
    data = CustomerOrder.find_active()
    return jsonify({'success': True, 'data': data})


# ── 需登入：今日統計 ──────────────────────────────
@app_customer_order.route('/stats', methods=['GET'])
@jwt_required()
def order_stats():
    """今日各狀態訂單數量與金額"""
    stats = CustomerOrder.today_stats()
    labeled = {
        ORDER_STATUS_LABEL.get(k, k): v
        for k, v in stats.items()
    }
    return jsonify({'success': True, 'data': labeled, 'raw': stats})


# ── 需登入：取得單筆訂單 ──────────────────────────
@app_customer_order.route('/<oid>', methods=['GET'])
@jwt_required()
def get_order(oid):
    order = CustomerOrder.find_by_id(oid)
    if not order:
        return jsonify({'success': False, 'message': '訂單不存在'}), 404
    return jsonify({'success': True, 'data': order})


# ── 需登入：更新訂單狀態 ──────────────────────────
@app_customer_order.route('/<oid>/status', methods=['PUT', 'PATCH'])
@jwt_required()
@require_role('admin', 'operator')
def update_order_status(oid):
    """
    更新訂單狀態
    body: { status: 'processing' | 'completed' | 'cancelled' }
    """
    data   = request.get_json(silent=True) or {}
    status = data.get('status', '')
    if not status:
        return jsonify({'success': False, 'message': '請提供 status'}), 400

    operator = get_jwt_identity()
    ok = CustomerOrder.update_status(oid, status, operator)
    if not ok:
        return jsonify({'success': False, 'message': '訂單不存在或狀態無效'}), 404

    order = CustomerOrder.find_by_id(oid)
    Log.create(operator, '更新顧客訂單狀態',
               f"order={order['order_no']} status={status}")

    # 訂單完成時自動建立 POS 銷售記錄
    if status == 'completed':
        try:
            from src.models.pos import PosOrder
            PosOrder.create_from_cust_order(order, operator)
        except Exception:
            pass

    # 結帳或取消 → 關閉桌況 session（通知顧客端 SSE）
    if status in ('completed', 'cancelled') and order and order.get('table_no'):
        try:
            TableSession.close(order['table_no'])
        except Exception:
            pass

    return jsonify({'success': True})


# ── 公開：顧客查詢 session 狀態 ──────────────────
@app_customer_order.route('/session', methods=['GET'])
def get_session():
    """
    公開 API：驗證桌況 session token 是否有效，回傳桌位資訊。
    ?token=SESSION_TOKEN
    """
    raw_token = request.args.get('token', '').strip()
    session = TableSession.get_by_token(raw_token) if raw_token else None
    if not session:
        return jsonify({'success': False, 'message': '桌況已結束，請重新掃描 QR Code'}), 401
    return jsonify({'success': True, 'data': {
        'table_no':    session['table_no'],
        'table_label': session['table_label'],
        'expires_at':  session.get('expires_at'),
    }})


# ── 公開：顧客點餐 SSE ────────────────────────────
@app_customer_order.route('/customer-stream', methods=['GET'])
def customer_stream():
    """
    SSE 推播顧客點餐頁面（?token=SESSION_TOKEN）
    事件類型：
      order_update   — 此桌今日訂單有變更時推送
      session_closed — 結帳/取消/管理員關閉後推送，前端應顯示結束提示
    """
    raw_token = request.args.get('token', '').strip()
    session = TableSession.get_by_token(raw_token) if raw_token else None
    if not session:
        return jsonify({'success': False, 'message': '桌況已結束，請重新掃描 QR Code'}), 401

    table_no = session['table_no']

    def generate():
        last_hash = None
        while True:
            try:
                if TableSession.is_closed(table_no):
                    yield 'event: session_closed\ndata: {}\n\n'
                    break

                orders = CustomerOrder.find_by_table(table_no)
                h = hashlib.md5(
                    json.dumps(orders, sort_keys=True, default=str).encode()
                ).hexdigest()
                if h != last_hash:
                    last_hash = h
                    payload = {'orders': orders, 'table_no': table_no}
                    yield f"event: order_update\ndata: {json.dumps(payload, default=str)}\n\n"

                time.sleep(2)
            except GeneratorExit:
                break
            except Exception:
                break

    return Response(
        stream_with_context(generate()),
        content_type='text/event-stream',
        headers={
            'Cache-Control':    'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection':       'keep-alive',
        },
    )


# ── Admin：手動關閉桌況 session ───────────────────
@app_customer_order.route('/session/<table_no>', methods=['DELETE'])
@jwt_required()
@require_role('admin', 'operator')
def close_table_session(table_no):
    """
    管理員手動關閉桌況（會觸發顧客端 SSE session_closed 事件）
    """
    closed = TableSession.close(table_no)
    operator = get_jwt_identity()
    Log.create(operator, '關閉桌況 session', f'table={table_no}')
    return jsonify({'success': True, 'closed': closed})


# ── Admin：取得 QR Token 清單與設定 ──────────────
@app_customer_order.route('/tokens', methods=['GET'])
@jwt_required()
@require_role('admin')
def get_qr_tokens():
    """取得所有桌位 token、TTL 設定與上次刷新時間，附帶各桌目前 session 狀態"""
    tokens      = SystemSettings.get('table_tokens', {})
    ttl_hours   = _get_ttl_hours()
    last_refresh = SystemSettings.get('qr_token_last_refresh', '')

    sessions = {}
    for table_no in tokens:
        sess = TableSession.get_by_table(table_no)
        if sess:
            sessions[table_no] = {
                'active':      True,
                'created_at':  sess.get('created_at'),
                'expires_at':  sess.get('expires_at'),
                'table_label': sess.get('table_label'),
            }
        else:
            sessions[table_no] = {'active': False}

    return jsonify({'success': True, 'data': {
        'tokens':       tokens,
        'ttl_hours':    ttl_hours,
        'last_refresh': last_refresh,
        'sessions':     sessions,
    }})


# ── Admin：手動刷新所有 QR Token ─────────────────
@app_customer_order.route('/tokens/refresh', methods=['POST'])
@jwt_required()
@require_role('admin')
def refresh_qr_tokens():
    """
    重產所有桌位 token，可同時更新 TTL。
    body（選填）: { ttl_hours: int }
    """
    data = request.get_json(silent=True) or {}
    if 'ttl_hours' in data:
        SystemSettings.set('qr_token_ttl_hours', max(1, int(data['ttl_hours'])))

    ttl_hours    = _get_ttl_hours()
    table_tokens = SystemSettings.get('table_tokens', {})
    expires_at   = (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat()

    new_tokens = {
        tn: {**info, 'token': secrets.token_urlsafe(24), 'expires_at': expires_at}
        for tn, info in table_tokens.items()
    }
    now = datetime.utcnow().isoformat()
    SystemSettings.set('table_tokens', new_tokens)
    SystemSettings.set('qr_token_last_refresh', now)

    operator = get_jwt_identity()
    Log.create(operator, '刷新 QR Token',
               f'共 {len(new_tokens)} 桌位，TTL={ttl_hours}h')
    return jsonify({'success': True, 'data': {
        'tokens':        new_tokens,
        'ttl_hours':     ttl_hours,
        'last_refresh':  now,
    }})


# ── Admin：更新桌位清單 ───────────────────────────
@app_customer_order.route('/tokens/tables', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_qr_tables():
    """
    新增/修改/刪除/開關桌位。
    現有桌位保留 token，新桌位自動產生 token。
    body: { tables: [{table_no, label, enabled}] }
    """
    data   = request.get_json(silent=True) or {}
    tables = data.get('tables', [])

    current   = SystemSettings.get('table_tokens', {})
    ttl_hours = _get_ttl_hours()
    expires_at = (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat()

    # 計算已有的最大序號（用於自動生成 code）
    existing_codes = {info.get('code', '') for info in current.values() if info.get('code')}

    new_tokens = {}
    seq = 1
    for t in tables:
        table_no = (t.get('table_no') or '').strip()
        if not table_no:
            continue
        existing = current.get(table_no, {})

        # code：前端有傳就用前端的，否則沿用舊值，再否則自動生成
        code = (t.get('code') or '').strip() or existing.get('code', '')
        if not code:
            while f'T-{seq:03d}' in existing_codes:
                seq += 1
            code = f'T-{seq:03d}'
            existing_codes.add(code)
            seq += 1

        new_tokens[table_no] = {
            'label':      t.get('label', table_no),
            'enabled':    t.get('enabled', True),
            'code':       code,
            'token':      existing.get('token') or secrets.token_urlsafe(24),
            'expires_at': existing.get('expires_at') or expires_at,
        }

    SystemSettings.set('table_tokens', new_tokens)
    operator = get_jwt_identity()
    Log.create(operator, '更新 QR 桌位清單', f'共 {len(new_tokens)} 桌位')
    return jsonify({'success': True, 'data': new_tokens})
