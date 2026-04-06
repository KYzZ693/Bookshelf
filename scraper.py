"""
BookShelf Scraper — Fast Async Edition
=======================================
ความเร็ว: ดึง detail หนังสือพร้อมกัน 15 เล่มต่อครั้ง
ผลลัพธ์: เร็วขึ้น ~8-10x จากโค้ดเดิม

วิธีรัน:
  pip install -r requirements.txt
  python scraper.py               ← Flask API mode (ใช้กับเว็บ)
  python scraper.py --standalone  ← รันตรง export xlsx เลย
"""

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

# ══════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
}

PUBLISHERS: dict = {
    "PhoenixNext": {
        "base":  "https://www.phoenixnext.com",
        "ln":    "/light-novel.html",
        "manga": "/manga.html",
    },
}

DB_FILE     = "db.json"
MAX_WORKERS = 15
TIMEOUT     = 8
DELAY_PAGE  = 0.2
MAX_PAGES   = 50

# ══════════════════════════════════════════════════════
# HTTP SESSION
# ══════════════════════════════════════════════════════

session = requests.Session()
session.headers.update(HEADERS)
adapter = requests.adapters.HTTPAdapter(
    pool_connections=50,
    pool_maxsize=50,
    max_retries=requests.adapters.Retry(total=3, backoff_factor=0.1),
)
session.mount("https://", adapter)
session.mount("http://",  adapter)


# ══════════════════════════════════════════════════════
# TYPE DETECTION
# ══════════════════════════════════════════════════════

def detect_book_type(title: str, existing_type: str = "") -> str:
    """
    ตรวจสอบ prefix จากชื่อเพื่อระบุประเภทหนังสือ
    Returns: 'LN', 'Novel', 'Manga', 'Artbook', หรือ existing_type
    """
    t = title.strip()
    t_lower = t.lower()
    
    # ลบวงเล็บรอบ prefix
    t_no_bracket = re.sub(r'^[\(\[](.+?)[\)\]]', r'\1', t_lower).strip()
    
    # Check prefixes (ทั้งมีและไม่มีวงเล็บ)
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
    
    # Default to LN (Light Novel ทั่วไปที่ไม่มี prefix)
    return existing_type if existing_type else 'LN'


# ══════════════════════════════════════════════════════
# JUNK DETECTION
# ══════════════════════════════════════════════════════

def is_product_url(url: str, base_url: str) -> bool:
    if not url:
        return False
    if url.startswith(base_url):
        return True
    return '/catalog/product/view/id/' in url or '.html' in url.split('?')[0]


def is_junk_item(title: str, price: str, link: str, base_url: str = "") -> bool:
    """ตรวจว่า item นี้เป็น junk หรือเปล่า (True = ทิ้ง)"""
    t = (title or "").strip()
    p = (price or "").strip()
    l = (link  or "").strip()

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
        r'^คุณกำลัง',
        r'^กำลัง',
        r'^โปรด',
        r'^กรุณา',
        r'^ขออภัย',
        r'^ไม่มี',
        r'^ไม่พบ',
    ]
    for pattern in MESSAGE_PATTERNS:
        if re.match(pattern, t):
            return True

    # Price-range filter
    if re.search(r'฿[\d,.]+\s*[-–]\s*฿[\d,.]+', t):
        return True
    if re.search(r'฿[\d,.]+\s*[-–]\s*฿[\d,.]+', p):
        return True
    if re.search(r'\(\d+\)\s*รายการ', t):
        return True
    if re.search(r'\d+\)\s*รายการ', t):
        return True
    if re.search(r'รายการ$', t):
        return True

    # ราคาที่มี range
    if re.search(r'[\$฿][\d,.]+\s*[-–]\s*[\$฿][\d,.]+', t):
        return True

    # ชื่อหมวดหมู่
    JUNK_TITLES = {
        "light novel", "manga", "การ์ตูน", "นิยาย", "หนังสือ",
        "ทั้งหมด", "all", "new arrivals", "สินค้าใหม่",
        "bestseller", "ขายดี", "sale", "ลดราคา",
        "ln", "comic", "book", "books",
        "genre", "category", "publisher",
        "home", "หน้าแรก", "search", "ค้นหา",
    }
    if t.lower() in JUNK_TITLES:
        return True

    # link ไม่ใช่ product URL
    if base_url and not is_product_url(l, base_url):
        return True
    elif not base_url and re.search(r'[?&](price|cat|brand|publisher|manufacturer)=', l):
        return True

    return False


