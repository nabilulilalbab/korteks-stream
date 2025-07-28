import requests
from bs4 import BeautifulSoup
import json
import re

def scrape_anime_details_with_soup(soup, anime_slug=None):
    """
    Fungsi untuk scrape semua detail dari satu halaman anime menggunakan objek BeautifulSoup,
    termasuk daftar episode dan rekomendasi.
    
    :param soup: Objek BeautifulSoup yang sudah diinisialisasi
    :param anime_slug: Slug anime (opsional, untuk logging)
    :return: Dictionary berisi detail anime
    """
    try:
        anime_details = {}

        # --- Informasi Utama ---
        info_box = soup.find("div", class_="infoanime")
        if not info_box:
            print("❌ Kotak informasi utama tidak ditemukan.")
            return None

        anime_details['title'] = info_box.find("h2", class_="entry-title").text.strip()
        anime_details['thumbnail_url'] = info_box.find("img")['src'] if info_box.find("img") else "N/A"
        
        synopsis_p = info_box.select_one("div.desc .entry-content p")
        anime_details['synopsis'] = synopsis_p.text.strip() if synopsis_p else "N/A"

        rating_value = info_box.select_one(".archiveanime-rating span[itemprop='ratingValue']")
        rating_count = info_box.select_one(".archiveanime-rating i[itemprop='ratingCount']")
        anime_details['rating'] = {
            "score": rating_value.text.strip() if rating_value else "N/A",
            "users": rating_count.text.strip() if rating_count else "N/A"
        }

        genres = info_box.select(".genre-info a")
        anime_details['genres'] = [genre.text.strip() for genre in genres]

        # --- Detail Teknis ---
        detail_box = soup.find("div", class_="spe")
        details_data = {}
        if detail_box:
            for span in detail_box.find_all("span", recursive=False):
                if key_tag := span.find("b"):
                    key = key_tag.text.strip()
                    key_tag.decompose()
                    value = span.text.strip()
                    details_data[key] = value
        anime_details['details'] = details_data

        # --- Daftar Episode ---
        episode_list = []
        if episode_container := soup.find("div", class_="lstepsiode"):
            for ep in episode_container.find_all("li"):
                episode_title_tag = ep.select_one(".lchx a")
                episode_num_tag = ep.select_one(".eps a")
                episode_date_tag = ep.select_one(".date")
                episode_list.append({
                    "episode": episode_num_tag.text.strip() if episode_num_tag else "N/A",
                    "title": episode_title_tag.text.strip() if episode_title_tag else "N/A",
                    "url": episode_title_tag['href'] if episode_title_tag else "N/A",
                    "release_date": episode_date_tag.text.strip() if episode_date_tag else "N/A"
                })
        
        # Fungsi untuk mengekstrak angka dari string episode
        def extract_episode_number(episode_str):
            try:
                # Ekstrak angka dari string (misalnya "1031 FIX" menjadi 1031)
                match = re.search(r'(\d+)', str(episode_str.get('episode', '0')))
                if match:
                    return int(match.group(1))
                return 0
            except Exception:
                return 0
                
        # Urutkan episode berdasarkan nomor episode (ekstrak angka saja)
        anime_details['episode_list'] = sorted(episode_list, key=extract_episode_number, reverse=True)

        # --- [KODE BARU] Rekomendasi Anime Lainnya ---
        recommendations_list = []
        if rec_container := soup.select_one("div.rand-animesu ul"):
            for item in rec_container.select("li"):
                link_tag = item.select_one("a.series")
                if link_tag:
                    title_tag = link_tag.select_one("span.judul")
                    rating_tag = link_tag.select_one("span.rating")
                    episode_tag = link_tag.select_one("span.episode")
                    img_tag = link_tag.select_one("img")

                    recommendations_list.append({
                        "title": title_tag.text.strip() if title_tag else "N/A",
                        "url": link_tag.get('href', "N/A"),
                        "cover_url": img_tag.get('src', "N/A") if img_tag else "N/A",
                        "rating": rating_tag.text.strip().replace("\n", " ") if rating_tag else "N/A",
                        "episode": episode_tag.text.strip() if episode_tag else "N/A"
                    })
        anime_details['recommendations'] = recommendations_list
        
        return anime_details

    except Exception as e:
        print(f"❌ Terjadi error saat parsing: {e}")
        return None

def scrape_anime_details(url):
    """
    Fungsi untuk scrape semua detail dari satu halaman anime,
    termasuk daftar episode dan rekomendasi.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    }

    print(f"⚙️  Mengambil data dari: {url}")

    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, "lxml")
        
        # Ekstrak slug anime dari URL untuk logging
        anime_slug = url.rstrip('/').split('/')[-1] if url else None
        
        # Gunakan fungsi dengan soup
        return scrape_anime_details_with_soup(soup, anime_slug)

    except Exception as e:
        print(f"❌ Gagal mengambil atau memproses data: {e}")
        return None

# --- CONTOH PENGGUNAAN ---
# if __name__ == "__main__":
#     target_url = "https://samehadaku.now/anime/one-piece/"
#     scraped_data = scrape_anime_details(target_url)

#     if scraped_data:
#         print("\n✅ Data anime (termasuk rekomendasi) berhasil di-scrape!")
#         print(json.dumps(scraped_data, indent=4, ensure_ascii=False))
