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

def scrape_project_movies_with_soup(soup, get_better_covers=True):
    """
    Versi fungsi scrape_project_movies yang menerima objek BeautifulSoup
    sebagai parameter untuk menghindari pengambilan HTML berulang kali.
    
    :param soup: Objek BeautifulSoup yang sudah diinisialisasi
    :param get_better_covers: Jika True, akan mencoba mendapatkan cover yang lebih bagus dari detail anime
    :return: List movie
    """
    # Temukan div.widgets yang punya h3 "Project Movie Samehadaku"
    project_section = None
    for section in soup.select("div.widgets"):
        h3 = section.find("h3")
        if h3 and "Project Movie Samehadaku" in h3.text:
            project_section = section
            break

    # Ambil movie list hanya dari section ini
    project_movies = []
    if project_section:
        movie_list = project_section.select("div.widgetseries ul > li")
        
        for li in movie_list:
            # Judul dan URL
            title_el = li.select_one("h2 > a.series")
            title = title_el.text.strip() if title_el else "-"
            url_movie = title_el["href"] if title_el and title_el.has_attr("href") else "-"

            # Cover
            cover_el = li.select_one("img")
            cover = cover_el["src"] if cover_el and cover_el.has_attr("src") else "-"

            # Genre
            genres_span = li.find("span")
            genres = []
            if genres_span:
                genres = [a.text.strip() for a in genres_span.find_all("a")]

            # Tanggal rilis (span terakhir)
            tanggal_span = li.find_all("span")[-1]
            tanggal = tanggal_span.text.strip() if tanggal_span else "-"

            project_movies.append({
                "judul": title,
                "url": url_movie,
                "cover": cover,
                "genres": genres,
                "tanggal": tanggal
            })

    # Jika get_better_covers=True, coba dapatkan cover yang lebih bagus untuk setiap movie
    if get_better_covers and project_movies:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Buat tugas untuk setiap movie
            future_to_movie = {}
            for i, movie in enumerate(project_movies):
                anime_slug = extract_anime_slug_from_url(movie['url'])
                if anime_slug:
                    future = executor.submit(get_better_cover, anime_slug)
                    future_to_movie[future] = i
            
            # Kumpulkan hasil
            for future in concurrent.futures.as_completed(future_to_movie):
                i = future_to_movie[future]
                try:
                    better_cover = future.result()
                    if better_cover:
                        project_movies[i]['cover'] = better_cover
                except Exception as e:
                    print(f"Error saat mendapatkan cover yang lebih bagus: {e}")

    return project_movies

def scrape_project_movies(get_better_covers=True):
    """
    Fungsi original yang mengambil HTML dan melakukan scraping.
    Sekarang menggunakan scrape_project_movies_with_soup untuk menghindari duplikasi kode.
    
    :param get_better_covers: Jika True, akan mencoba mendapatkan cover yang lebih bagus dari detail anime
    :return: List movie
    """
    url = "https://samehadaku.now/"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "lxml")
    
    return scrape_project_movies_with_soup(soup, get_better_covers)

# if __name__ == "__main__":
#     print(scrape_project_movies())