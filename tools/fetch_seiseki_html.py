import sys
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# .envからCookie値を取得
load_dotenv()
COOKIE_KEYS = [
    'keibabook_session',
    'tk',
    'XSRF-TOKEN',
    'keibabook_settei',
]

# 使い方: python tools/fetch_seiseki_html.py <race_id>
# 例: python tools/fetch_seiseki_html.py 202502041211

def fetch_seiseki_html(race_id):
    url = f"https://p.keibabook.co.jp/cyuou/seiseki/{race_id}"
    save_dir = os.path.join('data', 'debug')
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"seiseki_{race_id}_full.html")

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # 本物のChromeのUser-Agentに偽装
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(url)
        # Cookieをセット
        for key in COOKIE_KEYS:
            value = os.getenv(key)
            if value:
                driver.add_cookie({"name": key, "value": value, "domain": "p.keibabook.co.jp"})
        # Cookieセット後にリロード
        driver.refresh()
        time.sleep(4)  # JS描画待ち（必要に応じて調整）
        html = driver.page_source
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"保存完了: {save_path}")
    finally:
        driver.quit()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python tools/fetch_seiseki_html.py <race_id>")
        sys.exit(1)
    race_id = sys.argv[1]
    fetch_seiseki_html(race_id) 