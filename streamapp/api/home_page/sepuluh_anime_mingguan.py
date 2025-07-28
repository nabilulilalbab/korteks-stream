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

def scrape_top_10_anime_with_soup(soup, get_better_covers=False):
    """
    Versi fungsi scrape_top_10_anime yang menerima objek BeautifulSoup
    sebagai parameter untuk menghindari pengambilan HTML berulang kali.
    
    :param soup: Objek BeautifulSoup yang sudah diinisialisasi
    :param get_better_covers: Jika True, akan mencoba mendapatkan cover yang lebih bagus dari detail anime
                             (Dinonaktifkan secara default karena cover yang ada sudah bagus)
    :return: List top 10 anime mingguan
    """
    top_anime_list = []

    top10_block = soup.select_one(".topten-animesu")
    if top10_block:
        for li in top10_block.select("li"):
            title = li.select_one(".judul")
            rating = li.select_one(".rating")
            link = li.select_one("a.series")
            img = li.select_one("img")

            anime_data = {
                "judul": title.text.strip() if title else "-",
                "rating": rating.text.strip() if rating else "-",
                "url": link['href'] if link else "-",
                "cover": img['src'] if img and img.has_attr("src") else "-"
            }

            # Ekstrak anime_slug dari URL untuk digunakan di template
            anime_slug = extract_anime_slug_from_url(anime_data['url'])
            if anime_slug:
                anime_data['anime_slug'] = anime_slug

            top_anime_list.append(anime_data)

    # Fitur get_better_covers dinonaktifkan karena cover yang ada sudah bagus
    # dan untuk menghindari error saat dijalankan langsung dari command line
    # Kode di bawah ini hanya akan dijalankan jika get_better_covers=True dan
    # sedang berjalan di dalam Django (bukan dari command line)
    if get_better_covers:
        try:
            # Cek apakah Django settings sudah dikonfigurasi
            from django.conf import settings
            if not settings.configured:
                return top_anime_list
                
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # Buat tugas untuk setiap anime
                future_to_anime = {}
                for i, anime in enumerate(top_anime_list):
                    anime_slug = anime.get('anime_slug') or extract_anime_slug_from_url(anime['url'])
                    if anime_slug:
                        future = executor.submit(get_better_cover, anime_slug)
                        future_to_anime[future] = i
                
                # Kumpulkan hasil
                for future in concurrent.futures.as_completed(future_to_anime):
                    i = future_to_anime[future]
                    try:
                        better_cover = future.result()
                        if better_cover:
                            top_anime_list[i]['cover'] = better_cover
                    except Exception as e:
                        print(f"Error saat mendapatkan cover yang lebih bagus: {e}")
        except ImportError:
            # Jika tidak bisa mengimpor Django settings, berarti sedang berjalan di luar Django
            pass

    return top_anime_list

def scrape_top_10_anime(get_better_covers=True):
    """
    Fungsi original yang mengambil HTML dan melakukan scraping.
    Sekarang menggunakan scrape_top_10_anime_with_soup untuk menghindari duplikasi kode.
    
    :param get_better_covers: Jika True, akan mencoba mendapatkan cover yang lebih bagus dari detail anime
    :return: List top 10 anime mingguan
    """
    url = "https://samehadaku.now/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "lxml")
    
    return scrape_top_10_anime_with_soup(soup, get_better_covers)

if __name__ == "__main__":
    print(scrape_top_10_anime())