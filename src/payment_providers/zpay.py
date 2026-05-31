"""
全支付（ZingPay）電子支付 CPM 收款 / 退款 Adapter

CPM 流程：
  1. 顧客開啟全支付 App → 付款 → 出示條碼（一次性 QR/Barcode）
  2. 商家收銀系統掃描條碼 → 呼叫 charge()
  3. 扣款成功 → 記錄訂單；失敗 → 拒絕交易
  4. 退款呼叫 refund()

官方文件：https://developer.zing.com.tw/
  - 沙盒 API：https://sandbox-api.zing.com.tw
  - 正式 API：https://api.zing.com.tw
"""
import hashlib
import hmac
import json
import time
import uuid
import base64

import requests


class ZPayCPM:
    SANDBOX_URL = 'https://sandbox-api.zing.com.tw'
    PROD_URL    = 'https://api.zing.com.tw'

    def __init__(self, merchant_id: str, merchant_secret: str, sandbox: bool = True):
        if not merchant_id or not merchant_secret:
            raise ValueError('全支付尚未設定 Merchant ID / Secret，請至系統設定完成設定')
        self.merchant_id     = merchant_id
        self.merchant_secret = merchant_secret
        self.base_url        = self.SANDBOX_URL if sandbox else self.PROD_URL

    # ── 簽章 ────────────────────────────────────────────────────────────
    def _sign(self, uri: str, body: str, nonce: str) -> str:
        """HMAC-SHA256：merchantSecret + uri + body + nonce"""
        msg = self.merchant_secret + uri + body + nonce
        raw = hmac.new(
            self.merchant_secret.encode('utf-8'),
            msg.encode('utf-8'),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(raw).decode('utf-8')

    def _headers(self, uri: str, body: str) -> dict:
        nonce = str(uuid.uuid4())
        return {
            'Content-Type':          'application/json',
            'X-Zing-MerchantId':     self.merchant_id,
            'X-Zing-Nonce':          nonce,
            'X-Zing-Authorization':  self._sign(uri, body, nonce),
        }

    def _post(self, path: str, payload: dict) -> dict:
        url  = self.base_url + path
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        resp = requests.post(url, data=body, headers=self._headers(path, body), timeout=20)
        resp.raise_for_status()
        return resp.json()

    # ── 收款 ────────────────────────────────────────────────────────────
    def charge(self, qr_code: str, order_id: str, amount: int,
               product_name: str = '購物付款') -> dict:
        """
        CPM 掃碼扣款
        :param qr_code:      顧客全支付 App 出示的一次性條碼
        :param order_id:     商家訂單號（唯一）
        :param amount:       金額（整數，台幣）
        :param product_name: 商品說明
        :return: API 回應 dict；returnCode == '0000' 為成功
        """
        payload = {
            'merchantOrderId': order_id,
            'amount':          amount,
            'currency':        'TWD',
            'paymentCode':     qr_code,
            'productName':     product_name,
            'orderedTime':     int(time.time()),
        }
        return self._post('/v1/payments/cpm/charge', payload)

    # ── 退款 ────────────────────────────────────────────────────────────
    def refund(self, transaction_id: str, amount: int) -> dict:
        """
        退款
        :param transaction_id: 全支付交易 ID（charge 成功後 transactionId）
        :param amount:         退款金額
        :return: API 回應 dict；returnCode == '0000' 為成功
        """
        payload = {
            'refundAmount': amount,
            'reason':       '商家退款',
        }
        return self._post(f'/v1/payments/{transaction_id}/refund', payload)
