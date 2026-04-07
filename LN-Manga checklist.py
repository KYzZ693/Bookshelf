import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from tqdm import tqdm

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================
# CONFIG (เพิ่มเว็บทีหลังได้)
# =========================
PUBLISHERS = {
    "PhoenixNext": {
        "base": "https://www.phoenixnext.com",
        "ln": "/light-novel.html",
        "manga": "/manga.html"
    }
}

# =========================
# CORE SCRAPER
# =========================
def get_items(url):
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    items = soup.select(".product-item")
    data = []

    for item in items:
        try:
            title = item.select_one(".product-item-link").text.strip()
            link = item.select_one(".product-item-link")["href"]

            price_tag = item.select_one(".price")
            price = price_tag.text.strip() if price_tag else ""

            img = item.select_one("img")["src"]

            data.append({
                "Genre": "",
                "Image": img,
                "Title": title,
                "Author": "",
                "Illustrator": "",
                "Price": price,
                "Link": link,
                "Owned": False
            })
        except:
            continue

    return data

def get_detail(link):
    try:
        res = requests.get(link, headers=HEADERS)
        soup = BeautifulSoup(res.text, "html.parser")

        text = soup.get_text()

        author = ""
        illustrator = ""
        genre = ""

        if "ผู้เขียน" in text:
            author = text.split("ผู้เขียน")[1].split("\n")[1].strip()

        if "ภาพประกอบ" in text:
            illustrator = text.split("ภาพประกอบ")[1].split("\n")[1].strip()

        return author, illustrator, genre

    except:
        return "", "", ""


def scrape_all(base, path, type_name):
    results = []
    page = 1

    while True:
        url = f"{base}{path}?p={page}"
        print("Scraping:", url)

        items = get_items(url)
        if not items:
            break
        
        for i in items:
            author, illustrator, genre = get_detail(i["Link"])

            i["Author"] = author
            i["Illustrator"] = illustrator
            i["Genre"] = genre

        for i in items:
            i["Type"] = type_name

        results.extend(items)
        page += 1
        time.sleep(1)

    return results


# =========================
# EXPORT
# =========================
def export_excel(data, filename):
    df = pd.DataFrame(data)

    # เรียง LN ก่อน
    df["Order"] = df["Type"].apply(lambda x: 0 if x == "LN" else 1)
    df = df.sort_values(by=["Order", "Title"])
    df.drop(columns=["Order"], inplace=True)

    df.to_excel(filename, index=False)


# =========================
# MAIN
# =========================
def main():
    master = []

    for name, cfg in PUBLISHERS.items():
        print(f"\n===== {name} =====")

        ln = scrape_all(cfg["base"], cfg["ln"], "LN")
        manga = scrape_all(cfg["base"], cfg["manga"], "Manga")

        all_data = ln + manga

        # export แยก
        export_excel(all_data, f"{name}.xlsx")

        # เพิ่ม publisher ลง master
        for d in all_data:
            d["Publisher"] = name
            master.append(d)

    # export รวม
    df = pd.DataFrame(master)
    df.to_excel("MASTER.xlsx", index=False)

    print("\n✅ DONE ALL")

if __name__ == "__main__":
    main()

print(title)