from django.shortcuts import render
from .api.home_page import anime_terbaru, movie_movie_samehadaku, sepuluh_anime_mingguan
from django.http import HttpResponse
from .api.anime_detail import detail_anime as anime_detail_module
from .api.anime_terbaru import anime_terbaru as all_anime_terbaru_module
from .api.jadwal_release import jadwal_releas as jadwal_rilis_module
from .api.detail_with_video import detail_video_episode
import asyncio
import concurrent.futures
import requests
from bs4 import BeautifulSoup
from django.core.cache import cache
import time
import functools
from .models import Advertisement
from django.utils import timezone
from django.db import models
from asgiref.sync import sync_to_async

# Fungsi untuk mengambil HTML dari URL
def get_html_content(url, headers=None):
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
    response = requests.get(url, headers=headers)
    return response.content

# Fungsi untuk menjalankan fungsi scraping dengan HTML yang sudah diambil
def run_scraper_with_html(scraper_func, html_content, *args):
    # Membuat soup dari HTML
    soup = BeautifulSoup(html_content, "lxml")
    
    # Memodifikasi fungsi scraper untuk menggunakan soup yang sudah dibuat
    if scraper_func == anime_terbaru.scrape_anime_terbaru:
        return anime_terbaru.scrape_anime_terbaru_with_soup(soup, True)  # Aktifkan get_better_covers
    elif scraper_func == movie_movie_samehadaku.scrape_project_movies:
        return movie_movie_samehadaku.scrape_project_movies_with_soup(soup, True)  # Aktifkan get_better_covers
    elif scraper_func == sepuluh_anime_mingguan.scrape_top_10_anime:
        # Periksa apakah ada argumen tambahan untuk get_better_covers
        get_better_covers = args[0] if args else False
        return sepuluh_anime_mingguan.scrape_top_10_anime_with_soup(soup, get_better_covers)
    elif scraper_func == anime_detail_module.scrape_anime_details:
        # Untuk detail anime, kita perlu meneruskan anime_slug
        anime_slug = args[0] if args else None
        return anime_detail_module.scrape_anime_details_with_soup(soup, anime_slug)
    
    # Fallback jika fungsi tidak dikenali
    return None

# Decorator untuk caching
def async_cache(ttl=60*15, prefix='view_cache_'):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Membuat cache key berdasarkan nama fungsi dan argumen
            cache_key = f"{prefix}{func.__name__}"
            
            # Jika ada argumen, tambahkan ke cache key
            if args:
                cache_key += f"_{args[0]}"
            # Mencoba mendapatkan data dari cache
            cached_data = await cache.aget(cache_key)
            if cached_data:
                return cached_data
            # Jika tidak ada di cache, jalankan fungsi asli
            result = await func(*args, **kwargs)
            # Simpan hasil ke cache
            await cache.aset(cache_key, result, ttl)
            return result
        return wrapper
    return decorator

# Fungsi untuk mendapatkan data anime terbaru dengan caching
@async_cache(ttl=60*10, prefix='anime_terbaru_')
async def get_anime_terbaru(html_content):
    return await asyncio.to_thread(
        run_scraper_with_html,
        anime_terbaru.scrape_anime_terbaru,
        html_content
    )

# Fungsi untuk mendapatkan data movie dengan caching
@async_cache(ttl=60*30, prefix='movie_')
async def get_movie_data(html_content):
    return await asyncio.to_thread(
        run_scraper_with_html,
        movie_movie_samehadaku.scrape_project_movies,
        html_content
    )

# Fungsi untuk mendapatkan data anime mingguan dengan caching
@async_cache(ttl=60*60, prefix='anime_mingguan_')
async def get_anime_mingguan(html_content):
    return await asyncio.to_thread(
        run_scraper_with_html,
        sepuluh_anime_mingguan.scrape_top_10_anime,
        html_content,
        False  # Nonaktifkan get_better_covers karena cover yang ada sudah bagus
    )

