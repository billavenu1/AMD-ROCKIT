import os
import requests
from duckduckgo_search import DDGS
from urllib.parse import urlparse

def download_similar_images(query, num_images=25, save_dir="images"):
    os.makedirs(save_dir, exist_ok=True)

    downloaded = 0
    seen_urls = set()

    with DDGS() as ddgs:
        results = ddgs.images(query, max_results=num_images * 2)

        for i, result in enumerate(results):
            if downloaded >= num_images:
                break

            url = result.get("image")
            if not url or url in seen_urls:
                continue

            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    ext = os.path.splitext(urlparse(url).path)[1]
                    if ext.lower() not in [".jpg", ".jpeg", ".png"]:
                        ext = ".jpg"

                    file_path = os.path.join(save_dir, f"{query}_{downloaded}{ext}")

                    with open(file_path, "wb") as f:
                        f.write(response.content)

                    print(f"Downloaded: {file_path}")
                    downloaded += 1
                    seen_urls.add(url)

            except Exception as e:
                print(f"Skipped: {e}")

    print(f"\nTotal downloaded: {downloaded}")


# Example usage
download_similar_images("red sports car", num_images=25)