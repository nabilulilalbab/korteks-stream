import requests
from bs4 import BeautifulSoup
import re
import sys
import os
import concurrent.futures
import functools
from django.core.cache import cache

# Tambahkan path ke direktori parent untuk mengimpor detail_anime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from anime_detail import detail_anime

# Decorator untuk caching
def cache_result(ttl=60*60*24):  # Cache selama 24 jam
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Membuat cache key berdasarkan nama fungsi dan argumen
            cache_key = f"cover_cache_{func.__name__}_{args[0]}"
            
            # Mencoba mendapatkan data dari cache
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
            
            # Jika tidak ada di cache, jalankan fungsi asli
            result = func(*args, **kwargs)
            
            # Simpan hasil ke cache
            if result:
                cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

def extract_anime_slug_from_url(url):
    """
    Ekstrak anime_slug dari URL anime atau episode
    """
    # Coba ekstrak slug dari URL anime
    anime_match = re.search(r'anime/([^/]+)', url)
    if anime_match:
        return anime_match.group(1)
    
    # Jika bukan URL anime, coba ekstrak dari URL episode
    episode_match = re.search(r'([^/]+)-episode-\d+', url)
    if episode_match:
        return episode_match.group(1)
    
    # Jika tidak ada yang cocok, kembalikan None
    return None

@cache_result()
def get_better_cover(anime_slug):
    """
    Mendapatkan cover yang lebih bagus dari detail anime
    dengan caching untuk meningkatkan performa
    """
    try:
        # Bangun URL detail anime
        url = f"https://samehadaku.now/anime/{anime_slug}/"
        
        # Dapatkan detail anime
        anime_details = detail_anime.scrape_anime_details(url)
        
        # Jika berhasil, kembalikan cover dari detail anime
        if anime_details and anime_details.get('thumbnail_url') and anime_details['thumbnail_url'] != "N/A":
            return anime_details['thumbnail_url']
    except Exception as e:
        print(f"Error saat mendapatkan cover yang lebih bagus: {e}")
    
    # Jika gagal, kembalikan None
    return None

def scrape_anime_terbaru_with_soup(soup, get_better_covers=True):
    """
    Versi fungsi scrape_anime_terbaru yang menerima objek BeautifulSoup
    sebagai parameter untuk menghindari pengambilan HTML berulang kali.
    
    :param soup: Objek BeautifulSoup yang sudah diinisialisasi
    :param get_better_covers: Jika True, akan mencoba mendapatkan cover yang lebih bagus dari detail anime
    :return: List anime terbaru
    """
    anime_terbaru_list = []

    items = soup.select(".post-show ul li")

    for li in items:
        title_el = li.select_one("h2.entry-title a")
        episode_el = li.select_one("span:contains('Episode')")
        posted_by_el = li.select_one(".author author")
        posted_by_fallback = li.select_one(".author vcard author")
        posted_by = posted_by_el.text.strip() if posted_by_el else (posted_by_fallback.text.strip() if posted_by_fallback else "-")
        released_on = li.select_one("span:contains('Released on')")
        
        url = title_el["href"] if title_el else "-"
        cover = li.select_one("img")["src"] if li.select_one("img") else "-"

        anime = {
            "judul": title_el.text.strip() if title_el else "-",
            "url": url,
            "cover": cover,
            "episode": episode_el.text.strip() if episode_el else "-",
            "posted_by": posted_by,
            "rilis": released_on.text.strip().replace("Released on", "").strip() if released_on else "-"
        }

        anime_terbaru_list.append(anime)

    # Jika get_better_covers=True, coba dapatkan cover yang lebih bagus untuk setiap anime
    if get_better_covers:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Buat tugas untuk setiap anime
            future_to_anime = {}
            for i, anime in enumerate(anime_terbaru_list):
                anime_slug = extract_anime_slug_from_url(anime['url'])
                if anime_slug:
                    future = executor.submit(get_better_cover, anime_slug)
                    future_to_anime[future] = i
            
            # Kumpulkan hasil
            for future in concurrent.futures.as_completed(future_to_anime):
                i = future_to_anime[future]
                try:
                    better_cover = future.result()
                    if better_cover:
                        anime_terbaru_list[i]['cover'] = better_cover
                except Exception as e:
                    print(f"Error saat mendapatkan cover yang lebih bagus: {e}")

    return anime_terbaru_list

def scrape_anime_terbaru(get_better_covers=True):
    """
    Fungsi original yang mengambil HTML dan melakukan scraping.
    Sekarang menggunakan scrape_anime_terbaru_with_soup untuk menghindari duplikasi kode.
    
    :param get_better_covers: Jika True, akan mencoba mendapatkan cover yang lebih bagus dari detail anime
    :return: List anime terbaru
    """
    url = "https://samehadaku.now/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "lxml")
    
    return scrape_anime_terbaru_with_soup(soup, get_better_covers)

# print(scrape_anime_terbaru())