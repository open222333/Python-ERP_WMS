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


def build_ecpay_items(pos_items: list, sales_amount: int = None) -> list:
    """
    將 POS 品項轉換為 ECPay Items 格式。

    [D3] 品項金額合計必須等於發票總額（SalesAmount）。原本直接用折扣前單價，
    訂單有折扣時合計 ≠ 總額而被退件；單價也用 int() 直接捨去小數。
    現在把總額依各品項金額比例分攤（最大餘數法，合計精確等於 sales_amount），
    並維持「數量 × 單價 = 金額」皆為整數：分攤後金額無法被數量整除時，
    拆成兩行（r 份單價 p+1、其餘單價 p）。

    sales_amount：發票總額（整數元）。None = 不分攤，等於品項小計四捨五入。
    """
    rows = []
    for item in pos_items:
        qty = int(item.get('quantity', 1) or 0)
        if qty <= 0:
            continue
        price = float(item.get('unit_price', 0) or 0)
        rows.append({
            'name':  item.get('product_name') or '商品',
            'unit':  item.get('unit') or '份',
            'qty':   qty,
            'gross': max(0.0, qty * price),
        })
    gross_total = sum(r['gross'] for r in rows)
    if sales_amount is None:
        sales_amount = int(round(gross_total))
    sales_amount = int(sales_amount)
    if sales_amount <= 0:
        raise ValueError('發票金額必須大於 0')

    if not rows or gross_total <= 0:
        # 無可分攤的品項金額（例如全部 0 元）：以單一品項開立總額
        rows = [{'name': '商品', 'unit': '份', 'qty': 1, 'gross': float(sales_amount)}]
        gross_total = float(sales_amount)

    # 最大餘數法：先取整數部分，差額依小數部分由大到小各補 1
    shares = [r['gross'] * sales_amount / gross_total for r in rows]
    alloc = [int(x) for x in shares]
    remain = sales_amount - sum(alloc)
    for idx in sorted(range(len(rows)), key=lambda k: shares[k] - alloc[k], reverse=True)[:remain]:
        alloc[idx] += 1

    result = []
    def _line(row, count, price):
        result.append({
            'ItemSeq':     len(result) + 1,
            'ItemName':    row['name'],
            'ItemCount':   count,
            'ItemWord':    row['unit'],
            'ItemPrice':   price,
            'ItemTaxType': '1',
            'ItemAmount':  count * price,
            'ItemRemark':  '',
        })

    for row, amount in zip(rows, alloc):
        if amount <= 0:
            continue
        q = row['qty']
        p, r = divmod(amount, q)
        if r == 0:
            _line(row, q, p)
        else:
            _line(row, r, p + 1)          # r 份多 1 元
            if q - r > 0 and p > 0:
                _line(row, q - r, p)
            elif q - r > 0:               # p == 0：其餘份數 0 元，不另列
                pass
    return result
