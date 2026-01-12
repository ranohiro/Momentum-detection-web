#!/usr/bin/env python3
# csv_downloader_multi.py
# 使用:
#   export KABU_ID="your-id"
#   export KABU_PW="your-pw"
#   python csv_downloader_multi.py 5   ← 過去5日分を取得
#
#   ↓全銘柄株価一覧表
#   "https://csvex.com/kabu.plus/csv/japan-all-stock-prices/daily/japan-all-stock-prices"
#   SAVE_DIR = os.path.join("data", "raw", "japan_all_stock")
#
#　　↓業種・指数指数データ
#   "https://csvex.com/kabu.plus/csv/tosho-index-data/daily/tosho-index-data"
#   SAVE_DIR = os.path.join("data", "raw", "tosho_index")

import os
import sys
import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 設定 ---
BASE_URL = "https://csvex.com/kabu.plus/csv/tosho-index-data/daily/tosho-index-data"
SAVE_DIR = os.path.join("data", "raw", "tosho_index")
TIMEOUT = 20  # 秒
# ----------------

def get_credentials_from_env():
    id_ = os.environ.get("KABU_ID")
    pw = os.environ.get("KABU_PW")
    return id_, pw

def make_session_with_retries():
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET", "POST"])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        "User-Agent": "momentum-downloader/1.1 (+https://yourdomain.example)"
    })
    return s

def download_csv_for_date(target_date, session, id_, pw):
    """特定日付のCSVをダウンロード"""
    os.makedirs(SAVE_DIR, exist_ok=True)
    date_str = target_date.strftime("%Y%m%d")
    url = f"{BASE_URL}_{date_str}.csv"
    filename = f"tosho-index-data_{date_str}.csv"
    save_path_tmp = os.path.join(SAVE_DIR, filename + ".part")
    save_path = os.path.join(SAVE_DIR, filename)

    print(f"📥 {date_str} のCSVをダウンロード中...")

    try:
        if id_ and pw:
            res = session.get(url, auth=(id_, pw), timeout=TIMEOUT)
        else:
            res = session.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"❌ {date_str}: リクエストエラー {e}")
        return False

    if res.status_code == 200:
        with open(save_path_tmp, "wb") as f:
            f.write(res.content)
        os.replace(save_path_tmp, save_path)
        print(f"✅ {date_str}: 保存完了 → {save_path}")
        return True
    elif res.status_code == 404:
        print(f"⚠️ {date_str}: データが存在しません (404)")
    elif res.status_code == 401:
        print(f"❌ {date_str}: 認証エラー (401)")
    else:
        print(f"❌ {date_str}: ダウンロード失敗 (HTTP {res.status_code})")
    return False

def download_past_n_days(n_days):
    """過去n日分を順にダウンロード"""
    id_, pw = get_credentials_from_env()
    session = make_session_with_retries()

    today = datetime.date.today()
    for i in range(n_days):
        target_date = today - datetime.timedelta(days=i)
        download_csv_for_date(target_date, session, id_, pw)

if __name__ == "__main__":
    # コマンドライン引数で日数を指定（例: python csv_downloader_multi.py 7）
    if len(sys.argv) >= 2:
        try:
            n = int(sys.argv[1])
        except ValueError:
            print("❌ 引数は整数で指定してください。例: python csv_downloader_multi.py 7")
            sys.exit(1)
    else:
        n = 150

    print(f"📆 過去 {n} 営業日分のCSVを取得します...")
    download_past_n_days(n)
    print("🎯 全ての処理が完了しました。")