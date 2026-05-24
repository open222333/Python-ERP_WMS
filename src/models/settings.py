"""
系統設定 Model
Collection: system_settings
文件結構: { _id, key, value, updated_at }
"""
from datetime import datetime
from src.mongo import get_db


class SystemSettings:
    COLLECTION = 'system_settings'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def get_all(cls) -> dict:
        """回傳所有設定的 {key: value} 字典"""
        docs = cls._col().find({}, {'_id': 0, 'key': 1, 'value': 1})
        return {d['key']: d['value'] for d in docs}

    @classmethod
    def get(cls, key: str, default=None):
        """取得單一設定值，不存在時回傳 default"""
        doc = cls._col().find_one({'key': key}, {'_id': 0, 'value': 1})
        return doc['value'] if doc else default

    @classmethod
    def set(cls, key: str, value) -> None:
        """設定（upsert）單一鍵值"""
        cls._col().update_one(
            {'key': key},
            {'$set': {'value': value, 'updated_at': datetime.utcnow()}},
            upsert=True,
        )

    @classmethod
    def set_many(cls, data: dict) -> None:
        """批次設定，data 為 {key: value}"""
        now = datetime.utcnow()
        for key, value in data.items():
            cls._col().update_one(
                {'key': key},
                {'$set': {'value': value, 'updated_at': now}},
                upsert=True,
            )
