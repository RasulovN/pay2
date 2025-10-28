#!/usr/bin/env python3
"""
credit_refund.py – Kredit chekni qaytarish
- ReceiptSeq avtomatik
- Avval yuborilgan kredit chekining SaleReceiptInfo ma’lumotlari bilan
"""

import subprocess
import requests
import json
import os
from datetime import datetime

CERT_FILE = "certificates/EZ000000000931.crt"
KEY_FILE = "certificates/amaar.key"
OFD_URL = "https://test.ofd.uz/emp/v3/receipt"

os.makedirs("logs", exist_ok=True)

# Sequence
seq_file = "logs/last_seq.txt"
if os.path.exists(seq_file):
    last_seq = int(open(seq_file).read().strip() or "0")
else:
    last_seq = 0
ReceiptSeq = last_seq + 1
with open(seq_file, "w") as f:
    f.write(str(ReceiptSeq))

# Avvalgi kredit chekining ma’lumotlari
last_credit_file = "logs/last_credit_info.json"
if not os.path.exists(last_credit_file):
    print("❌ Avval kredit chek yuborilmagan, last_credit_info.json yo‘q!")
    exit(1)
last_credit = json.load(open(last_credit_file, encoding="utf-8"))

# Items – qaytarilayotgan mahsulot
items = [
    {
        "Name": "Kompyuter sichqonchasi",
        "Barcode": "1234567890123",
        "SPIC": "08471012005000000",
        "PackageCode": "1503256",
        "GoodPrice": 150000,
        "Price": 300000,
        "VAT": 36000,
        "VATPercent": 12,
        "Amount": 2000,
        "Discount": 300000,
        "Other": 0,
        "CommissionInfo": {
            "TIN": "190261951",
            "PINFL": "30747919403015"
        }
    }
]

total_vat = sum(i["VAT"] for i in items)
now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

receipt_data = {
    "ReceiptSeq": ReceiptSeq,
    "IsRefund": 1,   # qaytarish
    "Items": items,
    "ReceivedCash": 0,
    "ReceivedCard": 0,
    "TotalVAT": total_vat,
    "Time": now_time,
    "ReceiptType": 2,   # Kredit chek
    "Location": {"Latitude": 41.2967745, "Longitude": 69.2179078},
    "ExtraInfo": {"PhoneNumber": "998901234567"},
    "SaleReceiptInfo": {
        "TerminalID": last_credit["TerminalID"],
        "ReceiptSeq": str(last_credit["ReceiptSeq"]),
        "DateTime": last_credit["DateTime"],
        "FiscalSign": last_credit["FiscalSign"]
    }
}

receipt_json_path = "logs/CreditRefund.json"
with open(receipt_json_path, "w", encoding="utf-8") as f:
    json.dump(receipt_data, f, ensure_ascii=False, indent=4)
print(f"✅ CreditRefund.json yaratildi: {receipt_json_path}")

# Sign
signed_path = "keys/CreditRefund.p7b"
cmd = [
    "openssl", "cms", "-sign", "-nodetach", "-binary",
    "-in", receipt_json_path, "-text", "-outform", "der",
    "-out", signed_path, "-nocerts",
    "-signer", CERT_FILE, "-inkey", KEY_FILE
]
subprocess.run(cmd, check=True)
print(f"✅ Imzolangan fayl yaratildi: {signed_path}")

# Send
headers = {"Content-Type": "application/octet-stream"}
with open(signed_path, "rb") as f:
    resp = requests.post(OFD_URL, headers=headers, data=f, timeout=60)

print("Status:", resp.status_code)
print("Body:", resp.text)

try:
    resp_json = resp.json()
    qurl = resp_json.get("QRCodeURL")
    if qurl:
        unescaped = qurl.encode("utf-8").decode("unicode_escape")
        print("✅ Unescaped QRCodeURL:", unescaped)
        open("logs/kridet_qaytish_qrcode.txt", "w", encoding="utf-8").write(unescaped)
except Exception:
    print("❌ Server javobi JSON emas")
