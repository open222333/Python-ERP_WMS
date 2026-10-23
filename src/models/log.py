import re
from datetime import datetime, timedelta
from src.mongo import get_db


class Log:
    COLLECTION = 'logs'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def create(cls, username: str, action: str, detail: str = '', success: bool = True,
               session=None) -> str:
        # session: [OPT-N1] 可選 pymongo ClientSession（交易內呼叫時傳入，讓操作紀錄
        # 與其協調的業務寫入同進退——例如出入庫完成失敗時，Log 也一併回滾）
        result = cls._col().insert_one({
            'username':   username,
            'action':     action,
            'detail':     detail,
            'success':    success,
            'created_at': datetime.utcnow(),
        }, session=session)
        return str(result.inserted_id)

    _PROJECTION = {'_id': 1, 'username': 1, 'action': 1,
                   'detail': 1, 'success': 1, 'created_at': 1}

    @staticmethod
    def _fmt_row(log: dict) -> dict:
        log['_id'] = str(log['_id'])
        if 'created_at' in log and isinstance(log['created_at'], datetime):
            log['created_at'] = log['created_at'].isoformat()
        return log

    @classmethod
    def find_all(cls, limit: int = 200,
                 username: str = None,
                 action: str = None,
                 start_date: str = None,
                 end_date: str = None,
                 usernames: list = None) -> list:
        """
        查詢紀錄（列表頁用），limit 限制在 1~10000。
        匯出全部請用 iter_all()，逐筆讀取不整批載入記憶體。
        start_date / end_date 格式：'YYYY-MM-DD'
        """
        q = cls._build_query(username, action, start_date, end_date, usernames)
        limit = max(1, min(int(limit), 10000))
        cursor = cls._col().find(q, cls._PROJECTION).sort('created_at', -1).limit(limit)
        return [cls._fmt_row(log) for log in cursor]

    @classmethod
    def iter_all(cls, username: str = None, action: str = None,
                 start_date: str = None, end_date: str = None,
                 batch_size: int = 500, usernames: list = None):
        """
        [OPT-MEM] 匯出用：逐筆 yield，無筆數上限。
        cursor 每批只從 MongoDB 取 batch_size 筆，記憶體用量與總筆數無關。
        """
        # 查詢條件在呼叫當下建立（非 generator 內），日期格式錯誤會立即拋 ValueError，
        # 讓 view 在開始串流前就能回 400，而不是串流到一半才失敗。
        q = cls._build_query(username, action, start_date, end_date, usernames)
        cursor = cls._col().find(q, cls._PROJECTION).sort('created_at', -1) \
                           .batch_size(batch_size)
        return (cls._fmt_row(log) for log in cursor)

    @staticmethod
    def _build_query(username: str = None, action: str = None,
                     start_date: str = None, end_date: str = None,
                     usernames: list = None) -> dict:
        """
        username / action：關鍵字部分比對（不分大小寫）。[A6] 輸入先 re.escape，
        只當一般文字比對，避免使用者送出極耗資源的正規表達式。
        usernames：[A2] 店家帳號只看本店使用者的紀錄（None = 不限）。
        """
        q: dict = {}
        if username:
            q['username'] = {'$regex': re.escape(username), '$options': 'i'}
        if usernames is not None:
            q.setdefault('username', {})['$in'] = list(usernames)
        if action:
            q['action'] = {'$regex': re.escape(action), '$options': 'i'}
        if start_date or end_date:
            dt_q: dict = {}
            if start_date:
                try:
                    dt_q['$gte'] = datetime.fromisoformat(start_date)
                except ValueError:
                    raise ValueError(f'start_date 格式無效: {start_date!r}')
            if end_date:
                try:
                    # end_date 當天含入：加一天
                    dt_q['$lt'] = datetime.fromisoformat(end_date) + timedelta(days=1)
                except ValueError:
                    raise ValueError(f'end_date 格式無效: {end_date!r}')
            if dt_q:
                q['created_at'] = dt_q
        return q

    @classmethod
    def count_all(cls, usernames: list = None) -> int:
        """傳回 logs collection 的總筆數；usernames 有值時只算這些使用者（[A2]）。"""
        if usernames is not None:
            return cls._col().count_documents({'username': {'$in': list(usernames)}})
        return cls._col().estimated_document_count()

    @classmethod
    def count_older_than(cls, days: int, usernames: list = None) -> int:
        """傳回超過 days 天的紀錄數（預覽用）。"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        q = {'created_at': {'$lt': cutoff}}
        if usernames is not None:
            q['username'] = {'$in': list(usernames)}
        return cls._col().count_documents(q)

    @classmethod
    def cleanup_old(cls, days: int) -> int:
        """刪除超過 days 天的紀錄，傳回刪除筆數。"""
        if days <= 0:
            return 0
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = cls._col().delete_many({'created_at': {'$lt': cutoff}})
        return result.deleted_count

    @classmethod
    def bulk_insert(cls, rows: list) -> int:
        """
        批次匯入紀錄。rows 格式：
        [{'username', 'action', 'detail'(opt), 'success'(opt), 'created_at'(opt iso str)}]
        傳回成功插入筆數。
        """
        docs = []
        for r in rows:
            username = str(r.get('username') or '').strip()
            action   = str(r.get('action')   or '').strip()
            if not username or not action:
                continue
            success_raw = r.get('success', True)
            if isinstance(success_raw, str):
                success = success_raw.strip() not in ('false', '0', '失敗', 'False')
            else:
                success = bool(success_raw)
            try:
                created_at = datetime.fromisoformat(str(r.get('created_at', '')))
            except (ValueError, TypeError):
                created_at = datetime.utcnow()
            docs.append({
                'username':   username,
                'action':     action,
                'detail':     str(r.get('detail') or ''),
                'success':    success,
                'created_at': created_at,
            })
        if docs:
            cls._col().insert_many(docs)
        return len(docs)
