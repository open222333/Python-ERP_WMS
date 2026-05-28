from datetime import datetime, timedelta
from src.mongo import get_db


class Log:
    COLLECTION = 'logs'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def create(cls, username: str, action: str, detail: str = '', success: bool = True) -> str:
        result = cls._col().insert_one({
            'username':   username,
            'action':     action,
            'detail':     detail,
            'success':    success,
            'created_at': datetime.utcnow(),
        })
        return str(result.inserted_id)

    @classmethod
    def find_all(cls, limit: int = 200,
                 username: str = None,
                 action: str = None,
                 start_date: str = None,
                 end_date: str = None) -> list:
        """
        查詢紀錄。
        limit=0 → 無上限（僅供匯出使用）。
        start_date / end_date 格式：'YYYY-MM-DD'
        """
        q: dict = {}
        if username:
            q['username'] = {'$regex': username, '$options': 'i'}
        if action:
            q['action'] = {'$regex': action, '$options': 'i'}
        if start_date or end_date:
            dt_q: dict = {}
            if start_date:
                try:
                    dt_q['$gte'] = datetime.fromisoformat(start_date)
                except ValueError:
                    pass
            if end_date:
                try:
                    # end_date 當天含入：加一天
                    dt_q['$lt'] = datetime.fromisoformat(end_date) + timedelta(days=1)
                except ValueError:
                    pass
            if dt_q:
                q['created_at'] = dt_q

        cursor = cls._col().find(q, {'_id': 1, 'username': 1, 'action': 1,
                                     'detail': 1, 'success': 1, 'created_at': 1}) \
                            .sort('created_at', -1)
        if limit and limit > 0:
            cursor = cursor.limit(limit)

        result = []
        for log in cursor:
            log['_id'] = str(log['_id'])
            if 'created_at' in log and isinstance(log['created_at'], datetime):
                log['created_at'] = log['created_at'].isoformat()
            result.append(log)
        return result

    @classmethod
    def count_all(cls) -> int:
        """傳回 logs collection 的總筆數。"""
        return cls._col().estimated_document_count()

    @classmethod
    def count_older_than(cls, days: int) -> int:
        """傳回超過 days 天的紀錄數（預覽用）。"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return cls._col().count_documents({'created_at': {'$lt': cutoff}})

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
