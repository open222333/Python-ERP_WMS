"""Auth API：登入成功/失敗/鎖定、JWT 保護、角色權限。"""


class TestLogin:
    def test_login_success(self, client, make_user):
        u = make_user(role='operator')
        r = client.post('/auth/login', json={'username': u['username'],
                                             'password': u['password']})
        assert r.status_code == 200
        body = r.get_json()
        assert body['success'] is True
        assert body['token']
        assert body['role'] == 'operator'
        assert 'refresh_token' not in body   # 未帶 remember_me

    def test_login_remember_me_returns_refresh_token(self, client, make_user):
        u = make_user()
        r = client.post('/auth/login', json={'username': u['username'],
                                             'password': u['password'],
                                             'remember_me': True})
        assert r.status_code == 200
        assert r.get_json()['refresh_token']

    def test_login_wrong_password(self, client, make_user):
        u = make_user()
        r = client.post('/auth/login', json={'username': u['username'],
                                             'password': 'wrong'})
        assert r.status_code == 401

    def test_login_unknown_user(self, client):
        r = client.post('/auth/login', json={'username': 'ghost',
                                             'password': 'x'})
        assert r.status_code == 401

    def test_login_missing_fields(self, client):
        assert client.post('/auth/login', json={}).status_code == 400
        assert client.post('/auth/login',
                           json={'username': 'a'}).status_code == 400

    def test_login_locked_account_403(self, client, make_user):
        u = make_user(locked=True)
        r = client.post('/auth/login', json={'username': u['username'],
                                             'password': u['password']})
        assert r.status_code == 403

    def test_login_malformed_hash_returns_401_not_500(self, client, db):
        # FIXES.md: check_password 容錯 — DB 中 hash 壞掉時登入應回 401 而非 500
        db['users'].insert_one({'username': 'broken', 'password': 'not-a-hash',
                                'role': 'admin', 'store_ids': []})
        r = client.post('/auth/login', json={'username': 'broken',
                                             'password': 'whatever'})
        assert r.status_code == 401

    def test_login_returns_store_ids_as_strings(self, client, make_user):
        from bson import ObjectId
        sid = str(ObjectId())
        u = make_user(store_ids=[sid])
        r = client.post('/auth/login', json={'username': u['username'],
                                             'password': u['password']})
        assert r.get_json()['store_ids'] == [sid]


class TestRefresh:
    def test_refresh_issues_new_access_token(self, client, make_user):
        u = make_user()
        rt = client.post('/auth/login',
                         json={'username': u['username'],
                               'password': u['password'],
                               'remember_me': True}).get_json()['refresh_token']
        r = client.post('/auth/refresh',
                        headers={'Authorization': f'Bearer {rt}'})
        assert r.status_code == 200
        assert r.get_json()['token']

    def test_refresh_locked_user_403(self, client, make_user, db):
        u = make_user()
        rt = client.post('/auth/login',
                         json={'username': u['username'],
                               'password': u['password'],
                               'remember_me': True}).get_json()['refresh_token']
        db['users'].update_one({'username': u['username']},
                               {'$set': {'locked': True}})
        r = client.post('/auth/refresh',
                        headers={'Authorization': f'Bearer {rt}'})
        assert r.status_code == 403


class TestJwtProtection:
    def test_protected_endpoint_without_jwt_401(self, client):
        for path in ('/warehouse/', '/product/', '/inventory/movement/',
                     '/settings/'):
            assert client.get(path).status_code == 401, path

    def test_role_insufficient_403(self, client, cashier_headers):
        # cashier(1) < operator(2)：建立產品需 admin/operator
        r = client.post('/product/', headers=cashier_headers,
                        json={'sku': 'X', 'name': 'X'})
        assert r.status_code == 403

    def test_operator_cannot_delete_product_admin_only(self, client,
                                                       operator_headers):
        from bson import ObjectId
        r = client.delete(f'/product/{ObjectId()}', headers=operator_headers)
        assert r.status_code == 403

    def test_me_returns_identity(self, client, make_user):
        u = make_user(role='cashier')
        token = client.post('/auth/login',
                            json={'username': u['username'],
                                  'password': u['password']}).get_json()['token']
        r = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
        assert r.status_code == 200
        body = r.get_json()
        assert body['username'] == u['username']
        assert body['role'] == 'cashier'
