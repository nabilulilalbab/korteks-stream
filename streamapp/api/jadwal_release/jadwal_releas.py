import requests
import json
import time
import functools
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.cache import cache

# Decorator untuk caching
def cache_result(ttl=60*60*24):  # Cache selama 24 jam
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Membuat cache key berdasarkan nama fungsi dan argumen
            cache_key = f"jadwal_rilis_cache_{func.__name__}"
            
            # Jika ada argumen, tambahkan ke cache key
            if args and len(args) > 1:
                cache_key += f"_{args[1]}"  # args[1] adalah day
            
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
def fetch_schedule_for_day(session, day):
    """
    Mengambil dan memproses jadwal rilis untuk satu hari spesifik.
    """
    api_url = f"https://samehadaku.now/wp-json/custom/v1/all-schedule?perpage=100&day={day}"
    try:
        res = session.get(api_url)
        res.raise_for_status()
        
        daily_schedule_raw = res.json()
        
        cleaned_schedule = []
        for item in daily_schedule_raw:
            genres_raw = item.get("genre", "")
            genres_list = []
            if genres_raw and genres_raw != "N/A":
                genres_list = [g.strip() for g in genres_raw.split(',')]

            # Ekstrak anime_slug dari URL
            anime_slug = None
            url = item.get("url", "N/A")
            if url != "N/A":
                import re
                anime_match = re.search(r'anime/([^/]+)', url)
                if anime_match:
                    anime_slug = anime_match.group(1)

            cleaned_schedule.append({
                "title": item.get("title", "N/A"),
                "url": url,
                "cover_url": item.get("featured_img_src", "N/A"),
                "type": item.get("east_type", "N/A"),
                "score": item.get("east_score", "N/A"),
                "genres": genres_list,
                "release_time": item.get("east_time", "N/A"),
                "anime_slug": anime_slug
            })
        print(f"  -> Jadwal untuk hari {day.capitalize()} selesai diproses.")
        return day, cleaned_schedule
    except requests.exceptions.RequestException as e:
        print(f"❌ Gagal mengambil jadwal untuk hari {day}: {e}")
        return day, []

@cache_result(ttl=60*60*3)  # Cache selama 3 jam
def scrape_all_schedules_fast():
    """
    Mengambil jadwal rilis anime untuk semua hari secara bersamaan (concurrent).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    }
    session = requests.Session()
    session.headers.update(headers)

    days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    full_schedule = {}

    print("⚙️  Memulai pengambilan jadwal rilis untuk semua hari secara paralel...")

    with ThreadPoolExecutor(max_workers=7) as executor:
        # Menjadwalkan semua tugas untuk dieksekusi
        future_to_day = {executor.submit(fetch_schedule_for_day, session, day): day for day in days_of_week}
        
        # Mengumpulkan hasil saat tugas selesai
        for future in as_completed(future_to_day):
            day, schedule_data = future.result()
            full_schedule[day.capitalize()] = schedule_data

    # Mengurutkan hasil akhir sesuai urutan hari
    sorted_schedule = {day.capitalize(): full_schedule[day.capitalize()] for day in days_of_week}
    return sorted_schedule

def get_schedule_for_day(day):
    """
    Mengambil jadwal rilis untuk satu hari tertentu.
    """
    if day.lower() not in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        return []
    
    # Coba ambil dari cache jadwal lengkap terlebih dahulu
    full_schedule = cache.get("jadwal_rilis_cache_scrape_all_schedules_fast")
    if full_schedule and day.capitalize() in full_schedule:
        return full_schedule[day.capitalize()]
    
    # Jika tidak ada di cache, ambil jadwal untuk hari tertentu saja
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    }
    session = requests.Session()
    session.headers.update(headers)
    
    _, schedule_data = fetch_schedule_for_day(session, day.lower())
    return schedule_data

# --- CONTOH PENGGUNAAN ---
if __name__ == "__main__":
    start_time = time.time()
    jadwal_lengkap = scrape_all_schedules_fast()
    end_time = time.time()

    if jadwal_lengkap:
        print("\n✅ Jadwal rilis lengkap berhasil di-scrape!")
        print(json.dumps(jadwal_lengkap, indent=4, ensure_ascii=False))
        print(f"\n🚀 Selesai dalam {end_time - start_time:.2f} detik")