# ══════════════════════════════════════════════════════
# SCRAPER CORE
# ══════════════════════════════════════════════════════

def fetch(url: str):
    """GET → BeautifulSoup หรือ None"""
    try:
        res = session.get(url, timeout=TIMEOUT)
        res.raise_for_status()
        res.encoding = res.apparent_encoding or "utf-8"
        return BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"  [!] fetch failed: {url[:70]}… — {e}")
        return None


def parse_catalog_page(url: str, base_url: str = "") -> list:
    """ดึงรายการหนังสือจาก 1 หน้า catalog"""
    soup = fetch(url)
    if not soup:
        return []

    items = (
        soup.select("li.product-item") or
        soup.select(".product-item") or
        soup.select("li.item.product")
    )

    books = []
    seen_links = set()

    for item in items:
        try:
            link_tag = (
                item.select_one("a.product-item-link") or
                item.select_one(".product-item-link")
            )
            if not link_tag:
                continue

            title = link_tag.get_text(strip=True)
            link  = link_tag.get("href", "")
            if link.startswith("/"):
                link = base_url + link

            # ราคา
            price = ""
            price_tag = item.select_one(".price-box .price")
            if price_tag:
                price = re.sub(r"\s+", " ", price_tag.get_text(strip=True)).strip()

            # กรอง junk
            if is_junk_item(title, price, link, base_url):
                continue

            if link in seen_links:
                continue
            seen_links.add(link)

            # Clean title
            title = re.sub(r'^\s*\(LN\)\s*', '', title).strip()
            title = re.sub(r'^\s*\(Manga\)\s*', '', title).strip()

            # Detect type จาก prefix
            book_type = detect_book_type(title, "LN")

            # รูปภาพ
            img = ""
            img_tag = item.select_one("img")
            if img_tag:
                img = img_tag.get("data-src") or img_tag.get("src") or ""
                if img.startswith("data:"):
                    img = ""

            if title and link:
                books.append({
                    "Title":       title,
                    "Price":       price,
                    "Image":       img,
                    "Link":        link,
                    "Type":        book_type,
                    "Author":      "",
                    "Illustrator": "",
                    "Genre":       "",
                })
        except Exception:
            continue

    return books


def parse_detail_page(book: dict) -> dict:
    """ดึง author / illustrator / genre จากหน้า detail"""
    soup = fetch(book["Link"])
    if not soup:
        return book

    # หาจาก attribute rows
    for row in soup.select(".product-attribute, table.additional-attributes tr"):
        label_tag = row.select_one(".product-attribute-label, th, label")
        value_tag = row.select_one(".product-attribute-value, td")
        if not label_tag or not value_tag:
            continue

        lbl = label_tag.get_text(strip=True).lower()
        val = value_tag.get_text(strip=True)
        if not val:
            continue

        if any(k in lbl for k in ["ผู้เขียน", "author", "เขียน"]):
            book["Author"] = val
        elif any(k in lbl for k in ["ภาพ", "illustrat", "วาด"]):
            book["Illustrator"] = val
        elif any(k in lbl for k in ["หมวด", "genre", "category"]):
            book["Genre"] = val

    return book


def enrich_books_concurrent(books: list, max_workers: int = MAX_WORKERS) -> list:
    """ดึง detail ของทุกเล่มพร้อมกัน"""
    total   = len(books)
    results = [None] * total

    print(f"  → กำลังดึง detail {total} เล่ม (พร้อมกัน {max_workers} เล่ม)…")
    start = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {
            pool.submit(parse_detail_page, book): i
            for i, book in enumerate(books)
        }
        done = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = books[idx]
            done += 1
            if done % 10 == 0 or done == total:
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                print(f"     {done}/{total} ({rate:.1f} เล่ม/วิ)")

    elapsed = time.time() - start
    print(f"  ✅ detail เสร็จ {total} เล่ม ใช้เวลา {elapsed:.1f}s")
    return [r for r in results if r is not None]


