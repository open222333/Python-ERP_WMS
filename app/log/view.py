"""
操作紀錄 Blueprint  /log
  GET  /          列表（含搜尋/分頁）
  GET  /export    匯出 CSV（無筆數上限）
  POST /import    匯入 CSV / JSON
  GET  /stats     統計（總筆數 + 指定天數的超齡筆數）
  POST /cleanup   立即清除超齡紀錄（需 admin）
"""
import csv
import io
import json
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.log import Log
from src.models.settings import SystemSettings
from src.permissions import require_role

logger    = logging.getLogger(__name__)
app_log   = Blueprint('app_log', __name__)

# 每次查看紀錄頁時，若距上次清除已超過此秒數則自動觸發清除
_AUTO_CLEANUP_INTERVAL = 86400   # 1 天


# ── 輔助：自動清除（懶觸發）─────────────────────────────
def _maybe_auto_cleanup():
    """若已設定保留天數，且距上次清除 ≥ 1 天，則自動清除超齡紀錄。"""
    try:
        s = SystemSettings.get_all()
        days = int(s.get('log_retention_days', 0) or 0)
        if days <= 0:
            return
        last_str = s.get('log_last_cleanup_at', '')
        if last_str:
            try:
                last_dt = datetime.fromisoformat(last_str)
                elapsed = (datetime.utcnow() - last_dt).total_seconds()
                if elapsed < _AUTO_CLEANUP_INTERVAL:
                    return   # 不到 1 天，跳過
            except ValueError:
                pass
        deleted = Log.cleanup_old(days)
        SystemSettings.set('log_last_cleanup_at', datetime.utcnow().isoformat())
        if deleted:
            logger.info('auto-cleanup: removed %d log entries older than %d days', deleted, days)
    except Exception as e:
        logger.warning('auto-cleanup error: %s', e)


# ── GET / ────────────────────────────────────────────────
@app_log.route('/', methods=['GET'])
@jwt_required()
def list_logs():
    """
    列出操作紀錄
    ---
    tags:
      - Log
    security:
      - Bearer: []
    parameters:
      - {in: query, name: limit,      type: integer, default: 200}
      - {in: query, name: username,   type: string}
      - {in: query, name: action,     type: string}
      - {in: query, name: start_date, type: string, description: "YYYY-MM-DD"}
      - {in: query, name: end_date,   type: string, description: "YYYY-MM-DD"}
    responses:
      200:
        description: 成功
    """
    _maybe_auto_cleanup()   # 懶觸發：若設定保留天數且距上次 ≥ 1 天則自動清除

    limit      = request.args.get('limit',      200,  type=int)
    username   = request.args.get('username',   '')
    action     = request.args.get('action',     '')
    start_date = request.args.get('start_date', '')
    end_date   = request.args.get('end_date',   '')

    logs = Log.find_all(
        limit      = limit,
        username   = username   or None,
        action     = action     or None,
        start_date = start_date or None,
        end_date   = end_date   or None,
    )
    return jsonify({'success': True, 'data': logs})


# ── GET /stats ───────────────────────────────────────────
@app_log.route('/stats', methods=['GET'])
@jwt_required()
def log_stats():
    """
    取得紀錄統計（總筆數 + 指定天數超齡筆數）
    ---
    tags:
      - Log
    security:
      - Bearer: []
    parameters:
      - {in: query, name: preview_days, type: integer,
         description: "預覽超過 N 天的筆數（預設讀取系統設定）"}
    responses:
      200:
        description: 成功
    """
    total = Log.count_all()
    s = SystemSettings.get_all()
    days = request.args.get('preview_days', None, type=int)
    if days is None:
        days = int(s.get('log_retention_days', 0) or 0)

    older_count = Log.count_older_than(days) if days > 0 else 0
    last_cleanup = s.get('log_last_cleanup_at', None)
    return jsonify({
        'success':      True,
        'total':        total,
        'older_count':  older_count,
        'preview_days': days,
        'last_cleanup': last_cleanup,
    })


