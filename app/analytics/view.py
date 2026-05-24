from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timedelta
from src.mongo import get_db

app_analytics = Blueprint('app_analytics', __name__)


def _period_start(period: str) -> datetime:
    """回傳指定週期的起始 UTC 時間"""
    now = datetime.utcnow()
    if period == 'day':
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == 'week':
        return (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
    if period == 'month':
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period == 'year':
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f'unknown period: {period}')


def _count(collection: str, start: datetime, status: str = None) -> int:
    q = {'created_at': {'$gte': start}}
    if status:
        q['status'] = status
    return get_db()[collection].count_documents(q)


def _completed_count(collection: str, start: datetime) -> int:
    return get_db()[collection].count_documents(
        {'completed_at': {'$gte': start}, 'status': 'completed'})


def _completed_stats(collection: str, start: datetime) -> dict:
    """
    單次 aggregation 同時計算：
      qty    — 實際數量（received_qty / shipped_qty）
      amount — 實際金額（qty × unit_price）
    回傳 {'qty': int, 'amount': float}
    """
    qty_field = 'received_qty' if collection == 'inbound_orders' else 'shipped_qty'
    pipeline = [
        {'$match': {'completed_at': {'$gte': start}, 'status': 'completed'}},
        {'$unwind': '$items'},
        {'$group': {
            '_id': None,
            'qty':    {'$sum': f'$items.{qty_field}'},
            'amount': {'$sum': {'$multiply': [f'$items.{qty_field}', '$items.unit_price']}},
        }},
    ]
    result = list(get_db()[collection].aggregate(pipeline))
    if result:
        return {'qty': int(result[0]['qty']), 'amount': round(result[0]['amount'], 2)}
    return {'qty': 0, 'amount': 0.0}


def _stock_alerts() -> list:
    """
    回傳庫存異常清單（低庫存 / 超量）。
    以 inventory 為主表，lookup products & warehouses，
    篩選 quantity < min_stock（且 min_stock > 0）或 quantity > max_stock（且 max_stock > 0）
    """
    db = get_db()
    pipeline = [
        # join products
        {'$lookup': {
            'from': 'products',
            'localField': 'product_id',
            'foreignField': '_id',
            'as': 'product',
        }},
        {'$unwind': '$product'},
        # join warehouses
        {'$lookup': {
            'from': 'warehouses',
            'localField': 'warehouse_id',
            'foreignField': '_id',
            'as': 'warehouse',
        }},
        {'$unwind': '$warehouse'},
        # 只取啟用中產品
        {'$match': {'product.status': 1}},
        # 計算警示類型
        {'$addFields': {
            'low':  {'$and': [
                {'$gt': ['$product.min_stock', 0]},
                {'$lt': ['$quantity', '$product.min_stock']},
            ]},
            'high': {'$and': [
                {'$gt': ['$product.max_stock', 0]},
                {'$gt': ['$quantity', '$product.max_stock']},
            ]},
        }},
        # 只保留有警示的
        {'$match': {'$or': [{'low': True}, {'high': True}]}},
        {'$project': {
            '_id': 0,
            'product_id':    {'$toString': '$product._id'},
            'product_name':  '$product.name',
            'product_sku':   '$product.sku',
            'warehouse_id':  {'$toString': '$warehouse._id'},
            'warehouse_name':'$warehouse.name',
            'quantity':      1,
            'min_stock':     '$product.min_stock',
            'max_stock':     '$product.max_stock',
            'alert':         {'$cond': ['$low', 'low', 'high']},
        }},
        {'$sort': {'alert': 1, 'product_sku': 1}},
    ]
    return list(db['inventory'].aggregate(pipeline))


@app_analytics.route('/stock_alerts', methods=['GET'])
@jwt_required()
def stock_alerts():
    """
    庫存警示清單
    ---
    tags:
      - 分析
    security:
      - Bearer: []
    responses:
      200:
        description: 成功
        schema:
          properties:
            success: {type: boolean}
            data:
              type: array
              items:
                type: object
                properties:
                  product_sku:    {type: string}
                  product_name:   {type: string}
                  warehouse_name: {type: string}
                  quantity:       {type: integer}
                  min_stock:      {type: integer}
                  max_stock:      {type: integer}
                  alert:          {type: string, enum: [low, high]}
    """
    return jsonify({'success': True, 'data': _stock_alerts()})


@app_analytics.route('/summary', methods=['GET'])
@jwt_required()
def summary():
    """
    儀表板分析摘要
    ---
    tags:
      - 分析
    security:
      - Bearer: []
    responses:
      200:
        description: 成功
        schema:
          properties:
            success: {type: boolean}
            data:
              type: object
              description: "key = day|week|month|year，每個 period 包含 inbound / outbound 統計"
    """
    alerts = _stock_alerts()
    alert_count = {'low': 0, 'high': 0}
    for a in alerts:
        alert_count[a['alert']] += 1

    result = {
        'stock_alerts': alerts,
        'stock_alert_count': alert_count,
    }
    for period in ('day', 'week', 'month', 'year'):
        start = _period_start(period)

        ib_stats = _completed_stats('inbound_orders',  start)
        ob_stats = _completed_stats('outbound_orders', start)

        gross_profit = round(ob_stats['amount'] - ib_stats['amount'], 2)

        result[period] = {
            'inbound': {
                'orders':    _count('inbound_orders', start),
                'completed': _completed_count('inbound_orders', start),
                'qty':       ib_stats['qty'],
                'amount':    ib_stats['amount'],
            },
            'outbound': {
                'orders':    _count('outbound_orders', start),
                'completed': _completed_count('outbound_orders', start),
                'qty':       ob_stats['qty'],
                'amount':    ob_stats['amount'],
            },
            'gross_profit': gross_profit,
        }
    return jsonify({'success': True, 'data': result})
