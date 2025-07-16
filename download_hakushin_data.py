import requests
import os

def download_file(url, save_path):
    resp = requests.get(url)
    if resp.status_code == 200:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(resp.content)
        print(f"다운로드 완료: {save_path}")
    else:
        print(f"다운로드 실패: {url} (status {resp.status_code})")

if __name__ == "__main__":
    files = [
        ("https://api.hakush.in/hsr/data/character.json", "./hakushin_data/character.json"),
        ("https://api.hakush.in/hsr/data/lightcone.json", "./hakushin_data/lightcone.json"),
    ]
    for url, path in files:
        download_file(url, path)