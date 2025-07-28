import requests
from bs4 import BeautifulSoup
import json
import re
import time

# Membuat Session object untuk efisiensi, karena akan melakukan beberapa request
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
})

def get_movie_max_page(url="https://samehadaku.now/anime-movie/"):
    """
    Mengambil jumlah total halaman dari halaman movie.
    Hanya perlu dijalankan sekali untuk mendapatkan info.
    """
    try:
        print("🔎 Mencari jumlah halaman movie maksimal...")
        res = session.get(url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'lxml')
        
        # Selector untuk text pagination, cth: "Page 0 of 2"
        pagination_text_tag = soup.select_one("div.pagination > span:first-child")
        
        if pagination_text_tag:
            text = pagination_text_tag.text
            # Mengambil angka terakhir dari teks
            max_page = int(re.findall(r'\d+', text)[-1])
            print(f"✅ Halaman movie maksimal ditemukan: {max_page}")
            return max_page
        else:
            print("⚠️ Pagination tidak ditemukan, mengasumsikan hanya ada 1 halaman.")
            return 1
            
    except Exception as e:
        print(f"❌ Gagal mendapatkan halaman movie maksimal: {e}")
        return 1

def scrape_movie_page(page_number=1):
    """
    Fungsi untuk scrape data movie dari satu halaman spesifik.
    Menerima input nomor halaman dan mengembalikan list data movie.
    """
    base_url = "https://samehadaku.now/anime-movie/"
    
    if page_number == 1:
        target_url = base_url
    else:
        target_url = f"{base_url}page/{page_number}/"
        
    print(f"⚙️  Sedang men-scrape halaman movie {page_number}: {target_url}")

    try:
        res = session.get(target_url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "lxml")
        
        articles = soup.find_all("article", class_="animpost")
        page_data = []

        if not articles:
            print(f"⚠️  Tidak ada movie ditemukan di halaman {page_number}.")
            return []

        # Logika scraping inti Anda ditempatkan di sini
        for article in articles:
            main_link_tag = article.find("a")
            url_movie = main_link_tag["href"] if main_link_tag else "N/A"
            title_tag = article.find("h2", class_="entry-title")
            title = title_tag.text.strip() if title_tag else "N/A"
            cover_tag = article.find("img")
            cover = cover_tag.get("src") if cover_tag else "N/A"
            status_tag = article.select_one("div.data .type")
            status = status_tag.text.strip() if status_tag else "N/A"
            score_tag = article.select_one("span.skor")
            score = score_tag.text.strip() if score_tag else "N/A"
            synopsis_tag = article.select_one("div.ttls")
            synopsis = synopsis_tag.text.strip() if synopsis_tag else "N/A"
            
            views = "N/A"
            metadata_spans = article.select("div.metadata span")
            for span in metadata_spans:
                if "Views" in span.text:
                    views = span.text.strip()
                    break

            genre_tags = article.select("div.genres a")
            genres = [g.text.strip() for g in genre_tags] if genre_tags else []
            
            page_data.append({
                "judul": title, "url": url_movie, "cover": cover,
                "status": status, "skor": score, "sinopsis": synopsis,
                "views": views, "genres": genres
            })
            
        return page_data

    except Exception as e:
        print(f"❌ Gagal men-scrape halaman movie {page_number}: {e}")
        return []




if __name__ == "__main__":
    
    # 1. Dapatkan dulu informasi total halaman yang ada.
    #    Ini bisa Anda simpan (cache) agar tidak perlu dicek setiap saat.
    max_halaman_movie = get_movie_max_page()
    print(f"Total halaman movie yang tersedia adalah: {max_halaman_movie}")
    
    print("\n" + "="*40 + "\n")

    # 2. Sekarang, scrape halaman spesifik sesuai kebutuhan.
    #    Misalnya, user API meminta data dari halaman 2.
    halaman_yang_diminta = 2
    
    if halaman_yang_diminta <= max_halaman_movie:
        data_halaman_movie = scrape_movie_page(page_number=halaman_yang_diminta)
        
        if data_halaman_movie:
            print(f"✅ Berhasil mendapatkan {len(data_halaman_movie)} data movie dari halaman {halaman_yang_diminta}")
            print(json.dumps(data_halaman_movie, indent=4, ensure_ascii=False))
    else:
        print(f"❌ Halaman {halaman_yang_diminta} tidak valid. Halaman maksimal adalah {max_halaman_movie}.")
