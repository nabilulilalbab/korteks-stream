import requests
from bs4 import BeautifulSoup
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
def fetch_stream_url(session, ajax_url, payload, headers):
    """Fungsi kecil untuk mengambil satu link streaming."""
    try:
        ajax_res = session.post(ajax_url, data=payload, headers=headers)
        ajax_res.raise_for_status()
        embed_html = ajax_res.text
        embed_soup = BeautifulSoup(embed_html, 'lxml')
        iframe = embed_soup.find("iframe")
        if iframe and iframe.has_attr('src'):
            return iframe['src']
    except Exception:
        return None
    return None

def scrape_episode_details(url):
    """
    Scrape semua detail episode secara efisien menggunakan concurrency.
    """
    headers = {"User-Agent": "Mozilla/5.0 ..."} # User-Agent Anda
    session = requests.Session()
    
    print(f"⚙️  Langkah 1: Mengambil data awal dari: {url}")
    try:
        initial_res = session.get(url, headers=headers)
        initial_res.raise_for_status()
        soup = BeautifulSoup(initial_res.text, "lxml")

        episode_details = {}

        # --- Informasi Dasar & Navigasi ---
        episode_details['title'] = soup.select_one("h1.entry-title").text.strip()
        release_info_tag = soup.select_one(".sbdbti .time-post")
        episode_details['release_info'] = release_info_tag.text.strip() if release_info_tag else "N/A"
        # ... (sisa kode info dasar & navigasi tetap sama) ...
        nav_container = soup.select_one('.naveps')
        if nav_container:
            prev_link = nav_container.select_one('a:has(i.fa-chevron-left)')
            next_link = nav_container.select_one('a:has(i.fa-chevron-right)')
            all_eps_link = nav_container.select_one('a.semuaep')
            episode_details['navigation'] = {
                "previous_episode_url": prev_link.get('href') if prev_link and 'nonex' not in prev_link.get('class', []) else None,
                "all_episodes_url": all_eps_link.get('href') if all_eps_link else None,
                "next_episode_url": next_link.get('href') if next_link and 'nonex' not in next_link.get('class', []) else None
            }
        else:
            episode_details['navigation'] = {"previous_episode_url": None, "all_episodes_url": None, "next_episode_url": None}


        # --- [OPTIMASI] Langkah 2: Ambil Semua Link Streaming secara Bersamaan ---
        server_options = soup.select("#server .east_player_option")
        post_id = server_options[0]['data-post'] if server_options else None
        
        streaming_servers = []
        if post_id:
            print(f"✅ Post ID ditemukan: {post_id}. Memulai pengambilan link streaming secara paralel...")
            ajax_url = "https://samehadaku.now/wp-admin/admin-ajax.php"
            ajax_headers = {"User-Agent": headers["User-Agent"], "Referer": url, "X-Requested-With": "XMLHttpRequest"}

            # Gunakan ThreadPoolExecutor untuk menjalankan tugas secara bersamaan
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_server = {}
                for option in server_options:
                    server_name_tag = option.find("span")
                    server_name = server_name_tag.text.strip() if server_name_tag else "N/A"
                    server_nume = option.get('data-nume')
                    if not server_nume: # Skip if data-nume is not found
                        continue
                    payload = {'action': 'player_ajax', 'post': post_id, 'nume': server_nume, 'type': 'schtml'}
                    
                    # Jadwalkan fungsi fetch_stream_url untuk dieksekusi
                    future = executor.submit(fetch_stream_url, session, ajax_url, payload, ajax_headers)
                    future_to_server[future] = server_name

                # Kumpulkan hasil saat sudah selesai
                for future in as_completed(future_to_server):
                    server_name = future_to_server[future]
                    streaming_url = future.result()
                    if streaming_url:
                        print(f"  -> Link ditemukan untuk server: {server_name}")
                        streaming_servers.append({"server_name": server_name, "streaming_url": streaming_url})
        
        episode_details['streaming_servers'] = sorted(streaming_servers, key=lambda x: x['server_name'])

        # --- Download Links & Info Anime Lainnya (tetap sama) ---
        download_links = {}
        download_containers = soup.select(".download-eps")
        for container in download_containers:
            if format_type_tag := container.find("p"):
                format_type = format_type_tag.text.strip()
                download_links[format_type] = {}
                for item in container.select("li"):
                    if resolution_tag := item.find("strong"):
                        resolution = resolution_tag.text.strip()
                        providers = [{"provider": a.text.strip(), "url": a['href']} for a in item.find_all("a")]
                        download_links[format_type][resolution] = providers
        episode_details['download_links'] = download_links
        # ... (sisa kode untuk anime_info dan other_episodes tetap sama) ...
        anime_info_box = soup.select_one(".episodeinf .infoanime")
        if anime_info_box:
            anime_details = {}
            title_tag = anime_info_box.select_one(".infox h2.entry-title")
            synopsis_tag = anime_info_box.select_one(".desc .entry-content-single")
            genre_tags = anime_info_box.select(".genre-info a")
            
            anime_details['title'] = title_tag.text.replace("Sinopsis Anime", "").replace("Indo", "").strip() if title_tag else "N/A"
            anime_details['synopsis'] = synopsis_tag.text.strip() if synopsis_tag else "N/A"
            anime_details['genres'] = [tag.text.strip() for tag in genre_tags]
            
            episode_details['anime_info'] = anime_details
        other_episodes_list = []
        other_eps_container = soup.select_one(".episode-lainnya .lstepsiode")
        if other_eps_container:
            for ep_item in other_eps_container.find_all("li"):
                title_tag = ep_item.select_one(".lchx a")
                date_tag = ep_item.select_one(".date")
                thumb_tag = ep_item.select_one(".epsright img")
                
                other_episodes_list.append({
                    "title": title_tag.text.strip() if title_tag else "N/A",
                    "url": title_tag['href'] if title_tag else "N/A",
                    "thumbnail_url": thumb_tag['src'] if thumb_tag else "N/A",
                    "release_date": date_tag.text.strip() if date_tag else "N/A"
                })
        episode_details['other_episodes'] = other_episodes_list

        return episode_details

    except Exception as e:
        print(f"❌ Terjadi error: {e}")
        return None

# --- CONTOH PENGGUNAAN ---
if __name__ == "__main__":
    target_url = "https://samehadaku.now/sakamoto-days-cour-2-episode-1/"
    start_time = time.time()
    scraped_data = scrape_episode_details(target_url)
    end_time = time.time()

    if scraped_data:
        print("\n✅ Data episode berhasil di-scrape secara SUPER LENGKAP!")
        print(json.dumps(scraped_data, indent=4, ensure_ascii=False))
        print(f"\n🚀 Selesai dalam {end_time - start_time:.2f} detik")
