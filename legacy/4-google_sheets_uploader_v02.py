import os
import pandas as pd
import json
import sys
import gspread
from google.oauth2.service_account import Credentials

# ==============================
# Googleスプレッドシート設定
# ==============================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = "credentials.json"
SPREADSHEET_ID = "1CTRQdjsgFsRPgRdsT_c_rJheztivNAa1gyTKjxL-QR4"
SECTOR_SHEET_NAME = "sector_log"
MOMENTUM_SHEET_NAME = "momentum_log"

# ==============================
# Google認証
# ==============================
gcp_creds_env = os.environ.get("GCP_CREDENTIALS")
if gcp_creds_env:
    info = json.loads(gcp_creds_env)
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
else:
    # 従来のファイル読み込み（ファイルがなければここで FileNotFoundError が出る）
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

# ==============================
# 共通アップロード関数（重複防止）
# ==============================
def upload_csv_to_sheet(csv_path, sheet_name, max_rows=19800):
    print(f"Uploading {csv_path} → {sheet_name} ...")

    # --- CSV読み込み ---
    try:
        df_new = pd.read_csv(csv_path, encoding="cp932")
    except UnicodeDecodeError:
        df_new = pd.read_csv(csv_path, encoding="utf-8-sig")

    header = list(df_new.columns)

    # --- 対象シート取得 ---
    worksheet = sh.worksheet(sheet_name)

    # --- 既存データ取得 ---
    existing_data = worksheet.get_all_values()
    if existing_data:
        existing_df = pd.DataFrame(existing_data[1:], columns=existing_data[0])

        # 日付と業種をキーに既存行をセット化
        existing_keys = set(zip(existing_df["日付"], existing_df["業種"]))

        # 新規データから既存キーを除外
        df_new_filtered = df_new[~df_new.apply(lambda row: (row["日付"], row["業種"]) in existing_keys, axis=1)]
    else:
        existing_df = pd.DataFrame(columns=header)
        df_new_filtered = df_new

    # 書き込み用2次元リスト
    values = [header] + df_new_filtered.values.tolist() + existing_df.values.tolist()

    # 最大行数制限
    if len(values) > max_rows + 1:  # ヘッダー込み
        values = values[:max_rows + 1]

    # 一括更新
    worksheet.clear()
    worksheet.update(values, value_input_option="RAW")

    print(f"✅ {sheet_name}: {len(df_new_filtered)} 行を追加、合計 {len(values)-1} 行に更新しました。")


# ==============================
# メイン処理
# ==============================
if __name__ == "__main__":
    base_sector_dir = "data/processed_data/sector_summary"
    base_momentum_dir = "data/processed_data/momentum_summary"

    latest_sector_csv = sorted(os.listdir(base_sector_dir))[-1]
    latest_momentum_csv = sorted(os.listdir(base_momentum_dir))[-1]

    upload_csv_to_sheet(
        csv_path=os.path.join(base_sector_dir, latest_sector_csv),
        sheet_name=SECTOR_SHEET_NAME
    )

    upload_csv_to_sheet(
        csv_path=os.path.join(base_momentum_dir, latest_momentum_csv),
        sheet_name=MOMENTUM_SHEET_NAME
    )

    print("全シート更新完了！")