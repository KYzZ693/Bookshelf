import requests

r = requests.get('http://localhost:5000/books')
data = r.json()
manga = [b for b in data['books'] if b.get('Type') == 'Manga']

print(f"Manga books: {len(manga)}")
for b in manga[:10]:
    print(f"  - {b['Title']}")