# Fungsi untuk mendapatkan detail anime dengan caching
@async_cache(ttl=60*60*24, prefix='anime_detail_')  # Cache selama 24 jam
async def get_anime_detail(anime_slug):
    # Buat cache key yang unik untuk setiap anime_slug
    cache_key = f"anime_detail_{anime_slug}"
    
    # Cek cache terlebih dahulu
    cached_data = await cache.aget(cache_key)
    if cached_data:
        return cached_data
    
    # Jika tidak ada di cache, ambil data baru
    # Bangun URL lengkap di dalam fungsi (tidak terlihat oleh pengguna)
    base_url = "https://samehadaku.now/anime/"
    url = f"{base_url}{anime_slug}/"
    
    # Ambil HTML dari URL
    html_content = await asyncio.to_thread(get_html_content, url)
    
    # Jalankan scraper dengan HTML yang sudah diambil
    result = await asyncio.to_thread(
        run_scraper_with_html,
        anime_detail_module.scrape_anime_details,
        html_content,
        anime_slug
    )
    
    # Simpan hasil ke cache
    await cache.aset(cache_key, result, 60*60*24)  # Cache selama 24 jam
    
    return result

# Create your views here.
async def index(request):
    # Cek cache untuk seluruh halaman dengan versioning
    cache_version = int(time.time() / (60 * 15))  # Versi berubah setiap 15 menit
    cached_data = await cache.aget(f'home_page_data_v{cache_version}')
    
    # Jika tidak ada di cache versi terbaru, coba cek cache standar
    if not cached_data:
        cached_data = await cache.aget('home_page_data')
    
    if cached_data:
        return render(request, 'streamapp/index.html', context=cached_data)
    
    # Ambil HTML dari URL hanya sekali
    url = "https://samehadaku.now/"
    html_content = await asyncio.to_thread(get_html_content, url)
    
    # Jalankan semua fungsi scraping secara asinkron dan paralel
    # Menggunakan asyncio.gather untuk menjalankan semua tugas secara bersamaan
    try:
        anime_terbaru_home, movie_home, anime_mingguan, jadwal_rilis_home = await asyncio.gather(
            get_anime_terbaru(html_content),
            get_movie_data(html_content),
            get_anime_mingguan(html_content),
            get_jadwal_rilis_data()  # Ambil jadwal rilis untuk semua hari
        )
    except Exception as e:
        print(f"Error saat menjalankan scraping secara paralel: {e}")
        # Fallback ke metode sekuensial jika terjadi error
        anime_terbaru_home = await asyncio.to_thread(anime_terbaru.scrape_anime_terbaru, True)  # Aktifkan get_better_covers
        movie_home = await asyncio.to_thread(movie_movie_samehadaku.scrape_project_movies, True)  # Aktifkan get_better_covers
        anime_mingguan = await asyncio.to_thread(sepuluh_anime_mingguan.scrape_top_10_anime, True)  # Aktifkan get_better_covers
        jadwal_rilis_home = await asyncio.to_thread(jadwal_rilis_module.scrape_all_schedules_fast)
    
    # Buat context untuk template
    context = {
        'anime_terbaru': anime_terbaru_home,
        'movie': movie_home,
        'anime_mingguan': anime_mingguan,
        'jadwal_rilis': jadwal_rilis_home,
        'days_of_week': ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    }
    
    # Cache hasil untuk 15 menit
    # Gunakan versioning untuk memudahkan invalidasi cache
    cache_version = int(time.time() / (60 * 15))  # Versi berubah setiap 15 menit
    await cache.aset(f'home_page_data_v{cache_version}', context, 60 * 15)
    
    # Simpan juga dengan kunci standar untuk kompatibilitas
    await cache.aset('home_page_data', context, 60 * 15)
    
    return render(request, 'streamapp/index.html', context=context)

async def detail_anime(request, anime_slug=None):
    # Jika tidak ada anime_slug, kembalikan halaman kosong
    if not anime_slug:
        return render(request, 'streamapp/detail_anime.html', {})
    
    try:
        # Dapatkan detail anime dengan caching
        anime_data = await get_anime_detail(anime_slug)
        
        # Jika data tidak ditemukan, kembalikan halaman kosong
        if not anime_data:
            return render(request, 'streamapp/detail_anime.html', {'error': 'Anime tidak ditemukan'})
        
        # Render template dengan data anime
        context = {
            'anime': anime_data
        }
        
        return render(request, 'streamapp/detail_anime.html', context=context)
    
    except Exception as e:
        print(f"Error saat mendapatkan detail anime: {e}")
        return render(request, 'streamapp/detail_anime.html', {'error': 'Terjadi kesalahan saat memuat data'})
    
    
