from flask import Flask, redirect
from flasgger import Swagger
from flask_jwt_extended import JWTManager
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
from src import FLASK_JSON_PATH
import json

app = Flask(__name__)
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


def create_app(confgi_object=None):
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
    app.register_blueprint(blueprint=app_docs,           url_prefix='/docs')
    if confgi_object:
        app.config.from_object(confgi_object)
    return app
