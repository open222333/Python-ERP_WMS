# [REFACTOR] pydantic 驗證層共用基礎
#
# 使用模式（與既有手寫檢查並存）：
#   既有手寫檢查先跑（保留原錯誤訊息，前端有 string-match 依賴），
#   pydantic 作為型別/結構的最後防線，攔下手寫檢查漏掉的畸形輸入
#   （如 price 傳非數字造成 float() 拋 ValueError → 500）。
#
#   payload, err = validate_payload(SomeSchema, data)
#   if err:
#       return err          # (jsonify(...), 400)
#   # 之後使用 payload（pydantic model）或原 data dict
from typing import Annotated, Optional

from bson import ObjectId
from bson.errors import InvalidId
from flask import jsonify
from pydantic import BaseModel, BeforeValidator, ConfigDict, ValidationError


def _check_object_id(v):
    """驗證字串為合法 MongoDB ObjectId（保留原字串型別回傳）"""
    if not isinstance(v, str):
        raise ValueError('必須為字串')
    try:
        ObjectId(v)
    except (InvalidId, TypeError):
        raise ValueError('ObjectId 格式無效')
    return v


# 合法 ObjectId 字串型別，schema 中直接標註使用
ObjectIdStr = Annotated[str, BeforeValidator(_check_object_id)]


def _check_object_id_lenient(v):
    """寬鬆版：None / 空字串放行（讓既有手寫「必填」檢查保留原訊息），非空才驗格式"""
    if v is None or v == '':
        return v
    return _check_object_id(v)


# 寬鬆 ObjectId：空值交給端點既有的必填檢查，非空值驗格式
LooseObjectIdStr = Annotated[Optional[str], BeforeValidator(_check_object_id_lenient)]


def apply_coerced(data: dict, model, fields):
    """把 schema 轉型後的欄位值寫回原 dict（僅限有出現在 payload 的欄位），
    供後續以原 dict 運算的既有程式使用（避免字串數字比較造成 TypeError）"""
    dumped = model.model_dump(exclude_unset=True)
    for f in fields:
        if f in dumped and dumped[f] is not None:
            data[f] = dumped[f]


class BaseSchema(BaseModel):
    """共用設定：允許多餘欄位（相容既有前端 payload），不做隱式型別破壞"""
    model_config = ConfigDict(extra='allow')


def format_errors(exc: ValidationError) -> list:
    """把 pydantic 錯誤轉成精簡的 [{'field', 'message'}] 列表"""
    out = []
    for e in exc.errors():
        loc = '.'.join(str(x) for x in e.get('loc', ()))
        out.append({'field': loc, 'message': e.get('msg', '')})
    return out


def validate_payload(schema_cls, data: dict, message: str = '輸入資料格式錯誤'):
    """
    以 schema 驗證 data。
    回傳 (model, None) 或 (None, (jsonify_response, 400))。
    message 可帶入與該端點既有錯誤風格一致的訊息。
    """
    try:
        model = schema_cls.model_validate(data or {})
        return model, None
    except ValidationError as exc:
        return None, (jsonify({'success': False,
                               'message': message,
                               'errors': format_errors(exc)}), 400)