@async_cache(ttl=60*15, prefix='all_anime_terbaru_')
async def get_all_anime_terbaru_data(page=1, max_pages=5):
    """
    Fungsi untuk mendapatkan data semua anime terbaru dengan caching.
    """
    # Gunakan asyncio.to_thread untuk menjalankan fungsi yang blocking di thread terpisah
    if page > 1:
        # Jika meminta halaman tertentu
        result = await asyncio.to_thread(all_anime_terbaru_module.scrape_anime_page, page)
        return {
            "current_page": page,
            "data": result
        }
    else:
        # Jika meminta semua data dari beberapa halaman
        result = await asyncio.to_thread(all_anime_terbaru_module.get_all_anime_terbaru, max_pages)
        return result

async def all_list_anime_terbaru(request):
    """
    View untuk menampilkan semua anime terbaru dengan pagination.
    """
    # Ambil parameter page dari query string, default ke 1 jika tidak ada
    page = request.GET.get('page', 1)
    try:
        page = int(page)
    except ValueError:
        page = 1
    
    # Ambil parameter max_pages dari query string, default ke 5 jika tidak ada
    max_pages = request.GET.get('max_pages', 5)
    try:
        max_pages = int(max_pages)
    except ValueError:
        max_pages = 5
    
    try:
        # Dapatkan data anime terbaru dengan caching
        anime_data = await get_all_anime_terbaru_data(page, max_pages)
        
        # Buat context untuk template
        context = {
            'anime_data': anime_data,
            'current_page': page,
            'max_pages': max_pages
        }
        
        return render(request, 'streamapp/all_list_anime_terbaru.html', context=context)
    
    except Exception as e:
        print(f"Error saat mendapatkan data anime terbaru: {e}")
        return render(request, 'streamapp/all_list_anime_terbaru.html', {'error': 'Terjadi kesalahan saat memuat data'})
    
    
    
@async_cache(ttl=60*60*3, prefix='jadwal_rilis_')  # Cache selama 3 jam
async def get_jadwal_rilis_data(day=None):
    """
    Fungsi untuk mendapatkan data jadwal rilis dengan caching.
    Jika day=None, ambil jadwal untuk semua hari.
    Jika day diisi, ambil jadwal untuk hari tertentu saja.
    """
    # Gunakan asyncio.to_thread untuk menjalankan fungsi yang blocking di thread terpisah
    if day:
        # Jika meminta jadwal untuk hari tertentu
        result = await asyncio.to_thread(jadwal_rilis_module.get_schedule_for_day, day)
        return {
            "day": day.capitalize(),
            "data": result
        }
    else:
        # Jika meminta jadwal untuk semua hari
        result = await asyncio.to_thread(jadwal_rilis_module.scrape_all_schedules_fast)
        return result

async def all_list_jadwal_rilis(request):
    """
    View untuk menampilkan jadwal rilis anime.
    """
    # Ambil parameter day dari query string, default ke None jika tidak ada
    day = request.GET.get('day', None)
    
    try:
        # Dapatkan data jadwal rilis dengan caching
        jadwal_data = await get_jadwal_rilis_data(day)
        
        # Buat context untuk template
        context = {
            'jadwal_data': jadwal_data,
            'selected_day': day.capitalize() if day else None,
            'days_of_week': ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        }
        
        return render(request, 'streamapp/all_list_jadwal_rilis.html', context=context)
    
    except Exception as e:
        print(f"Error saat mendapatkan data jadwal rilis: {e}")
        return render(request, 'streamapp/all_list_jadwal_rilis.html', {'error': 'Terjadi kesalahan saat memuat data'})
    

from .api.movie_list import movie_list

