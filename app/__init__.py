from flask import Flask, redirect, jsonify
from flasgger import Swagger
from flask_jwt_extended import JWTManager
from app.extensions import limiter
from app.auth.view import app_auth
from app.user.view import app_user
from app.log.view import app_log
from app.product.view import app_product
from app.warehouse.view import app_warehouse
from app.inventory.view import app_inventory
from app.inbound.view import app_inbound
from app.outbound.view import app_outbound
from app.analytics.view import app_analytics
from app.pos.view import app_pos
from app.delivery.view import app_delivery
from app.menu.view import app_menu
from app.quick_io.view import app_quick_io
from app.settings.view import app_settings
from app.docs.view import app_docs
from app.customer_order.view import app_customer_order
from app.invoice.view import app_invoice
from src import FLASK_JSON_PATH, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB
import json

app = Flask(__name__)

# ── 登入速率限制（Redis backend，跨 worker 共享計數）────
_redis_uri = (
    f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    if REDIS_PASSWORD
    else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
)
app.config['RATELIMIT_STORAGE_URI'] = _redis_uri
limiter.init_app(app)

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'success': False, 'message': '嘗試次數過多，請稍後再試'}), 429

template = {
    "swagger": "2.0",
    "info": {
        "title": "WMS 倉儲管理系統 API",
        "description": "WMS API 文檔",
        "contact": {
            "email": "tom_li@appdet.com",
        },
        "version": "1.0.0"
    },
    "host": "127.0.0.1:5000",
    "basePath": "/",
    "schemes": ["http"],
    "operationId": "getmyData",
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT token，格式: Bearer <token>"
        }
    }
}

swagger = Swagger(app, template=template)
jwt = JWTManager(app)


@app.route("/")
def status():
    return redirect('/apidocs/')


def _ensure_indexes():
    """在應用啟動時建立 MongoDB 複合索引。
    - unique 索引建立前先去重，避免舊資料導致啟動失敗。
    - 其餘索引用 try/except 隔離，單一失敗不影響其他索引或啟動。
    """
    import logging
    from pymongo import ASCENDING, DESCENDING
    from src.mongo import get_db
    _log = logging.getLogger(__name__)
    db = get_db()

    # ── inventory 唯一索引：先去重再建立 ──────────────────
    inv_col = db['inventory']
    pipeline = [
        {'$group': {
            '_id': {'product_id': '$product_id', 'warehouse_id': '$warehouse_id',
                    'location_id': '$location_id'},
            'ids': {'$push': '$_id'}, 'count': {'$sum': 1},
        }},
        {'$match': {'count': {'$gt': 1}}},
    ]
    try:
        for dup in inv_col.aggregate(pipeline):
            for oid in dup['ids'][1:]:
                inv_col.delete_one({'_id': oid})
                _log.warning('_ensure_indexes: 刪除重複 inventory _id=%s', oid)
    except Exception as e:
        _log.error('inventory 去重失敗，跳過（唯一索引建立可能失敗）：%s', e)
    try:
        inv_col.create_index(
            [('product_id', ASCENDING), ('warehouse_id', ASCENDING), ('location_id', ASCENDING)],
            unique=True, name='inv_product_warehouse_location',
        )
    except Exception as e:
        _log.error('inventory 唯一索引建立失敗：%s', e)

    # ── 其他索引（冪等，失敗不中斷啟動）─────────────────
    _indexes = [
        ('stock_movements', [('warehouse_id', ASCENDING), ('product_id', ASCENDING), ('created_at', DESCENDING)],
         {'name': 'mv_warehouse_product_time'}),
        ('stock_movements', [('reference_type', ASCENDING), ('created_at', DESCENDING)],
         {'name': 'mv_reftype_time'}),
        ('pos_orders',      [('created_at', DESCENDING)],
         {'name': 'pos_created_at'}),
        ('pos_orders',      [('delivery_order_id', ASCENDING), ('source', ASCENDING)],
         {'name': 'pos_delivery_order', 'unique': True, 'sparse': True}),
        ('customer_orders', [('order_date', ASCENDING), ('created_at', DESCENDING)],
         {'name': 'cust_order_date_time'}),
        ('inbound_orders',  [('created_at', DESCENDING)],
         {'name': 'inbound_created_at'}),
        ('outbound_orders', [('created_at', DESCENDING)],
         {'name': 'outbound_created_at'}),
    ]
    for col_name, keys, kwargs in _indexes:
        try:
            db[col_name].create_index(keys, **kwargs)
        except Exception as e:
            _log.error('索引建立失敗 %s %s：%s', col_name, kwargs.get('name'), e)


def create_app(config_object=None):
    from src.models.user import User
    User.ensure_guest_user()
    _ensure_indexes()

    # ── API Blueprints（原始路徑，與 nginx proxy 規則一致）──────
    app.register_blueprint(blueprint=app_auth,           url_prefix='/auth')
    app.register_blueprint(blueprint=app_user,           url_prefix='/user')
    app.register_blueprint(blueprint=app_log,            url_prefix='/log')
    app.register_blueprint(blueprint=app_product,        url_prefix='/product')
    app.register_blueprint(blueprint=app_warehouse,      url_prefix='/warehouse')
    app.register_blueprint(blueprint=app_inventory,      url_prefix='/inventory')
    app.register_blueprint(blueprint=app_inbound,        url_prefix='/inbound')
    app.register_blueprint(blueprint=app_outbound,       url_prefix='/outbound')
    app.register_blueprint(blueprint=app_analytics,      url_prefix='/analytics')
    app.register_blueprint(blueprint=app_pos,            url_prefix='/pos')
    app.register_blueprint(blueprint=app_delivery,       url_prefix='/delivery')
    app.register_blueprint(blueprint=app_menu,           url_prefix='/menu')
    app.register_blueprint(blueprint=app_quick_io,       url_prefix='/quick-io')
    app.register_blueprint(blueprint=app_settings,       url_prefix='/settings')
    app.register_blueprint(blueprint=app_customer_order, url_prefix='/customer-order')
    app.register_blueprint(blueprint=app_invoice,        url_prefix='/invoice')
    app.register_blueprint(blueprint=app_docs,           url_prefix='/docs')
    if config_object:
        app.config.from_object(config_object)
    return app
