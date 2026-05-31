"""
LINE Pay CPM（Consumer Presented Mode）API 串接
顧客出示條碼 → 商家掃描 → 發起付款

API 文件：https://developers.line.biz/en/docs/line-pay/
CPM 端點：POST /v3/payments/oneTimeKeys/pay/preapproved
"""
import base64
import hashlib
import hmac as _hmac
import json
import uuid

import requests


class LinePayCPM:
    SANDBOX_URL = 'https://sandbox-api-pay.line.me'
    PROD_URL    = 'https://api-pay.line.me'

    def __init__(self, channel_id: str, channel_secret: str, sandbox: bool = True):
        self.channel_id     = str(channel_id).strip()
        self.channel_secret = str(channel_secret).strip()
        self.base_url       = self.SANDBOX_URL if sandbox else self.PROD_URL

    # ── HMAC-SHA256 簽章 ────────────────────────────────────
    def _sign(self, uri: str, body: str, nonce: str) -> str:
        """
        LINE Pay v3 簽章格式：
          HMAC-SHA256(key=channelSecret, data=channelSecret + uri + body + nonce)
          → Base64
        """
        msg = self.channel_secret + uri + body + nonce
        sig = _hmac.new(
            self.channel_secret.encode('utf-8'),
            msg.encode('utf-8'),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(sig).decode('utf-8')

    def _headers(self, uri: str, body: str) -> dict:
        nonce = str(uuid.uuid4())
        return {
            'Content-Type':               'application/json',
            'X-LINE-ChannelId':           self.channel_id,
            'X-LINE-Authorization-Nonce': nonce,
            'X-LINE-Authorization':       self._sign(uri, body, nonce),
        }

    def _post(self, path: str, payload: dict) -> dict:
        body    = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        headers = self._headers(path, body)
        resp    = requests.post(
            self.base_url + path,
            data=body.encode('utf-8'),
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ── 付款（掃顧客條碼）────────────────────────────────────
    def charge(self, one_time_key: str, order_id: str, amount: int,
               product_name: str = '購物付款') -> dict:
        """
        one_time_key: 從顧客 LINE Pay app 條碼讀取的一次性金鑰
        order_id:     商家唯一訂單號（建議與 POS order_no 對應）
        amount:       整數，新台幣元
        回傳 LINE Pay 原始 response dict
          成功: returnCode == '0000'
          info.transactionId: LINE Pay 交易 ID
        """
        return self._post('/v3/payments/oneTimeKeys/pay/preapproved', {
            'productName': product_name,
            'amount':      int(amount),
            'currency':    'TWD',
            'orderId':     order_id,
            'oneTimeKey':  one_time_key,
        })

    # ── 退款 ─────────────────────────────────────────────────
    def refund(self, transaction_id: str, amount: int) -> dict:
        """
        transaction_id: 原付款的 LINE Pay transactionId
        amount:         退款金額（整數新台幣）
        """
        path = f'/v3/payments/{transaction_id}/refund'
        return self._post(path, {'refundAmount': int(amount)})