def scrape_publisher(name: str, cfg: dict, existing_books: dict = None) -> list:
    """Scrape LN + Manga ทุกหน้า"""
    all_books = []
    if existing_books is None:
        existing_books = {}

    for type_name, path in [("LN", cfg["ln"]), ("Manga", cfg["manga"])]:
        print(f"\n  [{name}] ── {type_name} ──")
        page = 1
        type_books = []
        seen_links = set()

        while True:
            url = f"{cfg['base']}{path}?p={page}"
            print(f"    Page {page}: {url}")
            items = parse_catalog_page(url, cfg["base"])

            new_items = []
            for item in items:
                if item["Link"] in seen_links:
                    continue
                
                # ตรวจสอบว่ามีข้อมูลอยู่แล้ว
                if item["Link"] in existing_books:
                    existing = existing_books[item["Link"]]
                    # Merge ข้อมูล
                    item = {**existing, **item}
                    # Update type จาก prefix
                    item["Type"] = detect_book_type(item["Title"], existing.get("Type", type_name))
                    seen_links.add(item["Link"])
                    type_books.append(item)
                    continue
                
                item["Type"] = detect_book_type(item["Title"], type_name)
                seen_links.add(item["Link"])
                new_items.append(item)

            if not new_items:
                break

            print(f"    → ได้ {len(new_items)} เล่มใหม่")
            for item in new_items:
                item["Publisher"] = name
            type_books.extend(new_items)
            page += 1
            if page > MAX_PAGES:
                break
            time.sleep(DELAY_PAGE)

        if not type_books:
            continue

        # Enrich detail
        need_detail = [b for b in type_books if not b.get("Author")]
        has_detail = [b for b in type_books if b.get("Author")]
        
        if need_detail:
            type_books = enrich_books_concurrent(need_detail) + has_detail
        
        all_books.extend(type_books)

    return all_books


# ══════════════════════════════════════════════════════
# DB HELPERS
# ══════════════════════════════════════════════════════

def load_db() -> dict:
    if Path(DB_FILE).exists():
        with open(DB_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"books": [], "owned": {}}


def save_db(db: dict):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def clean_titles_in_db(db: dict) -> int:
    """ลบ (LN)/(Manga) prefix"""
    count = 0
    for b in db["books"]:
        old = b.get("Title", "")
        new = re.sub(r'^\s*\(LN\)\s*', '', old).strip()
        new = re.sub(r'^\s*\(Manga\)\s*', '', new).strip()
        if old != new:
            b["Title"] = new
            count += 1
    return count


def remove_junk_from_db(db: dict) -> int:
    """ลบ junk items"""
    original = len(db["books"])
    db["books"] = [
        b for b in db["books"]
        if not is_junk_item(b.get('Title', ''), b.get('Price', ''), b.get('Link', ''))
    ]
    return original - len(db["books"])


def update_types_in_db(db: dict) -> int:
    """อัพเดต Type ตาม prefix"""
    count = 0
    for b in db["books"]:
        old_type = b.get("Type", "LN")
        new_type = detect_book_type(b.get("Title", ""), old_type)
        if old_type != new_type:
            b["Type"] = new_type
            count += 1
    return count


# ══════════════════════════════════════════════════════
# FLASK API
# ══════════════════════════════════════════════════════

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


@app.route("/")
def home():
    return jsonify({"status": "BookShelf API", "version": "3.0"})


@app.route("/books", methods=["GET"])
def get_books():
    return jsonify(load_db())


