#!/usr/bin/env python3


#qaytarish cheki yuborish
"""
send_refund.py

OFD serveriga qaytarish chekini yuborish:
- ReceiptSeq avtomatik oshib boradi (logs/last_seq.txt orqali).
- RefundInfo ichida qaytarilayotgan chek ma'lumotlari ko‘rsatiladi.
"""

import subprocess
import requests
import json
import os
from datetime import datetime

# ------------------------------
# 0. Konfiguratsiya
# ------------------------------
CERT_FILE = "certificates/EZ000000000931.crt"
KEY_FILE = "certificates/amaar.key"
OFD_URL = "https://test.ofd.uz/emp/v3/receipt"  # test endpoint

# Merchant (marketplace)
merchant = {
    "TIN": "190261951",
    "PINFL": "30747919403015",
    "ContractDate": "2025-09-21 07:41:09",
    "ContractNumber": "264"
}

# Qaytarilayotgan chek ma'lumotlari (sotuv chekidan olinsin!)
refund_info = {
    "TerminalID": "EZ000000000931",
    "ReceiptSeq": "121",
    "DateTime": "20250924154010",   # YYYYMMDDhhmmss
    "FiscalSign": "596201067621"
}

# ------------------------------
# 1. Qaytarilayotgan itemlar (sotuv chekidan to‘liq ko‘chirildi)
# ------------------------------
items = [
    {
        "Name": "Kompyuter sichqonchasi",
        "Barcode": "1234567890123",
        "Labels": [],
        "SPIC": "08471012005000000",
        "PackageCode": "1503256",
        "OwnerType": 0,
        "GoodPrice": 150000,
        "Price": 150000,
        "VAT": 18000,
        "VATPercent": 12,
        "Amount": 1000,
        "Discount": 0,
        "Other": 0,
        "Voucher": 0,
        "CommissionInfo": {
            "TIN": merchant["TIN"],
            "PINFL": merchant["PINFL"]
        }
    },
    {
        "Name": "Klaviatura",
        "Barcode": "2345678901234",
        "Labels": [],
        "SPIC": "08471012004000000",
        "PackageCode": "1503267",
        "OwnerType": 0,
        "GoodPrice": 250000,
        "Price": 250000,
        "VAT": 30000,
        "VATPercent": 12,
        "Amount": 2000,
        "Discount": 0,
        "Other": 0,
        "Voucher": 0,
        "CommissionInfo": {
            "TIN": merchant["TIN"],
            "PINFL": merchant["PINFL"]
        }
    },
    {
        "Name": "Purkovchi printerlar uchun siyoh",
        "Barcode": "3456789012345",
        "Labels": [],
        "SPIC": "03215001006000000",
        "PackageCode": "1344346",
        "OwnerType": 0,
        "GoodPrice": 50000,
        "Price": 50000,
        "VAT": 6000,
        "VATPercent": 12,
        "Amount": 5000,
        "Discount": 0,
        "Other": 0,
        "Voucher": 0,
        "CommissionInfo": {
            "TIN": merchant["TIN"],
            "PINFL": merchant["PINFL"]
        }
    }
]

# ------------------------------
# 2. ReceiptSeq ni avtomatik qilish
# ------------------------------
os.makedirs("logs", exist_ok=True)
seq_file = "logs/last_seq.txt"
if os.path.exists(seq_file):
    with open(seq_file, "r") as sf:
        try:
            last_seq = int(sf.read().strip())
        except ValueError:
            last_seq = 0
else:
    last_seq = 0

ReceiptSeq = last_seq + 1

with open(seq_file, "w") as sf:
    sf.write(str(ReceiptSeq))

# ------------------------------
# 3. Summalarni hisoblash
# ------------------------------
total_price = sum(item["Price"] for item in items)
total_vat = sum(item["VAT"] for item in items)

# Hamma summa kartadan qaytarilyapti
ReceivedCash = 0
ReceivedCard = total_price

# ------------------------------
# 4. Receipt JSON yaratish
# ------------------------------
now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

receipt_data = {
    "ReceiptSeq": ReceiptSeq,
    "IsRefund": 1,          # qaytarish
    "Items": items,
    "ReceivedCash": ReceivedCash,
    "ReceivedCard": ReceivedCard,
    "TotalVAT": total_vat,
    "Time": now_time,
    "ReceiptType": 0,       # sotuv/qaytarish uchun
    "RefundInfo": refund_info,
    "Location": {"Latitude": 41.2967745, "Longitude": 69.2179078},
    "ExtraInfo": {
        "PhoneNumber": "998901234567"
    },
    "MerchantInfo": merchant
}

# ------------------------------
# 5. JSON faylga yozish
# ------------------------------
receipt_json_path = os.path.join("logs", "RefundReceipt.json")
with open(receipt_json_path, "w", encoding="utf-8") as f:
    json.dump(receipt_data, f, ensure_ascii=False, indent=4)

print(f"✅ RefundReceipt.json yaratildi: {receipt_json_path}")

# ------------------------------
# 6. JSONni imzolash
# ------------------------------
os.makedirs("keys", exist_ok=True)
signed_path = os.path.join("keys", "RefundReceipt.p7b")
cmd = [
    "openssl", "cms", "-sign",
    "-nodetach", "-binary",
    "-in", receipt_json_path,
    "-text",
    "-outform", "der",
    "-out", signed_path,
    "-nocerts",
    "-signer", CERT_FILE,
    "-inkey", KEY_FILE
]

print("Qaytarish chekini imzolash...")
try:
    subprocess.run(cmd, check=True)
    print(f"✅ Imzolangan qaytarish chek: {signed_path}")
except subprocess.CalledProcessError as e:
    print("❌ OpenSSL imzolash xatosi:", e)
    raise SystemExit(1)

# ------------------------------
# 7. OFD serveriga yuborish
# ------------------------------
headers = {"Content-Type": "application/octet-stream"}
print("Qaytarish chekini yuborish...")

try:
    with open(signed_path, "rb") as f:
        response = requests.post(OFD_URL, headers=headers, data=f, timeout=60)

    print("✅ Server javobi:")
    print("Status:", response.status_code)
    print("Body:", response.text)

    # Saqlash
    with open("logs/refund_response.log", "w", encoding="utf-8") as lf:
        lf.write(f"Status: {response.status_code}\n")
        lf.write(response.text)

    try:
        resp_json = response.json()
        with open("logs/refund_response.json", "w", encoding="utf-8") as rf:
            json.dump(resp_json, rf, ensure_ascii=False, indent=4)

        qurl = resp_json.get("QRCodeURL")
        if qurl:
            try:
                unescaped = qurl.encode("utf-8").decode("unicode_escape")
            except Exception:
                unescaped = qurl
            print("✅ Unescaped QRCodeURL:", unescaped)
            with open("logs/refund_qrcode_url.txt", "w", encoding="utf-8") as qf:
                qf.write(unescaped + "\n")

    except ValueError:
        with open("logs/refund_response_raw.txt", "w", encoding="utf-8") as rf:
            rf.write(response.text)

    print("Natija logs papkasiga saqlandi ✅")

except requests.exceptions.RequestException as e:
    print("❌ So‘rov xatoligi:", e)
    with open("logs/refund_error.log", "w", encoding="utf-8") as f:
        f.write(str(e))
    raise SystemExit(1)
