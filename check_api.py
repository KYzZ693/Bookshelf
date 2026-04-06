import requests

r = requests.get('http://localhost:5000/books')
data = r.json()
print(f"Books: {len(data.get('books', []))}")
if data.get('books'):
    print(f"First 3 books:")
    for b in data['books'][:3]:
        print(f"  - {b['Title']}")
