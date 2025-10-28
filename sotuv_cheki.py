#!/usr/bin/env python3
"""
send_receipt.py – Marketplace Order Cheki

- ReceiptSeq avtomatik oshib boradi (logs/last_seq.txt orqali).
- Har bir item seller_id orqali sellerga bog‘lanadi va CommissionInfo qo‘shiladi.
- Delivery (TaxiInfo) db/delivery_default.json dan olinadi va alohida item sifatida qo‘shiladi.
- Marketplace ma’lumotlari ExtraInfo ichida chiqadi.
- Chek vaqti datetime.now() dan olinadi.
- Payment type (card | cash | mix) dinamik.
- OFD javobidagi QRCodeURL ni unescape qilib saqlash.
- Oxirgi sotuv logs/last_sale_info.json ga yoziladi.
"""

import subprocess
import requests
import json
import os
from datetime import datetime

# ------------------------------
# 0. Konfiguratsiya
# ------------------------------
# CERT_FILE = "certificates/EZ000000000931.crt" # test
CERT_FILE = "certificates/EP000000000589.crt"
KEY_FILE = "certificates/amaar.key"
# OFD_URL = "https://test.ofd.uz/emp/v3/receipt" #test
# OFD_URL = "https://txkm.soliq.uz/api/txkm-api/emp/v3/receipt"
# OFD_URL = "https://txkm.soliq.uz/api/emp/v3/receipt"
OFD_URL = "https://txkm.soliq.uz/emp/v3/receipt"

payment_type = "card"  # "card" | "cash" | "mix"

# Sellerlar
sellers = [
    {"id": "s1", "TIN": "", "PINFL": "", "HasVAT": True},
    {"id": "s2", "TIN": "311439965", "PINFL": "", "HasVAT": False},
    {"id": "s3", "TIN": "311439965", "PINFL": "", "HasVAT": True},
]
seller_map = {s["id"]: s for s in sellers}

# Marketplace
marketplace = {
    "name": "AMAAR MARKET",
    "address": "Oʻzbekiston, Qashqadaryo viloyati, Qarshi, Beshkent Yoʻli koʻchasi, 1/153",
    "ep_number": "EP000000000589",
    "receipt_number": "RCP-0001",
}

# Merchant
merchant = {
    "TIN": "190261951",
    "PINFL": "30747919403015",
    "ContractDate": "2025-09-21 07:41:09",
    "ContractNumber": "264"
}

amountKop = 1000

# ------------------------------
# 1. Order default.json dan olish
# ------------------------------
order_file = "db/order_default.json"
items = []

if os.path.exists(order_file):
    with open(order_file, "r", encoding="utf-8") as of:
        try:
            order_data = json.load(of)
            raw_items = order_data.get("items", [])
        except Exception as e:
            print("❌ Order faylni o‘qishda xatolik:", e)
            raw_items = []
else:
    raw_items = []

# Itemlarni normalizatsiya qilib yig‘ish
for it in raw_items:
    sid = it.get("seller_id")
    seller_info = seller_map.get(sid)

    if not seller_info:
        continue

    has_vat = seller_info.get("HasVAT", True)
    price = it["Price"]
    vat_percent = 12 if has_vat else 0

    if has_vat:
        # Price ichida QQS bor
        vat_sum = round(price * vat_percent / (100 + vat_percent))
        good_price = price
    else:
        # QQS yo‘q
        vat_sum = 0
        good_price = price

    item = {
        "Name": it["Name"],
        "Barcode": it.get("Barcode", ""),
        "Labels": it.get("Labels", []),
        "SPIC": it.get("SPIC", ""),
        "PackageCode": it.get("PackageCode", ""),
        "OwnerType": 0,
        "GoodPrice": good_price,
        "Price": price,
        "VAT": vat_sum,
        "VATPercent": vat_percent,
        "Amount": it["Amount"] * amountKop,
        "Discount": 0,
        "Other": 0,
        "Voucher": 0,
        "CommissionInfo": {
            "TIN": seller_info["TIN"],
            "PINFL": seller_info.get("PINFL", "")
        }
    }

    items.append(item)