# ── GET /export ──────────────────────────────────────────
@app_log.route('/export', methods=['GET'])
@jwt_required()
def export_logs():
    """
    匯出操作紀錄為 CSV（不限筆數）
    ---
    tags:
      - Log
    security:
      - Bearer: []
    parameters:
      - {in: query, name: username,   type: string}
      - {in: query, name: action,     type: string}
      - {in: query, name: start_date, type: string, description: "YYYY-MM-DD"}
      - {in: query, name: end_date,   type: string, description: "YYYY-MM-DD"}
    responses:
      200:
        description: CSV 檔案下載
    """
    username   = request.args.get('username',   '')
    action     = request.args.get('action',     '')
    start_date = request.args.get('start_date', '')
    end_date   = request.args.get('end_date',   '')

    logs = Log.find_all(
        limit      = 0,          # 0 = 無上限
        username   = username   or None,
        action     = action     or None,
        start_date = start_date or None,
        end_date   = end_date   or None,
    )

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['username', 'action', 'detail', 'success', 'created_at'])
        yield buf.getvalue(); buf.seek(0); buf.truncate()
        for row in logs:
            writer.writerow([
                row.get('username', ''),
                row.get('action', ''),
                row.get('detail', ''),
                'true' if row.get('success', True) else 'false',
                row.get('created_at', ''),
            ])
            yield buf.getvalue(); buf.seek(0); buf.truncate()

    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f'logs_{ts}.csv'
    return Response(
        stream_with_context(generate()),
        mimetype='text/csv; charset=utf-8-sig',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'X-Accel-Buffering': 'no',
        },
    )


# ── POST /import ─────────────────────────────────────────
@app_log.route('/import', methods=['POST'])
@jwt_required()
@require_role('admin')
def import_logs():
    """
    批次匯入操作紀錄（CSV 或 JSON）
    ---
    tags:
      - Log
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
      - application/json
    parameters:
      - in: formData
        name: file
        type: file
        description: CSV 或 JSON 檔案（選一）
    responses:
      200:
        description: 匯入成功，回傳 inserted 筆數
      400:
        description: 格式錯誤或無內容
    """
    rows: list = []

    if request.files.get('file'):
        f = request.files['file']
        raw = f.read().decode('utf-8-sig', errors='replace')
        if f.filename.lower().endswith('.json'):
            try:
                rows = json.loads(raw)
                if not isinstance(rows, list):
                    return jsonify({'success': False, 'message': 'JSON 必須為陣列'}), 400
            except Exception:
                return jsonify({'success': False, 'message': 'JSON 格式錯誤'}), 400
        else:
            # 預設視為 CSV
            reader = csv.DictReader(io.StringIO(raw))
            rows = list(reader)
    else:
        # JSON body
        body = request.get_json(silent=True)
        if isinstance(body, list):
            rows = body
        elif isinstance(body, dict) and 'data' in body:
            rows = body['data']

    if not rows:
        return jsonify({'success': False, 'message': '無可匯入的資料'}), 400

    inserted = Log.bulk_insert(rows)
    operator = get_jwt_identity()
    Log.create(operator, '操作紀錄匯入', f'inserted={inserted}')
    return jsonify({'success': True, 'inserted': inserted})


# ── POST /cleanup ────────────────────────────────────────
@app_log.route('/cleanup', methods=['POST'])
@jwt_required()
@require_role('admin')
def cleanup_logs():
    """
    立即清除超齡操作紀錄（需 admin）
    ---
    tags:
      - Log
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          properties:
            days:
              type: integer
              description: "清除幾天前的紀錄，不帶則讀取系統設定"
    responses:
      200:
        description: 成功，回傳 deleted 筆數
      400:
        description: 未設定保留天數
    """
    data = request.get_json(silent=True) or {}
    days = data.get('days', None)
    if days is None:
        days = int(SystemSettings.get('log_retention_days', 0) or 0)
    else:
        days = int(days)

    if days <= 0:
        return jsonify({'success': False, 'message': '保留天數未設定或為 0，無法清除'}), 400

    deleted = Log.cleanup_old(days)
    SystemSettings.set('log_last_cleanup_at', datetime.utcnow().isoformat())

    operator = get_jwt_identity()
    Log.create(operator, '操作紀錄清除', f'days={days} deleted={deleted}')
    return jsonify({'success': True, 'deleted': deleted, 'days': days})
