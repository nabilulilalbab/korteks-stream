import requests
from bs4 import BeautifulSoup
import json
import re # Modul untuk regular expression, berguna untuk mencari angka
import concurrent.futures
import functools
from django.core.cache import cache

# Membuat Session object lebih efisien untuk beberapa request
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
})

# Decorator untuk caching
def cache_result(ttl=60*60):  # Cache selama 1 jam
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Membuat cache key berdasarkan nama fungsi dan argumen
            cache_key = f"anime_terbaru_cache_{func.__name__}"
            
            # Jika ada argumen, tambahkan ke cache key
            if args:
                cache_key += f"_{args[0]}"
            
            # Mencoba mendapatkan data dari cache
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
            
            # Jika tidak ada di cache, jalankan fungsi asli
            result = func(*args, **kwargs)
            
            # Simpan hasil ke cache
            cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

@cache_result(ttl=60*30)  # Cache selama 30 menit
def get_max_page(url="https://samehadaku.now/anime-terbaru/"):
    """
    Mengunjungi halaman pertama untuk mencari tahu jumlah total halaman.
    Mengembalikan integer jumlah halaman maksimal.
    """
    try:
        print("🔎 Mencari jumlah halaman maksimal...")
        res = session.get(url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'lxml')
        
        # Mencari tag span yang berisi teks "Page x of y"
        pagination_text_tag = soup.select_one("div.pagination > span:first-child")
        
        if pagination_text_tag:
            # Contoh teks: "Page 1 of 649"
            text = pagination_text_tag.text
            # Mengambil angka terakhir dari teks menggunakan regex
            max_page = int(re.findall(r'\d+', text)[-1])
            print(f"✅ Halaman maksimal ditemukan: {max_page}")
            return max_page
        else:
            print("⚠️ Pagination tidak ditemukan, mengasumsikan hanya ada 1 halaman.")
            return 1
            
    except Exception as e:
        print(f"❌ Gagal mendapatkan halaman maksimal: {e}")
        return 1 # Mengembalikan 1 jika terjadi error

@cache_result(ttl=60*15)  # Cache selama 15 menit
def scrape_anime_page(page_number=1):
    """
    Fungsi untuk men-scrape data anime dari satu halaman spesifik.
    Menerima input nomor halaman, mengembalikan list berisi data anime.
    """
    base_url = "https://samehadaku.now/anime-terbaru/"
    
    if page_number == 1:
        target_url = base_url
    else:
        target_url = f"{base_url}page/{page_number}/"
        
    print(f"⚙️  Sedang men-scrape halaman {page_number}: {target_url}")

    try:
        res = session.get(target_url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "lxml")
        
        articles = soup.select("div.post-show li")
        page_data = []

        if not articles:
            print(f"⚠️  Tidak ada anime ditemukan di halaman {page_number}.")
            return []

        for article in articles:
            title_tag = article.select_one("h2.entry-title a")
            cover_tag = article.select_one("img.npws")
            spans = article.select("div.dtla > span")

            title = title_tag.text.strip() if title_tag else "N/A"
            anime_url = title_tag["href"] if title_tag else "N/A"
            cover_url = cover_tag["src"] if cover_tag and cover_tag.has_attr("src") else "N/A"
            
            episode_tag = spans[0].find("author") if len(spans) > 0 else None
            episode = episode_tag.text.strip() if episode_tag else "N/A"

            uploader_tag = spans[1].find("author") if len(spans) > 1 else None
            uploader = uploader_tag.text.strip() if uploader_tag else "N/A"

            release_tag = spans[2] if len(spans) > 2 else None
            release_time = release_tag.text.replace("Released on:", "").strip() if release_tag else "N/A"

            # Ekstrak anime_slug dari URL
            anime_slug = None
            if anime_url != "N/A":
                # Pastikan anime_url adalah string
                anime_url_str = str(anime_url)
                anime_match = re.search(r'anime/([^/]+)', anime_url_str)
                if anime_match:
                    anime_slug = anime_match.group(1)
                else:
                    episode_match = re.search(r'([^/]+)-episode-\d+', anime_url_str)
                    if episode_match:
                        anime_slug = episode_match.group(1)

            page_data.append({
                "judul": title,
                "episode": episode,
                "uploader": uploader,
                "waktu_rilis": release_time,
                "url_episode": anime_url,
                "url_cover": cover_url,
                "anime_slug": anime_slug
            })
        
        return page_data

    except Exception as e:
        print(f"❌ Gagal men-scrape halaman {page_number}: {e}")
        return []

def scrape_multiple_pages(start_page=1, end_page=5):
    """
    Fungsi untuk men-scrape beberapa halaman secara paralel menggunakan multi-threading.
    Menerima input halaman awal dan akhir, mengembalikan list berisi data anime dari semua halaman.
    """
    all_data = []
    
    # Gunakan ThreadPoolExecutor untuk menjalankan scraping secara paralel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Buat tugas untuk setiap halaman
        future_to_page = {executor.submit(scrape_anime_page, page): page for page in range(start_page, end_page + 1)}
        
        # Kumpulkan hasil
        for future in concurrent.futures.as_completed(future_to_page):
            page = future_to_page[future]
            try:
                page_data = future.result()
                if page_data:
                    all_data.extend(page_data)
                    print(f"✅ Berhasil mendapatkan {len(page_data)} data dari halaman {page}")
            except Exception as e:
                print(f"❌ Error saat mengambil data halaman {page}: {e}")
    
    return all_data

@cache_result(ttl=60*15)  # Cache selama 15 menit
def get_all_anime_terbaru(max_pages=5):
    """
    Fungsi untuk mendapatkan semua anime terbaru dari beberapa halaman.
    Menggunakan caching untuk meningkatkan performa.
    """
    # Dapatkan jumlah halaman maksimal
    total_pages = get_max_page()
    
    # Batasi jumlah halaman yang diambil
    pages_to_fetch = min(max_pages, total_pages)
    
    # Ambil data dari beberapa halaman secara paralel
    all_anime_data = scrape_multiple_pages(1, pages_to_fetch)
    
    return {
        "total_pages": total_pages,
        "pages_fetched": pages_to_fetch,
        "anime_count": len(all_anime_data),
        "data": all_anime_data
    }

# --- CONTOH PENGGUNAAN ---
if __name__ == "__main__":
    
    # Contoh 1: Hanya ingin tahu ada berapa total halaman
    max_halaman = get_max_page()
    print(f"Total halaman yang tersedia adalah: {max_halaman}")
    
    print("\n" + "="*40 + "\n")

    # Contoh 2: User API meminta data dari halaman 5
    halaman_yang_diminta = 5
    data_halaman_5 = scrape_anime_page(halaman_yang_diminta)
    
    if data_halaman_5:
        print(f"✅ Berhasil mendapatkan {len(data_halaman_5)} data dari halaman {halaman_yang_diminta}")
        print(json.dumps(data_halaman_5, indent=4, ensure_ascii=False))
    
    print("\n" + "="*40 + "\n")
    
    # Contoh 3: Mengambil data dari beberapa halaman secara paralel
    print("Mengambil data dari 3 halaman pertama secara paralel...")
    all_data = scrape_multiple_pages(1, 3)
    print(f"✅ Total data yang berhasil diambil: {len(all_data)}")
