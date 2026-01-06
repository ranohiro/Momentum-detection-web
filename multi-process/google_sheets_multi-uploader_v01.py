import os
import csv
import time
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# ==============================
# 設定
# ==============================
SERVICE_ACCOUNT_FILE = "credentials.json"
SPREADSHEET_ID = "1CTRQdjsgFsRPgRdsT_c_rJheztivNAa1gyTKjxL-QR4"

# データ格納ディレクトリ
BASE_SECTOR_DIR = "data/processed_data/sector_summary"
BASE_MOMENTUM_DIR = "data/processed_data/momentum_summary"

# シート名
SECTOR_SHEET_NAME = "sector_log"
MOMENTUM_SHEET_NAME = "momentum_log"

# ==============================
# Google認証
# ==============================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)


# ==============================
# 新データをヘッダー直下に挿入
# ==============================
def upload_csvs_to_sheet(base_dir, sheet_name, key_cols):
    worksheet = sh.worksheet(sheet_name)

    print(f"\n📥 {sheet_name} の既存データを取得中...")
    existing_data = worksheet.get_all_values()
    if len(existing_data) <= 1:
        existing_df = pd.DataFrame()
        header = None
    else:
        header = existing_data[0]
        existing_df = pd.DataFrame(existing_data[1:], columns=header)

    print(f"➡ 既存 {len(existing_df)} 行を確認済み")

    # --- CSVファイル一覧（古い順） ---
    csv_files = sorted(os.listdir(base_dir))
    added_total = 0

    for csv_file in csv_files:
        if not csv_file.endswith(".csv"):
            continue

        csv_path = os.path.join(base_dir, csv_file)
        print(f"\n📤 Uploading {csv_file} → {sheet_name} ...")

        # --- CSV読み込み ---
        try:
            df_new = pd.read_csv(csv_path, encoding="cp932")
        except UnicodeDecodeError:
            df_new = pd.read_csv(csv_path, encoding="utf-8-sig")

        # --- 日付文字列を統一（ゼロ埋めやスラッシュ差異を吸収） ---
        if "日付" in df_new.columns:
            df_new["日付"] = pd.to_datetime(df_new["日付"], errors="coerce").dt.strftime("%Y-%m-%d")
        if not existing_df.empty and "日付" in existing_df.columns:
            existing_df["日付"] = pd.to_datetime(existing_df["日付"], errors="coerce").dt.strftime("%Y-%m-%d")

        # --- 重複除外 ---
        before_count = len(df_new)
        if not existing_df.empty:
            existing_keys = set(zip(existing_df[key_cols[0]], existing_df[key_cols[1]]))
            df_new = df_new[
                ~df_new.apply(lambda r: (r[key_cols[0]], r[key_cols[1]]) in existing_keys, axis=1)
            ]
        after_count = len(df_new)

        if after_count == 0:
            print("⏭ 新しいデータなし（スキップ）")
            continue

        # --- 新データをヘッダー直下に追加（古い順なので上に積み上がる）---
        updated_df = pd.concat([df_new, existing_df], ignore_index=True)

        # --- Googleシート更新 ---
        values = [list(updated_df.columns)] + updated_df.values.tolist()
        worksheet.clear()
        worksheet.update(values, value_input_option="RAW")

        added_total += after_count
        print(f"✅ {after_count} 行をヘッダー直下に追加（合計 {len(updated_df)} 行）")

        # --- 次回の重複判定のために更新 ---
        existing_df = updated_df.copy()

        # --- API負荷軽減 ---
        time.sleep(1)

    print(f"\n🎉 {sheet_name} 更新完了：合計 {added_total} 行追加")


# ==============================
# メイン処理
# ==============================
if __name__ == "__main__":
    # sector_log（日付＋業種をキーに判定）
    upload_csvs_to_sheet(
        base_dir=BASE_SECTOR_DIR,
        sheet_name=SECTOR_SHEET_NAME,
        key_cols=["日付", "業種"]
    )

    # momentum_log（日付＋業種をキーに判定）
    upload_csvs_to_sheet(
        base_dir=BASE_MOMENTUM_DIR,
        sheet_name=MOMENTUM_SHEET_NAME,
        key_cols=["日付", "業種"]
    )

    print("\n🚀 全シート更新完了！")