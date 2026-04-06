from scraper import detect_book_type
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

tests = [
    ('(มังงะ) สกิลโกงไร้เทียมทาน', 'LN', 'Manga'),
    ('มังงะวันพีซ', 'LN', 'Manga'),
    ('[มังงะ] นารูโตะ', 'LN', 'Manga'),
    ('(Manga) Attack on Titan', 'LN', 'Manga'),
    ('(N) เรืองรัก', 'LN', 'LN'),
    ('N123', 'LN', 'LN'),
    ('(AB) Art Book', 'LN', 'Artbook'),
    ('AB123', 'LN', 'Artbook'),
    ('(Artbook) Collection', 'LN', 'Artbook'),
    ('ดาบพิฆาต', 'LN', 'LN'),
    ('(Light Novel) Overlord', 'LN', 'LN'),
]

print("Testing detect_book_type:")
for title, existing, expected in tests:
    result = detect_book_type(title, existing)
    status = "OK" if result == expected else "FAIL"
    print(f"  [{status}] '{title}' -> {result} (expected: {expected})")