@async_cache(ttl=60*60*2, prefix='all_movie_')  # Cache selama 2 jam
async def get_all_movie_data(page=1):
    """
    Fungsi untuk mendapatkan data semua movie dengan caching.
    Menggunakan movie_list.py untuk mengambil data dari halaman khusus movie.
    """
    try:
        # Dapatkan jumlah halaman maksimal
        max_pages = await asyncio.to_thread(movie_list.get_movie_max_page)
        
        # Jika halaman yang diminta melebihi jumlah halaman maksimal, gunakan halaman terakhir
        if page > max_pages:
            page = max_pages
        
        # Ambil data movie dari halaman yang diminta
        movie_data = await asyncio.to_thread(movie_list.scrape_movie_page, page)
        
        # Pastikan movie_data tidak None
        if movie_data is None:
            movie_data = []
        
        # Tambahkan anime_slug ke setiap movie
        for movie in movie_data:
            # Ekstrak anime_slug dari URL
            if movie.get('url', "N/A") != "N/A":
                import re
                anime_match = re.search(r'anime/([^/]+)', movie['url'])
                if anime_match:
                    movie['anime_slug'] = anime_match.group(1)
        
        return {
            "current_page": page,
            "total_pages": max_pages,
            "movie_count": len(movie_data),
            "data": movie_data
        }
    except Exception as e:
        print(f"Error saat mendapatkan data movie: {e}")
        return {
            "current_page": page,
            "total_pages": 1,
            "movie_count": 0,
            "data": []
        }

async def all_list_movie(request):
    """
    View untuk menampilkan semua movie dengan pagination.
    """
    # Ambil parameter page dari query string, default ke 1 jika tidak ada
    page = request.GET.get('page', 1)
    try:
        page = int(page)
    except ValueError:
        page = 1
    
    try:
        # Dapatkan data movie dengan caching
        movie_data = await get_all_movie_data(page)
        
        # Buat context untuk template
        context = {
            'movie_data': movie_data,
            'current_page': page
        }
        
        return render(request, 'streamapp/all_list_movie.html', context=context)
    
    except Exception as e:
        print(f"Error saat mendapatkan data movie: {e}")
        return render(request, 'streamapp/all_list_movie.html', {'error': 'Terjadi kesalahan saat memuat data'})
    
    
@async_cache(ttl=60*60*2, prefix='detail_episode_')  # Cache selama 2 jam
async def get_detail_episode_data(episode_url):
    """
    Fungsi untuk mendapatkan data detail episode dengan caching.
    """
    # Buat cache key yang unik untuk setiap episode_url
    cache_key = f"detail_episode_{episode_url.replace('/', '_')}"
    
    # Cek cache terlebih dahulu
    cached_data = await cache.aget(cache_key)
    if cached_data:
        return cached_data
    
    # Jika tidak ada di cache, ambil data baru
    try:
        # Gunakan asyncio.to_thread untuk menjalankan fungsi yang blocking di thread terpisah
        result = await asyncio.to_thread(detail_video_episode.scrape_episode_details, episode_url)
        
        # Simpan hasil ke cache
        if result:
            await cache.aset(cache_key, result, 60*60*2)  # Cache selama 2 jam
        
        return result
    except Exception as e:
        print(f"Error saat mendapatkan detail episode: {e}")
        return None

# Fungsi sinkron untuk mendapatkan iklan aktif
def get_active_ads_sync(position=None):
    """
    Fungsi sinkron untuk mendapatkan iklan yang aktif berdasarkan posisi.
    """
    try:
        now = timezone.now()
        print(f"Current time: {now}")
        
        # Dapatkan semua iklan untuk debugging
        all_ads = list(Advertisement.objects.all())
        print(f"Total iklan di database: {len(all_ads)}")
        for ad in all_ads:
            print(f"Iklan: {ad.name}, Posisi: {ad.position}, Aktif: {ad.is_active}, Start: {ad.start_date}, End: {ad.end_date}")
        
        # Filter iklan yang aktif dan dalam rentang tanggal yang valid
        ads_query = Advertisement.objects.filter(is_active=True)
        print(f"Iklan aktif: {ads_query.count()}")
        
        # Filter berdasarkan tanggal mulai dan berakhir
        date_filtered = ads_query.filter(
            (models.Q(start_date__isnull=True) | models.Q(start_date__lte=now)) &
            (models.Q(end_date__isnull=True) | models.Q(end_date__gte=now))
        )
        print(f"Iklan dalam rentang tanggal valid: {date_filtered.count()}")
        
        # Filter berdasarkan posisi jika ada
        if position:
            position_filtered = date_filtered.filter(position=position)
            print(f"Iklan untuk posisi {position}: {position_filtered.count()}")
        else:
            position_filtered = date_filtered
            print("Tidak ada filter posisi")
        
        # Urutkan berdasarkan prioritas (tinggi ke rendah)
        ordered_ads = position_filtered.order_by('-priority')
        
        # Konversi queryset ke list
        result = list(ordered_ads)
        print(f"Hasil akhir: {len(result)} iklan")
        for ad in result:
            print(f"Iklan hasil: {ad.name}, Posisi: {ad.position}")
        
        return result
    except Exception as e:
        print(f"Error saat mendapatkan iklan aktif: {e}")
        import traceback
        traceback.print_exc()
        return []