@app.route("/scrape", methods=["POST"])
def scrape():
    """POST /scrape  body: { "publishers": ["PhoenixNext"], "force": false }"""
    body = request.get_json(force=True) or {}
    target_pubs = body.get("publishers", list(PUBLISHERS.keys()))
    force_scrape = body.get("force", False)

    db = load_db()
    existing_books = {} if force_scrape else {b["Link"]: b for b in db["books"]}
    new_all = []

    for name in target_pubs:
        if name not in PUBLISHERS:
            continue
        print(f"\n{'='*50}\n  Scraping: {name}\n{'='*50}")
        scraped = scrape_publisher(name, PUBLISHERS[name], existing_books)
        new_all.extend(scraped)
        print(f"  [{name}] รวม {len(scraped)} เล่ม")
        
        for b in scraped:
            existing_books[b["Link"]] = b

    db["books"] = list(existing_books.values())
    save_db(db)

    return jsonify({
        "status":     "ok",
        "books":      db["books"],
        "total":      len(db["books"]),
        "scraped":    len(new_all),
        "publishers": len(target_pubs),
    })


@app.route("/owned", methods=["POST"])
def update_owned():
    body = request.get_json(force=True) or {}
    db = load_db()
    db["owned"] = body.get("owned", db.get("owned", {}))
    save_db(db)
    return jsonify({"status": "ok", "owned_count": sum(1 for v in db["owned"].values() if v)})


@app.route("/clean", methods=["POST"])
def clean_route():
    db = load_db()
    title_count = clean_titles_in_db(db)
    junk_count = remove_junk_from_db(db)
    type_count = update_types_in_db(db)
    save_db(db)
    print(f"[/clean] titles={title_count}, junk={junk_count}, types={type_count}")
    return jsonify({
        "status": "ok",
        "cleaned": title_count,
        "junk_removed": junk_count,
        "types_updated": type_count,
        "total": len(db["books"])
    })


@app.route("/export", methods=["POST"])
def export_excel():
    body = request.get_json(force=True) or {}
    books = body.get("books") or load_db()["books"]
    owned = body.get("owned") or load_db().get("owned", {})

    rows = [{
        "Title":       b.get("Title", ""),
        "Author":      b.get("Author", ""),
        "Illustrator": b.get("Illustrator", ""),
        "Type":        b.get("Type", ""),
        "Publisher":   b.get("Publisher", ""),
        "Genre":       b.get("Genre", ""),
        "Price":       b.get("Price", ""),
        "Owned":       "✓" if owned.get(b.get("Link", "")) else "",
        "Link":        b.get("Link", ""),
        "Image":       b.get("Image", ""),
    } for b in books]

    df = pd.DataFrame(rows)
    df["_ord"] = df["Type"].apply(lambda x: 0 if x == "LN" else 1 if x == "Manga" else 2)
    df = df.sort_values(["_ord", "Title"]).drop(columns=["_ord"])
    path = "my_booklist.xlsx"
    df.to_excel(path, index=False)
    return send_file(path, as_attachment=True, download_name="my_booklist.xlsx")


# ══════════════════════════════════════════════════════
# STANDALONE MODE
# ══════════════════════════════════════════════════════

def run_standalone():
    print("BookShelf Scraper — Standalone Mode")
    print("=" * 50)
    master = []

    for name, cfg in PUBLISHERS.items():
        print(f"\n{'='*50}")
        print(f"  Scraping: {name}")
        print(f"{'='*50}")
        books = scrape_publisher(name, cfg)
        print(f"  [{name}] ✓ ได้ทั้งหมด {len(books)} เล่ม")

        df = pd.DataFrame(books)
        if not df.empty:
            df.to_excel(f"{name}.xlsx", index=False)
            print(f"  → บันทึก {name}.xlsx")

        master.extend(books)

    if master:
        pd.DataFrame(master).to_excel("MASTER.xlsx", index=False)
        print(f"\n✅ DONE — MASTER.xlsx ({len(master)} เล่ม)")

    db = load_db()
    existing = {b["Link"]: b for b in db["books"]}
    for b in master:
        existing[b["Link"]] = {**existing.get(b["Link"], {}), **b}
    db["books"] = list(existing.values())
    save_db(db)
    print(f"  → บันทึก db.json ({len(db['books'])} เล่ม)")


# ══════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--standalone" in sys.argv:
        run_standalone()
    else:
        print("=" * 50)
        print("  BookShelf API  v3.0")
        print("  http://localhost:5000")
        print("=" * 50)
        app.run(debug=False, port=5000, threaded=True)
