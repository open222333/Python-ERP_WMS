from datetime import datetime
from src.mongo import get_db


class Log:
    COLLECTION = 'logs'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def create(cls, username: str, action: str, detail: str = '', success: bool = True) -> str:
        result = cls._col().insert_one({
            'username': username,
            'action': action,
            'detail': detail,
            'success': success,
            'created_at': datetime.utcnow()
        })
        return str(result.inserted_id)

    @classmethod
    def find_all(cls, limit: int = 200, username: str = None, action: str = None) -> list:
        q = {}
        if username:
            q['username'] = {'$regex': username, '$options': 'i'}
        if action:
            q['action'] = {'$regex': action, '$options': 'i'}
        logs = cls._col().find(q, {'_id': 0}).sort('created_at', -1).limit(limit)
        result = []
        for log in logs:
            if 'created_at' in log and isinstance(log['created_at'], datetime):
                log['created_at'] = log['created_at'].isoformat()
            result.append(log)
        return result
