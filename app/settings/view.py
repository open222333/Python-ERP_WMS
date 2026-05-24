"""
系統設定 Blueprint  /settings
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.settings import SystemSettings
from src.models.log import Log
from src.permissions import require_role

app_settings = Blueprint('app_settings', __name__)


@app_settings.route('/', methods=['GET'])
@jwt_required()
def get_settings():
    """
    取得所有系統設定
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    responses:
      200:
        description: 成功，回傳 {key: value} 字典
    """
    data = SystemSettings.get_all()
    return jsonify({'success': True, 'data': data})


@app_settings.route('/', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_settings():
    """
    批次更新系統設定（僅限 admin）
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          description: "任意 {key: value} 鍵值對"
          example:
            default_warehouse_id: "64abc123..."
    responses:
      200:
        description: 儲存成功
      400:
        description: 無內容
    """
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({'success': False, 'message': '無設定內容'}), 400

    SystemSettings.set_many(data)
    Log.create(get_jwt_identity(), '更新系統設定',
               ', '.join(f'{k}={v}' for k, v in data.items()))
    return jsonify({'success': True})
