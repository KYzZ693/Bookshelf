"""
ลบ junk items ออกจาก db.json
"""
import json
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_FILE = "db.json"

def is_junk_item(title, price, link):
    """ตรวจว่า item เป็น junk หรือไม่"""
    import re
    t = (title or "").strip()
    p = (price or "").strip()
    
    # title ว่าง / สั้นเกิน
    if not t or len(t) < 2:
        return True
    
    # แค่ตัวเลข
    if re.match(r'^\d+$', t):
        return True
    
    # "หน้า X" / "Page X"
    if re.match(r'^(หน้า?|page)\s*\d+$', t, re.IGNORECASE):
        return True
    if re.match(r'^หน้า\s*[๐-๙]+$', t):
        return True
    
    # Messages / Status text
    MESSAGE_PATTERNS = [
        r'^คุณกำลัง',  # คุณกำลังอ่านหน้าเว็บอยู่
        r'^กำลัง',      # กำลัง...
        r'^โปรด',       # โปรด...
        r'^กรุณา',     # กรุณา...
        r'^ขออภัย',    # ขออภัย...
        r'^ไม่มี',      # ไม่มีสินค้า
        r'^ไม่พบ',      # ไม่พบข้อมูล
    ]
    for pattern in MESSAGE_PATTERNS:
        if re.match(pattern, t):
            return True
    
    # Price range
    if re.search(r'฿[\d,.]+\s*[-–]\s*฿[\d,.]+', t):
        return True
    if re.search(r'฿[\d,.]+\s*[-–]\s*฿[\d,.]+', p):
        return True
    
    # มีคำว่า "รายการ"
    if re.search(r'\(\d+\)\s*รายการ', t):
        return True
    if re.search(r'\d+\)\s*รายการ', t):
        return True
    if re.search(r'รายการ$', t):
        return True
    
    return False

print("Cleaning db.json...")

with open(DB_FILE, 'r', encoding='utf-8') as f:
    db = json.load(f)

original_count = len(db['books'])
print(f"Original: {original_count} books")

# ลบ junk
db['books'] = [
    b for b in db['books']
    if not is_junk_item(b.get('Title', ''), b.get('Price', ''), b.get('Link', ''))
]

new_count = len(db['books'])
junk_count = original_count - new_count

print(f"Removed: {junk_count} junk items")
print(f"Remaining: {new_count} books")

with open(DB_FILE, 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print(f"\nSaved to {DB_FILE}")

# แสดง junk ที่ถูกลบ
if junk_count > 0:
    print(f"\nRemoved items (examples):")
    # อ่านใหม่เพื่อดูว่าอะไรถูกลบ
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        clean_db = json.load(f)
    
    # สมมติว่า junk อยู่ต้นๆ
    print("  (Junk items have been removed)")