# Fungsi asinkron yang memanggil fungsi sinkron menggunakan sync_to_async
async def get_active_ads(position=None):
    """
    Fungsi asinkron untuk mendapatkan iklan yang aktif berdasarkan posisi.
    Menggunakan sync_to_async untuk memanggil fungsi sinkron dari konteks asinkron.
    """
    try:
        # Gunakan sync_to_async untuk memanggil fungsi sinkron dari konteks asinkron
        return await sync_to_async(get_active_ads_sync)(position)
    except Exception as e:
        print(f"Error saat mendapatkan iklan aktif (async): {e}")
        import traceback
        traceback.print_exc()
        return []

async def detail_episode_video(request, episode_slug=None):
    """
    View untuk menampilkan detail episode dengan video player.
    """
    if not episode_slug:
        return render(request, 'streamapp/detail_episode_video.html', {'error': 'Episode tidak ditemukan'})
    
    try:
        # Bangun URL lengkap
        base_url = "https://samehadaku.now/"
        episode_url = f"{base_url}{episode_slug}/"
        
        # Dapatkan data detail episode dengan caching
        episode_data = await get_detail_episode_data(episode_url)
        
        # Jika data tidak ditemukan, kembalikan halaman kosong
        if not episode_data:
            return render(request, 'streamapp/detail_episode_video.html', {'error': 'Episode tidak ditemukan'})
        
        # Dapatkan iklan yang aktif untuk berbagai posisi
        ads = {}
        debug_info = {
            'has_advertisement_model': 'Advertisement' in globals(),
            'positions': [],
            'ads_found': {},
            'errors': []
        }
        
        try:
            # Hanya coba dapatkan iklan jika model Advertisement ada
            if 'Advertisement' in globals():
                print("Model Advertisement ditemukan, mencoba mendapatkan iklan")
                positions = [pos[0] for pos in Advertisement.POSITION_CHOICES]
                debug_info['positions'] = positions
                print(f"Posisi iklan yang tersedia: {positions}")
                
                # Dapatkan semua iklan untuk debugging (menggunakan sync_to_async)
                all_ads = await sync_to_async(list)(Advertisement.objects.all())
                debug_info['total_ads'] = len(all_ads)
                debug_info['all_ads'] = [{'name': ad.name, 'position': ad.position, 'is_active': ad.is_active} for ad in all_ads]
                
                for position in positions:
                    print(f"Mencoba mendapatkan iklan untuk posisi: {position}")
                    position_ads = await get_active_ads(position)
                    debug_info['ads_found'][position] = len(position_ads)
                    
                    if position_ads:
                        # Ambil iklan dengan prioritas tertinggi untuk posisi ini
                        ads[position] = position_ads[0]
                        print(f"Iklan ditemukan untuk posisi {position}: {position_ads[0].name}")
                    else:
                        print(f"Tidak ada iklan untuk posisi {position}")
                
                print(f"Total iklan yang akan ditampilkan: {len(ads)}")
                for pos, ad in ads.items():
                    print(f"Posisi: {pos}, Iklan: {ad.name}, Kode: {ad.ad_code[:30]}...")
            else:
                print("Model Advertisement tidak ditemukan")
                debug_info['errors'].append("Model Advertisement tidak ditemukan")
        except Exception as ad_error:
            print(f"Error saat mendapatkan iklan: {ad_error}")
            import traceback
            traceback.print_exc()
            debug_info['errors'].append(str(ad_error))
            # Jika ada error dengan iklan, tetap lanjutkan tanpa iklan
            ads = {}
        
        # Pastikan episode_data memiliki semua field yang diperlukan
        if not episode_data.get('navigation'):
            episode_data['navigation'] = {}
        
        if not episode_data.get('anime_info'):
            episode_data['anime_info'] = {}
        
        if not episode_data.get('other_episodes'):
            episode_data['other_episodes'] = []
        
        # Render template dengan data episode, iklan, dan debug info
        context = {
            'episode': episode_data,
            'ads': ads,
            'debug_info': debug_info
        }
        
        return render(request, 'streamapp/detail_episode_video.html', context=context)
    
    except Exception as e:
        print(f"Error saat mendapatkan detail episode: {e}")
        return render(request, 'streamapp/detail_episode_video.html', {'error': 'Terjadi kesalahan saat memuat data'})

