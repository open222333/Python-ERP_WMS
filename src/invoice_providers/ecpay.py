"""
ECPay 電子發票 API 串接
API 文件：https://www.ecpay.com.tw/Service/API_Doorway
"""
import base64
import json
import time
import urllib.parse

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class ECPayInvoice:
    STAGE_URL = 'https://einvoice-stage.ecpay.com.tw'
    PROD_URL  = 'https://einvoice.ecpay.com.tw'

    def __init__(self, merchant_id: str, hash_key: str, hash_iv: str,
                 seller_id: str = '', test_mode: bool = True):
        self.merchant_id = merchant_id
        self.hash_key    = hash_key
        self.hash_iv     = hash_iv
        self.seller_id   = seller_id
        self.base_url    = self.STAGE_URL if test_mode else self.PROD_URL

    # ── AES-128-CBC encrypt/decrypt ──────────────────────────────────
    def _key_iv(self):
        return (
            self.hash_key[:16].encode('utf-8'),
            self.hash_iv[:16].encode('utf-8'),
        )

    def _encrypt(self, data: dict) -> str:
        json_str    = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        url_encoded = urllib.parse.quote(json_str)
        key, iv     = self._key_iv()
        padder      = padding.PKCS7(128).padder()
        padded      = padder.update(url_encoded.encode('utf-8')) + padder.finalize()
        cipher      = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        enc         = cipher.encryptor()
        ct          = enc.update(padded) + enc.finalize()
        return urllib.parse.quote(base64.b64encode(ct).decode('utf-8'))

    def _decrypt(self, encrypted: str) -> dict:
        decoded   = urllib.parse.unquote(encrypted)
        ct        = base64.b64decode(decoded)
        key, iv   = self._key_iv()
        cipher    = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        dec       = cipher.decryptor()
        padded    = dec.update(ct) + dec.finalize()
        unpadder  = padding.PKCS7(128).unpadder()
        plain     = (unpadder.update(padded) + unpadder.finalize()).decode('utf-8')
        return json.loads(urllib.parse.unquote(plain))

    def _post(self, path: str, data: dict) -> dict:
        rq_header = json.dumps({
            'Timestamp': str(int(time.time())),
            'Revision':  '0.035',
        })
        payload = {
            'MerchantID': self.merchant_id,
            'RqHeader':   urllib.parse.quote(rq_header),
            'Data':       self._encrypt(data),
        }
        resp = requests.post(
            f'{self.base_url}{path}',
            data=payload,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        trans_code = result.get('TransCode', 0)
        if trans_code != 1:
            raise Exception(f"ECPay error {trans_code}: {result.get('TransMsg', '未知錯誤')}")
        return self._decrypt(result['Data'])

    # ── 開立發票 ─────────────────────────────────────────────────────
    def issue(self, relate_no: str, items: list, total: int,
              carrier_type: str = '', carrier_num: str = '',
              buyer_id: str = '', love_code: str = '',
              customer_name: str = '', customer_email: str = '',
              remark: str = '') -> dict:
        """
        carrier_type: '' 無, '1' 手機條碼, '2' 自然人憑證
        buyer_id:     統一編號（B2B）
        love_code:    愛心碼（捐贈）
        回傳 dict: RtnCode, InvoiceNo, InvoiceDate, RandomNumber
        """
        is_donation = '1' if love_code else '0'
        is_print    = '1' if buyer_id else '0'

        data = {
            'MerchantID':         self.merchant_id,
            'RelateNumber':       relate_no,
            'CustomerID':         '',
            'CustomerIdentifier': buyer_id,
            'CustomerName':       customer_name,
            'CustomerAddr':       '',
            'CustomerPhone':      '',
            'CustomerEmail':      customer_email,
            'ClearanceMark':      '',
            'Print':              is_print,
            'Donation':           is_donation,
            'LoveCode':           love_code,
            'CarrierType':        '' if love_code else carrier_type,
            'CarrierNum':         '' if love_code else carrier_num,
            'TaxType':            '1',
            'SalesAmount':        int(total),
            'InvoiceRemark':      remark,
            'Items':              items,
            'InvType':            '07',
            'vat':                '1',
        }
        return self._post('/B2CInvoice/Issue', data)

    # ── 作廢發票 ─────────────────────────────────────────────────────
    def void(self, invoice_no: str, invoice_date: str, reason: str) -> dict:
        data = {
            'MerchantID':  self.merchant_id,
            'InvoiceNo':   invoice_no,
            'InvoiceDate': invoice_date,
            'Reason':      reason,
        }
        return self._post('/B2CInvoice/Invalid', data)


def build_ecpay_items(pos_items: list) -> list:
    """將 POS 品項轉換為 ECPay Items 格式"""
    result = []
    for idx, item in enumerate(pos_items, start=1):
        qty   = int(item.get('quantity', 1))
        price = int(item.get('unit_price', 0))
        result.append({
            'ItemSeq':     idx,
            'ItemName':    item.get('product_name', '商品'),
            'ItemCount':   qty,
            'ItemWord':    item.get('unit', '份'),
            'ItemPrice':   price,
            'ItemTaxType': '1',
            'ItemAmount':  qty * price,
            'ItemRemark':  '',
        })
    return result
