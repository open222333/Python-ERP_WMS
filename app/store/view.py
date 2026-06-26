from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from src.models.store import Store
from src.models.store_role import StoreRole
from src.models.menu import Menu
from src.models.warehouse import Warehouse
from src.models.user import User
from src.permissions import require_role

app_store = Blueprint('store', __name__)


# ── 店家角色模板 ─────────────────────────────────────────

@app_store.route('/role/', methods=['GET'])
@jwt_required()
@require_role('admin')
def list_store_roles():
    return jsonify({'success': True, 'data': StoreRole.find_all()})


@app_store.route('/role/', methods=['POST'])
@jwt_required()
@require_role('admin')
def create_store_role():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': '角色名稱不得為空'}), 400
    rid = StoreRole.create(name=name, description=data.get('description', ''))
    return jsonify({'success': True, 'id': rid}), 201


@app_store.route('/role/<rid>', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_store_role(rid):
    role = StoreRole.find_by_id(rid)
    if not role:
        return jsonify({'success': False, 'message': '角色不存在'}), 404
    if role.get('is_system'):
        return jsonify({'success': False, 'message': '系統預設角色不可修改名稱'}), 403
    data = request.get_json(silent=True) or {}
    StoreRole.update(rid, name=data.get('name'), description=data.get('description'))
    return jsonify({'success': True})


@app_store.route('/role/<rid>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_store_role(rid):
    role = StoreRole.find_by_id(rid)
    if not role:
        return jsonify({'success': False, 'message': '角色不存在'}), 404
    if role.get('is_system'):
        return jsonify({'success': False, 'message': '系統預設角色不可刪除'}), 403
    StoreRole.delete(rid)
    return jsonify({'success': True})


# ── 店家 CRUD ─────────────────────────────────────────────

@app_store.route('/', methods=['GET'])
@jwt_required()
@require_role('admin')
def list_stores():
    return jsonify({'success': True, 'data': Store.find_all()})


@app_store.route('/', methods=['POST'])
@jwt_required()
@require_role('admin')
def create_store():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': '店家名稱不得為空'}), 400

    store_role_id = (data.get('store_role_id') or '').strip() or None
    store_id = Store.create(name=name, code=data.get('code', '').strip(),
                            store_role_id=store_role_id)
    store = Store.find_by_id(store_id)
    Menu.create(name=name, store_id=store_id)
    Warehouse.create({'code': store['code'], 'name': name,
                      'address': '', 'manager': '', 'phone': '', 'description': ''},
                     store_id=store_id)
    return jsonify({'success': True, 'id': store_id}), 201


@app_store.route('/<store_id>', methods=['GET'])
@jwt_required()
@require_role('admin')
def get_store(store_id):
    store = Store.find_by_id(store_id)
    if not store:
        return jsonify({'success': False, 'message': '店家不存在'}), 404
    return jsonify({'success': True, 'data': store})


@app_store.route('/<store_id>', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_store(store_id):
    data = request.get_json(silent=True) or {}
    new_code = (data.get('code') or '').strip()
    if new_code:
        existing = Store.find_by_code(new_code)
        if existing and existing['_id'] != store_id:
            return jsonify({'success': False, 'message': f'店家代碼「{new_code}」已被其他店家使用'}), 409
    store_role_id = data.get('store_role_id')  # None = don't change, '' = clear
    if not Store.update(store_id,
                        name=data.get('name'),
                        code=new_code or None,
                        status=data.get('status'),
                        store_role_id=store_role_id):
        return jsonify({'success': False, 'message': '店家不存在'}), 404
    return jsonify({'success': True})


@app_store.route('/<store_id>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_store(store_id):
    if not Store.delete(store_id):
        return jsonify({'success': False, 'message': '店家不存在'}), 404
    return jsonify({'success': True})


# ── 店家帳號管理（由主帳號操作）────────────────────────

@app_store.route('/<store_id>/users', methods=['GET'])
@jwt_required()
@require_role('admin')
def list_store_users(store_id):
    users = User.find_by_store(store_id)
    return jsonify({'success': True, 'data': users})


@app_store.route('/<store_id>/users', methods=['POST'])
@jwt_required()
@require_role('admin')
def create_store_user(store_id):
    if not Store.find_by_id(store_id):
        return jsonify({'success': False, 'message': '店家不存在'}), 404

    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password', '')
    role     = data.get('role', 'admin')

    if not username or not password:
        return jsonify({'success': False, 'message': 'username 或 password 不得為空'}), 400

    if User.find_by_username(username):
        return jsonify({'success': False, 'message': '使用者已存在'}), 409

    user_id = User.create(username, password, role=role, store_ids=[store_id])
    return jsonify({'success': True, 'id': user_id}), 201
