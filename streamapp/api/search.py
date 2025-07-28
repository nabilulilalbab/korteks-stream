import requests
from bs4 import BeautifulSoup
import json

def scrape_search_results_fully(query):
    """
    Melakukan pencarian di Samehadaku dan mengambil semua data dari hasilnya,
    termasuk tipe dan jumlah penonton.
    """
    # Membuat URL pencarian yang valid dari query
    search_url = f"https://samehadaku.now/?s={query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    }
    
    print(f"⚙️  Mencari dengan query '{query}' di: {search_url}")

    try:
        res = requests.get(search_url, headers=headers)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, "lxml")
        
        search_results = []
        
        # Setiap hasil pencarian ada di dalam tag <article class="animpost">
        articles = soup.select("main.relat article.animpost")
        
        if not articles:
            print(f"⚠️ Tidak ada hasil yang ditemukan untuk query '{query}'.")
            return []

        for article in articles:
            # Mengambil elemen-elemen utama
            link_tag = article.select_one("a")
            title_tag = article.select_one(".data .title h2")
            status_tag = article.select_one(".data .type")
            type_tag = article.select_one(".content-thumb .type") # Tipe (TV, Movie, dll.)
            score_tag = article.select_one(".content-thumb .score") # Skor
            cover_tag = article.select_one(".content-thumb img") # Cover Image
            
            # Mengambil data dari tooltip hover
            tooltip = article.select_one(".stooltip")
            synopsis_tag = tooltip.select_one(".ttls")
            genre_tags = tooltip.select(".genres a")
            
            # Ekstraksi jumlah penonton dari metadata di dalam tooltip
            views = "N/A"
            if tooltip:
                metadata_spans = tooltip.select(".metadata span")
                for span in metadata_spans:
                    if "Views" in span.text:
                        views = span.text.strip()
                        break

            search_results.append({
                "judul": title_tag.text.strip() if title_tag else "N/A",
                "url_anime": link_tag.get('href') if link_tag else "N/A",
                "status": status_tag.text.strip() if status_tag else "N/A",
                "tipe": type_tag.text.strip() if type_tag else "N/A",
                "skor": score_tag.text.strip() if score_tag else "N/A",
                "penonton": views,
                "sinopsis": synopsis_tag.text.strip() if synopsis_tag else "N/A",
                "genre": [tag.text.strip() for tag in genre_tags],
                "url_cover": cover_tag.get('src') if cover_tag else "N/A"
            })
            
        return search_results

    except Exception as e:
        print(f"❌ Terjadi error: {e}")
        return None

# --- CONTOH PENGGUNAAN ---
if __name__ == "__main__":
    kata_kunci = "naruto"
    
    results = scrape_search_results_fully(kata_kunci)

    if results:
        print(f"\n✅ Ditemukan {len(results)} hasil untuk pencarian '{kata_kunci}'!")
        print(json.dumps(results, indent=4, ensure_ascii=False))
