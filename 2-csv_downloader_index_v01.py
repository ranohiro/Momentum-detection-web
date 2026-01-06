import os
import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 設定 ---
CSV_URL = "https://csvex.com/kabu.plus/csv/tosho-index-data/daily/tosho-index-data.csv"
SAVE_DIR = os.path.join("data", "raw", "tosho_index")
TIMEOUT = 20  # 秒
# ----------------

def get_credentials_from_env():
    """環境変数からID/PWを取得（見つからなければNoneを返す）"""
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
        "User-Agent": "momentum-downloader/1.0 (+https://yourdomain.example)"
    })
    return s

def download_csv(save_dir=SAVE_DIR, url=CSV_URL, use_basic_auth=True):
    os.makedirs(save_dir, exist_ok=True)

    today = datetime.datetime.now().strftime("%Y%m%d")
    filename = f"tosho-index-data_{today}.csv"
    tmp_name = filename + ".part"
    save_path_tmp = os.path.join(save_dir, tmp_name)
    save_path = os.path.join(save_dir, filename)

    id_, pw = get_credentials_from_env()
    session = make_session_with_retries()

    print(f"📥 Downloading CSV from {url} ...")

    try:
        if use_basic_auth and id_ and pw:
            # Basic認証を付けてGET（推奨）
            response = session.get(url, auth=(id_, pw), timeout=TIMEOUT)
        else:
            # 認証情報が無い／使わない場合（公開URL向け）
            response = session.get(url, timeout=TIMEOUT)

    except requests.RequestException as e:
        print(f"❌ リクエストエラー: {e}")
        return None

    # ステータス別の処理
    if response.status_code == 200:
        # 一時ファイルに書いてからリネーム（途中で落ちても壊れない）
        with open(save_path_tmp, "wb") as f:
            f.write(response.content)
        os.replace(save_path_tmp, save_path)
        print(f"✅ Downloaded successfully → {save_path}")
        return save_path

    elif response.status_code == 401:
        # 認証エラー
        print("❌ 401 Unauthorized：認証が必要です。")
        print("  - 環境変数 KABU_ID / KABU_PW がセットされているか確認してください。")
        print("  - Basic認証でなく、ログインフォーム（POST）経由のログインが必要な場合があります。")
        # デバッグヘルプ（先頭数百文字のみ）
        snippet = response.text[:800].replace("\n", " ")
        print("  サーバー応答（先頭）：", snippet)
        return None

    elif response.status_code == 403:
        print("❌ 403 Forbidden：アクセス権がありません。サービス側で制限されている可能性があります。")
        return None

    elif response.status_code == 404:
        print("❌ 404 Not Found：URLが誤っているか、エンドポイントが存在しません。")
        return None

    else:
        print(f"❌ Failed to download CSV. Status code: {response.status_code}")
        print("  レスポンスヘッダ:", dict(response.headers))
        return None

if __name__ == "__main__":
    res = download_csv()
    if not res:
        print("ダウンロード失敗。必要なら `use_basic_auth=False` で試すか、ログインセッション方式を使ってください。")