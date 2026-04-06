"""
อัพเดต Type ตาม prefix ใน db.json (รองรับวงเล็บ)
- (มังงะ)... / [มังงะ]... → Manga
- (N)... / N... → LN  
- (AB)... / [AB]... / Artbook → Artbook
"""
import json
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_FILE = "db.json"

def detect_book_type(title: str, existing_type: str = "") -> str:
    t = title.strip()
    t_lower = t.lower()
    
    # ลบวงเล็บรอบ prefix
    t_no_bracket = re.sub(r'^[\(\[](.+?)[\)\]]', r'\1', t_lower).strip()
    
    if t_lower.startswith('มังงะ') or t_lower.startswith('manga') or \
       t_no_bracket.startswith('มังงะ') or t_no_bracket.startswith('manga'):
        return 'Manga'
    
    # N prefix → Novel (แยกจาก LN)
    if re.match(r'^n\s', t_lower) or re.match(r'^n\d', t_lower) or \
       re.match(r'^n\s', t_no_bracket) or re.match(r'^n\d', t_no_bracket):
        return 'Novel'
    
    if t_lower.startswith('ab ') or re.match(r'^ab\d', t_lower) or \
       t_lower.startswith('artbook') or \
       t_no_bracket.startswith('ab ') or re.match(r'^ab\d', t_no_bracket) or \
       t_no_bracket.startswith('artbook'):
        return 'Artbook'
    
    # Default to LN
    return existing_type if existing_type else 'LN'

print("Updating book types in db.json...")

with open(DB_FILE, 'r', encoding='utf-8') as f:
    db = json.load(f)

count = 0
type_stats = {'LN': 0, 'Manga': 0, 'Artbook': 0, 'Other': 0}
changed_examples = []

for b in db['books']:
    old_type = b.get('Type', 'LN')
    new_type = detect_book_type(b.get('Title', ''), old_type)
    
    if old_type != new_type:
        b['Type'] = new_type
        count += 1
        if len(changed_examples) < 10:
            changed_examples.append({
                'title': b['Title'][:60],
                'old': old_type,
                'new': new_type
            })
    
    type_stats[new_type] = type_stats.get(new_type, 0) + 1

with open(DB_FILE, 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print(f"\nUpdated {count} books\n")

if changed_examples:
    print("Examples:")
    for ex in changed_examples:
        print(f"  {ex['title']}... : {ex['old']} → {ex['new']}")

print(f"\nType statistics:")
for t, c in type_stats.items():
    print(f"  {t}: {c} books")

print(f"\nSaved to {DB_FILE}")
