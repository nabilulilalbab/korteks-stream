
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import time
from concurrent.futures import ThreadPoolExecutor

# Import modul scraper Anda
from .jadwal_release import jadwal_releas
from .anime_terbaru import anime_terbaru
from .movie_list import movie_list
from .anime_detail import detail_anime
from .detail_with_video import detail_video_episode
from .home_page import sepuluh_anime_mingguan, anime_terbaru as home_anime_terbaru, movie_movie_samehadaku
from .search import scrape_search_results_fully

app = FastAPI()

# --- Caching System ---
cache = {}
CACHE_DURATION = 600  # Cache expires in 600 seconds (10 minutes)

def get_from_cache_or_fetch(key, fetch_func, *args, **kwargs):
    current_time = time.time()
    if key in cache and (current_time - cache[key]['timestamp']) < CACHE_DURATION:
        print(f"CACHE HIT: Mengambil data dari cache untuk key: {key}")
        return cache[key]['data']

    print(f"CACHE MISS: Melakukan fetch baru untuk key: {key}")
    try:
        data = fetch_func(*args, **kwargs)
        if data:
            cache[key] = {'timestamp': current_time, 'data': data}
        return data
    except Exception as e:
        print(f"Error saat fetching {key}: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal mengambil data dari sumber: {e}")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/static", StaticFiles(directory="static"), name="static")
# --- Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        with open("static/index.html") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="index.html tidak ditemukan")

@app.get("/api/jadwal-rilis")
async def get_jadwal_rilis_cached():
    return get_from_cache_or_fetch("jadwal_rilis", jadwal_releas.scrape_all_schedules_fast)

@app.get("/api/anime-terbaru")
async def get_anime_terbaru_cached(page: int = 1):
    return get_from_cache_or_fetch(f"anime_terbaru_{page}", anime_terbaru.scrape_anime_page, page)

@app.get("/api/movie")
async def get_movie_list_cached(page: int = 1):
    return get_from_cache_or_fetch(f"movie_list_{page}", movie_list.scrape_movie_page, page)

@app.get("/api/anime-detail")
async def get_anime_detail_cached(url: str):
    return get_from_cache_or_fetch(f"detail_{url}", detail_anime.scrape_anime_details, url)

@app.get("/api/episode-detail")
async def get_episode_detail_cached(url: str):
    # Episode details change less often, but we still cache them
    return get_from_cache_or_fetch(f"episode_{url}", detail_video_episode.scrape_episode_details, url)

@app.get("/api/search")
async def search_anime(query: str):
    if not query:
        raise HTTPException(status_code=400, detail="Parameter 'query' tidak boleh kosong.")
    
    # Menggunakan cache untuk hasil pencarian
    cache_key = f"search_{query}"
    return get_from_cache_or_fetch(cache_key, scrape_search_results_fully, query)

# --- Homepage Endpoint with Concurrency ---
def fetch_home_sections():
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_top10 = executor.submit(get_from_cache_or_fetch, "home_top10", sepuluh_anime_mingguan.scrape_top_10_anime)
        future_new_eps = executor.submit(get_from_cache_or_fetch, "home_new_eps", home_anime_terbaru.scrape_anime_terbaru)
        future_movies = executor.submit(get_from_cache_or_fetch, "home_movies", movie_movie_samehadaku.scrape_project_movies)

        return {
            "top10": future_top10.result(),
            "new_eps": future_new_eps.result(),
            "movies": future_movies.result()
        }

@app.get("/api/home")
async def get_home_page_data_concurrently():
    return fetch_home_sections()