# ------------------------------
# 2. Delivery default.json dan olish
# ------------------------------
delivery_file = "db/delivery_default.json"
if os.path.exists(delivery_file):
    with open(delivery_file, "r", encoding="utf-8") as df:
        try:
            taxi_info = json.load(df)
        except Exception:
            taxi_info = {"TIN": "", "PINFL": "", "CarNumber": ""}
else:
    taxi_info = {"TIN": "", "PINFL": "", "CarNumber": ""}

# 🚚 Xizmat bazaviy narxi
delivery_total_price = 15000

delivery_item = {
    "Name": "Maxsulotlarni yetkazib berish xizmati",
    "Barcode": "10112006002000000",
    "Labels": [],
    "SPIC": "10112006002000000",
    "PackageCode": "1209779",
    "OwnerType": 0,
    "GoodPrice": delivery_total_price,
    "Price": delivery_total_price,
    "VAT": round(delivery_total_price * 12 / 112),  # QQS ichidan ajratiladi
    "VATPercent": 12,
    "Amount": 1 * amountKop,
    "Discount": 0,
    "Other": 0,
    "Voucher": 0,
    "TaxiInfo": taxi_info
}
items.append(delivery_item)

# ------------------------------
# 3. ReceiptSeq
# ------------------------------
os.makedirs("logs", exist_ok=True)
seq_file = "logs/last_seq.txt"
if os.path.exists(seq_file):
    try:
        last_seq = int(open(seq_file).read().strip())
    except ValueError:
        last_seq = 0
else:
    last_seq = 0
ReceiptSeq = last_seq + 1
open(seq_file, "w").write(str(ReceiptSeq))

# ------------------------------
# 4. Summalar
# ------------------------------
total_price = sum(i["Price"] for i in items)
total_vat = sum(i["VAT"] for i in items)

ReceivedCash = 0
ReceivedCard = 0
if payment_type == "cash":
    ReceivedCash = total_price
elif payment_type == "card":
    ReceivedCard = total_price
elif payment_type == "mix":
    ReceivedCash = total_price // 2
    ReceivedCard = total_price - ReceivedCash

# ------------------------------
# 5. Receipt JSON
# ------------------------------
now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
request_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        "RequestTime": request_time,
        "CreatedTime": now_time
    },
    "MerchantInfo": merchant
}

# ------------------------------
# 6. JSON yozish
# ------------------------------
receipt_json_path = "logs/ReceiptInfo.json"
with open(receipt_json_path, "w", encoding="utf-8") as f:
    json.dump(receipt_data, f, ensure_ascii=False, indent=4)
print(f"✅ ReceiptInfo.json yaratildi: {receipt_json_path}")

# ------------------------------
# 7. Imzolash
# ------------------------------
signed_path = "keys/ReceiptInfo.p7b"
os.makedirs("keys", exist_ok=True)
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
print("Chekni imzolash...")
subprocess.run(cmd, check=True)
print(f"✅ Imzolangan fayl yaratildi: {signed_path}")

# ------------------------------
# 8. OFDga yuborish
# ------------------------------
headers = {"Content-Type": "application/octet-stream"}
print("Chekni yuborish...")

with open(signed_path, "rb") as f:
    response = requests.post(OFD_URL, headers=headers, data=f, timeout=60)

print("✅ Server javobi:")
print("Status:", response.status_code)
print("Body:", response.text)

try:
    resp_json = response.json()
    with open("logs/response.json", "w", encoding="utf-8") as rf:
        json.dump(resp_json, rf, ensure_ascii=False, indent=4)

    with open("logs/last_sale_info.json", "w", encoding="utf-8") as sf:
        json.dump(resp_json, sf, ensure_ascii=False, indent=4)

    qurl = resp_json.get("QRCodeURL")
    if qurl:
        unescaped = qurl.encode("utf-8").decode("unicode_escape")
        print("✅ Unescaped QRCodeURL:", unescaped)
        open("logs/qrcode_url.txt", "w", encoding="utf-8").write(unescaped + "\n")

except Exception:
    open("logs/response_raw.txt", "w", encoding="utf-8").write(response.text)

print("Natija logs papkasiga saqlandi ✅")

# print("\n📌 Soliq serveriga ketayotgan JSON:")
# print(json.dumps(receipt_data, indent=4, ensure_ascii=False))