import os
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from industry_name_mapping import industry_name_mapping

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
# [追加] スライディングウィンドウ設定
# ==============================
KEEP_DAYS = 120 # [修正箇所] 常に保持したい日付の列数

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
    """GoogleシートをDataFrameとして取得"""
    worksheet = sh.worksheet(sheet_name)
    data = worksheet.get_all_values()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

def update_sheet(df, sheet_name):
    """
    GoogleシートにDataFrameをアップロード。
    [修正箇所] アップロード前に日付列を最新120日分にカットします。
    """
    worksheet = sh.worksheet(sheet_name)
    df = df.replace([np.inf, -np.inf], np.nan).fillna("")

    # 現状のデータフレームの列数
    current_cols = df.shape[1]

    if current_cols > 1:
        # 1列目 (インデックス/タイトル) は常に保持
        index_col = df.columns[0]

        # 2列目以降の日付列部分
        date_cols_data = df.iloc[:, 1:]

        if date_cols_data.shape[1] > KEEP_DAYS:
            # 保持する日付列部分をスライス (後ろから120列)
            df_recent_data = date_cols_data.iloc[:, -KEEP_DAYS:]

            # [インデックス列] と [最新120日のデータ列] を結合
            df_final = pd.concat([df.iloc[:, [0]], df_recent_data], axis=1)
            print(f"[{sheet_name}] 古い日付データを削除し、最新{KEEP_DAYS}日分にカットしました。")
        else:
            df_final = df # カット不要
    else:
        df_final = df # 1列しかない場合はそのまま

    # 書き込み処理
    values = df_final.values.tolist() # [修正箇所] df から df_final に変更
    worksheet.clear()
    worksheet.update(values, value_input_option="RAW")

# ==============================
# sector_ranking 作成
# ==============================
def create_sector_ranking():
    df = get_sheet_dataframe(SECTOR_LOG_SHEET)
    if df.empty:
        print("sector_log が空です")
        return

    # 「全体」区分のみ
    df = df[df["時価総額帯"] == "全体"]

    # 業種名統一
    # df["業種"] = df["業種"].map(industry_name_mapping).fillna(df["業種"]) # [仮定] industry_name_mappingが存在
    df["業種"] = df["業種"].fillna(df["業種"])

    # 騰落率表
    df["時価総額加重平均騰落率"] = pd.to_numeric(df["時価総額加重平均騰落率"], errors="coerce")
    pivot_rate = df.pivot(index="業種", columns="日付", values="時価総額加重平均騰落率")
    pivot_rate = pivot_rate.reindex(SECTOR_ORDER).reset_index()

    # ランキング表
    pivot_rank = pivot_rate.copy()
    for c in pivot_rank.columns[1:]:
        pivot_rank[c] = pivot_rank[c].rank(ascending=False, method="min")

    # ===== タイトル + ヘッダー + データ (このブロックの列構造が最終的な列幅を決定) =====
    # pivot_rate.shape[1] は [業種] + [日付数] の合計列数
    title_rate = pd.DataFrame([["業種別 時価総額加重平均騰落率"] + [""] * (pivot_rate.shape[1] - 1)],
                              columns=pivot_rate.columns)
    header_rate = pd.DataFrame([pivot_rate.columns.tolist()], columns=pivot_rate.columns)
    rate_block = pd.concat([title_rate, header_rate, pivot_rate], ignore_index=True)

    # ===== ランキング表 =====
    title_rank = pd.DataFrame([["業種別 騰落率ランキング"] + [""] * (pivot_rank.shape[1] - 1)],
                              columns=pivot_rank.columns)
    header_rank = pd.DataFrame([pivot_rank.columns.tolist()], columns=pivot_rank.columns)
    rank_block = pd.concat([title_rank, header_rank, pivot_rank], ignore_index=True)

    # ===== 空行3行 + 結合 =====
    empty_rows = pd.DataFrame([[""] * pivot_rate.shape[1]] * 3, columns=pivot_rate.columns)
    combined_df = pd.concat([rate_block, empty_rows, rank_block], ignore_index=True)

    # ===== 書き込み =====
    update_sheet(combined_df, SECTOR_RANKING_SHEET)
    print("✅ sector_ranking 更新完了")

# ==============================
# momentum_flow 作成
# ==============================
def create_momentum_flow():
    df = get_sheet_dataframe(MOMENTUM_LOG_SHEET)
    if df.empty:
        print("momentum_log が空です")
        return

    # 業種名を統一
    # df["業種"] = df["業種"].map(industry_name_mapping).fillna(df["業種"]) # [仮定] industry_name_mappingが存在
    df["業種"] = df["業種"].fillna(df["業種"])

    # 数値化
    ratio_cols = ["売買代金5日平均/20日平均比率", "売買代金3日平均/10日平均比率"]
    for col in ratio_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- pivot 作成 ---
    pivot_5_20 = df.pivot(index="業種", columns="日付", values="売買代金5日平均/20日平均比率")
    pivot_5_20 = pivot_5_20.reindex(SECTOR_ORDER)
    pivot_5_20.reset_index(inplace=True)

    pivot_3_10 = df.pivot(index="業種", columns="日付", values="売買代金3日平均/10日平均比率")
    pivot_3_10 = pivot_3_10.reindex(SECTOR_ORDER)
    pivot_3_10.reset_index(inplace=True)

    # --- ヘッダー行を明示的に生成 ---
    header_5_20 = pd.DataFrame([pivot_5_20.columns], columns=pivot_5_20.columns)
    header_3_10 = pd.DataFrame([pivot_3_10.columns], columns=pivot_3_10.columns)

    # --- タイトル行 ---
    title_5_20 = pd.DataFrame(
        [["業種別 売買代金5日平均/20日平均比率"] + [""] * (len(pivot_5_20.columns) - 1)],
        columns=pivot_5_20.columns
    )
    title_3_10 = pd.DataFrame(
        [["業種別 売買代金3日平均/10日平均比率"] + [""] * (len(pivot_3_10.columns) - 1)],
        columns=pivot_3_10.columns
    )

    # --- 空行3行 ---
    empty_rows = pd.DataFrame([[""] * len(pivot_5_20.columns)] * 3, columns=pivot_5_20.columns)

    # --- 結合 ---
    combined_df = pd.concat(
        [
            title_5_20,
            header_5_20,
            pivot_5_20,
            empty_rows,
            title_3_10,
            header_3_10,
            pivot_3_10,
        ],
        ignore_index=True
    )

    update_sheet(combined_df, MOMENTUM_FLOW_SHEET)
    print("✅ momentum_flow 更新完了")

# ==============================
# メイン処理
# ==============================
if __name__ == "__main__":
    create_sector_ranking()
    create_momentum_flow()
    print("全シート更新完了！")
