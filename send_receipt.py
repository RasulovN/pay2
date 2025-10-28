#!/usr/bin/env python3
"""
send_receipt.py – Sotuv chekini yuborish
- ReceiptSeq avtomatik
- Har bir itemda seller_id orqali CommissionInfo qo‘shiladi
- Marketplace va MerchantInfo maydonlari qo‘shiladi
- Server javobidan SaleReceiptInfo ni logs/last_sale_info.json ga yozadi
"""

import subprocess
import requests
import json
import os
from datetime import datetime

CERT_FILE = "certificates/EZ000000000931.crt"
KEY_FILE = "certificates/amaar.key"
OFD_URL = "https://test.ofd.uz/emp/v3/receipt"

# Sellerlar
sellers = [
    {"id": "s1", "TIN": "311439965", "PINFL": ""},
    {"id": "s2", "TIN": "302547891", "PINFL": ""},
    {"id": "s3", "TIN": "209876543", "PINFL": ""}
]
seller_map = {s["id"]: s for s in sellers}

# Marketplace
marketplace = {
    "name": "My Marketplace",
    "address": "Toshkent, Chilonzor",
    "ep_number": "EP123456",
    "receipt_number": "RCP-0001",
}

# Merchant
merchant = {
    "TIN": "190261951",
    "PINFL": "30747919403015",
    "ContractDate": "2025-09-21 07:41:09",
    "ContractNumber": "264"
}

# Items
items = [
    {
        "Name": "Kompyuter sichqonchasi",
        "Barcode": "1234567890123",
        "SPIC": "08471012005000000",
        "PackageCode": "1503256",
        "GoodPrice": 150000,
        "Price": 150000,
        "VAT": 18000,
        "VATPercent": 12,
        "Amount": 1000,
        "Discount": 0,
        "Other": 0,
        "seller_id": "s1"
    },
    {
        "Name": "Klaviatura",
        "Barcode": "2345678901234",
        "SPIC": "08471012004000000",
        "PackageCode": "1503267",
        "GoodPrice": 250000,
        "Price": 250000,
        "VAT": 30000,
        "VATPercent": 12,
        "Amount": 2000,
        "Discount": 0,
        "Other": 0,
        "seller_id": "s2"
    }
]

# Seller_id → CommissionInfo
for item in items:
    sid = item.pop("seller_id", None)
    if sid:
        seller_info = seller_map[sid]
        item["CommissionInfo"] = {
            "TIN": seller_info["TIN"],
            "PINFL": seller_info["PINFL"]
        }

# Sequence
os.makedirs("logs", exist_ok=True)
seq_file = "logs/last_seq.txt"
if os.path.exists(seq_file):
    last_seq = int(open(seq_file).read().strip() or "0")
else:
    last_seq = 0
ReceiptSeq = last_seq + 1
with open(seq_file, "w") as f:
    f.write(str(ReceiptSeq))

# Summalar
total_price = sum(i["Price"] for i in items)
total_vat = sum(i["VAT"] for i in items)

# Faqat kartadan to‘lov
ReceivedCash = 0
ReceivedCard = total_price

# JSON yaratish
now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
receipt_data = {
    "ReceiptSeq": ReceiptSeq,
    "IsRefund": 0,
    "Items": items,
    "ReceivedCash": ReceivedCash,
    "ReceivedCard": ReceivedCard,
    "TotalVAT": total_vat,
    "Time": now_time,
    "ReceiptType": 0,
    "Location": {"Latitude": 41.2967745, "Longitude": 69.2179078},
    "ExtraInfo": {
        "PhoneNumber": "998901234567",
        "MarketplaceName": marketplace["name"],
        "MarketplaceAddress": marketplace["address"],
        "EPNumber": marketplace["ep_number"],
        "ReceiptNumber": marketplace["receipt_number"],
        "CreatedTime": now_time
    },
    "MerchantInfo": merchant
}

receipt_json_path = "logs/ReceiptInfo.json"
with open(receipt_json_path, "w", encoding="utf-8") as f:
    json.dump(receipt_data, f, ensure_ascii=False, indent=4)
print(f"✅ ReceiptInfo.json yaratildi: {receipt_json_path}")

# Sign
signed_path = "keys/ReceiptInfo.p7b"
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
    # SaleReceiptInfo saqlash
    sale_info = resp_json.get("SaleReceiptInfo")
    if sale_info:
        with open("logs/last_sale_info.json", "w", encoding="utf-8") as sf:
            json.dump(sale_info, sf, ensure_ascii=False, indent=4)
        print("✅ last_sale_info.json saqlandi")

    qurl = resp_json.get("QRCodeURL")
    if qurl:
        unescaped = qurl.encode("utf-8").decode("unicode_escape")
        print("✅ Unescaped QRCodeURL:", unescaped)
        open("logs/qrcode_url.txt", "w", encoding="utf-8").write(unescaped)

except Exception:
    print("❌ Server javobi JSON emas")

