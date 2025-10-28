#!/usr/bin/env python3


#avance cheki yuborish
"""
send_advance_receipt.py

OFD serveriga avans chek yuborish:
- ReceiptSeq avtomatik oshib boradi (logs/last_seq.txt orqali).
- Har bir itemda CommissionInfo bo‘ladi.
- Avans bo‘lgani uchun ReceiptType = 1 va AdvanceContractID qo‘shiladi.
- Server javobida kelgan QRCodeURL unescape qilinib ko‘rsatiladi.
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

# Seller / Merchant
merchant = {
    "TIN": "190261951",
    "PINFL": "30747919403015",
    "ContractDate": "2025-09-21 07:41:09",
    "ContractNumber": "264"
}

# Avans to‘lov shartnoma ID (odatda tashqi tizimdan olinadi)
ADVANCE_CONTRACT_ID = "2f138c8f0fe3499a9be756f4bdccc6d5"

amountKop = 1000  # ReceiptSeq qadam

# Itemlar (namuna)
items = [
    {
        "Name": "Kompyuter sichqonchasi",
        "Barcode": "1234567890123",
        "Labels": ["468449404843551080626"],
        "SPIC": "08471012005000000",
        "PackageCode": "1503256",
        "GoodPrice": 750338,
        "Price": 750338,
        "VAT": 80393,
        "VATPercent": 12,
        "Amount": 1 * amountKop,
        "Discount": 250112,
        "Other": 250112,
        "Voucher": 0,
        "CommissionInfo": {
            "TIN": merchant["TIN"],
            "PINFL": merchant["PINFL"]
        }
    }
]

# ------------------------------
# 1. ReceiptSeq avtomatik oshirish
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
# 2. Umumiy summalarni hisoblash
# ------------------------------
total_price = sum(item["Price"] for item in items)
total_vat = sum(item["VAT"] for item in items)

# Masalan, faqat karta orqali qisman to‘lanmoqda
ReceivedCash = 0
ReceivedCard = 250114  # avans summasi

# ------------------------------
# 3. Receipt JSON yaratish
# ------------------------------
now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

receipt_data = {
    "ReceiptSeq": ReceiptSeq,
    "IsRefund": 0,
    "Items": items,
    "ReceivedCash": ReceivedCash,
    "ReceivedCard": ReceivedCard,
    "TotalVAT": total_vat,
    "Time": now_time,
    "ReceiptType": 1,  # avans chek
    "AdvanceContractID": ADVANCE_CONTRACT_ID,
    "Location": {"Latitude": 41.2967745, "Longitude": 69.2179078},
    "ExtraInfo": {
        "PhoneNumber": "998901234567",
        "RequestTime": now_time,
        "CreatedTime": now_time
    },
    "MerchantInfo": merchant
}

# ------------------------------
# 4. JSON faylga yozish
# ------------------------------
receipt_json_path = os.path.join("logs", "AdvanceReceipt.json")
with open(receipt_json_path, "w", encoding="utf-8") as f:
    json.dump(receipt_data, f, ensure_ascii=False, indent=4)

print(f"✅ AdvanceReceipt.json yaratildi: {receipt_json_path}")

# ------------------------------
# 5. JSONni imzolash
# ------------------------------
os.makedirs("keys", exist_ok=True)
signed_path = os.path.join("keys", "AdvanceReceipt.p7b")
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

print("Avans chekni imzolash...")
try:
    subprocess.run(cmd, check=True)
    print(f"✅ Imzolangan fayl yaratildi: {signed_path}")
except subprocess.CalledProcessError as e:
    print("❌ OpenSSL imzolash xatosi:", e)
    raise SystemExit(1)

# ------------------------------
# 6. OFD serveriga yuborish
# ------------------------------
headers = {"Content-Type": "application/octet-stream"}
print("Avans chekni yuborish...")

try:
    with open(signed_path, "rb") as f:
        response = requests.post(OFD_URL, headers=headers, data=f, timeout=60)

    body = {}
    try:
        body = response.json()
    except Exception:
        print("⚠️ Serverdan JSON emas matn keldi")
        print("Body:", response.text)

    print("✅ Server javobi:")
    print("Status:", response.status_code)

    # Agar QRCodeURL bo‘lsa, unescape qilib chiqaramiz
    if "QRCodeURL" in body:
        qr_url = body["QRCodeURL"].encode("utf-8").decode("unicode_escape")
        print("✅ QR havola:", qr_url)
        body["QRCodeURL"] = qr_url  # logga ham toza variant tushadi

    print("Body:", json.dumps(body, indent=4, ensure_ascii=False))

    with open("logs/advance_response.log", "w", encoding="utf-8") as lf:
        lf.write(f"Status: {response.status_code}\n")
        lf.write(json.dumps(body, indent=4, ensure_ascii=False))

except requests.exceptions.RequestException as e:
    print("❌ So‘rov xatoligi:", e)
    with open("logs/advance_error.log", "w", encoding="utf-8") as f:
        f.write(str(e))
    raise SystemExit(1)
