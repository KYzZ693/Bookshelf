"""
Upload db.json to Firebase Realtime Database
วิธีที่ง่ายและชัวร์ที่สุด!
"""
import json
import requests
import sys
import io

# แก้ปัญหา Unicode
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Firebase Database URL
DATABASE_URL = "https://bookshelf-db-web-default-rtdb.asia-southeast1.firebasedatabase.app"

print("=" * 60)
print("Upload db.json to Firebase")
print("=" * 60)

# 1. อ่านไฟล์ db.json
print("\nReading db.json...")
try:
    with open("db.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    books = data.get("books", [])
    owned = data.get("owned", {})
    want = data.get("want", {})
    
    print(f"   OK - Found {len(books)} books")
    print(f"   OK - Found {len(owned)} owned items")
    print(f"   OK - Found {len(want)} want items")
    
except FileNotFoundError:
    print("   ERROR - db.json not found!")
    print("   Run 'python scraper.py --standalone' first")
    exit(1)
except Exception as e:
    print(f"   ERROR - Error reading file: {e}")
    exit(1)

# 2. อัพโหลดขึ้น Firebase
print("\nUploading to Firebase...")

# Upload books
print("   Uploading books... ", end="")
res = requests.put(f"{DATABASE_URL}/books.json", json=books)
if res.ok:
    print(f"SUCCESS ({res.status_code})")
else:
    print(f"FAILED ({res.status_code})")
    print(f"   Error: {res.text}")

# Upload owned
print("   Uploading owned... ", end="")
res = requests.put(f"{DATABASE_URL}/owned.json", json=owned)
if res.ok:
    print(f"SUCCESS ({res.status_code})")
else:
    print(f"FAILED ({res.status_code})")

# Upload want
print("   Uploading want... ", end="")
res = requests.put(f"{DATABASE_URL}/want.json", json=want)
if res.ok:
    print(f"SUCCESS ({res.status_code})")
else:
    print(f"FAILED ({res.status_code})")

# 3. ตรวจสอบว่าอัพสำเร็จ
print("\nVerifying upload...")
res = requests.get(f"{DATABASE_URL}/books.json")
if res.ok:
    uploaded_data = res.json()
    if uploaded_data and len(uploaded_data) == len(books):
        print(f"   OK - Verified: {len(uploaded_data)} books in Firebase")
    else:
        print(f"   WARNING - Mismatch: Expected {len(books)}, got {len(uploaded_data) if uploaded_data else 0}")
else:
    print(f"   ERROR - Cannot verify: {res.status_code}")

print("\n" + "=" * 60)
print("DONE! Check your Firebase console:")
print(f"   {DATABASE_URL}")
print("=" * 60)
