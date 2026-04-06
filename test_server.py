import requests
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

API_BASE = 'http://localhost:5000'

print("Testing API connection...")
try:
    # Test /books endpoint
    r = requests.get(f'{API_BASE}/books', timeout=5)
    print(f'✓ /books Status: {r.status_code}')
    data = r.json()
    print(f'✓ Books: {len(data.get("books", []))}')
    print(f'✓ Owned: {len(data.get("owned", {}))}')
    
    # Test /scrape endpoint
    print('\nTesting /scrape endpoint...')
    r = requests.post(f'{API_BASE}/scrape', 
                     json={'publishers': ['PhoenixNext']}, 
                     timeout=10)
    print(f'✓ /scrape Status: {r.status_code}')
    
    print('\n✅ API Server is working correctly!')
    
except requests.exceptions.ConnectionError:
    print('❌ Cannot connect to API server!')
    print('\nSolution:')
    print('  1. Run: python scraper.py')
    print('  2. Wait for "Running on http://127.0.0.1:5000"')
    print('  3. Refresh the web page')
except Exception as e:
    print(f'❌ Error: {e}')
