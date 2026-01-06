# -*- coding: utf-8 -*-
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from industry_name_mapping import industry_name_mapping
import time

# ==============================
# Googleスプレッドシート設定
# ==============================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = "credentials.json"
SPREADSHEET_ID = "1CTRQdjsgFsRPgRdsT_c_rJheztivNAa1gyTKjxL-QR4"

SECTOR_LOG_SHEET = "sector_log"
MOMENTUM_LOG_SHEET = "momentum_log"
SECTOR_RANKING_SHEET = "sector_ranking"
MOMENTUM_FLOW_SHEET = "momentum_flow"

# ==============================
# 固定業種順
# ==============================
SECTOR_ORDER = [
    "水産・農林業", "鉱業", "建設業", "食料品", "繊維製品", "パルプ・紙", "化学",
    "医薬品", "石油・石炭製品", "ゴム製品", "ガラス・土石製品", "鉄鋼", "非鉄金属",
    "金属製品", "機械", "電気機器", "輸送用機器", "精密機器", "その他製品", "電気・ガス業",
    "陸運業", "海運業", "空運業", "倉庫・運輸関連業", "情報・通信業", "卸売業", "小売業",
    "銀行業", "証券、商品先物取引業", "保険業", "その他金融業", "不動産業", "サービス業"
]

# ==============================
# Google認証
# ==============================
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

# ==============================
# 共通関数
# ==============================
def get_sheet_dataframe(sheet_name):
    ws = sh.worksheet(sheet_name)
    data = ws.get_all_values()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data[1:], columns=data[0])

def get_column_index_by_header(ws, header_row, value):
    """ヘッダー行に value があれば列番号返す。なければ最後に追加して列番号返す"""
    headers = ws.row_values(header_row)
    if value in headers:
        return headers.index(value) + 1
    else:
        col_index = len(headers) + 1
        ws.update_cell(header_row, col_index, value)
        return col_index

# ==============================
# SECTOR_RANKING 更新（過去N日分）
# ==============================
def append_sector_ranking_Ndays(N=5):
    ws = sh.worksheet(SECTOR_RANKING_SHEET)
    df = get_sheet_dataframe(SECTOR_LOG_SHEET)
    df["業種"] = df["業種"].map(industry_name_mapping).fillna(df["業種"])
    df["時価総額加重平均騰落率"] = pd.to_numeric(
        df["時価総額加重平均騰落率"].astype(str).str.replace(r"[^\d\.\-]", "", regex=True),
        errors="coerce"
    )

    last_dates = sorted(df["日付"].unique())[-N:]

    start_row = 3  # データ開始行
    for date in last_dates:
        col_index = get_column_index_by_header(ws, 2, date)  # 2行目ヘッダー

        df_date = df[df["日付"] == date].dropna(subset=["時価総額加重平均騰落率"])
        df_date = df_date.groupby("業種", as_index=False)["時価総額加重平均騰落率"].mean()
        df_date = df_date.set_index("業種").reindex(SECTOR_ORDER)
        values = [[v] for v in df_date["時価総額加重平均騰落率"].tolist()]

        # 列を動的に指定してまとめて書き込む
        ws.update(f"{gspread.utils.rowcol_to_a1(start_row, col_index)}:"
                  f"{gspread.utils.rowcol_to_a1(start_row + len(SECTOR_ORDER) - 1, col_index)}",
                  values)
        print(f"✅ {date} を sector_ranking に追記しました")
        time.sleep(3)  # API制限回避

# ==============================
# MOMENTUM_FLOW 更新（過去N日分）
# ==============================
def append_momentum_flow_Ndays(N=5):
    ws = sh.worksheet(MOMENTUM_FLOW_SHEET)
    df = get_sheet_dataframe(MOMENTUM_LOG_SHEET)
    df["業種"] = df["業種"].map(industry_name_mapping).fillna(df["業種"])

    ratio_cols = ["売買代金5日平均/20日平均比率", "売買代金3日平均/10日平均比率"]
    for col in ratio_cols:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(r"[^\d\.\-]", "", regex=True),
            errors="coerce"
        )

    last_dates = sorted(df["日付"].unique())[-N:]

    start_row_5_20 = 3
    start_row_3_10 = start_row_5_20 + len(SECTOR_ORDER) + 4

    for date in last_dates:
        col_index = get_column_index_by_header(ws, 2, date)  # 2行目ヘッダー

        df_date = df[df["日付"] == date].dropna(subset=ratio_cols)

        latest_5_20 = df_date[["業種", "売買代金5日平均/20日平均比率"]].set_index("業種").reindex(SECTOR_ORDER)
        values_5_20 = [[v] for v in latest_5_20["売買代金5日平均/20日平均比率"].tolist()]
        ws.update(f"{gspread.utils.rowcol_to_a1(start_row_5_20, col_index)}:"
                  f"{gspread.utils.rowcol_to_a1(start_row_5_20 + len(SECTOR_ORDER) - 1, col_index)}",
                  values_5_20)

        latest_3_10 = df_date[["業種", "売買代金3日平均/10日平均比率"]].set_index("業種").reindex(SECTOR_ORDER)
        values_3_10 = [[v] for v in latest_3_10["売買代金3日平均/10日平均比率"].tolist()]
        ws.update(f"{gspread.utils.rowcol_to_a1(start_row_3_10, col_index)}:"
                  f"{gspread.utils.rowcol_to_a1(start_row_3_10 + len(SECTOR_ORDER) - 1, col_index)}",
                  values_3_10)

        print(f"✅ {date} を momentum_flow に追記しました")
        time.sleep(3)  # API制限回避

# ==============================
# メイン処理
# ==============================
if __name__ == "__main__":
    N = 20  # 過去N日分を右端に追加
    append_sector_ranking_Ndays(N)
    append_momentum_flow_Ndays(N)
    print("全シート更新完了！")