from .api.search import scrape_search_results_fully

@async_cache(ttl=60*5, prefix='search_')  # Cache selama 5 menit
async def get_search_results(query, max_results=20):
    """
    Fungsi untuk mencari anime berdasarkan query dengan caching.
    """
    # Buat cache key yang unik untuk setiap query
    cache_key = f"search_{query.replace(' ', '_')}"
    
    # Cek cache terlebih dahulu
    cached_data = await cache.aget(cache_key)
    if cached_data:
        return cached_data
    
    # Jika tidak ada di cache, lakukan pencarian menggunakan search.py
    try:
        # Gunakan ThreadPoolExecutor untuk menjalankan fungsi scraping di thread terpisah
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Jalankan fungsi scrape_search_results_fully dari search.py
            search_results = await asyncio.to_thread(scrape_search_results_fully, query)
            
            # Batasi jumlah hasil jika diperlukan
            if search_results and len(search_results) > max_results:
                search_results = search_results[:max_results]
            
            # Tambahkan anime_slug ke setiap hasil jika search_results tidak None
            if search_results:
                for result in search_results:
                    # Ekstrak anime_slug dari URL
                    import re
                    anime_slug = ""
                    if result.get('url_anime', "N/A") != "N/A":
                        anime_match = re.search(r'anime/([^/]+)', result['url_anime'])
                        if anime_match:
                            result['anime_slug'] = anime_match.group(1)
                        else:
                            result['anime_slug'] = ""
        
        # Simpan hasil ke cache
        await cache.aset(cache_key, search_results, 60*5)  # Cache selama 5 menit
        
        return search_results
    
    except Exception as e:
        print(f"Error saat melakukan pencarian: {e}")
        return []

async def search(request):
    """
    View untuk menampilkan hasil pencarian.
    """
    # Ambil parameter query dari query string
    query = request.GET.get('q', '')
    
    # Jika query kosong, kembalikan halaman kosong
    if not query:
        return render(request, 'streamapp/search_results.html', {'query': query, 'results': []})
    
    try:
        # Dapatkan hasil pencarian dengan caching dan multi-threading
        search_results = await get_search_results(query)
        
        # Buat context untuk template
        context = {
            'query': query,
            'results': search_results if search_results else [],
            'result_count': len(search_results) if search_results else 0
        }
        
        return render(request, 'streamapp/search_results.html', context=context)
    
    except Exception as e:
        print(f"Error saat menampilkan hasil pencarian: {e}")
        return render(request, 'streamapp/search_results.html', {'query': query, 'error': 'Terjadi kesalahan saat memuat data'})

async def user_collection(request):
    """
    View untuk menampilkan koleksi pengguna (watchlist, favorites, dan watch history).
    Data disimpan di localStorage di sisi klien, jadi view ini hanya menampilkan template.
    """
    try:
        # Render template tanpa data khusus
        return render(request, 'streamapp/user_collection.html')
    except Exception as e:
        print(f"Error saat menampilkan koleksi pengguna: {e}")
        return HttpResponse("Terjadi kesalahan saat memuat halaman koleksi pengguna", status=500)